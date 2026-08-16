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

import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.packaging

REPO_ROOT = Path(__file__).resolve().parent.parent


def has_pre_commit() -> bool:
    return shutil.which("pre-commit") is not None


@pytest.mark.skipif(not has_pre_commit(), reason="pre-commit not installed")
def test_hooks_file_is_valid() -> None:
    r = subprocess.run(
        ["pre-commit", "validate-manifest", str(REPO_ROOT / ".pre-commit-hooks.yaml")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.skipif(not has_pre_commit(), reason="pre-commit not installed")
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
