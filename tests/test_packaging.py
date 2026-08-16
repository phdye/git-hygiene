"""Does pre-commit actually install and run these hooks?

Unit tests prove the logic. Only this proves the packaging - that
.pre-commit-hooks.yaml is valid, that the console scripts declared in
pyproject.toml exist under the name the hooks invoke, and that
pre-commit can build an environment from this repository.

An earlier iteration of this facility used `language: system` with a
relative script path. It passed every unit test and could not run as
an installed hook. That is exactly the gap this closes.

Marked `packaging` and deselected by default: it builds a virtualenv,
so it is slow. Run it in CI and before tagging a release.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.packaging

REPO_ROOT = Path(__file__).resolve().parent.parent

# The pre-commit framework calls `git ls-files -z --deduplicate`, and
# --deduplicate arrived in git 2.31.0 (2021-03-15). Below that the
# framework cannot start at all, so these tests skip: there is nothing
# to exercise, not a failure to tolerate.
#
# This is NOT a statement that old git is out of scope. This project's
# git floor is 2.21, matching RHEL 8.10, and that floor is covered by
# the native git-hook front end, which calls the console scripts
# directly and needs no framework. These tests cover the framework
# path only, which is inherently a >= 2.31 concern.
#
# See a/doc/rejected-pre-commit-git-2.21-backport.md for why the missing
# flag is not emulated even though it could be. That decision is closed.
MIN_GIT = (2, 31)


def git_version() -> tuple[int, ...]:
    try:
        out = subprocess.run(
            ["git", "--version"], capture_output=True, text=True, check=False
        ).stdout
    except OSError:
        return (0,)
    m = re.search(r"(\d+)\.(\d+)", out)
    return (int(m.group(1)), int(m.group(2))) if m else (0,)


_found = ".".join(map(str, git_version()))
needs_tooling = pytest.mark.skipif(
    shutil.which("pre-commit") is None or git_version() < MIN_GIT,
    reason=f"needs pre-commit and git >= {MIN_GIT[0]}.{MIN_GIT[1]} (found git {_found})",
)


@needs_tooling
def test_hooks_file_is_valid() -> None:
    r = subprocess.run(
        ["pre-commit", "validate-manifest", str(REPO_ROOT / ".pre-commit-hooks.yaml")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, r.stdout + r.stderr


@needs_tooling
def test_try_repo_installs_and_runs_the_content_hook(tmp_path: Path) -> None:
    """try-repo is the real test: it builds the hook environment from
    this repository exactly as a consumer would."""
    target = tmp_path / "consumer"
    target.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=target, check=True)
    (target / "file.md").write_text("ordinary content\n", encoding="utf-8")
    subprocess.run(["git", "add", "file.md"], cwd=target, check=True)

    r = subprocess.run(
        ["pre-commit", "try-repo", str(REPO_ROOT), "deny-terms", "--all-files"],
        cwd=target,
        capture_output=True,
        text=True,
        check=False,
    )
    # No term file in this environment, so the hook must pass - but it
    # must have actually run, not failed to install.
    combined = r.stdout + r.stderr
    assert "Passed" in combined or r.returncode == 0, combined
    assert "not found" not in combined.lower(), combined
