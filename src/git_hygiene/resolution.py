"""Layered, classified deny-term resolution - v0.2.0.

Design: a/doc/deny-term-resolution.md. That document is authoritative;
this module implements it. Read it before changing precedence, class
rules, or negation authorization - those are decided there, not here.

Terms live in files sitting on a spectrum from "system-wide and never
committed" to "the team's own tracked list", and previously only the
first of those was representable. Every file now declares a class:

    public   - safe to publish, expected to be tracked, terms print.
    private  - must never be tracked, terms stay hidden by default.

An undeclared file defaults to private - the safe direction, and the
one that keeps every existing ~/.config/git/deny-terms.txt working
unchanged.

Layers, lowest precedence first (see the module docstring's table in
the design doc for the full reasoning):

    1  /etc/git-hygiene/deny-terms
    2  $XDG_CONFIG_HOME/git/deny-terms.txt, else ~/.config/git/...
    3  ancestor .deny-terms / .deny-terms.private, outermost first
    4  <repo root>/.deny-terms
    5  <git dir>/info/deny-terms
    6  GIT_DENY_TERMS (os.pathsep separated)
    7  --terms FILE (repeatable)

Terms accumulate as a union across every layer. `!term` removes an
inherited term, but only when the negating source's layer is at or
above the introducing source's layer, and at least as strict a class -
a public source can never cancel a term a private source introduced,
since the cancellation would be visible where the term was not.
"""

import os
import stat
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Tuple

from .terms import Hit, TermPattern, compile_term, git, git_dir, term_file

_DIRECTIVE_PUBLIC = "# git-hygiene: public"
_DIRECTIVE_PRIVATE = "# git-hygiene: private"

# Strictness rank for the class-authorization rule on negation: a
# negating source must be at least as strict as the source it negates.
_RANK = {"private": 2, "public": 1}


class Source(NamedTuple):
    """One candidate term file and what became of it - the row shape
    --explain prints. `terms` counts only positive term lines actually
    contributed; a source with a conflict or a trust-check failure
    contributes none even if the file has content."""

    path: Path
    klass: str  # "public" | "private" | "-" (unset: absent, never read)
    declared: bool
    status: str  # loaded | absent | skipped:<reason> | error:<reason>
    terms: int
    walked: bool = False


class ResolutionResult(NamedTuple):
    patterns: List[TermPattern]
    sources: List[Source]
    errors: List[str]
    fatal: bool
    negations_honored: int


def _classify(path: Path) -> Tuple[str, bool]:
    """(class, declared) from the file's first non-blank line. An
    undeclared file is private - see the module docstring."""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return "private", False
    for raw in lines:
        stripped = raw.strip()
        if not stripped:
            continue
        lowered = stripped.lower()
        if lowered == _DIRECTIVE_PUBLIC:
            return "public", True
        if lowered == _DIRECTIVE_PRIVATE:
            return "private", True
        break  # first non-blank line was content, not a directive
    return "private", False


def _parse_terms(path: Path) -> "Tuple[List[str], List[str], Optional[str]]":
    """(positive terms, negated terms, error). Blank lines, comments,
    and the directive line itself are skipped. A term appearing both
    plain and negated in the same file is a conflict, not a
    last-one-wins - the file contributes nothing when that happens."""
    try:
        raw_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        return [], [], f"unreadable: {exc}"

    positives: List[str] = []
    negatives: List[str] = []
    seen_directive = False
    for raw in raw_lines:
        stripped = raw.strip()
        if not stripped:
            continue
        lowered = stripped.lower()
        if not seen_directive and lowered in (_DIRECTIVE_PUBLIC, _DIRECTIVE_PRIVATE):
            seen_directive = True
            continue
        seen_directive = True
        if stripped.startswith("#"):
            continue
        if stripped.startswith("!"):
            negatives.append(stripped[1:].strip())
        else:
            positives.append(stripped)

    conflicts = {t.lower() for t in positives} & {t.lower() for t in negatives}
    if conflicts:
        return [], [], "conflicting term/negation: {}".format(", ".join(sorted(conflicts)))
    return positives, negatives, None


def _trusted(path: Path) -> Tuple[bool, str]:
    """(trusted, reason-if-not). Applies only to the ancestor walk and
    the repo-root layer - files nobody in particular controls, per the
    design doc's ssh-style posture. On Windows, ownership and world
    writability are not meaningfully checkable through os.stat; this
    degrades to "exists and is readable", not a real guarantee."""
    if os.name != "posix":
        return True, ""
    try:
        st = path.stat()
    except OSError:
        return False, "unreadable"
    if st.st_mode & stat.S_IWOTH:
        return False, "world writable"
    # os.getuid is POSIX-only and the `os.name` guard above already
    # rules out Windows, but mypy checks against the platform it runs
    # on - which here is Windows - so it cannot see that.
    if st.st_uid not in (os.getuid(), 0):  # type: ignore[attr-defined]
        return False, "not owned by the invoking user or root"
    return True, ""


def _walk_ancestors(anchor: Path, walk_to: Optional[Path]) -> List[Path]:
    """Candidate .deny-terms / .deny-terms.private paths from anchor's
    ancestors, outermost first. Stops at walk_to (if given), $HOME, or
    a filesystem boundary - never above them."""
    home = Path.home()
    found: List[Path] = []
    seen = set()
    current = anchor.parent
    while True:
        if current in seen:
            break
        seen.add(current)
        for name in (".deny-terms", ".deny-terms.private"):
            candidate = current / name
            if candidate.is_file():
                found.append(candidate)
        if walk_to is not None and current == walk_to:
            break
        if current == home:
            break
        if current.parent == current:
            break
        current = current.parent
    found.reverse()  # outermost first
    return found


def _env_paths(name: str) -> List[Path]:
    raw = os.environ.get(name)
    if not raw:
        return []
    return [Path(p) for p in raw.split(os.pathsep) if p.strip()]


def _expected_class_from_name(path: Path) -> Optional[str]:
    """What the filename alone implies, used only to decide whether a
    MISSING *explicitly named* source is a silent skip or a loud
    error - a directive cannot be read from a file that is not there.
    Only applies to --terms / GIT_DENY_TERMS: an auto-probed candidate
    like the repo-root .deny-terms is optional by nature (most repos
    will never have one) and stays silent-absent regardless of name,
    matching every other layer's default. See a/doc/instructions.md."""
    if path.name == ".deny-terms":
        return "public"
    if path.name == ".deny-terms.private":
        return "private"
    return None


def _is_tracked_private(path: Path, repo_root: Optional[Path]) -> bool:
    if repo_root is None:
        return False
    try:
        rel = path.resolve().relative_to(repo_root.resolve())
    except (OSError, ValueError):
        return False
    result = git("ls-files", "--error-unmatch", str(rel), cwd=repo_root)
    return result.returncode == 0


def resolve(
    anchor: Optional[Path] = None,
    extra_terms: Optional[List[str]] = None,
    no_inherit: bool = False,
    no_walk: bool = False,
    walk_to: Optional[str] = None,
) -> ResolutionResult:
    """Build the merged, provenance-carrying pattern set. `anchor` is
    normally the work tree root (git_toplevel()); resolution happens
    once per invocation and is reused for every file scanned."""
    if anchor is None:
        anchor = Path.cwd()
    walk_boundary = Path(walk_to) if walk_to else None
    repo_root = anchor if (anchor / ".git").exists() else None

    explicit_paths = [Path(p) for p in (extra_terms or [])]
    env_paths = _env_paths("GIT_DENY_TERMS")

    # (path, walked, explicit) - `explicit` gates the loud-absence rule
    # below; only a source the operator specifically named can be
    # "missing" in a way worth failing on, since every auto-probed
    # candidate (system, xdg, walk, repo-root, git-info) is optional
    # by nature and silently absent is its ordinary, unremarkable state.
    if no_inherit:
        layers: List[Tuple[Path, bool, bool]] = []
        if explicit_paths:
            layers = [(p, False, True) for p in explicit_paths]
        elif env_paths:
            layers = [(p, False, True) for p in env_paths]
    else:
        layers = [(Path("/etc/git-hygiene/deny-terms"), False, False)]
        layers.append((term_file(), False, False))
        if not no_walk:
            layers += [(p, True, False) for p in _walk_ancestors(anchor, walk_boundary)]
        layers.append((anchor / ".deny-terms", True, False))
        gd = git_dir(anchor)
        if gd is not None:
            layers.append((gd / "info" / "deny-terms", False, False))
        layers += [(p, False, True) for p in env_paths]
        layers += [(p, False, True) for p in explicit_paths]

    sources: List[Source] = []
    errors: List[str] = []
    fatal = False
    negations_honored = 0

    # term (lowercased) -> (TermPattern, introducing source path, rank, klass)
    active: Dict[str, Tuple[TermPattern, Path, int, str]] = {}

    for rank, (path, walked, explicit) in enumerate(layers):
        if not path.is_file():
            expected = _expected_class_from_name(path) if explicit else None
            if expected == "public":
                errors.append(f"missing declared-public term source: {path}")
                fatal = True
                sources.append(Source(path, "public", True, "error:missing", 0, walked))
            else:
                sources.append(Source(path, "-", False, "absent", 0, walked))
            continue

        subject_to_trust = walked or path.name == ".deny-terms"
        if subject_to_trust:
            trusted, reason = _trusted(path)
            if not trusted:
                sources.append(Source(path, "-", False, "skipped:" + reason, 0, walked))
                continue

        klass, declared = _classify(path)
        if _is_tracked_private(path, repo_root) and klass == "private":
            errors.append(f"tracked private term file: {path}")
            fatal = True
            sources.append(Source(path, klass, declared, "error:tracked", 0, walked))
            continue

        positives, negatives, parse_error = _parse_terms(path)
        if parse_error is not None:
            errors.append(f"{path}: {parse_error}")
            sources.append(Source(path, klass, declared, "error:" + parse_error, 0, walked))
            continue

        contributed = 0
        for term in positives:
            key = term.lower()
            if key in active:
                continue  # first introduction wins provenance
            active[key] = (compile_term(term, path, klass), path, rank, klass)
            contributed += 1

        for term in negatives:
            key = term.lower()
            entry = active.get(key)
            if entry is None:
                continue  # nothing active to cancel; not an error
            _pattern, introducing_path, introducing_rank, introducing_klass = entry
            if rank < introducing_rank:
                continue  # cannot happen given processing order; defensive
            if _RANK[klass] < _RANK[introducing_klass]:
                errors.append(
                    f"unauthorized negation of '{term}': {path} ({klass}) cannot cancel a term from "
                    f"{introducing_path} ({introducing_klass})"
                )
                continue
            del active[key]
            negations_honored += 1

        sources.append(Source(path, klass, declared, "loaded", contributed, walked))

    patterns = [entry[0] for entry in active.values()]
    return ResolutionResult(
        patterns=patterns,
        sources=sources,
        errors=errors,
        fatal=fatal,
        negations_honored=negations_honored,
    )


def explain_lines(result: ResolutionResult) -> List[str]:
    lines = ["source                                        class    status      terms"]
    total_terms = 0
    total_sources = 0
    skipped = 0
    for source in result.sources:
        label = str(source.path)
        if source.walked:
            label = "(walk) " + label
        klass = source.klass
        lines.append(f"{label:<46} {klass:<8} {source.status:<11} {source.terms:>5}")
        if source.status == "loaded":
            total_terms += source.terms
            total_sources += 1
        if source.status.startswith("skipped"):
            skipped += 1
    lines.append("")
    lines.append(
        "{} terms from {} sources, {} skipped, {} negation{} honored".format(
            total_terms,
            total_sources,
            skipped,
            result.negations_honored,
            "" if result.negations_honored == 1 else "s",
        )
    )
    return lines


__all__ = ["Source", "ResolutionResult", "resolve", "explain_lines", "Hit", "TermPattern"]
