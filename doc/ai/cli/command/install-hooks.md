# install-hooks

Read when: you need the checks as plain git hooks on a host without
`pre-commit`, or are removing hooks that `install-hooks` wrote.

Writes two shims into `<git dir>/hooks/`: `pre-commit` running
`check-identifiers --staged` and `commit-msg` running
`check-identifiers --message "$1"`. No framework is involved. File-mode
normalization and other tools' checks are not installed; they need the
framework.

    install-hooks [-f] [-n] [-u] [repo]

`repo` defaults to the current directory.

## Options

| Option | Meaning |
|---|---|
| `-h`, `--help` | print usage and exit 0 |
| `-f`, `--force` | overwrite a hook file this command did not write |
| `-n`, `--dry-run` | print what would change; write and remove nothing |
| `-u`, `--uninstall` | remove every hook file this command wrote, and nothing else |

## What it writes

Each shim starts `#!/usr/bin/env bash`, carries the marker line

    # managed-by: git-hygiene install-hooks -- do not edit; reinstall to update

and runs `check-identifiers` found on `PATH`. When the command is missing,
the shim prints two `git-hygiene:` lines and exits 1, so the commit is
refused. The package must be installed where the shim's `PATH` finds it.
Files are written as bytes with LF endings and mode 0755.

A run rewrites both shims from a fixed template and removes any other file
in the hooks directory that carries the marker. A file without the marker
belongs to someone else: it is skipped unless `--force`. Re-running is
safe.

The hooks directory is `hooks/` under the directory
`git rev-parse --git-dir` names. The command does not read
`core.hooksPath`.

## Exit status

| Code | Meaning |
|---|---|
| 0 | every hook written, rewritten, removed or already absent |
| 1 | not a git repository (or git not on `PATH`), or a foreign hook was skipped for want of `--force` |
| 2 | usage error |

## Output

One line per hook on stdout:

    wrote   pre-commit
    skip    commit-msg  (existing hook not managed by git-hygiene; use --force)
    create  pre-commit  (dry run)
    rewrite pre-commit  (dry run)
    removed pre-push  (no longer installed)
    remove  commit-msg  (dry run)

Outside a repository, stderr says `<path>: not a git repository (or git not
on PATH)`.

## Enforced and stated

Enforced by `tests/test_install_hooks.py`: both hooks written and
executable, idempotent reinstall, removal of a stale marked hook, dry run,
foreign hooks left alone, uninstall scope, the non-repository error, a real
commit blocked through the shim, and no carriage returns in the shims.
Stated from source only: the missing-command refusal and the ignoring of
`core.hooksPath`.
