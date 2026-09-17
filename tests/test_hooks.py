"""The checks this package ships, driven through real commits and direct
runs (doc/proposal/2026-09-16.pre-commit-front-end.md, "Verification
criteria"). The framework itself is exercised in test_packaging.py.

Outcomes are asserted on what was said as well as on the exit status and
the resulting history, because a crashed hook and a refusing hook both
leave no commit behind.

Kept 3.6.8-clean like the rest of tests/.
"""

import os
import re
import shutil
from pathlib import Path

import pytest

from .helpers import CONSOLE_SCRIPTS, Sandbox, write

REPO_ROOT = Path(__file__).resolve().parent.parent
PLANTED = "zqvplantedterm"
REQUIRE = {"GIT_HYGIENE_REQUIRE_PRIVATE": "1"}


@pytest.fixture
def sb(tmp_path):
    # type: (Path) -> Sandbox
    return Sandbox(tmp_path)


# --- the public interface ----------------------------------------------------


def test_hook_ids_and_console_scripts():
    # type: () -> None
    manifest = (REPO_ROOT / ".pre-commit-hooks.yaml").read_text(encoding="utf-8")
    assert re.findall(r"^- id: (\S+)", manifest, re.MULTILINE) == [
        "deny-terms",
        "deny-terms-msg",
        "audit-tree",
        "normalize-file-modes",
    ]
    assert "entry: check-identifiers --staged" in manifest
    assert "entry: check-identifiers --message" in manifest
    assert "entry: normalize-file-modes" in manifest
    cfg = (REPO_ROOT / "setup.cfg").read_text(encoding="utf-8")
    for name, target in (
        ("check-identifiers", "git_hygiene.check_identifiers:main"),
        ("audit-tree", "git_hygiene.audit_tree:main"),
        ("install-hooks", "git_hygiene.install_hooks:main"),
        ("normalize-file-modes", "git_hygiene.filemode:main"),
    ):
        assert f"{name} = {target}" in cfg
    assert "git-hygiene =" not in cfg
    assert set(CONSOLE_SCRIPTS) == {"check-identifiers", "normalize-file-modes", "install-hooks"}


def test_the_dispatcher_is_gone(sb):
    # type: (Sandbox) -> None
    package = REPO_ROOT / "src" / "git_hygiene"
    for module in ("dispatch", "checks", "settings", "gitconfig"):
        assert not (package / (module + ".py")).exists(), module
    r = sb.tool("check-identifiers", "--help")
    assert r.returncode == 0
    assert "--exit-contract" not in r.stdout
    assert "--require-private" in r.stdout
    assert "--no-require-private" in r.stdout


# --- commits with nothing of the scanner's kind ------------------------------


def _binary(sb, rel, payload):
    # type: (Sandbox, str, bytes) -> None
    (sb.repo / rel).write_bytes(b"\x00\x01binary\x00" + payload)
    sb.git("add", "--", rel)


def test_a_binary_only_commit_passes(sb):
    # type: (Sandbox) -> None
    sb.private_terms(PLANTED + "\n")
    sb.install()
    _binary(sb, "image.bin", b"one")
    r = sb.commit()
    assert r.returncode == 0, r.stderr
    assert r.stderr == "", r.stderr
    assert sb.head_count() == 1


def test_a_binary_only_staged_set_passes_even_when_a_list_is_required(sb):
    # type: (Sandbox) -> None
    """Nothing staged could have been checked against the list. The
    message is text, so the commit-msg check still applies the
    requirement; this runs the content check alone."""
    _binary(sb, "image.bin", b"one")
    r = sb.tool("check-identifiers", "--staged", "--require-private")
    assert r.returncode == 0, r.stderr
    assert r.stderr == "", r.stderr


def test_a_merge_resolving_only_a_binary_passes(sb):
    # type: (Sandbox) -> None
    sb.private_terms(PLANTED + "\n")
    _binary(sb, "image.bin", b"base")
    assert sb.commit("base").returncode == 0
    sb.git("checkout", "-q", "-b", "side")
    _binary(sb, "image.bin", b"side")
    assert sb.commit("side").returncode == 0
    sb.git("checkout", "-q", "-")
    _binary(sb, "image.bin", b"main")
    assert sb.commit("main").returncode == 0
    merge = sb.git("merge", "-q", "side")
    assert merge.returncode != 0, "the merge was meant to conflict"
    sb.install()
    _binary(sb, "image.bin", b"resolved")
    r = sb.commit("merge side")
    assert r.returncode == 0, r.stderr
    assert "BLOCKED" not in r.stderr
    parents = sb.git("rev-list", "--parents", "-n", "1", "HEAD").stdout.split()
    assert len(parents) == 3, "HEAD is not a merge commit"


# --- a required private term list --------------------------------------------


def _probed_everywhere(stderr):
    # type: (str) -> None
    for name in ("deny-terms.txt", ".deny-terms.private", os.path.join("info", "deny-terms")):
        assert name in stderr, name


def _refused_for_want_of_a_list(sb, r):
    # type: (Sandbox, object) -> None
    assert r.returncode != 0
    assert "no private term source resolved, and one is required" in r.stderr, r.stderr
    _probed_everywhere(r.stderr)
    assert PLANTED not in r.stdout + r.stderr
    assert "Traceback" not in r.stderr


def test_required_by_environment_and_absent_refuses(sb):
    # type: (Sandbox) -> None
    sb.install()
    sb.stage("a.txt", "mentions " + PLANTED + "\n")
    r = sb.commit(extra_env=REQUIRE)
    _refused_for_want_of_a_list(sb, r)
    assert sb.head_count() == 0


def test_required_by_argument_and_absent_refuses(sb):
    # type: (Sandbox) -> None
    sb.stage("a.txt", "ordinary\n")
    r = sb.tool("check-identifiers", "--staged", "--require-private")
    _refused_for_want_of_a_list(sb, r)
    assert r.returncode == 1


def test_not_required_and_absent_passes_silently(sb):
    # type: (Sandbox) -> None
    sb.install()
    sb.stage("a.txt", "ordinary\n")
    r = sb.commit()
    assert r.returncode == 0, r.stderr
    assert r.stderr == ""


def test_the_negation_overrides_the_environment(sb):
    # type: (Sandbox) -> None
    sb.stage("a.txt", "ordinary\n")
    r = sb.tool("check-identifiers", "--staged", "--no-require-private", extra_env=REQUIRE)
    assert r.returncode == 0, r.stderr


def test_a_malformed_requirement_is_a_usage_error(sb):
    # type: (Sandbox) -> None
    sb.stage("a.txt", "ordinary\n")
    r = sb.tool("check-identifiers", "--staged", extra_env={"GIT_HYGIENE_REQUIRE_PRIVATE": "maybe"})
    assert r.returncode == 2
    assert "GIT_HYGIENE_REQUIRE_PRIVATE" in r.stderr


def test_a_required_message_check_refuses_too(sb):
    # type: (Sandbox) -> None
    message = write(sb.root / "msg.txt", "an ordinary message\n")
    r = sb.tool("check-identifiers", "--message", str(message), "--require-private")
    _refused_for_want_of_a_list(sb, r)


def test_a_moved_working_copy_loses_its_ancestor_list_and_refuses(sb):
    # type: (Sandbox) -> None
    home = sb.root / "projects"
    write(home / ".deny-terms.private", PLANTED + "\n")
    before = sb.new_repo(home / "work")
    sb.install(before)
    sb.stage("a.txt", "ordinary\n", cwd=before)
    r = sb.commit(cwd=before, extra_env=REQUIRE)
    assert r.returncode == 0, r.stderr

    after = sb.root / "elsewhere" / "work"
    after.parent.mkdir()
    shutil.move(str(before), str(after))
    sb.stage("b.txt", "ordinary\n", cwd=after)
    r = sb.commit("moved", cwd=after, extra_env=REQUIRE)
    _refused_for_want_of_a_list(sb, r)


@pytest.mark.parametrize("where", ["user", "ancestor", "root", "git-info"])
def test_one_private_source_anywhere_satisfies_the_requirement(sb, where):
    # type: (Sandbox, str) -> None
    if where == "user":
        write(sb.config_home / "git" / "deny-terms.txt", PLANTED + "\n")
    elif where == "ancestor":
        write(sb.repo.parent / ".deny-terms.private", PLANTED + "\n")
    elif where == "root":
        write(sb.repo / ".deny-terms.private", PLANTED + "\n")
    else:
        sb.private_terms(PLANTED + "\n")
    sb.install()
    sb.stage("a.txt", "ordinary\n")
    r = sb.commit(extra_env=REQUIRE)
    assert r.returncode == 0, r.stderr


def test_a_public_list_alone_does_not_satisfy_the_requirement(sb):
    # type: (Sandbox) -> None
    write(sb.repo / ".deny-terms", "zqvpublicterm\n")
    sb.install()
    sb.stage("a.txt", "ordinary\n")
    r = sb.commit(extra_env=REQUIRE)
    _refused_for_want_of_a_list(sb, r)


# --- file-mode normalization, run directly -----------------------------------


def _mode(sb, rel, ref=None):
    # type: (Sandbox, str, str) -> str
    if ref is None:
        out = sb.git("ls-files", "-s", "--", rel).stdout
    else:
        out = sb.git("ls-tree", ref, "--", rel).stdout
    return out.split()[0] if out.split() else "absent"


def _stage_mode(sb, rel, text, executable):
    # type: (Sandbox, str, str, bool) -> None
    path = sb.stage(rel, text)
    if os.name == "posix":
        path.chmod(0o755 if executable else 0o644)
    sb.git("update-index", "--chmod=" + ("+x" if executable else "-x"), "--", rel)


def _diff_is_clean_of_modes(sb):
    # type: (Sandbox) -> bool
    return "old mode" not in sb.git("diff").stdout


def test_modes_are_corrected_in_index_and_working_file(sb):
    # type: (Sandbox) -> None
    sb.git("config", "core.fileMode", "true")
    _stage_mode(sb, "tool.sh", "#!/bin/sh\necho hi\n", False)
    _stage_mode(sb, "notes.md", "plain text\n", True)
    before = sb.git("diff").stdout
    r = sb.tool("normalize-file-modes")
    assert r.returncode == 0, r.stderr
    assert _mode(sb, "tool.sh") == "100755"
    assert _mode(sb, "notes.md") == "100644"
    assert "filemode: mode 755 on tool.sh" in r.stderr
    assert "filemode: mode 644 on notes.md" in r.stderr
    # What the framework compares: git diff must not have changed.
    assert sb.git("diff").stdout == before
    assert "could not give the working file" not in r.stderr


def test_a_partly_staged_file_keeps_both_halves(sb):
    # type: (Sandbox) -> None
    sb.git("config", "core.fileMode", "true")
    staged_text = "#!/bin/sh\necho staged\n"
    _stage_mode(sb, "tool.sh", staged_text, False)
    work = sb.repo / "tool.sh"
    work.write_bytes(b"#!/bin/sh\necho staged\necho not staged\n")
    before_work = work.read_bytes()
    before_blob = sb.git("rev-parse", ":tool.sh").stdout.strip()
    r = sb.tool("normalize-file-modes")
    assert r.returncode == 0, r.stderr
    assert work.read_bytes() == before_work
    assert sb.git("rev-parse", ":tool.sh").stdout.strip() == before_blob
    assert _mode(sb, "tool.sh") == "100755"
    if os.name == "posix":
        assert _diff_is_clean_of_modes(sb), sb.git("diff").stdout
    assert sb.commit("staged half", "--no-verify").returncode == 0
    assert sb.git("show", "HEAD:tool.sh").stdout == staged_text


def test_nothing_staged_passes(sb):
    # type: (Sandbox) -> None
    r = sb.tool("normalize-file-modes")
    assert r.returncode == 0, r.stderr
    assert r.stderr == ""


def test_exceptions_keep_the_staged_mode_and_are_announced(sb):
    # type: (Sandbox) -> None
    sb.stage(".gitmodes-exceptions", "# sourced, shebang only for highlighting\nlib/*.sh\n")
    _stage_mode(sb, "lib/env.sh", "#!/bin/sh\n", False)
    r = sb.tool("normalize-file-modes")
    assert r.returncode == 0, r.stderr
    assert _mode(sb, "lib/env.sh") == "100644"
    assert "filemode: mode exception: lib/env.sh" in r.stderr


def test_a_match_everything_exception_is_refused(sb):
    # type: (Sandbox) -> None
    sb.stage(".gitmodes-exceptions", "\n*\n")
    r = sb.tool("normalize-file-modes")
    assert r.returncode == 2
    assert "line 2: the pattern '*' matches every" in r.stderr


def test_outside_a_work_tree_is_a_refusal(sb):
    # type: (Sandbox) -> None
    outside = sb.root / "not-a-repo"
    outside.mkdir()
    r = sb.tool(
        "normalize-file-modes", cwd=outside, extra_env={"GIT_CEILING_DIRECTORIES": str(sb.root)}
    )
    assert r.returncode == 1
    assert "not inside a git work tree" in r.stderr
