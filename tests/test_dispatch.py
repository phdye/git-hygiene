"""The multi-check front end, driven through real commits
(doc/proposal/2026-09-16.multi-check-hooks.md, "Verification criteria").

Every test installs the shims with install-hooks and lets git run them.
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

from git_hygiene import checks, dispatch

from .helpers import CONSOLE_SCRIPTS, Sandbox, fwd, make_command, python_command, write

REPO_ROOT = Path(__file__).resolve().parent.parent
PLANTED = "zqvplantedterm"


@pytest.fixture
def sb(tmp_path):
    # type: (Path) -> Sandbox
    return Sandbox(tmp_path)


def fake(sb, check_id, *options, hook="pre-commit", **keys):
    # type: (Sandbox, str, str, str, str) -> Path
    """Declare a fake-check under `check_id`; `keys` become declaration
    lines, with underscores in their names turned into dashes."""
    lines = [f'[check "{check_id}"]', "\tcommand = fake-check", f"\thook = {hook}"]
    if options:
        lines.append("\targs = " + " ".join(options))
    for key, value in keys.items():
        lines.append(f"\t{key.replace('_', '-')} = {value}")
    return sb.declare(check_id, "\n".join(lines) + "\n")


def only(sb, *ids):
    # type: (Sandbox, str) -> None
    """Leave exactly these checks enabled, through the tracked layer."""
    lines = []
    for check_id in ("filemode", "deny-terms", "deny-terms-msg"):
        if check_id not in ids:
            lines += [f'[check "{check_id}"]', "\tenabled = false"]
    write(sb.repo / ".git-hygiene", "\n".join(lines) + "\n")


# --- installation ----------------------------------------------------------


def test_install_twice_is_byte_identical(sb):
    # type: (Sandbox) -> None
    fake(sb, "pusher", hook="pre-push")
    sb.install()
    hooks = sb.repo / ".git" / "hooks"
    first = {n: (hooks / n).read_bytes() for n in ("pre-commit", "commit-msg", "pre-push")}
    sb.install()
    second = {n: (hooks / n).read_bytes() for n in first}
    assert first == second
    for name, body in first.items():
        assert b"exec git-hygiene run " + name.encode() + b' "$@"' in body
        assert b"\r" not in body


def test_a_retired_managed_hook_is_removed(sb):
    # type: (Sandbox) -> None
    declaration = fake(sb, "pusher", hook="pre-push")
    sb.install()
    assert (sb.repo / ".git" / "hooks" / "pre-push").is_file()
    declaration.unlink()
    r = sb.install()
    assert "removed pre-push" in r.stdout
    assert not (sb.repo / ".git" / "hooks" / "pre-push").exists()
    assert (sb.repo / ".git" / "hooks" / "pre-commit").is_file()


def test_shim_refuses_when_the_dispatcher_is_not_on_path(sb):
    # type: (Sandbox) -> None
    sb.install()
    for suffix in ("", ".cmd"):
        victim = sb.bin / ("git-hygiene" + suffix)
        if victim.exists():
            victim.unlink()
    # Only what the hook itself needs, so an installed git-hygiene
    # elsewhere on PATH cannot stand in for the one removed.
    needed = {str(sb.bin)}
    for tool in ("git", "bash", "sh"):
        found = shutil.which(tool)
        if found:
            needed.add(os.path.dirname(found))
    narrow = os.pathsep.join(sorted(needed))
    assert shutil.which("git-hygiene", path=narrow) is None
    sb.stage("a.txt", "ordinary\n")
    r = sb.commit(extra_env={"PATH": narrow})
    assert r.returncode != 0
    assert "git-hygiene is not on PATH; the pre-commit hook cannot run" in r.stderr, r.stderr
    assert sb.head_count() == 0


def test_git_hygiene_is_reachable_as_a_git_subcommand(sb):
    # type: (Sandbox) -> None
    r = sb.git("hygiene", "run", "--explain", "pre-commit")
    assert r.returncode == 0, r.stderr
    assert "deny-terms" in r.stdout
    assert "filemode" in r.stdout
    assert "deny-terms-msg" not in r.stdout  # a commit-msg check


def test_existing_hook_ids_and_console_scripts_are_unchanged():
    # type: () -> None
    manifest = (REPO_ROOT / ".pre-commit-hooks.yaml").read_text(encoding="utf-8")
    assert re.findall(r"^- id: (\S+)", manifest, re.MULTILINE) == [
        "deny-terms",
        "deny-terms-msg",
        "audit-tree",
    ]
    assert "entry: check-identifiers --staged" in manifest
    assert "entry: check-identifiers --message" in manifest
    project = (REPO_ROOT / "setup.cfg").read_text(encoding="utf-8")
    for name, target in (
        ("check-identifiers", "git_hygiene.check_identifiers:main"),
        ("audit-tree", "git_hygiene.audit_tree:main"),
        ("install-hooks", "git_hygiene.install_hooks:main"),
        ("git-hygiene", "git_hygiene.dispatch:main"),
        ("normalize-file-modes", "git_hygiene.filemode:main"),
    ):
        assert f"{name} = {target}" in project
    assert set(CONSOLE_SCRIPTS) <= {
        "git-hygiene",
        "check-identifiers",
        "normalize-file-modes",
        "install-hooks",
    }


# --- the exit contract -----------------------------------------------------


def _binary(sb, rel, payload):
    # type: (Sandbox, str, bytes) -> None
    (sb.repo / rel).write_bytes(b"\x00\x01binary\x00" + payload)
    sb.git("add", "--", rel)


def test_a_binary_only_commit_passes_a_text_scanner(sb):
    # type: (Sandbox) -> None
    only(sb, "deny-terms")
    sb.private_terms(PLANTED + "\n")
    sb.install()
    _binary(sb, "image.bin", b"one")
    r = sb.commit()
    assert r.returncode == 0, r.stderr
    assert r.stderr == "", r.stderr
    assert sb.head_count() == 1

    _binary(sb, "image.bin", b"two")
    r = sb.commit("again", extra_env={"GIT_HYGIENE_VERBOSE": "1"})
    assert r.returncode == 0, r.stderr
    assert "deny-terms: not applicable (exit 3, contract 2)" in r.stderr


def test_a_merge_resolving_only_a_binary_passes(sb):
    # type: (Sandbox) -> None
    only(sb, "deny-terms")
    sb.private_terms(PLANTED + "\n")
    sb.stage(".git-hygiene", (sb.repo / ".git-hygiene").read_text(encoding="utf-8"))
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
    assert "refused" not in r.stderr
    parents = sb.git("rev-list", "--parents", "-n", "1", "HEAD").stdout.split()
    assert len(parents) == 3, "HEAD is not a merge commit"


def test_a_required_check_whose_input_is_absent_refuses(sb):
    # type: (Sandbox) -> None
    only(sb, "deny-terms")
    sb.install()
    sb.stage("a.txt", "ordinary\n")
    r = sb.commit(extra_env={"GIT_HYGIENE_REQUIRE": "deny-terms"})
    assert r.returncode != 0
    assert "deny-terms: is required and could not run (exit 4, contract 2)" in r.stderr, r.stderr
    assert "no private term source resolved" in r.stderr
    assert "deny-terms.txt" in r.stderr
    assert sb.head_count() == 0


def test_an_optional_check_whose_input_is_absent_passes_quietly(sb):
    # type: (Sandbox) -> None
    only(sb, "deny-terms")
    sb.install()
    sb.stage("a.txt", "ordinary\n")
    r = sb.commit()
    assert r.returncode == 0, r.stderr
    assert r.stderr == ""
    sb.stage("b.txt", "ordinary\n")
    r = sb.commit("again", extra_env={"GIT_HYGIENE_VERBOSE": "yes"})
    assert r.returncode == 0, r.stderr
    assert "deny-terms: could not run (exit 4, contract 2); optional, so not refusing" in r.stderr
    assert "no private term source resolved" in r.stderr


@pytest.mark.parametrize("code,passes", [(0, True), (1, False), (2, False)])
def test_no_contract_means_contract_1(sb, code, passes):
    # type: (Sandbox, int, bool) -> None
    only(sb)
    fake(sb, "legacy", "--exit", str(code))
    sb.install()
    sb.stage("a.txt", "ordinary\n")
    r = sb.commit()
    assert (r.returncode == 0) == passes, r.stderr
    if code == 1:
        assert "legacy: refused (exit 1, contract 1)" in r.stderr
    if code == 2:
        assert "legacy: reported a usage error (exit 2, contract 1)" in r.stderr


@pytest.mark.parametrize("code", [3, 4])
def test_contract_1_codes_3_and_4_refuse_even_when_optional(sb, code):
    # type: (Sandbox, int) -> None
    only(sb)
    fake(sb, "legacy", "--exit", str(code), required="false")
    sb.install()
    sb.stage("a.txt", "ordinary\n")
    r = sb.commit()
    assert r.returncode != 0
    assert f"legacy: exited {code}, which contract 1 does not define; refusing." in r.stderr
    assert sb.head_count() == 0


@pytest.mark.parametrize("required", ["true", "false"])
def test_contract_2_codes_above_4_refuse(sb, required):
    # type: (Sandbox, str) -> None
    only(sb)
    fake(sb, "modern", "--exit", "5", contract="2", required=required)
    sb.install()
    sb.stage("a.txt", "ordinary\n")
    r = sb.commit()
    assert r.returncode != 0
    assert "modern: exited 5, which contract 2 does not define; refusing." in r.stderr


def test_an_unknown_contract_is_a_usage_error_before_anything_runs(sb):
    # type: (Sandbox) -> None
    only(sb)
    marker = sb.root / "ran"
    fake(sb, "aaa-first", "--marker", fwd(marker))
    sb.install()
    fake(sb, "zzz-broken", contract="3")
    assert sb.tool("install-hooks", str(sb.repo)).returncode == 2
    sb.stage("a.txt", "ordinary\n")
    r = sb.commit()
    assert r.returncode != 0
    assert "unknown exit contract '3'" in r.stderr, r.stderr
    assert "no check was run" in r.stderr
    assert not marker.exists()
    direct = sb.tool("git-hygiene", "run", "pre-commit")
    assert direct.returncode == 2


def test_contract_meanings_table():
    # type: () -> None
    assert dispatch.meaning(3, "2") == dispatch.NOT_APPLICABLE
    assert dispatch.meaning(3, "1") == dispatch.UNDEFINED
    assert dispatch.meaning(-9, "2") == dispatch.UNDEFINED
    assert not dispatch.refuses(dispatch.COULD_NOT_RUN, False)
    assert dispatch.refuses(dispatch.COULD_NOT_RUN, True)
    assert dispatch.refuses(dispatch.UNDEFINED, False)
    assert not dispatch.refuses(dispatch.NOT_APPLICABLE, True)


# --- configuration ---------------------------------------------------------


def test_an_unregistered_id_is_a_usage_error_naming_it(sb):
    # type: (Sandbox) -> None
    write(sb.repo / ".git-hygiene", '[check "no-such-check"]\n\tenabled = true\n')
    sb.install()
    sb.stage("a.txt", "ordinary\n")
    r = sb.commit()
    assert r.returncode != 0
    assert "'no-such-check' is not a registered check" in r.stderr, r.stderr
    assert sb.tool("git-hygiene", "run", "pre-commit").returncode == 2


@pytest.mark.parametrize(
    "text",
    [
        '[check "../bin/evil"]\n\tenabled = true\n',
        '[check "fake"]\n\tcommand = /bin/evil\n',
        "[core]\n\thooksPath = /tmp\n",
    ],
)
def test_a_setting_naming_a_path_or_command_is_rejected_before_anything_runs(sb, text):
    # type: (Sandbox, str) -> None
    only(sb)
    marker = sb.root / "ran"
    fake(sb, "fake", "--marker", fwd(marker))
    with (sb.repo / ".git-hygiene").open("ab") as handle:
        handle.write(text.encode("utf-8"))
    sb.install()
    sb.stage("a.txt", "ordinary\n")
    r = sb.commit()
    assert r.returncode != 0
    assert "configuration error; no check was run" in r.stderr, r.stderr
    assert not marker.exists()


def test_a_tracked_include_is_not_followed(sb):
    # type: (Sandbox) -> None
    only(sb)
    marker = sb.root / "ran"
    fake(sb, "fake", "--marker", fwd(marker), "--exit", "1", enabled="false")
    write(sb.repo / "extra.conf", '[check "fake"]\n\tenabled = true\n')
    with (sb.repo / ".git-hygiene").open("ab") as handle:
        handle.write(b"[include]\n\tpath = extra.conf\n")
    sb.install()
    sb.stage("a.txt", "ordinary\n")
    r = sb.commit()
    assert r.returncode == 0, r.stderr
    assert "include.path ignored; includes are not read" in r.stderr
    assert not marker.exists()


def test_each_layer_overrides_the_one_below(sb):
    # type: (Sandbox) -> None
    only(sb)
    fake(sb, "fake", "--exit", "1", enabled="false")
    sb.install()
    tracked = sb.repo / ".git-hygiene"
    clone = sb.repo / ".git" / "info" / "git-hygiene"

    def outcome(extra_env=None, *flags):
        # type: (dict, str) -> str
        r = sb.tool(
            "git-hygiene", "run", "--explain", *(list(flags) + ["pre-commit"]), extra_env=extra_env
        )
        assert r.returncode == 0, r.stderr
        block = r.stdout.split("fake\n", 1)[1]
        return [ln for ln in block.splitlines() if ln.strip().startswith("enabled")][0]

    assert "no   from declaration" in outcome()
    with tracked.open("ab") as handle:
        handle.write(b'[check "fake"]\n\tenabled = true\n')
    assert "yes  from repository" in outcome()
    write(clone, '[check "fake"]\n\tenabled = false\n')
    assert "no   from clone" in outcome()
    assert "yes  from environment GIT_HYGIENE_ENABLE" in outcome({"GIT_HYGIENE_ENABLE": "fake"})
    assert "no   from flag --disable" in outcome(
        {"GIT_HYGIENE_ENABLE": "fake"}, "--disable", "fake"
    )

    sb.stage("a.txt", "ordinary\n")
    assert sb.commit().returncode == 0  # the clone layer disabled it
    sb.stage("b.txt", "ordinary\n")
    r = sb.commit(extra_env={"GIT_HYGIENE_ENABLE": "fake"})
    assert r.returncode != 0
    assert "fake: refused (exit 1, contract 1)" in r.stderr


def test_naming_one_id_both_ways_in_one_layer_is_an_error(sb):
    # type: (Sandbox) -> None
    r = sb.tool(
        "git-hygiene",
        "run",
        "pre-commit",
        extra_env={"GIT_HYGIENE_REQUIRE": "deny-terms", "GIT_HYGIENE_OPTIONAL": "deny-terms"},
    )
    assert r.returncode == 2
    assert "'deny-terms' is also named by environment GIT_HYGIENE_REQUIRE" in r.stderr


def test_a_repository_may_enable_a_check_the_defaults_leave_off(sb):
    # type: (Sandbox) -> None
    only(sb)
    marker = sb.root / "ran"
    fake(sb, "extra", "--marker", fwd(marker), enabled="false")
    sb.install()
    sb.stage("a.txt", "ordinary\n")
    assert sb.commit().returncode == 0
    assert not marker.exists()
    with (sb.repo / ".git-hygiene").open("ab") as handle:
        handle.write(b'[check "extra"]\n\tenabled = yes\n')
    sb.stage("b.txt", "ordinary\n")
    assert sb.commit("second").returncode == 0
    assert marker.exists()


# --- registration and ordering ---------------------------------------------


def test_a_declared_check_is_found_and_run(sb):
    # type: (Sandbox) -> None
    only(sb)
    fake(sb, "talker", "--say", "talker-was-here")
    sb.install()
    sb.stage("a.txt", "ordinary\n")
    r = sb.commit()
    assert r.returncode == 0, r.stderr
    assert "talker-was-here" in r.stderr


def test_a_check_that_is_not_a_python_program(sb):
    # type: (Sandbox) -> None
    only(sb)
    marker = sb.root / "shell-ran"
    make_command(
        sb.bin,
        "shell-check",
        'echo "native check ran" > "$1"; exit 0',
        'echo native check ran> "%~1"\r\nexit /b 0',
    )
    sb.declare(
        "shell",
        f'[check "shell"]\n\tcommand = shell-check\n\thook = pre-commit\n\targs = "{fwd(marker)}"\n',
    )
    sb.install()
    sb.stage("a.txt", "ordinary\n")
    r = sb.commit()
    assert r.returncode == 0, r.stderr
    assert "native check ran" in marker.read_text(encoding="utf-8")


def test_a_check_installed_under_another_interpreter(sb):
    # type: (Sandbox) -> None
    """The check's module exists only inside a separate environment, so
    it can run only if the dispatcher starts that environment's
    interpreter rather than its own."""
    import subprocess
    import sys

    env_dir = sb.root / "other-env"
    made = subprocess.run(  # noqa: S603, UP022
        [sys.executable, "-m", "venv", "--without-pip", str(env_dir)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert made.returncode == 0, made.stderr
    scripts = env_dir / ("Scripts" if os.name == "nt" else "bin")
    other = scripts / ("python.exe" if os.name == "nt" else "python")
    purelib = (
        subprocess.run(  # noqa: S603, UP022
            [str(other), "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"],
            stdout=subprocess.PIPE,
            check=False,
        )
        .stdout.decode()
        .strip()
    )
    write(
        Path(purelib) / "hygiene_only_here.py",
        "import sys\nopen(sys.argv[1], 'w').write(sys.prefix)\n",
    )
    marker = sb.root / "prefix"
    python_command(sb.bin, "elsewhere-check", "-m hygiene_only_here", interpreter=str(other))
    only(sb)
    sb.declare(
        "elsewhere",
        f'[check "elsewhere"]\n\tcommand = elsewhere-check\n\thook = pre-commit\n\targs = "{fwd(marker)}"\n',
    )
    sb.install()
    sb.stage("a.txt", "ordinary\n")
    r = sb.commit()
    assert r.returncode == 0, r.stderr
    recorded = Path(marker.read_text(encoding="utf-8"))
    assert recorded.resolve() == env_dir.resolve()
    assert recorded.resolve() != Path(sys.prefix).resolve()


def test_adding_a_check_does_not_reorder_the_others(sb):
    # type: (Sandbox) -> None
    only(sb)
    log = sb.root / "order.log"
    fake(sb, "bravo", "--log", fwd(log), order="20")
    fake(sb, "delta", "--log", fwd(log), order="20")
    fake(sb, "alpha", "--log", fwd(log), order="30")
    sb.install()
    sb.stage("a.txt", "ordinary\n")
    assert sb.commit().returncode == 0
    assert log.read_text(encoding="utf-8").split() == ["bravo", "delta", "alpha"]
    log.unlink()
    fake(sb, "charlie", "--log", fwd(log), order="20")
    sb.stage("b.txt", "ordinary\n")
    assert sb.commit("second").returncode == 0
    assert log.read_text(encoding="utf-8").split() == ["bravo", "charlie", "delta", "alpha"]


def test_a_duplicate_declaration_is_a_usage_error(sb):
    # type: (Sandbox) -> None
    sb.declare("dup", '[check "deny-terms"]\n\tcommand = fake-check\n\thook = pre-commit\n')
    r = sb.tool("git-hygiene", "run", "pre-commit")
    assert r.returncode == 2
    assert "'deny-terms' is already declared by built-in" in r.stderr


def test_run_order_puts_index_changes_first():
    # type: () -> None
    base = checks.BUILT_IN[1]
    late_mutator = base._replace(id="zz", order=99, mutates_index=True)
    early_reader = base._replace(id="aa", order=1)
    ordered = checks.run_order([early_reader, late_mutator])
    assert [c.id for c in ordered] == ["zz", "aa"]


# --- file-mode normalization -----------------------------------------------


def _mode(sb, rel, ref=None):
    # type: (Sandbox, str, str) -> str
    if ref is None:
        out = sb.git("ls-files", "-s", "--", rel).stdout
    else:
        out = sb.git("ls-tree", ref, "--", rel).stdout
    return out.split()[0] if out.split() else "absent"


def _stage_mode(sb, rel, text, executable):
    # type: (Sandbox, str, str, bool) -> None
    sb.stage(rel, text)
    sb.git("update-index", "--chmod=" + ("+x" if executable else "-x"), "--", rel)


def test_modes_are_corrected_with_no_option(sb):
    # type: (Sandbox) -> None
    only(sb, "filemode")
    sb.install()
    _stage_mode(sb, "tool.sh", "#!/bin/sh\necho hi\n", False)
    _stage_mode(sb, "notes.md", "plain text\n", True)
    r = sb.commit()
    assert r.returncode == 0, r.stderr
    assert _mode(sb, "tool.sh", "HEAD") == "100755"
    assert _mode(sb, "notes.md", "HEAD") == "100644"
    assert "filemode: mode 755 on tool.sh" in r.stderr
    assert "filemode: mode 644 on notes.md" in r.stderr


def test_staged_content_and_working_tree_are_untouched(sb):
    # type: (Sandbox) -> None
    only(sb, "filemode")
    sb.install()
    staged_text = "#!/bin/sh\necho staged\n"
    _stage_mode(sb, "tool.sh", staged_text, False)
    work = sb.repo / "tool.sh"
    work.write_bytes(b"#!/bin/sh\necho staged\necho not staged\n")
    before_work = work.read_bytes()
    before_blob = sb.git("rev-parse", ":tool.sh").stdout.strip()
    r = sb.commit()
    assert r.returncode == 0, r.stderr
    assert work.read_bytes() == before_work
    assert sb.git("rev-parse", "HEAD:tool.sh").stdout.strip() == before_blob
    assert sb.git("show", "HEAD:tool.sh").stdout == staged_text
    assert _mode(sb, "tool.sh", "HEAD") == "100755"


@pytest.mark.parametrize("verbose", ["0", "1"])
def test_every_changed_path_is_named_and_the_status_note_given(sb, verbose):
    # type: (Sandbox, str) -> None
    only(sb, "filemode")
    sb.git("config", "core.fileMode", "true")
    sb.install()
    for i in range(3):
        _stage_mode(sb, f"s{i}.sh", "#!/bin/sh\n", False)
    r = sb.commit(extra_env={"GIT_HYGIENE_VERBOSE": verbose})
    assert r.returncode == 0, r.stderr
    for i in range(3):
        assert f"filemode: mode 755 on s{i}.sh" in r.stderr
    assert "`git status` may now show a changed file's" in r.stderr


def test_a_later_check_sees_the_corrected_mode(sb):
    # type: (Sandbox) -> None
    only(sb, "filemode")
    fake(sb, "reader", "--expect-mode", "tool.sh", "100755", order="1")
    sb.install()
    _stage_mode(sb, "tool.sh", "#!/bin/sh\n", False)
    r = sb.commit()
    assert r.returncode == 0, r.stderr
    assert "fake-check: tool.sh is 100755 in the index" in r.stderr


def test_exceptions_keep_the_staged_mode_and_are_announced(sb):
    # type: (Sandbox) -> None
    only(sb, "filemode")
    sb.install()
    sb.stage(".gitmodes-exceptions", "# sourced, shebang only for highlighting\nlib/*.sh\n")
    _stage_mode(sb, "lib/env.sh", "#!/bin/sh\n", False)
    r = sb.commit()
    assert r.returncode == 0, r.stderr
    assert _mode(sb, "lib/env.sh", "HEAD") == "100644"
    assert "filemode: mode exception: lib/env.sh" in r.stderr


def test_a_match_everything_exception_is_refused(sb):
    # type: (Sandbox) -> None
    only(sb, "filemode")
    sb.install()
    sb.stage(".gitmodes-exceptions", "\n*\n")
    r = sb.commit()
    assert r.returncode != 0
    assert "line 2: the pattern '*' matches every" in r.stderr
    assert "filemode: reported a usage error" in r.stderr


@pytest.mark.parametrize("layer", ["repository", "clone"])
def test_normalization_can_be_disabled(sb, layer):
    # type: (Sandbox, str) -> None
    only(sb, "filemode")
    text = '[check "filemode"]\n\tenabled = false\n'
    if layer == "repository":
        write(sb.repo / ".git-hygiene", text)
    else:
        write(sb.repo / ".git" / "info" / "git-hygiene", text)
    sb.install()
    _stage_mode(sb, "tool.sh", "#!/bin/sh\n", False)
    r = sb.commit()
    assert r.returncode == 0, r.stderr
    assert _mode(sb, "tool.sh", "HEAD") == "100644"
    assert "filemode" not in r.stderr


# --- a required private term list ------------------------------------------

_REQUIRE = '[check "deny-terms"]\n\trequired = true\n'


def _published(sb):
    # type: (Sandbox) -> Path
    """A repository whose tracked settings require deny-terms, and a
    fresh clone of it with the shims installed."""
    only(sb, "deny-terms")
    with (sb.repo / ".git-hygiene").open("ab") as handle:
        handle.write(_REQUIRE.encode("utf-8"))
    sb.git("add", ".git-hygiene")
    assert sb.commit("settings", "--no-verify").returncode == 0
    clone = sb.root / "clone"
    r = sb.git("clone", "-q", str(sb.repo), str(clone), cwd=sb.root)
    assert r.returncode == 0, r.stderr
    sb.install(clone)
    return clone


def _probed_everywhere(stderr):
    # type: (str) -> None
    for name in ("deny-terms.txt", ".deny-terms.private", os.path.join("info", "deny-terms")):
        assert name in stderr, name


def test_a_fresh_clone_without_a_private_list_refuses(sb):
    # type: (Sandbox) -> None
    clone = _published(sb)
    sb.stage("a.txt", "mentions " + PLANTED + "\n", cwd=clone)
    r = sb.commit(cwd=clone)
    assert r.returncode != 0
    assert "deny-terms: is required and could not run" in r.stderr, r.stderr
    _probed_everywhere(r.stderr)
    assert PLANTED not in r.stdout + r.stderr
    assert sb.head_count(clone) == 1


def test_a_moved_working_copy_loses_its_ancestor_list_and_refuses(sb):
    # type: (Sandbox) -> None
    only(sb, "deny-terms")
    write(sb.repo / ".git-hygiene", (sb.repo / ".git-hygiene").read_text() + _REQUIRE)
    home = sb.root / "projects"
    write(home / ".deny-terms.private", PLANTED + "\n")
    before = sb.new_repo(home / "work")
    shutil.copy(str(sb.repo / ".git-hygiene"), str(before / ".git-hygiene"))
    sb.install(before)
    sb.stage("a.txt", "ordinary\n", cwd=before)
    r = sb.commit(cwd=before)
    assert r.returncode == 0, r.stderr

    after = sb.root / "elsewhere" / "work"
    after.parent.mkdir()
    shutil.move(str(before), str(after))
    sb.stage("b.txt", "ordinary\n", cwd=after)
    r = sb.commit("moved", cwd=after)
    assert r.returncode != 0
    assert "deny-terms: is required and could not run" in r.stderr, r.stderr
    assert PLANTED not in r.stdout + r.stderr


@pytest.mark.parametrize("where", ["user", "ancestor", "root", "git-info"])
def test_one_private_source_anywhere_satisfies_the_requirement(sb, where):
    # type: (Sandbox, str) -> None
    clone = _published(sb)
    if where == "user":
        write(sb.config_home / "git" / "deny-terms.txt", PLANTED + "\n")
    elif where == "ancestor":
        write(clone.parent / ".deny-terms.private", PLANTED + "\n")
    elif where == "root":
        write(clone / ".deny-terms.private", PLANTED + "\n")
    else:
        sb.private_terms(PLANTED + "\n", cwd=clone)
    sb.stage("a.txt", "ordinary\n", cwd=clone)
    r = sb.commit(cwd=clone)
    assert r.returncode == 0, r.stderr


def test_a_public_list_alone_does_not_satisfy_the_requirement(sb):
    # type: (Sandbox) -> None
    clone = _published(sb)
    write(clone / ".deny-terms", "zqvpublicterm\n")
    sb.stage("a.txt", "ordinary\n", cwd=clone)
    r = sb.commit(cwd=clone)
    assert r.returncode != 0
    assert "deny-terms: is required and could not run" in r.stderr


def test_a_clone_may_require_it_by_itself(sb):
    # type: (Sandbox) -> None
    only(sb, "deny-terms")
    sb.install()
    sb.stage("a.txt", "ordinary\n")
    assert sb.commit().returncode == 0  # not required: silent pass
    write(sb.repo / ".git" / "info" / "git-hygiene", _REQUIRE)
    sb.stage("b.txt", "ordinary\n")
    r = sb.commit("second")
    assert r.returncode != 0
    assert "deny-terms: is required and could not run" in r.stderr
    _probed_everywhere(r.stderr)
