# Limits and security surface

Read when: you are deciding how far to trust a pass, running git-hygiene
under Windows or Cygwin, or reviewing what a repository's hook
configuration can make a commit run.

## What a pass does not prove

- The commit hooks see staged changes only. Anything already committed is
  found only by `audit-tree`, and history only by `audit-tree --objects`.
- Removing a term from the working tree leaves it in history until the
  history is rewritten and the old objects are expired and pruned.
- A run with no term resolved passes. So does a machine without the
  package behind a wrapper that tolerates its absence.
- Matching is literal, on word boundaries. Spelling variants, encodings
  and substrings inside longer words are not matched.
- The trust check on shared-directory lists does not run under Windows
  Python.

## Cost

`audit-tree --objects` runs one `git cat-file -p` per object, trees and
commits included, and decodes binaries as text. Its cost on a large
history has not been measured.

## Paths across interpreters

The work-tree root comes from `git rev-parse --show-cdup`, joined onto the
interpreter's own directory, so a Cygwin git and a native Windows Python
agree on where the repository is. The user list comes from `Path.home()`,
which under Windows Python is the user profile rather than a Cygwin
shell's `~`; a list placed in the wrong home is not found and the check
passes. Set `XDG_CONFIG_HOME` or `GIT_DENY_TERMS` and confirm with
`--explain`.

## What runs at commit time

A repository's `.pre-commit-config.yaml` decides what runs, and a
`repo: local` entry can name any command. Nothing runs until
`pre-commit install` has been run in the clone; after that, a pull that
changes the file changes what the next commit runs. Pin `rev:` to tags and
read changes to that file. The shims `install-hooks` writes run whatever
`check-identifiers` `PATH` finds first.

## Supported

Python 3.6.8 and newer. `pre-commit` 2.17.0 and newer. The git commands
used are long-established; the tested git is 2.43.7. The full list and how
each property is proven are in
[../../design/Architecture.md](../../design/Architecture.md) and
[../../design/Verification-Plan.md](../../design/Verification-Plan.md).

## Enforced and stated

Enforced: the orphaned blob found only by `--objects`
(`tests/test_end_to_end.py`); interpreter-safe root and git-dir paths
(`tests/test_path_conventions.py`). Stated: the cost, the security posture
and the supported versions, which rest on the design documents and on runs
outside this suite.
