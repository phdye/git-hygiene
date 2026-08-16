"""End-to-end tests against real temporary git repositories."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from git_hygiene import audit_tree, check_identifiers


def git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    git("init", "-q", cwd=r)
    git("config", "user.email", "test@example.invalid", cwd=r)
    git("config", "user.name", "Test", cwd=r)
    git("config", "commit.gpgsign", "false", cwd=r)
    return r


@pytest.fixture
def terms(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "deny-terms.txt"
    path.write_text("blockedname\n", encoding="utf-8")
    monkeypatch.setenv("GIT_DENY_TERMS", str(path))
    return path


def test_clean_staged_content_passes(repo: Path, terms: Path, monkeypatch) -> None:
    (repo / "ok.md").write_text("nothing to see\n", encoding="utf-8")
    git("add", "ok.md", cwd=repo)
    monkeypatch.chdir(repo)
    assert check_identifiers.main(["--staged"]) == 0


def test_dirty_staged_content_blocked(repo: Path, terms: Path, monkeypatch) -> None:
    (repo / "bad.md").write_text("has blockedname in it\n", encoding="utf-8")
    git("add", "bad.md", cwd=repo)
    monkeypatch.chdir(repo)
    assert check_identifiers.main(["--staged"]) == 1


def test_scans_staged_blob_not_working_tree(repo: Path, terms: Path, monkeypatch) -> None:
    """What gets committed is the staged blob. A file cleaned up after
    staging must still be caught."""
    f = repo / "x.md"
    f.write_text("has blockedname\n", encoding="utf-8")
    git("add", "x.md", cwd=repo)
    f.write_text("now clean\n", encoding="utf-8")  # working tree fixed, index is not
    monkeypatch.chdir(repo)
    assert check_identifiers.main(["--staged"]) == 1


def test_no_term_file_passes_silently(repo: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("GIT_DENY_TERMS", str(repo / "absent.txt"))
    (repo / "bad.md").write_text("has blockedname\n", encoding="utf-8")
    git("add", "bad.md", cwd=repo)
    monkeypatch.chdir(repo)
    assert check_identifiers.main(["--staged"]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_commit_message_blocked(repo: Path, terms: Path, tmp_path: Path, monkeypatch) -> None:
    msg = tmp_path / "COMMIT_EDITMSG"
    msg.write_text("mentions blockedname in the subject\n", encoding="utf-8")
    monkeypatch.chdir(repo)
    assert check_identifiers.main(["--message", str(msg)]) == 1


def test_clean_commit_message_passes(repo: Path, terms: Path, tmp_path: Path, monkeypatch) -> None:
    msg = tmp_path / "COMMIT_EDITMSG"
    msg.write_text("an ordinary subject line\n", encoding="utf-8")
    monkeypatch.chdir(repo)
    assert check_identifiers.main(["--message", str(msg)]) == 0


def test_audit_finds_committed_content(repo: Path, terms: Path, monkeypatch) -> None:
    (repo / "bad.md").write_text("has blockedname\n", encoding="utf-8")
    git("add", "bad.md", cwd=repo)
    git("commit", "-q", "-m", "add a file", cwd=repo)
    monkeypatch.chdir(repo)
    assert audit_tree.main([str(repo)]) == 1


def test_audit_finds_it_in_a_commit_message(repo: Path, terms: Path, monkeypatch) -> None:
    (repo / "ok.md").write_text("clean content\n", encoding="utf-8")
    git("add", "ok.md", cwd=repo)
    git("commit", "-q", "-m", "mentions blockedname", cwd=repo)
    monkeypatch.chdir(repo)
    assert audit_tree.main([str(repo)]) == 1


def test_audit_passes_on_a_clean_repo(repo: Path, terms: Path, monkeypatch) -> None:
    (repo / "ok.md").write_text("clean content\n", encoding="utf-8")
    git("add", "ok.md", cwd=repo)
    git("commit", "-q", "-m", "an ordinary subject", cwd=repo)
    monkeypatch.chdir(repo)
    assert audit_tree.main([str(repo)]) == 0


def test_audit_object_scan_finds_orphaned_blob(repo: Path, terms: Path, monkeypatch) -> None:
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
    monkeypatch.chdir(repo)

    # Default scan: tracked files and messages are both clean. Passes,
    # and would give false assurance before publishing.
    assert audit_tree.main([str(repo)]) == 0

    # Object scan: the blob is still there. This is the one that matters.
    assert audit_tree.main([str(repo), "--objects"]) == 1
