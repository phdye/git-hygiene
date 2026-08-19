"""Low-level primitives shared across git-hygiene: git plumbing, the
term-file location convention, and the scan/report step that turns a
resolved pattern set into pass/fail output.

Resolving *which* term files apply - the layered, classified model
described in a/doc/deny-term-resolution.md - lives in resolution.py.
This module stays beneath that: it does not know about layers,
classes, or negation. It only knows how to run git, where the legacy
single term file lives, and how to turn a list of already-resolved
patterns into hits and a report.

    term file:  ~/.config/git/deny-terms.txt   (mode 0600)
                one term per line, blank lines and # comments ignored
                overridden per XDG_CONFIG_HOME, see term_file() below

On a match it reports the file and line number, and - since v0.2.0 -
the term itself when the pattern's source is `public`. A term from a
`private` source stays hidden unless the caller explicitly asks to see
it. Printing an identifier from a public, already-tracked file
discloses nothing; printing one from a private file would put it into
terminal scrollback, CI logs, and any pasted error report - recreating
the leak this project exists to prevent. See report() below.
"""

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, List, NamedTuple, Optional

if TYPE_CHECKING:
    # typing.Pattern, not re.Pattern: re.Pattern is 3.8+ and the floor
    # here is 3.6.8 (RHEL 8.10). typing.Pattern was in turn removed in
    # 3.12, so the import is confined to TYPE_CHECKING - it never
    # executes, which keeps the annotation correct for a checker
    # targeting either end of the supported range and harmless at
    # runtime on both. Caught by mypy 0.971 run under the 3.6.9
    # replica; the runtime tests could not see it, because the
    # annotation below is quoted and so is never evaluated.
    from typing import Pattern

DEFAULT_TERM_FILE = Path.home() / ".config" / "git" / "deny-terms.txt"


def term_file() -> Path:
    """Where the legacy/XDG term list lives - resolution.py's layer 2.

    Checked in order: $XDG_CONFIG_HOME/git/deny-terms.txt, else
    ~/.config/git/deny-terms.txt. Path.home() is deliberate but worth
    understanding: on Windows it is the user profile, which is NOT the
    same directory as a Cygwin or MSYS shell's ~. Set XDG_CONFIG_HOME
    explicitly when those disagree - the failure mode otherwise is
    finding no terms and passing everything, which reads as success.
    """
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "git" / "deny-terms.txt"
    return DEFAULT_TERM_FILE


class TermPattern(NamedTuple):
    """One compiled term, with the provenance that governs whether a
    match against it may be printed."""

    regex: "Pattern[str]"
    term: str
    source: Path
    klass: str  # "public" | "private"


class Hit(NamedTuple):
    """One matching line. Always safe to hold in memory and pass
    around; report() is the only place that decides what may reach a
    stream, and it does so per hit from `klass` and `term`."""

    location: str  # "label:lineno"
    term: str
    source: Path
    klass: str


def compile_term(term: str, source: Path, klass: str) -> TermPattern:
    # Word boundaries, so a term does not match inside an unrelated
    # longer word. Without this you get false positives on ordinary
    # API names, and a guard that cries wolf gets switched off.
    regex = re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)
    return TermPattern(regex=regex, term=term, source=source, klass=klass)


def scan_text(text: str, patterns: List[TermPattern], label: str) -> List[Hit]:
    """Locations of matching lines, one Hit per line even when several
    patterns match it - the first pattern to match a line wins, same
    as the pre-v0.2.0 behavior of reporting a line once."""
    hits = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for pattern in patterns:
            if pattern.regex.search(line):
                hits.append(
                    Hit(
                        location=f"{label}:{lineno}",
                        term=pattern.term,
                        source=pattern.source,
                        klass=pattern.klass,
                    )
                )
                break
    return hits


def report(
    hits: List[Hit],
    scope: str,
    show_private: bool = False,
    show_terms: bool = True,
) -> int:
    if not hits:
        return 0
    sys.stderr.write(f"\nBLOCKED: {scope} matches a denylisted identifier.\n")
    for hit in hits:
        printable = show_terms and (hit.klass == "public" or show_private)
        if printable:
            sys.stderr.write(f"  {hit.location}  [{hit.term}]\n")
        else:
            sys.stderr.write(f"  {hit.location}\n")
    if not show_terms or any(h.klass == "private" and not show_private for h in hits):
        sys.stderr.write(
            "\nOne or more matches are from a private term source and are not "
            "shown - pass --show-private-terms to see them.\n"
        )
    sys.stderr.write(
        "\nRemove the identifier, or if this is a false positive, "
        "narrow the term in its term file.\n\n"
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


def git_dir(repo: Path) -> Optional[Path]:
    """The repository's git directory, resolved the way git itself
    would - so a worktree, or a repo reached through a symlink chain,
    lands on the right .git regardless of where the on-disk `.git`
    entry actually points.

    Like git_toplevel below, this must survive git answering in a path
    convention the running interpreter does not share. A relative
    answer is joined onto `repo` and is always usable; an absolute one
    may be a POSIX path from a Cygwin git under a native Windows
    interpreter, so it is checked before being trusted and the
    conventional location is used if it does not resolve.
    """
    out = git("rev-parse", "--git-dir", cwd=repo)
    if out.returncode != 0:
        return None
    rel = out.stdout.decode("utf-8", "replace").strip()
    if not rel:
        return None
    path = Path(rel)
    if not path.is_absolute():
        return repo / path
    if path.exists():
        return path
    fallback = repo / ".git"
    return fallback if fallback.exists() else None


def git_toplevel(start: Optional[Path] = None) -> Optional[Path]:
    """The work tree root, or None outside one. resolution.py's
    anchor - see a/doc/deny-term-resolution.md, "Resolve once".

    Deliberately NOT `rev-parse --show-toplevel`. That returns an
    absolute path in *git's* convention, and under Cygwin git that is a
    POSIX path like `/home/user/repo`. A native Windows interpreter can
    do nothing useful with it: `subprocess.run(cwd=...)` raises
    NotADirectoryError [WinError 267], and - worse, because it is
    silent - `Path("/home/user/repo") / ".deny-terms"` simply does not
    exist, so every layer probe answers False and the scan passes
    having found no terms at all. Fail-open is the outcome this project
    exists to prevent.

    `--show-cdup` instead returns a path *relative* to the current
    directory (empty at the root, `../../` two levels down). A relative
    path has no convention to disagree about, so joining it onto the
    interpreter's own `Path.cwd()` yields an answer the interpreter can
    both resolve and spawn with, on every platform, with no translation
    step and no `cygpath`.

    The general rule, which the sibling issues in a/issue/ keep
    rediscovering: git's answer identifies the repository, the
    interpreter's answer says where the interpreter can go, and those
    are different questions that merely coincide on most platforms.
    """
    out = git("rev-parse", "--show-cdup", cwd=start)
    if out.returncode != 0:
        return None
    cdup = out.stdout.decode("utf-8", "replace").strip()
    base = Path(start) if start is not None else Path.cwd()
    if not cdup:
        return base
    return (base / cdup).resolve()
