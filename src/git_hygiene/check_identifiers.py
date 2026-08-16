"""pre-commit entry point: refuse staged content or a commit message
carrying an engagement identifier.

Sees staged changes only. Prevents new leaks; it does not audit what
is already committed - use `audit-tree` for that.

Term resolution is layered and classified as of v0.2.0 - see
a/doc/deny-term-resolution.md and git_hygiene.resolution. A hard
resolution error (a tracked private term file, an unauthorized
negation, a missing declared-public source) stops the check before it
scans anything: a run that reported clean while misconfigured would be
worse than no run at all.
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from . import resolution
from .terms import git, git_toplevel, report, scan_text


def staged_files() -> List[str]:
    out = git("diff", "--cached", "--name-only", "--diff-filter=ACMR")
    return [f for f in out.stdout.decode("utf-8", "replace").splitlines() if f.strip()]


def staged_content(path: str) -> Optional[str]:
    """The staged blob, not the working-tree file. They can differ, and
    it is the staged version that would be committed."""
    r = git("show", f":{path}")
    if r.returncode != 0:
        return None
    return r.stdout.decode("utf-8", "replace")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Refuse engagement identifiers in staged content or a commit message.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--staged", action="store_true", help="scan staged file content")
    group.add_argument("--message", metavar="FILE", help="scan a commit message file")
    parser.add_argument(
        "--terms", action="append", metavar="FILE", help="explicit term source, repeatable"
    )
    parser.add_argument(
        "--no-inherit",
        action="store_true",
        help="use only the highest explicit source (--terms, else GIT_DENY_TERMS)",
    )
    parser.add_argument("--no-walk", action="store_true", help="skip the ancestor walk")
    parser.add_argument("--walk-to", metavar="DIR", help="bound the ancestor walk")
    parser.add_argument(
        "--show-private-terms",
        action="store_true",
        help="also print matched terms from private sources",
    )
    parser.add_argument(
        "--no-show-terms",
        action="store_true",
        help="suppress all term printing; locations only",
    )
    parser.add_argument("--explain", action="store_true", help="print term resolution and exit")
    args = parser.parse_args(argv)

    anchor = git_toplevel() or Path.cwd()
    result = resolution.resolve(
        anchor=anchor,
        extra_terms=args.terms,
        no_inherit=args.no_inherit,
        no_walk=args.no_walk,
        walk_to=args.walk_to,
    )

    if args.explain:
        for line in resolution.explain_lines(result):
            print(line)
        return 1 if result.fatal else 0

    if result.fatal:
        sys.stderr.write("\nBLOCKED: term resolution failed.\n\n")
        for error in result.errors:
            sys.stderr.write("  " + error + "\n")
        sys.stderr.write("\nRun with --explain for the full resolution.\n\n")
        return 1

    if not result.patterns:
        # No term anywhere resolved. Silent success by design - see
        # git_hygiene.resolution and the README.
        return 0

    show_terms = not args.no_show_terms

    if args.message:
        msg_path = Path(args.message)
        if not msg_path.is_file():
            return 0
        text = msg_path.read_text(encoding="utf-8", errors="replace")
        hits = scan_text(text, result.patterns, "commit message")
        return report(hits, "commit message", args.show_private_terms, show_terms)

    hits = []
    for path in staged_files():
        content = staged_content(path)
        if content is None:
            continue  # binary or unreadable; nothing to scan
        hits += scan_text(content, result.patterns, path)
    return report(hits, "staged content", args.show_private_terms, show_terms)


if __name__ == "__main__":
    sys.exit(main())
