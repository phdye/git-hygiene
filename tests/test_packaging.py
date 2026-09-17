"""Does pre-commit actually install and run these hooks?

Unit tests prove the logic. Only this proves the packaging - that
.pre-commit-hooks.yaml is valid, that the console scripts declared in
setup.cfg exist under the name the hooks invoke, and that
pre-commit can build an environment from this repository.

An earlier iteration of this facility used `language: system` with a
relative script path. It passed every unit test and could not run as
an installed hook. That is exactly the gap this closes.

Marked `packaging` and deselected by default: it builds a virtualenv,
so it is slow. Run it before tagging a release.

Kept 3.6.8-clean like the rest of tests/, and run at the floor with
pre-commit 2.17.0 on PATH, which is where the framework path matters
most. No `from __future__ import annotations`, no runtime subscripts,
no `capture_output=` (3.7+). The tests skip, naming why, when pre-commit
is missing or git is older than the framework needs.
"""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.packaging

REPO_ROOT = Path(__file__).resolve().parent.parent

# pre-commit 4.6.1 and later call `git ls-files -z --deduplicate`, which
# arrived in git 2.31.0; 2.17.0 does not. The tests keep 2.31 as their
# floor, which every supported host clears (RHEL 8.10 ships 2.43).
MIN_GIT = (2, 31)


def git_version():
    # type: () -> tuple
    try:
        # stdout/stderr spelled out rather than capture_output=/text=:
        # both are 3.7+ only, and the floor here is 3.6.8.
        out = subprocess.run(  # noqa: UP022
            ["git", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,  # noqa: UP021 - text= is also 3.7+ only
            check=False,
        ).stdout
    except OSError:
        return (0,)
    m = re.search(r"(\d+)\.(\d+)", out)
    return (int(m.group(1)), int(m.group(2))) if m else (0,)


_found = ".".join(str(part) for part in git_version())
needs_tooling = pytest.mark.skipif(
    shutil.which("pre-commit") is None or git_version() < MIN_GIT,
    reason=f"needs pre-commit and git >= {MIN_GIT[0]}.{MIN_GIT[1]} (found git {_found})",
)


def validate_manifest_command():
    # type: () -> list
    # pre-commit 2.17.0, the newest that installs at the 3.6 floor, has only
    # the standalone script; the subcommand arrived in 2.19.0 and the script
    # was removed in 3.0.0.
    if shutil.which("pre-commit-validate-manifest"):
        return ["pre-commit-validate-manifest"]
    return ["pre-commit", "validate-manifest"]


@needs_tooling
def test_hooks_file_is_valid():
    # type: () -> None
    r = subprocess.run(  # noqa: UP022
        validate_manifest_command() + [str(REPO_ROOT / ".pre-commit-hooks.yaml")],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,  # noqa: UP021 - text= is also 3.7+ only
        check=False,
    )
    assert r.returncode == 0, r.stdout + r.stderr


@needs_tooling
def test_try_repo_installs_and_runs_the_content_hook(tmp_path):
    # type: (Path) -> None
    """try-repo is the real test: it builds the hook environment from
    this repository exactly as a consumer would."""
    target = tmp_path / "consumer"
    target.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=str(target), check=True)
    (target / "file.md").write_text("ordinary content\n", encoding="utf-8")
    subprocess.run(["git", "add", "file.md"], cwd=str(target), check=True)

    r = subprocess.run(  # noqa: UP022
        ["pre-commit", "try-repo", str(REPO_ROOT), "deny-terms", "--all-files"],
        cwd=str(target),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,  # noqa: UP021 - text= is also 3.7+ only
        check=False,
    )
    # No term file in this environment, so the hook must pass - but it
    # must have actually run, not failed to install.
    combined = r.stdout + r.stderr
    assert "Passed" in combined or r.returncode == 0, combined
    assert "not found" not in combined.lower(), combined


# --- the framework as the front end ------------------------------------------
#
# Each consumer pins a snapshot of this working tree (tracked and unignored
# files, committed into a fresh repository) and lets `git commit` run the
# hooks through the installed framework, as a user would.

PLANTED = "zqvplantedterm"
_ISOLATE = (
    "GIT_DENY_TERMS",
    "GIT_HYGIENE_NO_INHERIT",
    "GIT_HYGIENE_NO_WALK",
    "GIT_HYGIENE_WALK_TO",
    "GIT_HYGIENE_SHOW_PRIVATE_TERMS",
    "GIT_HYGIENE_REQUIRE_PRIVATE",
    "GIT_INDEX_FILE",
    "GIT_DIR",
    "GIT_WORK_TREE",
)


def _run(argv, cwd, env):
    # type: (list, Path, dict) -> subprocess.CompletedProcess
    return subprocess.run(  # noqa: S603, UP022
        argv,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,  # noqa: UP021
        env=env,
        check=False,
    )


@pytest.fixture(scope="module")
def framework(tmp_path_factory):
    # type: (pytest.TempPathFactory) -> dict
    base = tmp_path_factory.mktemp("framework")
    env = {k: v for k, v in os.environ.items() if k not in _ISOLATE}
    env.update(
        {
            "PRE_COMMIT_HOME": str(base / "pre-commit-home"),
            "XDG_CONFIG_HOME": str(base / "xdg-config"),
            "GIT_HYGIENE_WALK_TO": str(base),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@example.invalid",
        }
    )
    listing = _run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], REPO_ROOT, env
    ).stdout
    snapshot = base / "snapshot"
    for rel in [f for f in listing.split("\0") if f and (REPO_ROOT / f).is_file()]:
        target = snapshot / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(str(REPO_ROOT / rel), str(target))
    for args in (("init", "-q"), ("add", "-A"), ("commit", "-q", "--no-verify", "-m", "snapshot")):
        r = _run(["git"] + list(args), snapshot, env)
        assert r.returncode == 0, r.stdout
    rev = _run(["git", "rev-parse", "HEAD"], snapshot, env).stdout.strip()
    return {"base": base, "env": env, "repo": str(snapshot).replace("\\", "/"), "rev": rev}


def _consumer(framework, name, hooks):
    # type: (dict, str, str) -> Path
    path = framework["base"] / name
    env = framework["env"]
    _run(["git", "init", "-q", str(path)], framework["base"], env)
    _run(["git", "config", "core.fileMode", "true"], path, env)
    config = "repos:\n- repo: {}\n  rev: {}\n  hooks:\n{}".format(
        framework["repo"], framework["rev"], hooks
    )
    (path / ".pre-commit-config.yaml").write_bytes(config.encode("utf-8"))
    r = _run(["pre-commit", "install"], path, env)
    assert r.returncode == 0, r.stdout
    _run(["git", "add", ".pre-commit-config.yaml"], path, env)
    r = _run(["git", "commit", "-q", "--no-verify", "-m", "config"], path, env)
    assert r.returncode == 0, r.stdout
    return path


def _commit(framework, path, rel, text, extra_env=None):
    # type: (dict, Path, str, str, dict) -> subprocess.CompletedProcess
    env = dict(framework["env"])
    env.update(extra_env or {})
    target = path / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(text.encode("utf-8"))
    _run(["git", "add", "--", rel], path, env)
    return _run(["git", "commit", "-q", "-m", "add " + rel], path, env)


@needs_tooling
def test_framework_blocks_a_planted_private_term_without_printing_it(framework):
    # type: (dict) -> None
    path = _consumer(framework, "planted", "  - id: deny-terms\n")
    terms = framework["base"] / "private-terms.txt"
    terms.write_bytes((PLANTED + "\n").encode("utf-8"))
    extra = {"GIT_DENY_TERMS": str(terms), "GIT_HYGIENE_NO_INHERIT": "1"}
    r = _commit(framework, path, "clean.md", "ordinary\n", extra)
    assert r.returncode == 0, r.stdout
    r = _commit(framework, path, "dirty.md", "mentions " + PLANTED + "\n", extra)
    assert r.returncode != 0
    assert "BLOCKED" in r.stdout, r.stdout
    assert PLANTED not in r.stdout


@needs_tooling
def test_framework_refuses_when_a_required_list_is_absent(framework):
    # type: (dict) -> None
    path = _consumer(framework, "required", "  - id: deny-terms\n    args: [--require-private]\n")
    r = _commit(framework, path, "a.md", "ordinary\n")
    assert r.returncode != 0
    assert "no private term source resolved, and one is required" in r.stdout, r.stdout
    for name in ("deny-terms.txt", ".deny-terms.private"):
        assert name in r.stdout, name


@needs_tooling
def test_framework_honors_the_environment_requirement(framework):
    # type: (dict) -> None
    path = _consumer(framework, "env-required", "  - id: deny-terms\n")
    r = _commit(framework, path, "a.md", "ordinary\n")
    assert r.returncode == 0, r.stdout
    r = _commit(framework, path, "b.md", "ordinary\n", {"GIT_HYGIENE_REQUIRE_PRIVATE": "1"})
    assert r.returncode != 0
    assert "no private term source resolved, and one is required" in r.stdout, r.stdout


@needs_tooling
def test_framework_mode_fix_lands_on_the_first_commit(framework):
    # type: (dict) -> None
    path = _consumer(framework, "modes", "  - id: normalize-file-modes\n")
    env = framework["env"]

    exceptions = path / ".gitmodes-exceptions"
    exceptions.write_bytes(b"lib/*.sh\n")
    lib = path / "lib" / "env.sh"
    lib.parent.mkdir()
    lib.write_bytes(b"#!/bin/sh\n")
    tool = path / "tool.sh"
    tool.write_bytes(b"#!/bin/sh\necho staged\n")
    for f in (exceptions, lib, tool):
        os.chmod(str(f), 0o644)
    _run(["git", "add", "-A"], path, env)
    tool.write_bytes(b"#!/bin/sh\necho staged\necho not staged\n")

    r = _run(["git", "commit", "-q", "-m", "modes"], path, env)
    assert r.returncode == 0, r.stdout
    assert "files were modified by this hook" not in r.stdout
    tree = _run(["git", "ls-tree", "HEAD", "--", "tool.sh", "lib/env.sh"], path, env).stdout
    modes = {line.split("\t")[1]: line.split()[0] for line in tree.splitlines()}
    assert modes == {"tool.sh": "100755", "lib/env.sh": "100644"}, tree
    shown = _run(["git", "show", "HEAD:tool.sh"], path, env).stdout
    assert shown == "#!/bin/sh\necho staged\n"
    assert tool.read_bytes() == b"#!/bin/sh\necho staged\necho not staged\n"
