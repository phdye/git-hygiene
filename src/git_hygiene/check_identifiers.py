"""pre-commit entry point: refuse staged content or a commit message
carrying an engagement identifier.

Sees staged changes only. Prevents new leaks; it does not audit what
is already committed - use `audit-tree` for that.

A hard resolution error (a tracked private term file, an unauthorized
negation, a class conflict, a missing named public source) stops the
check before it scans anything: a run that reported clean while
misconfigured would be worse than no run at all.

Exit codes: 0 pass, 1 refuse, 2 usage. With --require-private (or
GIT_HYGIENE_REQUIRE_PRIVATE), resolving no private term source is a
refusal rather than a silent pass, so a repository can insist that its
list reached the machine. A commit that staged nothing readable as text
still passes: there was nothing the list could have been checked against.
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from . import resolution
from .options import add_resolution_options, apply_environment
from .terms import (
    env_flag,
    git,
    git_toplevel,
    is_binary,
    patterns_excluding,
    report,
    resolved_path,
    scan_text,
)

_REQUIRE_ENV = "GIT_HYGIENE_REQUIRE_PRIVATE"


def staged_files() -> List[str]:
    out = git("diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR")
    return [f for f in out.stdout.decode("utf-8", "replace").split("\0") if f]


def staged_blob(path: str) -> Optional[bytes]:
    """The staged blob, not the working-tree file. They can differ, and
    it is the staged version that would be committed."""
    r = git("show", f":{path}")
    if r.returncode != 0:
        return None
    return r.stdout


def _no_private_source(result: resolution.ResolutionResult, what: str, walked: List[Path]) -> int:
    """Name every place a private list could have come from. Paths only;
    a term is never printed here."""
    sys.stderr.write(f"\nBLOCKED: no private term source resolved, and one is required; {what}.\n")
    sys.stderr.write("check-identifiers: probed:\n")
    listed = set()
    for source in result.sources:
        if source.klass == "private":
            listed.add(source.path)
            sys.stderr.write(f"  {source.path}  ({source.status})\n")
    for directory in walked:
        candidate = directory / resolution.PRIVATE_NAME
        if candidate not in listed:
            sys.stderr.write(f"  {candidate}  (absent)\n")
    return 1


def _require_private(args: argparse.Namespace, parser: argparse.ArgumentParser) -> bool:
    if args.require_private is not None:
        return bool(args.require_private)
    try:
        return bool(env_flag(_REQUIRE_ENV))
    except ValueError as exc:
        parser.error(str(exc))
    return False


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Refuse engagement identifiers in staged content or a commit message.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--staged", action="store_true", help="scan staged file content")
    group.add_argument("--message", metavar="FILE", help="scan a commit message file")
    add_resolution_options(parser)
    parser.add_argument("--explain", action="store_true", help="print term resolution and exit")
    parser.add_argument(
        "--require-private",
        dest="require_private",
        action="store_true",
        default=None,
        help="refuse when no private term source resolves (env: GIT_HYGIENE_REQUIRE_PRIVATE)",
    )
    parser.add_argument(
        "--no-require-private",
        dest="require_private",
        action="store_false",
        help="undo --require-private",
    )
    args = apply_environment(parser.parse_args(argv), parser)
    required = _require_private(args, parser)

    anchor = git_toplevel() or Path.cwd()
    result = resolution.resolve(
        anchor=anchor,
        extra_terms=args.terms,
        no_inherit=args.no_inherit,
        no_walk=args.no_walk,
        walk_to=args.walk_to,
        # --explain output is what gets pasted into bug reports; it names
        # no term under any flag (decision 0006).
        show_private_terms=args.show_private_terms and not args.explain,
    )

    if args.explain:
        for line in resolution.explain_lines(result):
            print(line)
        if result.fatal:
            sys.stderr.write("\nterm resolution failed:\n")
            for error in result.errors:
                sys.stderr.write("  " + error + "\n")
            return 1
        return 0

    if result.fatal:
        sys.stderr.write("\nBLOCKED: term resolution failed.\n\n")
        for error in result.errors:
            sys.stderr.write("  " + error + "\n")
        sys.stderr.write("\nRun with --explain for the full resolution.\n\n")
        return 1

    have_private = bool(result.loaded("private"))
    show_terms = not args.no_show_terms
    walked = (
        []
        if (args.no_walk or args.no_inherit)
        else resolution.walk_dirs(anchor, Path(args.walk_to) if args.walk_to else None)
    )

    if args.message:
        msg_path = Path(args.message)
        if not msg_path.is_file():
            return 0
        if not result.patterns and not required:
            return 0  # silent by design; see decision 0002
        text = msg_path.read_text(encoding="utf-8", errors="replace")
        hits = scan_text(text, result.patterns, "commit message")
        if hits:
            return report(hits, "commit message", args.show_private_terms, show_terms)
        if required and not have_private:
            return _no_private_source(
                result, "the message was checked against public terms only", walked
            )
        return 0

    if not result.patterns and not required:
        return 0  # silent by design; see decision 0002
    paths = staged_files()

    # A loaded term file is scanned against every source but its own.
    term_files = {c[0] for p in result.patterns for c in p.contributors}
    hits = []
    texts = 0
    for path in paths:
        blob = staged_blob(path)
        if blob is None:
            continue
        if not is_binary(blob):
            texts += 1
        own = resolved_path(anchor / path)
        patterns = (
            patterns_excluding(result.patterns, own) if own in term_files else result.patterns
        )
        hits += scan_text(blob.decode("utf-8", "replace"), patterns, path)
    if hits:
        return report(hits, "staged content", args.show_private_terms, show_terms)
    if required and texts and not have_private:
        return _no_private_source(
            result, "staged content was checked against public terms only", walked
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
