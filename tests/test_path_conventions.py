"""Path conventions across the git/interpreter boundary.

git reports paths in *its* convention; the running interpreter needs
them in *its own*. Under Cygwin git plus a native Windows interpreter
those differ, and the consequences are covered here. See
a/issue/git-toplevel-posix-path-breaks-windows-python.md.

These tests pass trivially where the two conventions coincide (Linux
CI, an all-Cygwin install, an all-Windows install). They are written so
that they fail loudly in the cell where they do not - which is exactly
the cell that shipped broken twice.

Kept 3.6.8-clean like the rest of tests/ - see a/doc/floor-checks.md.
"""

import os
import subprocess
from pathlib import Path  # noqa: F401 - resolves the type comments below

import pytest

from git_hygiene.terms import git_dir, git_toplevel


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
def repo(tmp_path):
    # type: (Path) -> Path
    r = tmp_path / "repo"
    (r / "sub" / "deeper").mkdir(parents=True)
    git("init", "-q", cwd=r)
    git("config", "user.email", "test@example.invalid", cwd=r)
    git("config", "user.name", "Test", cwd=r)
    return r


def test_toplevel_from_the_root(repo, monkeypatch):
    # type: (Path, pytest.MonkeyPatch) -> None
    monkeypatch.chdir(str(repo))
    top = git_toplevel()
    assert top is not None
    assert top.resolve() == repo.resolve()


def test_toplevel_from_a_subdirectory(repo, monkeypatch):
    # type: (Path, pytest.MonkeyPatch) -> None
    """--show-cdup returns '../../' here; the point is that the result
    is still the repo root and still usable."""
    monkeypatch.chdir(str(repo / "sub" / "deeper"))
    top = git_toplevel()
    assert top is not None
    assert top.resolve() == repo.resolve()


def test_toplevel_is_usable_by_this_interpreter(repo, monkeypatch):
    # type: (Path, pytest.MonkeyPatch) -> None
    """The crash half of the bug: the anchor is handed straight back to
    subprocess as cwd. A POSIX path from a Cygwin git raises
    NotADirectoryError [WinError 267] under a native Windows
    interpreter."""
    monkeypatch.chdir(str(repo / "sub"))
    top = git_toplevel()
    assert top is not None
    assert top.is_dir(), "git_toplevel returned something this interpreter cannot stat"
    r = git("rev-parse", "--is-inside-work-tree", cwd=top)
    assert r.returncode == 0, "git_toplevel is not usable as a subprocess cwd"


def test_toplevel_anchor_can_find_a_repo_root_file(repo, monkeypatch):
    # type: (Path, pytest.MonkeyPatch) -> None
    """The SILENT half, and the one that matters more. A path in the
    wrong convention does not raise on Windows - it simply does not
    exist, so every term-file probe answers False, no terms resolve,
    and the check passes having scanned against nothing. Fail-open is
    the exact outcome this project exists to prevent, so assert the
    anchor can actually see a file at the repo root."""
    marker = repo / ".deny-terms"
    marker.write_text("# git-hygiene: public\nmarkerterm\n", encoding="utf-8")
    monkeypatch.chdir(str(repo / "sub" / "deeper"))
    top = git_toplevel()
    assert top is not None
    assert (top / ".deny-terms").is_file(), (
        "anchor cannot see a file at the repo root - layer probes would silently find nothing"
    )


def test_outside_a_repository_returns_none(tmp_path, monkeypatch):
    # type: (Path, pytest.MonkeyPatch) -> None
    outside = tmp_path / "not-a-repo"
    outside.mkdir()
    monkeypatch.chdir(str(outside))
    assert git_toplevel() is None


def test_git_dir_is_usable_by_this_interpreter(repo):
    # type: (Path) -> None
    gd = git_dir(repo)
    assert gd is not None
    assert gd.is_dir(), "git_dir returned something this interpreter cannot stat"
    assert (gd / "HEAD").is_file()


def test_git_dir_outside_a_repository_returns_none(tmp_path):
    # type: (Path) -> None
    outside = tmp_path / "not-a-repo-either"
    outside.mkdir()
    assert git_dir(outside) is None


@pytest.mark.skipif(os.name != "posix", reason="needs a POSIX-rooted filesystem")
def test_absolute_git_dir_that_does_not_resolve_falls_back(repo):
    # type: (Path) -> None
    """git_dir tolerates git answering with an absolute path this
    interpreter cannot resolve, rather than handing it on."""
    gd = git_dir(repo)
    assert gd is not None
    assert gd.resolve() == (repo / ".git").resolve()
