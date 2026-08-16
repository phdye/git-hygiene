"""End-to-end tests against real temporary git repositories.

Kept 3.6.8-clean on purpose - see a/doc/instructions.md. No
`from __future__ import annotations` (needs 3.7+ to exist at all), no
runtime PEP 585/604 generics (subprocess.CompletedProcess[str] and
similar are given as type comments instead, never evaluated), and no
`capture_output=` (3.7+) - `stdout`/`stderr` piped explicitly with
`universal_newlines=True`, which has worked since Python 2.7.
"""

import subprocess
from pathlib import Path  # noqa: F401 - resolves the type comments below, not dead

import pytest

from git_hygiene import audit_tree, check_identifiers


def git(*args, cwd):
    # type: (str, Path) -> subprocess.CompletedProcess[str]
    # stdout/stderr spelled out rather than capture_output=/text=: both
    # are 3.7+ only, and the floor here is 3.6.8 to match RHEL 8.10 -
    # same reasoning as git_hygiene.terms.git().
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
    r.mkdir()
    git("init", "-q", cwd=r)
    git("config", "user.email", "test@example.invalid", cwd=r)
    git("config", "user.name", "Test", cwd=r)
    git("config", "commit.gpgsign", "false", cwd=r)
    return r


@pytest.fixture
def terms(tmp_path, monkeypatch):
    # type: (Path, pytest.MonkeyPatch) -> Path
    # v0.2.0's resolver always also checks the XDG/config layer,
    # independent of GIT_DENY_TERMS - isolate it so a real personal
    # term file on the machine running these tests cannot leak in.
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "no-xdg-here"))
    path = tmp_path / "deny-terms.txt"
    path.write_text("blockedname\n", encoding="utf-8")
    monkeypatch.setenv("GIT_DENY_TERMS", str(path))
    return path


def test_clean_staged_content_passes(repo, terms, monkeypatch):
    # type: (Path, Path, pytest.MonkeyPatch) -> None
    (repo / "ok.md").write_text("nothing to see\n", encoding="utf-8")
    git("add", "ok.md", cwd=repo)
    monkeypatch.chdir(str(repo))
    assert check_identifiers.main(["--staged"]) == 0


def test_dirty_staged_content_blocked(repo, terms, monkeypatch):
    # type: (Path, Path, pytest.MonkeyPatch) -> None
    (repo / "bad.md").write_text("has blockedname in it\n", encoding="utf-8")
    git("add", "bad.md", cwd=repo)
    monkeypatch.chdir(str(repo))
    assert check_identifiers.main(["--staged"]) == 1


def test_scans_staged_blob_not_working_tree(repo, terms, monkeypatch):
    # type: (Path, Path, pytest.MonkeyPatch) -> None
    """What gets committed is the staged blob. A file cleaned up after
    staging must still be caught."""
    f = repo / "x.md"
    f.write_text("has blockedname\n", encoding="utf-8")
    git("add", "x.md", cwd=repo)
    f.write_text("now clean\n", encoding="utf-8")  # working tree fixed, index is not
    monkeypatch.chdir(str(repo))
    assert check_identifiers.main(["--staged"]) == 1


def test_no_term_file_passes_silently(repo, monkeypatch, capsys):
    # type: (Path, pytest.MonkeyPatch, object) -> None
    monkeypatch.setenv("XDG_CONFIG_HOME", str(repo / "no-xdg-here"))
    monkeypatch.setenv("GIT_DENY_TERMS", str(repo / "absent.txt"))
    (repo / "bad.md").write_text("has blockedname\n", encoding="utf-8")
    git("add", "bad.md", cwd=repo)
    monkeypatch.chdir(str(repo))
    assert check_identifiers.main(["--staged"]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_commit_message_blocked(repo, terms, tmp_path, monkeypatch):
    # type: (Path, Path, Path, pytest.MonkeyPatch) -> None
    msg = tmp_path / "COMMIT_EDITMSG"
    msg.write_text("mentions blockedname in the subject\n", encoding="utf-8")
    monkeypatch.chdir(str(repo))
    assert check_identifiers.main(["--message", str(msg)]) == 1


def test_clean_commit_message_passes(repo, terms, tmp_path, monkeypatch):
    # type: (Path, Path, Path, pytest.MonkeyPatch) -> None
    msg = tmp_path / "COMMIT_EDITMSG"
    msg.write_text("an ordinary subject line\n", encoding="utf-8")
    monkeypatch.chdir(str(repo))
    assert check_identifiers.main(["--message", str(msg)]) == 0


def test_audit_finds_committed_content(repo, terms, monkeypatch):
    # type: (Path, Path, pytest.MonkeyPatch) -> None
    (repo / "bad.md").write_text("has blockedname\n", encoding="utf-8")
    git("add", "bad.md", cwd=repo)
    git("commit", "-q", "-m", "add a file", cwd=repo)
    monkeypatch.chdir(str(repo))
    assert audit_tree.main([str(repo)]) == 1


def test_audit_finds_it_in_a_commit_message(repo, terms, monkeypatch):
    # type: (Path, Path, pytest.MonkeyPatch) -> None
    (repo / "ok.md").write_text("clean content\n", encoding="utf-8")
    git("add", "ok.md", cwd=repo)
    git("commit", "-q", "-m", "mentions blockedname", cwd=repo)
    monkeypatch.chdir(str(repo))
    assert audit_tree.main([str(repo)]) == 1


def test_audit_passes_on_a_clean_repo(repo, terms, monkeypatch):
    # type: (Path, Path, pytest.MonkeyPatch) -> None
    (repo / "ok.md").write_text("clean content\n", encoding="utf-8")
    git("add", "ok.md", cwd=repo)
    git("commit", "-q", "-m", "an ordinary subject", cwd=repo)
    monkeypatch.chdir(str(repo))
    assert audit_tree.main([str(repo)]) == 0


def test_audit_object_scan_finds_orphaned_blob(repo, terms, monkeypatch):
    # type: (Path, Path, pytest.MonkeyPatch) -> None
    """The reason --objects exists, demonstrated: content removed from
    the working tree survives in the object store until history is
    rewritten, and a tracked-file scan cannot see it.

    Commit messages here deliberately do not mention the term, so the
    default scan has genuinely nothing to find - which is what makes
    the contrast meaningful rather than incidental.
    """
    (repo / "bad.md").write_text("has blockedname\n", encoding="utf-8")
    git("add", "bad.md", cwd=repo)
    git("commit", "-q", "-m", "add a file", cwd=repo)
    git("rm", "-q", "bad.md", cwd=repo)
    git("commit", "-q", "-m", "remove a file", cwd=repo)
    monkeypatch.chdir(str(repo))

    # Default scan: tracked files and messages are both clean. Passes,
    # and would give false assurance before publishing.
    assert audit_tree.main([str(repo)]) == 0

    # Object scan: the blob is still there. This is the one that matters.
    assert audit_tree.main([str(repo), "--objects"]) == 1
