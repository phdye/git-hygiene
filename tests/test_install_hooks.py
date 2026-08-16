"""The native hook front end: install-hooks writes plain
`.git/hooks/` shims that need no `pre-commit` framework, and that is
the path this project's own git 2.21 floor depends on.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from git_hygiene import install_hooks


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


def test_writes_both_hooks_executable(repo: Path) -> None:
    # The exec bit itself is only meaningful where the filesystem
    # tracks POSIX permissions - NTFS via native Windows Python does
    # not, even though os.chmod() there raises nothing. Content and
    # marker are what every platform can actually verify.
    assert install_hooks.main([str(repo)]) == 0
    for name in ("pre-commit", "commit-msg"):
        target = repo / ".git" / "hooks" / name
        assert target.is_file()
        if os.name == "posix":
            assert target.stat().st_mode & 0o111, f"{name} is not executable"
        assert install_hooks.MARKER in target.read_text(encoding="utf-8")


def test_idempotent_reinstall(repo: Path) -> None:
    assert install_hooks.main([str(repo)]) == 0
    first = (repo / ".git" / "hooks" / "pre-commit").read_text(encoding="utf-8")
    assert install_hooks.main([str(repo)]) == 0
    second = (repo / ".git" / "hooks" / "pre-commit").read_text(encoding="utf-8")
    assert first == second


def test_dry_run_writes_nothing(repo: Path) -> None:
    assert install_hooks.main([str(repo), "--dry-run"]) == 0
    assert not (repo / ".git" / "hooks" / "pre-commit").exists()
    assert not (repo / ".git" / "hooks" / "commit-msg").exists()


def test_foreign_hook_is_not_clobbered(repo: Path) -> None:
    hooks_dir = repo / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    foreign = hooks_dir / "pre-commit"
    foreign.write_text("#!/usr/bin/env bash\necho someone else's hook\n", encoding="utf-8")

    assert install_hooks.main([str(repo)]) == 1  # reports the conflict, does not fail loudly
    assert "someone else's hook" in foreign.read_text(encoding="utf-8")

    assert install_hooks.main([str(repo), "--force"]) == 0
    assert install_hooks.MARKER in foreign.read_text(encoding="utf-8")


def test_uninstall_removes_only_managed_hooks(repo: Path) -> None:
    hooks_dir = repo / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    foreign = hooks_dir / "commit-msg"
    foreign.write_text("#!/usr/bin/env bash\necho foreign\n", encoding="utf-8")

    assert install_hooks.main([str(repo), "--force"]) == 0  # installs both, overwriting commit-msg
    assert install_hooks.main([str(repo), "--uninstall"]) == 0
    assert not (hooks_dir / "pre-commit").exists()
    assert not (hooks_dir / "commit-msg").exists()


def test_uninstall_leaves_foreign_hook_alone(repo: Path) -> None:
    hooks_dir = repo / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    foreign = hooks_dir / "pre-commit"
    foreign.write_text("#!/usr/bin/env bash\necho foreign\n", encoding="utf-8")

    assert install_hooks.main([str(repo), "--uninstall"]) == 0
    assert foreign.is_file()
    assert "foreign" in foreign.read_text(encoding="utf-8")


def test_non_repository_reports_error(tmp_path: Path) -> None:
    not_a_repo = tmp_path / "not-a-repo"
    not_a_repo.mkdir()
    assert install_hooks.main([str(not_a_repo)]) == 1


def test_installed_hook_actually_blocks_a_commit(repo: Path, terms: Path) -> None:
    """The real proof: git itself, not this package, invoking the hook
    it was pointed at. Git for Windows runs a shebang-line hook through
    its own bundled sh regardless of the NTFS exec bit; Cygwin and
    other POSIX gits honor the exec bit directly - either way this is
    the same shim file exercised the same way a real commit would.
    check-identifiers must be reachable on PATH for the shim to find
    it - the running interpreter's own bin/Scripts directory is added
    defensively in case the test runner was not launched with it
    already active."""
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join([str(Path(sys.executable).parent), env.get("PATH", "")])

    assert install_hooks.main([str(repo)]) == 0

    (repo / "bad.md").write_text("has blockedname\n", encoding="utf-8")
    git("add", "bad.md", cwd=repo)
    r = subprocess.run(
        ["git", "commit", "-q", "-m", "add a file"],
        cwd=repo,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert r.returncode != 0
    assert git("log", "--oneline", cwd=repo).stdout.strip() == ""
