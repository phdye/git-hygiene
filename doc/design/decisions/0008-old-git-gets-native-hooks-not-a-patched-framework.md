# 0008. Old git gets native hooks, not a patched framework

Date: 2026-08-16
Status: accepted

## Context

`pre-commit` 4.6.2 calls `git ls-files -z --deduplicate`, a flag added in
git 2.31. On older git, the framework fails before any hook runs. This
package's own git calls are far older and work on 2.21.

Four options were on the table: pin an old `pre-commit`; ship plain git
hooks calling the console scripts; run `audit-tree` by hand on old-git
hosts; or run the hooks only where git is modern.

At first the problem looked urgent. The test environment then carried git
2.21, and that was mistaken for the RHEL 8.10 floor. RHEL 8.10 in fact ships
git 2.43. Nothing below depends on the version.

## Decision

`install-hooks` writes `pre-commit` and `commit-msg` shims into
`.git/hooks/`, and each shim calls `check-identifiers` directly. That path
serves git older than 2.31, as well as hosts where the framework cannot be
installed. Where the framework runs, it stays the documented first choice.

The framework is not patched.

## Why

Patching would work, at first. An order-preserving deduplication of
`ls-files -z` output matched `--deduplicate` byte for byte on a real
three-stage merge conflict, and a survey of roughly forty git calls in
`pre-commit` 4.6.2 found no other call newer than 2.21.

That survey, however, covers one release. Every upgrade would need it
repeated. Worse, a patch that quietly stopped matching the tool beneath it
would leave a hook that appears to run, which is failure reading as
success, the outcome this project exists to prevent.

Native shims give the same protection through git's own hook mechanism.
There is no framework to track.

## Consequences

Native hooks lose the framework's environment isolation, and its
`autoupdate` too. `check-identifiers` must be on `PATH` wherever the shim
runs; when it is not, the shim says so and refuses.

One condition reopens this: a consumer who needs the framework itself and
cannot leave git older than 2.31. Then the least bad patch replaces the
framework's file-listing function in process, pinned to one exact framework
version, with the survey repeated and a loud failure if the function has
moved.

## Alternatives

A `git` wrapper earlier on `PATH`. It changes git for every process that
inherits that `PATH`, and a Windows interpreter, going through
`CreateProcess`, will not run a shell-script wrapper at all.

A `sitecustomize.py` patch. It is scoped to one process, but it couples to a
private function and goes inert, without warning, if that function is
renamed.

A vendored, pinned fork. Inspectable, yes; also a fork of someone else's
tool to maintain.

Pinning an old `pre-commit`. It lasts only until some other new-git
requirement appears.
