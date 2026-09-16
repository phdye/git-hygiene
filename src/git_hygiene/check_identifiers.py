"""pre-commit entry point: refuse staged content or a commit message
carrying an engagement identifier.

Sees staged changes only. Prevents new leaks; it does not audit what
is already committed - use `audit-tree` for that.

A hard resolution error (a tracked private term file, an unauthorized
negation, a class conflict, a missing named public source) stops the
check before it scans anything: a run that reported clean while
misconfigured would be worse than no run at all.

Exit codes follow contract 1 (0 pass, 1 refuse, 2 usage) unless
`--exit-contract 2` is given, which adds 3 (nothing of this check's
kind was staged) and 4 (no private term source resolved, or the
message file is missing). The dispatcher asks for contract 2; a direct
caller such as the pre-commit framework keeps contract 1 and sees no
change.
"""

import argparse
import os
import sys
from pathlib import Path
from typing import List, Optional

from . import resolution
from .options import add_resolution_options, apply_environment
from .terms import (
    git,
    git_toplevel,
    is_binary,
    patterns_excluding,
    report,
    resolved_path,
    scan_text,
)

NOT_APPLICABLE = 3
COULD_NOT_RUN = 4
_CONTRACT_ENV = "GIT_HYGIENE_EXIT_CONTRACT"


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


def _no_private_source(result: resolution.ResolutionResult, what: str) -> int:
    sys.stderr.write(f"check-identifiers: no private term source resolved; {what}.\n")
    sys.stderr.write("check-identifiers: probed:\n")
    for source in result.sources:
        if source.klass == "private":
            sys.stderr.write(f"  {source.path}  ({source.status})\n")
    return COULD_NOT_RUN


def _contract(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    raw = args.exit_contract or os.environ.get(_CONTRACT_ENV, "").strip() or "1"
    if raw not in ("1", "2"):
        parser.error(f"exit contract must be 1 or 2, not {raw!r}")
    return int(raw)


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
        "--exit-contract",
        metavar="N",
        help="exit-code contract, 1 (default) or 2 (env: GIT_HYGIENE_EXIT_CONTRACT)",
    )
    args = apply_environment(parser.parse_args(argv), parser)
    contract = _contract(args, parser)

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

    if args.message:
        msg_path = Path(args.message)
        if not msg_path.is_file():
            if contract == 2:
                sys.stderr.write(f"check-identifiers: commit message file not found: {msg_path}\n")
                return COULD_NOT_RUN
            return 0
        if not result.patterns and contract == 1:
            return 0  # silent by design; see decision 0002
        text = msg_path.read_text(encoding="utf-8", errors="replace")
        hits = scan_text(text, result.patterns, "commit message")
        if hits:
            return report(hits, "commit message", args.show_private_terms, show_terms)
        if contract == 2 and not have_private:
            return _no_private_source(result, "the message was checked against public terms only")
        return 0

    if not result.patterns and contract == 1:
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
    if contract == 2:
        if texts == 0:
            return NOT_APPLICABLE
        if not have_private:
            return _no_private_source(
                result, "staged content was checked against public terms only"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
