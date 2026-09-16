"""Install git-hygiene's hook shims directly into a repository's
`.git/hooks/`, with no `pre-commit` framework involved.

Each installed hook is a short POSIX shell shim that runs
`git-hygiene run <hook>`, found on PATH, and hands it git's arguments.
The dispatcher decides which checks run (see dispatch.py); the shim holds
no logic, because it is the one file a package upgrade cannot replace.

A shim is written for pre-commit and commit-msg, which the package's own
checks use, and for every other hook a registered check declares.

Idempotent by reseeding: every run rewrites a hook file from a fixed
template rather than editing it in place, so a stale line from an
earlier version cannot survive an upgrade, and a shim this installer
wrote for a hook no longer in the set is removed. A hook file without
this installer's marker belongs to someone else and is left alone unless
--force is given.
"""

import argparse
import sys
from pathlib import Path
from typing import List, NamedTuple, Optional

from . import checks
from .gitconfig import ConfigError
from .terms import git_dir

MARKER = "# managed-by: git-hygiene install-hooks -- do not edit; reinstall to update"

_TEMPLATE = """#!/usr/bin/env bash
{marker}
if ! command -v git-hygiene >/dev/null 2>&1; then
    echo "git-hygiene: git-hygiene is not on PATH; the {hook} hook cannot run" >&2
    echo "git-hygiene: activate the environment it was installed into, or reinstall;" >&2
    echo "git-hygiene: refusing, since a check that did not run has not passed" >&2
    exit 1
fi
exec git-hygiene run {hook} "$@"
"""

BASE_HOOKS = ("pre-commit", "commit-msg")


class Result(NamedTuple):
    line: str
    ok: bool


def hook_names() -> List[str]:
    """The hooks to install: the package's own, plus any a registered
    check declares. Raises ConfigError on a bad declaration."""
    names = set(BASE_HOOKS)
    for check in checks.registry().values():
        names.update(check.hooks)
    return sorted(names)


def render(hook_name: str) -> str:
    return _TEMPLATE.format(marker=MARKER, hook=hook_name)


def owned_by_us(path: Path) -> bool:
    """True if nothing is there yet, or what is there is our own
    marker - i.e. safe to reseed without --force."""
    if not path.is_file():
        return True
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return MARKER in text


def install_one(hooks_dir: Path, hook_name: str, force: bool, dry_run: bool) -> Result:
    target = hooks_dir / hook_name
    if target.exists() and not owned_by_us(target) and not force:
        return Result(
            f"skip    {hook_name}  (existing hook not managed by git-hygiene; use --force)",
            False,
        )
    if dry_run:
        verb = "rewrite" if target.exists() else "create "
        return Result(f"{verb} {hook_name}  (dry run)", True)
    hooks_dir.mkdir(parents=True, exist_ok=True)
    # write_bytes, not write_text: write_text opens in text mode, so on
    # Windows every \n in _TEMPLATE becomes \r\n on disk. Cygwin bash
    # does not strip those, reads `fi\r` as a command name, and the
    # unclosed `if` fails with "syntax error: unexpected end of file" -
    # breaking every commit, clean or dirty. Path.write_text grew
    # newline= only in 3.10 and the floor is 3.6.8, so bytes is the
    # portable fix.
    target.write_bytes(render(hook_name).encode("utf-8"))
    target.chmod(0o755)
    return Result(f"wrote   {hook_name}", True)


def remove_one(hooks_dir: Path, hook_name: str, dry_run: bool, why: str = "") -> Result:
    target = hooks_dir / hook_name
    if not target.is_file() or not owned_by_us(target):
        return Result(f"skip    {hook_name}  (not managed by git-hygiene)", True)
    suffix = f"  ({why})" if why else ""
    if dry_run:
        return Result(f"remove  {hook_name}  (dry run){suffix}", True)
    target.unlink()
    return Result(f"removed {hook_name}{suffix}", True)


def managed_hooks(hooks_dir: Path) -> List[str]:
    if not hooks_dir.is_dir():
        return []
    return sorted(p.name for p in hooks_dir.iterdir() if p.is_file() and owned_by_us(p))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Install git-hygiene's hook shims directly into .git/hooks - no "
            "pre-commit framework. Each shim runs `git-hygiene run <hook>`."
        ),
    )
    parser.add_argument("repo", nargs="?", default=".", help="repository path (default: cwd)")
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="overwrite a hook that is not already managed by git-hygiene",
    )
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="print what would change; write nothing",
    )
    parser.add_argument(
        "-u",
        "--uninstall",
        action="store_true",
        help="remove every git-hygiene-managed hook instead of installing",
    )
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    dir_for_hooks = git_dir(repo)
    if dir_for_hooks is None:
        sys.stderr.write(f"{repo}: not a git repository (or git not on PATH)\n")
        return 1
    hooks_dir = dir_for_hooks / "hooks"

    results: List[Result] = []
    if args.uninstall:
        for name in managed_hooks(hooks_dir):
            results.append(remove_one(hooks_dir, name, args.dry_run))
    else:
        try:
            wanted = hook_names()
        except ConfigError as exc:
            sys.stderr.write(f"install-hooks: {exc}\n")
            return 2
        for name in wanted:
            results.append(install_one(hooks_dir, name, args.force, args.dry_run))
        for name in managed_hooks(hooks_dir):
            if name not in wanted:
                results.append(remove_one(hooks_dir, name, args.dry_run, "no check uses it"))

    for result in results:
        print(result.line)

    return 0 if all(r.ok for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
