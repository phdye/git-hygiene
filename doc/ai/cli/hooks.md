# Wiring the hooks into a repository

Read when: you are wiring the hooks into a repository (hook ids, `args:`,
`.pre-commit-config.yaml`), including on a Python 3.6 host or one without
`pre-commit`.

## The hook ids

Declared in the package's `.pre-commit-hooks.yaml`. Each is `language:
python` and declares `minimum_pre_commit_version: "2.17.0"`.

| Hook id | Stage | Entry | Notes |
|---|---|---|---|
| `deny-terms` | default (pre-commit) | `check-identifiers --staged` | `pass_filenames: false`, `always_run: true` |
| `deny-terms-msg` | `commit-msg` | `check-identifiers --message` | the framework appends the message file |
| `audit-tree` | `manual` | `audit-tree` | whole repository; run it before publishing |
| `normalize-file-modes` | default (pre-commit) | `normalize-file-modes` | `pass_filenames: false`, `always_run: true` |

## A typical configuration

```yaml
repos:
  - repo: https://github.com/phdye/git-hygiene
    rev: <tag>               # a tag, never a branch
    hooks:
      - id: deny-terms
      - id: deny-terms-msg
      - id: normalize-file-modes      # optional
```

Then `pre-commit install` and, for the message hook,
`pre-commit install --hook-type commit-msg`. Run the audit on demand with
`pre-commit run --hook-stage manual audit-tree`.

Options go in `args:` and are appended to the entry:

```yaml
      - id: deny-terms
        args: [--require-private]
```

Give `deny-terms-msg` the same `args:` if the message check should require
a private list too. The environment variables in
[environment.md](environment.md) reach the hooks from the committing shell.

## Installed but checking nothing

A missing list passes silently, and so does a consumer whose environment
lacks git-hygiene behind a hand-rolled wrapper. Assert somewhere loud that
the tool is installed (for example a CI step running
`check-identifiers --help`), and run `check-identifiers --staged --explain`
once on each machine to see which lists were found. Public CI has no
private list unless one is provisioned; the patterns are in
[../../ci-term-provisioning.md](../../ci-term-provisioning.md).

## Python 3.6 hosts

`pre-commit` 2.17.0 is the newest release that installs on Python 3.6, and
the hooks accept it. On first use per revision the framework builds this
package, which needs PyPI, or a local wheel directory named in
`PIP_FIND_LINKS` with `PIP_NO_INDEX=1`. A host with neither installs
git-hygiene once and names its commands directly:

```yaml
repos:
  - repo: local
    hooks:
      - id: deny-terms
        name: no engagement identifiers in content
        entry: check-identifiers --staged
        language: system
        pass_filenames: false
        always_run: true
```

## No framework at all

Install the package and run `install-hooks` in the clone. It writes plain
`pre-commit` and `commit-msg` shims that call `check-identifiers` from
`PATH`; see [command/install-hooks.md](command/install-hooks.md). The
shims start `#!/usr/bin/env bash`, so the host needs bash. `install-hooks`
writes no hook for file modes: run `normalize-file-modes` yourself in the
clone after staging, or call it from a hook you maintain; see
[command/normalize-file-modes.md](command/normalize-file-modes.md). That
use is stated, not tested: the suite runs the command directly and through
the framework, never from a hand-written hook.

## Enforced and stated

Enforced: the id list, the entries and the console-script names
(`tests/test_hooks.py`); this page's id table against the manifest
(`tests/test_doc_ai.py`); that `pre-commit try-repo` installs and runs the
hooks, refuses a planted private term without printing it, and honors the
requirement (`tests/test_packaging.py`, deselected by default and skipped
without `pre-commit` on `PATH`). Stated: the Python 3.6 guidance, which
rests on the spikes the design cites
([../../design/Verification-Plan.md](../../design/Verification-Plan.md)).
