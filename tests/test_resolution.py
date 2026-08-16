"""Layered, classified term resolution - the core of v0.2.0.

See a/doc/deny-term-resolution.md for the design this proves. Kept
3.6.8-clean like the rest of tests/ - see a/doc/instructions.md.
"""

import os
import subprocess
from pathlib import Path  # noqa: F401 - resolves the type comments below, not dead

import pytest

from git_hygiene import resolution


def git(*args, cwd):
    # type: (str, Path) -> subprocess.CompletedProcess[str]
    return subprocess.run(  # noqa: UP022
        ["git"] + list(args),
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,  # noqa: UP021 - text= is also 3.7+ only
        check=False,
    )


@pytest.fixture
def repo(tmp_path, monkeypatch):
    # type: (Path, pytest.MonkeyPatch) -> Path
    # Isolate every fixed layer this module checks outside the test's
    # own control, so only what a test explicitly sets up contributes.
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "no-xdg-here"))
    monkeypatch.delenv("GIT_DENY_TERMS", raising=False)
    r = tmp_path / "repo"
    r.mkdir()
    git("init", "-q", cwd=r)
    git("config", "user.email", "test@example.invalid", cwd=r)
    git("config", "user.name", "Test", cwd=r)
    git("config", "commit.gpgsign", "false", cwd=r)
    return r


def names(result):
    # type: (resolution.ResolutionResult) -> set
    return {p.term for p in result.patterns}


def test_undeclared_file_defaults_private(repo):
    # type: (Path) -> None
    f = repo / "list.txt"
    f.write_text("someterm\n", encoding="utf-8")
    result = resolution.resolve(anchor=repo, extra_terms=[str(f)], no_walk=True)
    assert names(result) == {"someterm"}
    assert result.patterns[0].klass == "private"


def test_declared_public_directive_is_honored(repo):
    # type: (Path) -> None
    f = repo / ".deny-terms"
    f.write_text("# git-hygiene: public\nteamword\n", encoding="utf-8")
    result = resolution.resolve(anchor=repo, no_walk=True)
    assert names(result) == {"teamword"}
    assert result.patterns[0].klass == "public"
    assert not result.fatal


def test_union_across_two_layers(repo):
    # type: (Path) -> None
    a = repo / "a.txt"
    a.write_text("alpha\n", encoding="utf-8")
    b = repo / "b.txt"
    b.write_text("beta\n", encoding="utf-8")
    result = resolution.resolve(anchor=repo, extra_terms=[str(a), str(b)], no_walk=True)
    assert names(result) == {"alpha", "beta"}


def test_no_term_anywhere_resolves_empty(repo):
    # type: (Path) -> None
    result = resolution.resolve(anchor=repo, no_walk=True)
    assert result.patterns == []
    assert not result.fatal
    assert result.errors == []


def test_missing_explicit_dot_deny_terms_is_fatal(repo):
    # type: (Path) -> None
    """.deny-terms is expected-public by filename convention even
    before anything can be read from it. That only matters for a
    source the operator explicitly named - an auto-probed candidate
    like the repo-root .deny-terms is optional by nature and its
    absence alone must not be an error (see the next test)."""
    missing = repo / "somewhere" / ".deny-terms"
    result = resolution.resolve(anchor=repo, extra_terms=[str(missing)], no_walk=True)
    assert result.fatal
    assert any("missing declared-public" in e for e in result.errors)


def test_auto_probed_repo_root_dot_deny_terms_absence_is_not_fatal(repo):
    # type: (Path) -> None
    # No repo/.deny-terms was created - this is the ordinary state of
    # nearly every repository and must not fail loudly on its own.
    result = resolution.resolve(anchor=repo, no_walk=True)
    assert not result.fatal
    assert result.errors == []


def test_missing_private_by_convention_is_silent(repo):
    # type: (Path) -> None
    missing = repo / "nope.txt"
    result = resolution.resolve(anchor=repo, extra_terms=[str(missing)], no_walk=True)
    assert not result.fatal
    assert result.errors == []
    assert result.patterns == []


def test_term_and_negation_conflict_in_same_file_is_an_error(repo):
    # type: (Path) -> None
    f = repo / "conflict.txt"
    f.write_text("alpha\n!alpha\n", encoding="utf-8")
    result = resolution.resolve(anchor=repo, extra_terms=[str(f)], no_walk=True)
    assert names(result) == set()
    assert any("conflicting term/negation" in e for e in result.errors)


def test_negation_from_a_stricter_layer_is_honored(repo):
    # type: (Path) -> None
    introducing = repo / "introducing.txt"
    introducing.write_text("# git-hygiene: public\nalpha\n", encoding="utf-8")
    negating = repo / "negating.txt"
    negating.write_text("# git-hygiene: private\n!alpha\n", encoding="utf-8")
    result = resolution.resolve(
        anchor=repo, extra_terms=[str(introducing), str(negating)], no_walk=True
    )
    assert names(result) == set()
    assert result.negations_honored == 1
    assert result.errors == []


def test_public_source_cannot_negate_a_private_term(repo):
    # type: (Path) -> None
    introducing = repo / "introducing.txt"
    introducing.write_text("# git-hygiene: private\nalpha\n", encoding="utf-8")
    negating = repo / "negating.txt"
    negating.write_text("# git-hygiene: public\n!alpha\n", encoding="utf-8")
    result = resolution.resolve(
        anchor=repo, extra_terms=[str(introducing), str(negating)], no_walk=True
    )
    # The term survives - the negation was refused, not silently dropped.
    assert names(result) == {"alpha"}
    assert result.negations_honored == 0
    assert any("unauthorized negation" in e for e in result.errors)


def test_negation_of_nothing_active_is_a_harmless_no_op(repo):
    # type: (Path) -> None
    f = repo / "only-negation.txt"
    f.write_text("!nothing-introduced-this\n", encoding="utf-8")
    result = resolution.resolve(anchor=repo, extra_terms=[str(f)], no_walk=True)
    assert result.errors == []
    assert result.negations_honored == 0


def test_tracked_private_term_file_is_fatal(repo):
    # type: (Path) -> None
    f = repo / "secret.txt"
    f.write_text("alpha\n", encoding="utf-8")
    git("add", "secret.txt", cwd=repo)
    git("commit", "-q", "-m", "oops, tracked it", cwd=repo)
    result = resolution.resolve(anchor=repo, extra_terms=[str(f)], no_walk=True)
    assert result.fatal
    assert any("tracked private term file" in e for e in result.errors)
    assert names(result) == set()  # scanning must not proceed on this term


def test_tracked_public_term_file_is_fine(repo):
    # type: (Path) -> None
    f = repo / ".deny-terms"
    f.write_text("# git-hygiene: public\nteamword\n", encoding="utf-8")
    git("add", ".deny-terms", cwd=repo)
    git("commit", "-q", "-m", "commit the team list", cwd=repo)
    result = resolution.resolve(anchor=repo, no_walk=True)
    assert not result.fatal
    assert names(result) == {"teamword"}


def test_no_inherit_uses_only_explicit_terms(repo):
    # type: (Path, ) -> None
    # A stray fixed-layer file would normally be silently skipped
    # (absent) or contribute nothing relevant here; --no-inherit's
    # real job is ignoring layers 1-5 even when they *would* resolve.
    system_like = repo / ".deny-terms"
    system_like.write_text("# git-hygiene: public\nshouldnotappear\n", encoding="utf-8")
    explicit = repo / "explicit.txt"
    explicit.write_text("shouldappear\n", encoding="utf-8")
    result = resolution.resolve(anchor=repo, extra_terms=[str(explicit)], no_inherit=True)
    assert names(result) == {"shouldappear"}


def test_no_inherit_falls_back_to_env_when_no_explicit_terms(repo, monkeypatch):
    # type: (Path, pytest.MonkeyPatch) -> None
    envfile = repo / "envfile.txt"
    envfile.write_text("fromenv\n", encoding="utf-8")
    monkeypatch.setenv("GIT_DENY_TERMS", str(envfile))
    result = resolution.resolve(anchor=repo, no_inherit=True)
    assert names(result) == {"fromenv"}


def test_walk_finds_an_ancestor_file_bounded_by_walk_to(tmp_path, monkeypatch):
    # type: (Path, pytest.MonkeyPatch) -> None
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "no-xdg-here"))
    monkeypatch.delenv("GIT_DENY_TERMS", raising=False)
    outer = tmp_path / "outer"
    inner = outer / "inner"
    inner.mkdir(parents=True)
    (outer / ".deny-terms.private").write_text("fromwalk\n", encoding="utf-8")
    git("init", "-q", cwd=inner)
    git("config", "user.email", "test@example.invalid", cwd=inner)
    git("config", "user.name", "Test", cwd=inner)
    result = resolution.resolve(anchor=inner, walk_to=str(tmp_path))
    assert "fromwalk" in names(result)
    walked_sources = [s for s in result.sources if s.walked and s.status == "loaded"]
    assert any(s.path == outer / ".deny-terms.private" for s in walked_sources)


def test_explain_lines_include_a_summary_with_counts(repo):
    # type: (Path) -> None
    f = repo / "a.txt"
    f.write_text("alpha\n", encoding="utf-8")
    result = resolution.resolve(anchor=repo, extra_terms=[str(f)], no_walk=True)
    lines = resolution.explain_lines(result)
    assert lines[0].startswith("source")
    assert "1 terms from 1 sources" in lines[-1]


@pytest.mark.skipif(os.name != "posix", reason="ownership/mode checks are POSIX-only")
def test_world_writable_walked_file_is_skipped_not_trusted(tmp_path, monkeypatch):
    # type: (Path, pytest.MonkeyPatch) -> None
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "no-xdg-here"))
    monkeypatch.delenv("GIT_DENY_TERMS", raising=False)
    outer = tmp_path / "outer"
    inner = outer / "inner"
    inner.mkdir(parents=True)
    target = outer / ".deny-terms.private"
    target.write_text("fromwalk\n", encoding="utf-8")
    target.chmod(0o666)  # world writable
    git("init", "-q", cwd=inner)

    result = resolution.resolve(anchor=inner, walk_to=str(tmp_path))
    assert "fromwalk" not in names(result)
    skipped = [s for s in result.sources if s.status.startswith("skipped")]
    assert any(s.path == target for s in skipped)
