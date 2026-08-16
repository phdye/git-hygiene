"""Install git-hygiene's hooks directly into a repository's
`.git/hooks/`, with no `pre-commit` framework involved.

Exists because `pre-commit` 4.6.2 cannot run under git 2.21 (it calls
`git ls-files -z --deduplicate`, which arrived in git 2.31), and git
2.21 is this project's own floor, matching RHEL 8.10. See
`a/doc/rejected-pre-commit-git-2.21-backport.md` for why that gap is
patched here rather than in `pre-commit` itself. Consumers on a newer
git keep the framework path documented in README.md; this is the path
for the floor, and it is required there, not a convenience.

Each installed hook is a short POSIX shell shim that calls this
package's own console scripts (`check-identifiers`), found on PATH
exactly as the framework path already requires. Nothing here
duplicates the scanning logic, so a fix to `check-identifiers` reaches
both fronts the moment the environment is reinstalled.

Idempotent by reseeding: every run rewrites a hook file from a fixed
template rather than editing it in place, so a stale line from an
earlier version of this installer cannot survive an upgrade. A hook
file that does not carry this installer's marker comment is assumed to
belong to someone else and is left alone unless --force is given.
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional

from .terms import git

MARKER = "# managed-by: git-hygiene install-hooks -- do not edit; reinstall to update"

_TEMPLATE = """#!/usr/bin/env bash
{marker}
if ! command -v check-identifiers >/dev/null 2>&1; then
    echo "git-hygiene: check-identifiers not found on PATH; hook cannot run" >&2
    echo "git-hygiene: activate the environment it was installed into, or reinstall" >&2
    exit 1
fi
exec check-identifiers {args}
"""

# One shim per git hook stage this project covers. commit-msg receives
# the message file path as $1 - that is git's own calling convention,
# not something this tool invents.
HOOKS: Dict[str, str] = {
    "pre-commit": "--staged",
    "commit-msg": '--message "$1"',
}


class Result(NamedTuple):
    line: str
    ok: bool


def git_dir(repo: Path) -> Optional[Path]:
    """The repository's git directory, resolved the way git itself
    would - so a worktree or a repo found via .primary-style symlinks
    lands on the right hooks/ regardless of where .git points."""
    out = git("rev-parse", "--git-dir", cwd=repo)
    if out.returncode != 0:
        return None
    rel = out.stdout.decode("utf-8", "replace").strip()
    if not rel:
        return None
    path = Path(rel)
    return path if path.is_absolute() else repo / path


def render(hook_name: str) -> str:
    return _TEMPLATE.format(marker=MARKER, args=HOOKS[hook_name])


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
    target.write_text(render(hook_name), encoding="utf-8")
    target.chmod(0o755)
    return Result(f"wrote   {hook_name}", True)


def uninstall_one(hooks_dir: Path, hook_name: str, dry_run: bool) -> Result:
    target = hooks_dir / hook_name
    if not target.is_file() or not owned_by_us(target):
        return Result(f"skip    {hook_name}  (not managed by git-hygiene)", True)
    if dry_run:
        return Result(f"remove  {hook_name}  (dry run)", True)
    target.unlink()
    return Result(f"removed {hook_name}", True)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Install git-hygiene's pre-commit and commit-msg hooks directly "
            "into .git/hooks - no pre-commit framework, no git floor above 2.21."
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
        help="remove git-hygiene-managed hooks instead of installing them",
    )
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    dir_for_hooks = git_dir(repo)
    if dir_for_hooks is None:
        sys.stderr.write(f"{repo}: not a git repository (or git not on PATH)\n")
        return 1
    hooks_dir = dir_for_hooks / "hooks"

    results: List[Result] = []
    for hook_name in HOOKS:
        if args.uninstall:
            results.append(uninstall_one(hooks_dir, hook_name, args.dry_run))
        else:
            results.append(install_one(hooks_dir, hook_name, args.force, args.dry_run))

    for result in results:
        print(result.line)

    return 0 if all(r.ok for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
