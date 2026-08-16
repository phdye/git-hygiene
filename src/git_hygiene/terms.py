"""Refuse content carrying an engagement identifier.

The terms live outside every repository, in a file this module reads
at run time. Nothing here names one, so this code is safe to publish;
the term list is not, and never should be - a denylist committed to a
public repository publishes exactly what it conceals.

    term file:  ~/.config/git/deny-terms.txt   (mode 0600)
                one term per line, blank lines and # comments ignored
                override with GIT_DENY_TERMS

Exits 0 and says nothing when the term file is absent. Anyone cloning
a public repository will not have one, and this is a local safety net
rather than a project requirement - it must never become a barrier to
contribution.

On a match it reports the file and line number but NOT the term that
matched. Printing it would put the identifier into terminal
scrollback, CI logs, and any pasted error report - reintroducing the
leak this exists to prevent.
"""

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Pattern

DEFAULT_TERM_FILE = Path.home() / ".config" / "git" / "deny-terms.txt"


def term_file() -> Path:
    """Where the term list lives.

    Path.home() is deliberate but worth understanding: on Windows it
    is the user profile, which is NOT the same directory as a Cygwin
    or MSYS shell's ~. When those disagree, set GIT_DENY_TERMS - the
    failure mode otherwise is finding no terms and passing everything,
    which reads as success.
    """
    override = os.environ.get("GIT_DENY_TERMS")
    return Path(override) if override else DEFAULT_TERM_FILE


def load_patterns(path: Optional[Path] = None) -> List[Pattern[str]]:
    path = path or term_file()
    if not path.is_file():
        return []
    patterns = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        term = raw.strip()
        if not term or term.startswith("#"):
            continue
        # Word boundaries, so a term does not match inside an unrelated
        # longer word. Without this you get false positives on ordinary
        # API names, and a guard that cries wolf gets switched off.
        patterns.append(re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE))
    return patterns


def scan_text(text: str, patterns: List[Pattern[str]], label: str) -> List[str]:
    """Locations of matching lines. Location only - never the term."""
    problems = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for pattern in patterns:
            if pattern.search(line):
                problems.append(f"  {label}:{lineno}")
                break
    return problems


def report(problems: List[str], scope: str) -> int:
    if not problems:
        return 0
    sys.stderr.write(
        f"\nBLOCKED: {scope} matches a denylisted identifier.\n"
        "The term is deliberately not printed - see your term file.\n\n"
    )
    for p in problems:
        sys.stderr.write(p + "\n")
    sys.stderr.write(
        "\nRemove the identifier, or if this is a false positive, "
        "narrow the term in the term file.\n\n"
    )
    return 1


def git(*args: str, cwd: Optional[Path] = None) -> "subprocess.CompletedProcess[bytes]":
    # stdout/stderr spelled out rather than capture_output=True: that
    # kwarg is 3.7+ only, and the floor here is 3.6.8 to match RHEL 8.10.
    # ruff's oldest target-version is py37 (no py36 exists), so UP022
    # fires suggesting capture_output even though it would break the
    # real floor - suppressed rather than silently regressed.
    return subprocess.run(  # noqa: S603, UP022
        ["git", *args],  # noqa: S607 - resolved from PATH, as git tooling does
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
