"""Layered, classified deny-term resolution.

The layered/classified model is specified in doc/design/Architecture.md
and decided in doc/design/decisions/, which remain authoritative; this
module implements them. Read them before changing precedence, class
rules, or negation authorization - those are decided there, not here.

Every term file is one of two classes:

    public   - safe to publish, expected to be tracked, terms print.
    private  - must never be tracked, terms stay hidden by default.

The class comes from the file's name or location and from nothing else
(decisions 0004 and 0006, as amended). `.deny-terms` is public,
`.deny-terms.private` is private, the system, user and git-dir files are
private because of where they live, and any other name is private. A
`# git-hygiene: public|private` first line is an optional assertion that
must agree with that; a disagreement is an error, not a precedence
question.

Layers, lowest precedence first:

    1  /etc/git-hygiene/deny-terms
    2  $XDG_CONFIG_HOME/git/deny-terms.txt, else ~/.config/git/...
    3  ancestor .deny-terms / .deny-terms.private, outermost first
    4  <repo root>/.deny-terms, then <repo root>/.deny-terms.private
    5  <git dir>/info/deny-terms
    6  GIT_DENY_TERMS (os.pathsep separated)
    7  --terms FILE (repeatable)

Terms accumulate as a union across every layer. `!term` removes an
inherited term, but only when the negating source is at least as strict
a class as every source that contributed the term - a public source can
never cancel a term a private source holds, since the cancellation would
be visible where the term was not.
"""

import os
import stat
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Tuple

from .terms import Hit, TermPattern, compile_term, git, git_dir, resolved_path, term_file

PUBLIC_NAME = ".deny-terms"
PRIVATE_NAME = ".deny-terms.private"

_DIRECTIVES = {
    "# git-hygiene: public": "public",
    "# git-hygiene: private": "private",
}

# Strictness rank for the class-authorization rule on negation: a
# negating source must be at least as strict as the source it negates.
_RANK = {"private": 2, "public": 1}

# Layer kinds whose class is fixed by location rather than by name.
_LOCATION_PRIVATE = ("system", "user", "git-info")


class Source(NamedTuple):
    """One candidate term file and what became of it - the row shape
    --explain prints. `klass` is always the derived class, whether or
    not the file exists. `declared` is true when the file carries an
    in-band directive. `terms` counts positive term lines contributed."""

    path: Path
    klass: str  # "public" | "private"
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

    def loaded(self, klass: Optional[str] = None) -> List[Source]:
        return [
            s for s in self.sources if s.status == "loaded" and (klass is None or s.klass == klass)
        ]


class _Layer(NamedTuple):
    path: Path
    kind: str  # system | user | walk | root | git-info | env | flag
    walked: bool
    explicit: bool


def class_of(path: Path, kind: str = "flag") -> str:
    """The class a candidate has before anything is read from it."""
    if kind in _LOCATION_PRIVATE:
        return "private"
    return "public" if path.name == PUBLIC_NAME else "private"


def _declared_class(path: Path) -> Optional[str]:
    """The class asserted on the first non-blank line, or None."""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    for raw in lines:
        stripped = raw.strip()
        if stripped:
            return _DIRECTIVES.get(stripped.lower())
    return None


def _parse_terms(path: Path) -> "Tuple[List[str], List[str], Optional[str]]":
    """(positive terms, negated terms, error). Blank lines and comments
    are skipped; the directive is a comment. A term appearing both
    plain and negated in the same file is a conflict, not a
    last-one-wins - the file contributes nothing when that happens."""
    try:
        raw_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        return [], [], f"unreadable: {exc}"

    positives: List[str] = []
    negatives: List[str] = []
    for raw in raw_lines:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
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
    ssh-style posture of decision 0004. On Windows, ownership and world
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
    # os.getuid is POSIX-only, and the os.name guard above already rules
    # out Windows. mypy is told to target linux (see pyproject.toml) so
    # this needs no suppression - an ignore here would be correct under
    # a Windows-run mypy and an unused-ignore error under a Linux-run
    # one, which is a property of the checker's host, not of this code.
    if st.st_uid not in (os.getuid(), 0):
        return False, "not owned by the invoking user or root"
    return True, ""


def walk_dirs(anchor: Path, walk_to: Optional[Path]) -> List[Path]:
    """The ancestor directories the walk probes, innermost first. Stops
    at walk_to (if given), $HOME, or a filesystem boundary - never above
    them.

    The bounds are compared after resolving symlinks on both sides. A
    bound spelled through a link (a /tmp or $HOME that is a mount or a
    symlink) otherwise never equals the resolved anchor git reports, and
    the walk runs on to the filesystem root."""
    home = Path.home().resolve()
    bound = walk_to.resolve() if walk_to is not None else None
    dirs: List[Path] = []
    current = anchor.parent
    while current not in dirs:
        dirs.append(current)
        here = current.resolve()
        if bound is not None and here == bound:
            break
        if here == home or current.parent == current:
            break
        current = current.parent
    return dirs


def _walk_ancestors(anchor: Path, walk_to: Optional[Path]) -> List[Path]:
    """Existing .deny-terms / .deny-terms.private files in anchor's
    ancestors, outermost first."""
    found: List[Path] = []
    for directory in reversed(walk_dirs(anchor, walk_to)):
        for name in (PUBLIC_NAME, PRIVATE_NAME):
            candidate = directory / name
            if candidate.is_file():
                found.append(candidate)
    return found


def _env_paths(name: str) -> List[Path]:
    raw = os.environ.get(name)
    if not raw:
        return []
    return [Path(p) for p in raw.split(os.pathsep) if p.strip()]


def _is_tracked(path: Path, repo_root: Optional[Path]) -> bool:
    if repo_root is None:
        return False
    try:
        rel = path.resolve().relative_to(repo_root.resolve())
    except (OSError, ValueError):
        return False
    result = git("ls-files", "--error-unmatch", "--", rel.as_posix(), cwd=repo_root)
    return result.returncode == 0


def candidate_layers(
    anchor: Path,
    extra_terms: Optional[List[str]] = None,
    no_inherit: bool = False,
    no_walk: bool = False,
    walk_to: Optional[str] = None,
) -> List[_Layer]:
    """Every candidate path, lowest precedence first."""
    explicit = [_Layer(Path(p), "flag", False, True) for p in (extra_terms or [])]
    env = [_Layer(p, "env", False, True) for p in _env_paths("GIT_DENY_TERMS")]
    if no_inherit:
        return explicit or env
    layers = [
        _Layer(Path("/etc/git-hygiene/deny-terms"), "system", False, False),
        _Layer(term_file(), "user", False, False),
    ]
    if not no_walk:
        boundary = Path(walk_to) if walk_to else None
        layers += [_Layer(p, "walk", True, False) for p in _walk_ancestors(anchor, boundary)]
    # The root is probed for both names, like every directory the walk
    # visits, so a root-level private list is loaded and, if tracked,
    # caught.
    layers.append(_Layer(anchor / PUBLIC_NAME, "root", True, False))
    layers.append(_Layer(anchor / PRIVATE_NAME, "root", True, False))
    gd = git_dir(anchor)
    if gd is not None:
        layers.append(_Layer(gd / "info" / "deny-terms", "git-info", False, False))
    return layers + env + explicit


class _Active(NamedTuple):
    term: str  # spelling from the first contributor
    contributors: List[Tuple[Path, str]]  # (resolved path, class), in layer order


def resolve(
    anchor: Optional[Path] = None,
    extra_terms: Optional[List[str]] = None,
    no_inherit: bool = False,
    no_walk: bool = False,
    walk_to: Optional[str] = None,
    show_private_terms: bool = False,
) -> ResolutionResult:
    """Build the merged, provenance-carrying pattern set. `anchor` is
    normally the work tree root (git_toplevel()); resolution happens
    once per invocation and is reused for every file scanned.

    `show_private_terms` governs error text only. A refused negation
    always cancels a term a private source holds, so its message names
    the term only when the caller would also print that term in a hit
    (decision 0006).
    """
    if anchor is None:
        anchor = Path.cwd()
    repo_root = anchor if (anchor / ".git").exists() else None
    layers = candidate_layers(anchor, extra_terms, no_inherit, no_walk, walk_to)

    sources: List[Source] = []
    errors: List[str] = []
    fatal = False
    negations_honored = 0
    active: Dict[str, _Active] = {}

    for layer in layers:
        path, walked = layer.path, layer.walked
        klass = class_of(path, layer.kind)

        if not path.is_file():
            # Only a source the operator named can be missing in a way
            # worth failing on, and only when its name says it ships with
            # a repository (decision 0005).
            if layer.explicit and klass == "public":
                errors.append(f"missing public term source: {path}")
                fatal = True
                sources.append(Source(path, klass, False, "error:missing", 0, walked))
            else:
                sources.append(Source(path, klass, False, "absent", 0, walked))
            continue

        if layer.kind in ("walk", "root") or path.name == PUBLIC_NAME:
            trusted, reason = _trusted(path)
            if not trusted:
                sources.append(Source(path, klass, False, "skipped:" + reason, 0, walked))
                continue

        declared = _declared_class(path)
        if declared is not None and declared != klass:
            errors.append(
                f"{path}: declares itself {declared}, but its name or location makes it {klass}"
            )
            fatal = True
            sources.append(Source(path, klass, True, "error:class-conflict", 0, walked))
            continue

        if klass == "private" and _is_tracked(path, repo_root):
            errors.append(f"tracked private term file: {path}")
            fatal = True
            sources.append(Source(path, klass, declared is not None, "error:tracked", 0, walked))
            continue

        positives, negatives, parse_error = _parse_terms(path)
        if parse_error is not None:
            # Fatal, not a skip: a list that silently contributes nothing
            # is a reduction in protection nobody asked for (decision 0009).
            errors.append(f"{path}: {parse_error}")
            fatal = True
            status = "error:" + parse_error
            sources.append(Source(path, klass, declared is not None, status, 0, walked))
            continue

        own = resolved_path(path)
        contributed = 0
        for term in positives:
            key = term.lower()
            entry = active.get(key)
            if entry is None:
                active[key] = _Active(term, [(own, klass)])
                contributed += 1
            elif all(p != own for p, _k in entry.contributors):
                entry.contributors.append((own, klass))
                contributed += 1

        for term in negatives:
            key = term.lower()
            entry = active.get(key)
            if entry is None:
                continue  # nothing active to cancel; not an error
            strictest_path, strictest = max(entry.contributors, key=lambda c: _RANK[c[1]])
            if _RANK[klass] < _RANK[strictest]:
                named = f" of '{term}'" if show_private_terms else ""
                errors.append(
                    f"unauthorized negation{named}: {path} ({klass}) cannot cancel a term from "
                    f"{strictest_path} ({strictest})"
                )
                fatal = True
                continue
            del active[key]
            negations_honored += 1

        sources.append(Source(path, klass, declared is not None, "loaded", contributed, walked))

    patterns = []
    for entry in active.values():
        first_path, first_klass = entry.contributors[0]
        pattern = compile_term(entry.term, first_path, first_klass)
        patterns.append(pattern._replace(contributors=tuple(entry.contributors)))
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
        lines.append(f"{label:<46} {source.klass:<8} {source.status:<11} {source.terms:>5}")
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


__all__ = [
    "PRIVATE_NAME",
    "PUBLIC_NAME",
    "Hit",
    "ResolutionResult",
    "Source",
    "TermPattern",
    "candidate_layers",
    "class_of",
    "explain_lines",
    "resolve",
]
