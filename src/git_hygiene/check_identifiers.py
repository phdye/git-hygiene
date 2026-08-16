"""pre-commit entry point: refuse staged content or a commit message
carrying an engagement identifier.

Sees staged changes only. Prevents new leaks; it does not audit what
is already committed - use `audit-tree` for that.
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from .terms import git, load_patterns, report, scan_text


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
    args = parser.parse_args(argv)

    patterns = load_patterns()
    if not patterns:
        # No term file. Silent success by design - see module docstring.
        return 0

    if args.message:
        msg_path = Path(args.message)
        if not msg_path.is_file():
            return 0
        text = msg_path.read_text(encoding="utf-8", errors="replace")
        return report(scan_text(text, patterns, "commit message"), "commit message")

    problems: List[str] = []
    for path in staged_files():
        content = staged_content(path)
        if content is None:
            continue  # binary or unreadable; nothing to scan
        problems += scan_text(content, patterns, path)
    return report(problems, "staged content")


if __name__ == "__main__":
    sys.exit(main())
