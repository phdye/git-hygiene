"""Shared scaffolding for tests that drive real commits through the
installed hook shims.

Commands the hook shims run are found on PATH, so each test gets a bin
directory of portable stand-ins for the console scripts: an extensionless
POSIX shell script (what bash, and so the hook shim, finds) and, on
Windows, a `.cmd` file (what a native interpreter can start). Both run
this interpreter against the source tree, so no `pip install` is needed.

Kept 3.6.8-clean like the rest of tests/.
"""

import os
import subprocess
import sys
from pathlib import Path  # noqa: F401 - resolves the type comments below

SRC_ROOT = str(Path(__file__).resolve().parent.parent / "src")

CONSOLE_SCRIPTS = {
    "check-identifiers": "git_hygiene.check_identifiers",
    "normalize-file-modes": "git_hygiene.filemode",
    "install-hooks": "git_hygiene.install_hooks",
}

_ISOLATE = (
    "GIT_DENY_TERMS",
    "GIT_HYGIENE_NO_INHERIT",
    "GIT_HYGIENE_NO_WALK",
    "GIT_HYGIENE_SHOW_PRIVATE_TERMS",
    "GIT_HYGIENE_REQUIRE_PRIVATE",
    "GIT_INDEX_FILE",
    "GIT_DIR",
    "GIT_WORK_TREE",
)


def fwd(path):
    # type: (object) -> str
    """A path spelled with forward slashes: safe inside a shell script,
    a batch file, and a shlex-split declaration on every platform."""
    return str(path).replace("\\", "/")


def run(argv, cwd, env=None, stdin=None):
    # type: (list, Path, dict, str) -> subprocess.CompletedProcess[str]
    return subprocess.run(  # noqa: UP022, S603
        argv,
        cwd=str(cwd),
        input=stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,  # noqa: UP021 - text= is also 3.7+ only
        env=env,
        check=False,
    )


def git(*args, cwd, env=None):
    # type: (str, Path, dict) -> subprocess.CompletedProcess[str]
    return run(["git"] + list(args), cwd, env)


def write(path, text):
    # type: (Path, str) -> Path
    """Write bytes, so no platform turns LF into CRLF."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path


def make_command(bin_dir, name, posix_body, cmd_body):
    # type: (Path, str, str, str) -> None
    write(bin_dir / name, "#!/bin/sh\n" + posix_body + "\n")
    (bin_dir / name).chmod(0o755)
    if os.name == "nt":
        write(bin_dir / (name + ".cmd"), "@echo off\r\n" + cmd_body + "\r\n")


def python_command(bin_dir, name, target, interpreter=None):
    # type: (Path, str, str, str) -> None
    """`target` is `-m module` or a script path, already quoted."""
    py = fwd(interpreter or sys.executable)
    make_command(bin_dir, name, f'exec "{py}" {target} "$@"', f'"{py}" {target} %*')


def make_bin(bin_dir):
    # type: (Path) -> Path
    bin_dir.mkdir(parents=True, exist_ok=True)
    for name, module in CONSOLE_SCRIPTS.items():
        python_command(bin_dir, name, "-m " + module)
    return bin_dir


class Sandbox:
    """A repository, an isolated environment, and the shims installed.

    Every location the package reads outside the repository points into
    the test's own directory: term lists above all."""

    def __init__(self, root):
        # type: (Path) -> None
        self.root = root
        self.home = root / "home"
        self.home.mkdir(parents=True, exist_ok=True)
        self.bin = make_bin(root / "bin")
        self.config_home = root / "xdg-config"
        env = {k: v for k, v in os.environ.items() if k not in _ISOLATE}
        env.update(
            {
                "PATH": os.pathsep.join([str(self.bin), os.environ.get("PATH", "")]),
                "PYTHONPATH": os.pathsep.join([SRC_ROOT, os.environ.get("PYTHONPATH", "")]),
                "HOME": str(self.home),
                "GIT_CONFIG_NOSYSTEM": "1",
                "XDG_CONFIG_HOME": str(self.config_home),
                "XDG_CONFIG_DIRS": str(root / "xdg-config-dirs"),
                "GIT_HYGIENE_WALK_TO": str(root),
                "GIT_AUTHOR_NAME": "Test",
                "GIT_AUTHOR_EMAIL": "test@example.invalid",
                "GIT_COMMITTER_NAME": "Test",
                "GIT_COMMITTER_EMAIL": "test@example.invalid",
            }
        )
        self.env = env
        self.repo = self.new_repo(root / "repo")

    def new_repo(self, path):
        # type: (Path) -> Path
        path.mkdir(parents=True, exist_ok=True)
        self.git("init", "-q", cwd=path)
        self.git("config", "commit.gpgsign", "false", cwd=path)
        return path

    def git(self, *args, cwd=None):
        # type: (str, Path) -> subprocess.CompletedProcess[str]
        return run(["git"] + list(args), cwd or self.repo, self.env)

    def tool(self, name, *args, cwd=None, extra_env=None):
        # type: (str, str, Path, dict) -> subprocess.CompletedProcess[str]
        env = dict(self.env)
        env.update(extra_env or {})
        module = CONSOLE_SCRIPTS[name]
        return run([sys.executable, "-m", module] + list(args), cwd or self.repo, env)

    def install(self, repo=None):
        # type: (Path) -> subprocess.CompletedProcess[str]
        r = self.tool("install-hooks", str(repo or self.repo))
        assert r.returncode == 0, r.stdout + r.stderr
        return r

    def commit(self, message="a commit", *extra, cwd=None, extra_env=None):
        # type: (str, str, Path, dict) -> subprocess.CompletedProcess[str]
        env = dict(self.env)
        env.update(extra_env or {})
        return run(["git", "commit", "-q", "-m", message] + list(extra), cwd or self.repo, env)

    def stage(self, rel, text, cwd=None):
        # type: (str, str, Path) -> Path
        repo = cwd or self.repo
        path = write(repo / rel, text)
        r = self.git("add", "--", rel, cwd=repo)
        assert r.returncode == 0, r.stderr
        return path

    def head_count(self, cwd=None):
        # type: (Path) -> int
        r = self.git("rev-list", "--count", "HEAD", cwd=cwd)
        return int(r.stdout.strip()) if r.returncode == 0 else 0

    def private_terms(self, text, cwd=None):
        # type: (str, Path) -> Path
        return write((cwd or self.repo) / ".git" / "info" / "deny-terms", text)
