"""The fallback without the framework: install-hooks writes plain
`.git/hooks/` shims that need no `pre-commit`, for a host that cannot
have it.

Kept 3.6.8-clean like the rest of tests/.
No `from __future__ import annotations`, no runtime
`subprocess.CompletedProcess[str]` subscript (a type comment instead),
no `capture_output=` (3.7+).
"""

import os
import subprocess

import pytest

from git_hygiene import install_hooks

from .helpers import Sandbox


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


def test_writes_both_hooks_executable(repo):
    # type: (Path) -> None
    # The exec bit itself is only meaningful where the filesystem
    # tracks POSIX permissions - NTFS via native Windows Python does
    # not, even though os.chmod() there raises nothing. Content and
    # marker are what every platform can actually verify.
    assert install_hooks.main([str(repo)]) == 0
    for name in ("pre-commit", "commit-msg"):
        target = repo / ".git" / "hooks" / name
        assert target.is_file()
        if os.name == "posix":
            assert target.stat().st_mode & 0o111, name + " is not executable"
        assert install_hooks.MARKER in target.read_text(encoding="utf-8")


def test_idempotent_reinstall(repo):
    # type: (Path) -> None
    assert install_hooks.main([str(repo)]) == 0
    hooks = repo / ".git" / "hooks"
    first = {n: (hooks / n).read_bytes() for n in ("pre-commit", "commit-msg")}
    assert install_hooks.main([str(repo)]) == 0
    second = {n: (hooks / n).read_bytes() for n in first}
    assert first == second
    assert b"exec check-identifiers --staged\n" in first["pre-commit"]
    assert b'exec check-identifiers --message "$1"\n' in first["commit-msg"]
    assert b"git-hygiene run" not in first["pre-commit"] + first["commit-msg"]


def test_a_marked_hook_it_no_longer_installs_is_removed(repo, capsys):
    # type: (Path, pytest.CaptureFixture[str]) -> None
    """An unreleased dispatcher wrote marked shims for other hooks, and
    for pre-commit and commit-msg a different body. Reinstalling brings
    both back to this installer's set."""
    hooks = repo / ".git" / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    old = "#!/usr/bin/env bash\n{}\nexec git-hygiene run {{}} \"$@\"\n".format(install_hooks.MARKER)
    for name in ("pre-commit", "pre-push"):
        (hooks / name).write_bytes(old.format(name).encode("utf-8"))
    assert install_hooks.main([str(repo)]) == 0
    assert "removed pre-push  (no longer installed)" in capsys.readouterr().out
    assert not (hooks / "pre-push").exists()
    assert b"exec check-identifiers --staged" in (hooks / "pre-commit").read_bytes()


def test_dry_run_writes_nothing(repo):
    # type: (Path) -> None
    assert install_hooks.main([str(repo), "--dry-run"]) == 0
    assert not (repo / ".git" / "hooks" / "pre-commit").exists()
    assert not (repo / ".git" / "hooks" / "commit-msg").exists()


def test_foreign_hook_is_not_clobbered(repo):
    # type: (Path) -> None
    hooks_dir = repo / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    foreign = hooks_dir / "pre-commit"
    foreign.write_text("#!/usr/bin/env bash\necho someone else's hook\n", encoding="utf-8")

    assert install_hooks.main([str(repo)]) == 1  # reports the conflict, does not fail loudly
    assert "someone else's hook" in foreign.read_text(encoding="utf-8")

    assert install_hooks.main([str(repo), "--force"]) == 0
    assert install_hooks.MARKER in foreign.read_text(encoding="utf-8")


def test_uninstall_removes_only_managed_hooks(repo):
    # type: (Path) -> None
    hooks_dir = repo / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    foreign = hooks_dir / "commit-msg"
    foreign.write_text("#!/usr/bin/env bash\necho foreign\n", encoding="utf-8")

    assert install_hooks.main([str(repo), "--force"]) == 0  # installs both, overwriting commit-msg
    assert install_hooks.main([str(repo), "--uninstall"]) == 0
    assert not (hooks_dir / "pre-commit").exists()
    assert not (hooks_dir / "commit-msg").exists()


def test_uninstall_leaves_foreign_hook_alone(repo):
    # type: (Path) -> None
    hooks_dir = repo / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    foreign = hooks_dir / "pre-commit"
    foreign.write_text("#!/usr/bin/env bash\necho foreign\n", encoding="utf-8")

    assert install_hooks.main([str(repo), "--uninstall"]) == 0
    assert foreign.is_file()
    assert "foreign" in foreign.read_text(encoding="utf-8")


def test_non_repository_reports_error(tmp_path):
    # type: (Path) -> None
    not_a_repo = tmp_path / "not-a-repo"
    not_a_repo.mkdir()
    assert install_hooks.main([str(not_a_repo)]) == 1


def test_installed_hook_actually_blocks_a_commit(tmp_path):
    # type: (Path) -> None
    """The real proof: git itself, not this package, invoking the hook
    it was pointed at, which runs the scanner. Git for Windows runs a shebang-line hook through its own
    bundled sh regardless of the NTFS exec bit; Cygwin and other POSIX
    gits honor the exec bit directly - either way this is the same shim
    file exercised the same way a real commit would."""
    sb = Sandbox(tmp_path)
    sb.private_terms("blockedname\n")
    sb.install()
    sb.stage("bad.md", "has blockedname\n")
    r = sb.commit("add a file")
    assert r.returncode != 0
    assert sb.head_count() == 0
    # A hook that REFUSES and a hook that CRASHES both give a non-zero rc
    # and an empty log, so the two assertions above cannot tell them
    # apart - a completely broken hook satisfies them. Assert on what the
    # hook actually said.
    assert "BLOCKED" in r.stderr, r.stderr
    assert "syntax error" not in r.stderr, r.stderr
    assert "blockedname" not in r.stderr


def test_installed_hooks_have_no_carriage_returns(repo):
    # type: (Path) -> None
    """Path.write_text opens in text mode, so on Windows it turns every
    \\n into \\r\\n. Cygwin bash then reads `fi\\r` as a command name and
    every commit dies with "syntax error: unexpected end of file", clean
    or dirty. Git for Windows' bash tolerates CRLF, so this is invisible
    to a Windows-only check - assert on the bytes, which is true
    everywhere and points straight at the cause."""
    assert install_hooks.main([str(repo)]) == 0
    for name in ("pre-commit", "commit-msg"):
        raw = (repo / ".git" / "hooks" / name).read_bytes()
        assert b"\r\n" not in raw, name + " was written with CRLF line endings"
