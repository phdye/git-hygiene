#!/usr/bin/env python3
"""Record whether pre-commit's pinned wheel declares support for Python 3.6.8.

Reads only the wheel's package metadata, so any host with network access
gives the same answer. Standard library only; runs under Python 3.6.8+.
"""

import argparse
import datetime
import hashlib
import io
import json
import re
import sys
import traceback
import urllib.request
import zipfile

PRECOMMIT_VERSION = "4.6.2"
WHEEL_FILENAME = "pre_commit-4.6.2-py2.py3-none-any.whl"
WHEEL_SHA256 = "e2dde9a75d3bce11bd3831c26d134df00a2803c1d818be6a0383c3dcda25dc4e"
TARGET_PYTHON = "3.6.8"

PYPI_JSON_URL = f"https://pypi.org/pypi/pre-commit/{PRECOMMIT_VERSION}/json"
SCRIPT_VERSION = "1.0.0"
VERDICT_PREFIX = f"verdict: Requires-Python admits {TARGET_PYTHON}: "
TIMEOUT = 60

_RELEASE = re.compile(r"^[0-9]+(\.[0-9]+)*$")
_CLAUSE = re.compile(r"^(~=|==|!=|<=|>=|<|>)\s*(\S+)$")


class SpikeError(Exception):
    """A failure with a message and the exit status it maps to."""

    def __init__(self, message, status):
        super().__init__(message)
        self.status = status


def parse_release(text):
    if not _RELEASE.match(text):
        raise SpikeError(f"cannot parse version {text!r} (release-only supported)", 2)
    return tuple(int(part) for part in text.split("."))


def _pad(version, width):
    return version + (0,) * (width - len(version))


def clause_admits(op, spec, candidate):
    width = max(len(spec), len(candidate))
    a, b = _pad(candidate, width), _pad(spec, width)
    if op == "==":
        return a == b
    if op == "!=":
        return a != b
    if op == ">=":
        return a >= b
    if op == ">":
        return a > b
    if op == "<=":
        return a <= b
    if op == "<":
        return a < b
    if op == "~=":
        if len(spec) < 2:
            raise SpikeError("'~=' needs at least two release components", 2)
        prefix = spec[:-1]
        return a >= b and a[: len(prefix)] == prefix
    raise SpikeError(f"unsupported operator {op!r}", 2)


def specifier_admits(specifier, candidate_text):
    candidate = parse_release(candidate_text)
    clauses = [c.strip() for c in specifier.split(",")]
    if not any(clauses) or not all(clauses):
        raise SpikeError(f"empty clause in specifier {specifier!r}", 2)
    admitted = True
    for clause in clauses:
        match = _CLAUSE.match(clause)
        if not match:
            raise SpikeError(f"cannot parse specifier clause {clause!r}", 2)
        op, version = match.groups()
        if not clause_admits(op, parse_release(version), candidate):
            admitted = False
    return admitted


def _fetch(url, log):
    if not url.startswith("https://"):
        raise SpikeError(f"refusing non-https URL {url!r}", 1)
    log(f"fetching {url}")
    # urlopen's default opener honours HTTPS_PROXY; the scheme is checked above.
    with urllib.request.urlopen(url, timeout=TIMEOUT) as response:  # noqa: S310
        return response.read()


def wheel_url(log):
    data = json.loads(_fetch(PYPI_JSON_URL, log).decode("utf-8"))
    for entry in data.get("urls", []):
        if entry.get("filename") == WHEEL_FILENAME:
            return entry["url"]
    raise SpikeError(f"PyPI lists no file named {WHEEL_FILENAME}", 1)


def requires_python(wheel_bytes):
    with zipfile.ZipFile(io.BytesIO(wheel_bytes)) as wheel:
        names = [
            n for n in wheel.namelist() if n.count("/") == 1 and n.endswith(".dist-info/METADATA")
        ]
        if len(names) != 1:
            raise SpikeError(f"expected one dist-info/METADATA, found {names}", 2)
        metadata = wheel.read(names[0]).decode("utf-8")
    for line in metadata.splitlines():
        if not line.strip():
            break
        if line.lower().startswith("requires-python:"):
            return line.split(":", 1)[1].strip()
    raise SpikeError("METADATA has no Requires-Python field", 2)


def measure(log):
    wheel_bytes = _fetch(wheel_url(log), log)
    digest = hashlib.sha256(wheel_bytes).hexdigest()
    if digest != WHEEL_SHA256:
        raise SpikeError(
            f"sha256 mismatch for {WHEEL_FILENAME}: expected {WHEEL_SHA256}, got {digest}",
            1,
        )
    raw = requires_python(wheel_bytes)
    admits = specifier_admits(raw, TARGET_PYTHON)
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    header = [
        f"date-utc: {now}",
        f"python: {sys.version.split()[0]}",
        f"pre-commit: {PRECOMMIT_VERSION}",
        f"wheel: {WHEEL_FILENAME}",
        f"sha256: {digest}",
        f"requires-python: {raw}",
    ]
    return header, VERDICT_PREFIX + ("yes" if admits else "no")


def verdict_in(path):
    try:
        with open(path, encoding="utf-8") as handle:
            lines = [line.rstrip("\r\n") for line in handle]
    except OSError as exc:
        raise SpikeError(f"cannot read {path}: {exc}", 2) from exc
    verdicts = [line for line in lines if line.startswith("verdict: ")]
    if not verdicts:
        raise SpikeError(f"no verdict line in {path}", 2)
    return verdicts[-1]


def build_parser():
    parser = argparse.ArgumentParser(
        description=f"Record whether pre-commit {PRECOMMIT_VERSION}'s wheel admits Python {TARGET_PYTHON}.",
        epilog="Exit status: 0 verdict produced (or --compare matched), "
        "1 download, checksum or --compare mismatch, 2 unparseable input.",
    )
    parser.add_argument("--version", action="version", version="%(prog)s " + SCRIPT_VERSION)
    parser.add_argument("-v", "--verbose", action="store_true", help="report each fetch on stderr")
    parser.add_argument("-d", "--debug", action="store_true", help="print tracebacks on failure")
    parser.add_argument("-t", "--terse", action="store_true", help="print only the verdict line")
    parser.add_argument(
        "--compare",
        metavar="FILE",
        help="rerun and compare only the verdict line with the one in FILE",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)

    def log(message):
        if args.verbose or args.debug:
            print(message, file=sys.stderr)

    try:
        expected = verdict_in(args.compare) if args.compare else None
        header, verdict = measure(log)
    except SpikeError as exc:
        if args.debug:
            traceback.print_exc()
        print(f"check-floor: error: {exc}", file=sys.stderr)
        return exc.status
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        if args.debug:
            traceback.print_exc()
        print(f"check-floor: error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    if not args.terse:
        for line in header:
            print(line)
    print(verdict)
    if expected is None:
        return 0
    if verdict == expected:
        print(f"compare: verdict matches {args.compare}", file=sys.stderr)
        return 0
    print(f"compare: verdict differs; {args.compare} has: {expected}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
