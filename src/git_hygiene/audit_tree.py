"""Audit an entire repository - working tree, every tracked file, and
every git object - for engagement identifiers.

The companion to `check-identifiers`, which only sees staged changes.
That one prevents new leaks; this one finds what is already there.
Run it before publishing a repository, not on every commit.

Scanning the object store rather than just HEAD is the point: a term
removed from the working tree survives in history until the history
itself is rewritten, and `git log -S` alone will not show it in a
deleted blob.

Term resolution is layered and classified as of v0.2.0 - see
a/doc/deny-term-resolution.md. The resolution summary always prints,
even without --explain: this is a pre-publish gate, and whether it
audited against zero terms is the entire question being asked of it.
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from . import resolution
from .terms import Hit, git, scan_text


def tracked_files(repo: Path) -> List[str]:
    out = git("ls-files", cwd=repo)
    return [f for f in out.stdout.decode("utf-8", "replace").splitlines() if f.strip()]


def all_object_ids(repo: Path) -> List[str]:
    out = git("cat-file", "--batch-all-objects", "--batch-check", cwd=repo)
    ids = []
    for line in out.stdout.decode("utf-8", "replace").splitlines():
        parts = line.split()
        if parts:
            ids.append(parts[0])
    return ids


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audit a repository's tracked files, commit messages and git "
            "objects for engagement identifiers. Run before publishing."
        ),
    )
    parser.add_argument("repo", nargs="?", default=".", help="repository path (default: cwd)")
    parser.add_argument(
        "--objects",
        action="store_true",
        help="also scan every git object, including unreachable history (slow)",
    )
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
    parser.add_argument(
        "--explain",
        action="store_true",
        help="print the full term resolution, not just its summary",
    )
    args = parser.parse_args(argv)
    repo = Path(args.repo).resolve()

    result = resolution.resolve(
        anchor=repo,
        extra_terms=args.terms,
        no_inherit=args.no_inherit,
        no_walk=args.no_walk,
        walk_to=args.walk_to,
    )

    if args.explain:
        for line in resolution.explain_lines(result):
            print(line)
    else:
        print(resolution.explain_lines(result)[-1])  # the summary line, unconditionally

    if result.fatal:
        sys.stderr.write("\nFAIL - term resolution failed:\n\n")
        for error in result.errors:
            sys.stderr.write("  " + error + "\n")
        sys.stderr.write("\nNothing was scanned. Run with --explain for the full resolution.\n\n")
        return 1

    if not result.patterns:
        sys.stderr.write("No term resolved - nothing to audit against. See --explain.\n")
        return 0

    hits: List[Hit] = []

    files = tracked_files(repo)
    for rel in files:
        path = repo / rel
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        hits += scan_text(text, result.patterns, rel)

    log = git("log", "--all", "--format=%H%n%B", cwd=repo)
    hits += scan_text(log.stdout.decode("utf-8", "replace"), result.patterns, "commit messages")

    scanned_objects = 0
    if args.objects:
        for oid in all_object_ids(repo):
            blob = git("cat-file", "-p", oid, cwd=repo).stdout
            text = blob.decode("utf-8", "replace")
            hits += scan_text(text, result.patterns, f"object {oid[:10]}")
            scanned_objects += 1

    print(f"tracked files scanned: {len(files)}")
    print(f"git objects scanned:   {scanned_objects}")

    if hits:
        sys.stderr.write("\nFAIL - identifiers present:\n\n")
        show_terms = not args.no_show_terms
        for hit in hits:
            printable = show_terms and (hit.klass == "public" or args.show_private_terms)
            if printable:
                sys.stderr.write(f"  {hit.location}  [{hit.term}]\n")
            else:
                sys.stderr.write(f"  {hit.location}\n")
        sys.stderr.write(
            "\nA private-source term is withheld unless --show-private-terms is "
            "given. Note that removing a term from the working tree does not "
            "remove it from history - that needs the history itself rewritten.\n\n"
        )
        return 1

    print("\nCLEAN - no identifier found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
