# 0016. pre-commit is the hook front end

Date: 2026-09-16
Status: accepted, implemented 2026-09-16; supersedes 0012

## Context

[0012](0012-one-front-end-dispatches-every-check.md) built a dispatcher,
`git-hygiene run <hook>`, with a check registry, layered settings and a
five-code exit contract. It turned the `pre-commit` framework down because
its current release needs Python 3.10 and because it could not tell a
required check from an optional one.

Neither reason held once measured. `pre-commit` 2.17.0 installs on Python
3.6.9 and runs these hooks on the RHEL 8.10 replica, given the build pins of
[0013](0013-build-tools-run-at-the-floor.md) and the manifest minimum of
[0015](0015-hooks-admit-pre-commit-2-17.md). A check can carry its own
requirement as an argument. The dispatcher had not been released.
The argument is in
[the pre-commit front-end proposal](../../proposal/2026-09-16.pre-commit-front-end.md).

## Decision

The framework composes, orders and runs every check. The dispatcher, its
registry, declaration files, settings files (`.git-hygiene`,
`.git/info/git-hygiene`), the `git-hygiene` command and
`check-identifiers --exit-contract` are removed.

`check-identifiers` gains `--require-private`, `--no-require-private` and
`GIT_HYGIENE_REQUIRE_PRIVATE`. `normalize-file-modes` gains the hook id of the
same name and sets the working file's mode as well as the index's.
`install-hooks` writes the direct shims of `v0.1.0` again, as the path for a
host with no framework, and removes any other shim carrying its marker.

A repository's `.pre-commit-config.yaml` may name any command, and this
project accepts that model.

## Why

Battle-tested, tier 4. Correctness did not separate the candidates once the
floor and the mode fix were measured, and neither did reliability or
robustness. Between a widely used framework and one this project would
maintain alone, the used one wins, with less code to carry.

The mode fix was measured on the replica on September 16, 2026, with
`pre-commit` 2.17.0, Python 3.6.9 and git 2.43.7
(`spike/pre-commit-at-floor`, `filemode_true_both_*`). Changing only the
index mode is refused once under `core.fileMode` true; setting the working
file too lands on the first commit, and a partly staged file keeps its
unstaged half.

Giving up the rule that tracked settings could name only installed checks
was the operator's call, made by accepting the proposal.

## Consequences

Checks from other tools become entries in a repository's
`.pre-commit-config.yaml`. The package no longer offers a per-clone settings
layer or a report of where a setting came from; the framework has one config
file per repository, which `pre-commit install --config` can point elsewhere.

A floor host needs `pre-commit` 2.17.0 and, for the manifest's
`language: python` hooks, a way to build the package: PyPI or a local
wheelhouse. A `repo: local` entry with `language: system` avoids the build.

The environment requirement applies to `deny-terms-msg` as well, so on a
machine that sets it every commit needs a private list, however little was
staged.

## Alternatives

Keeping the dispatcher, or running it as a single framework hook: both keep
all of its code. Requiring a current framework: excludes the floor. A fork
of a current framework backported to 3.6: the maintenance
[0008](0008-old-git-gets-native-hooks-not-a-patched-framework.md) declined,
enlarged. Native shims alone: nothing composes checks from different tools.
