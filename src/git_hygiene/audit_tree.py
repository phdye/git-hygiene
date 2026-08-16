"""Audit an entire repository - working tree, every tracked file, and
every git object - for engagement identifiers.

The companion to `check-identifiers`, which only sees staged changes.
That one prevents new leaks; this one finds what is already there.
Run it before publishing a repository, not on every commit.

Scanning the object store rather than just HEAD is the point: a term
removed from the working tree survives in history until the history
itself is rewritten, and `git log -S` alone will not show it in a
deleted blob.
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from .terms import git, load_patterns, scan_text


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
    args = parser.parse_args(argv)
    repo = Path(args.repo).resolve()

    patterns = load_patterns()
    if not patterns:
        sys.stderr.write("No term file found - nothing to audit against. See GIT_DENY_TERMS.\n")
        return 0

    problems: List[str] = []

    files = tracked_files(repo)
    for rel in files:
        path = repo / rel
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        problems += scan_text(text, patterns, rel)

    log = git("log", "--all", "--format=%H%n%B", cwd=repo)
    problems += scan_text(log.stdout.decode("utf-8", "replace"), patterns, "commit messages")

    scanned_objects = 0
    if args.objects:
        for oid in all_object_ids(repo):
            blob = git("cat-file", "-p", oid, cwd=repo).stdout
            text = blob.decode("utf-8", "replace")
            hits = scan_text(text, patterns, f"object {oid[:10]}")
            problems += hits
            scanned_objects += 1

    print(f"tracked files scanned: {len(files)}")
    print(f"git objects scanned:   {scanned_objects}")

    if problems:
        sys.stderr.write("\nFAIL - identifiers present:\n\n")
        for p in problems:
            sys.stderr.write(p + "\n")
        sys.stderr.write(
            "\nLocations only; terms are not printed. Note that removing a "
            "term from the working tree does not remove it from history - "
            "that needs the history itself rewritten.\n\n"
        )
        return 1

    print("\nCLEAN - no identifier found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
