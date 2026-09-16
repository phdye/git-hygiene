# 0015. The hooks admit pre-commit 2.17.0

Date: 2026-09-16
Status: accepted

## Context

Every hook in `.pre-commit-hooks.yaml` declared
`minimum_pre_commit_version: "3.2.0"` from the first commit, with no reason
recorded. The manifest uses no feature that needs it: its only stage names,
`commit-msg` and `manual`, both exist in 2.17.0.

pre-commit 2.17.0 is the newest release that installs on Python 3.6; 2.18.0
requires 3.7. The `--deduplicate` call behind
[0008](0008-old-git-gets-native-hooks-not-a-patched-framework.md) arrived
only in 4.6.1, so 2.17.0 has no git requirement that git 2.43.7 misses.

## Decision

The minimum is 2.17.0 for all three hooks.

## Why

Measured by `spike/build-at-floor` and `spike/pre-commit-at-floor` on the
RHEL 8.10 replica (Python 3.6.9, git 2.43.7) on September 16, 2026, with
both candidates run through `pre-commit try-repo` against the same commit.
With 3.2.0 the framework refuses the hook before running it. With 2.17.0 a
clean file passes and a planted term is blocked by the hook, which shows it
ran. That needed the build pins of
[0013](0013-build-tools-run-at-the-floor.md), since the framework builds the
hook environment from this repository.

Correctness decides it. The 3.2.0 value is not a correct claim for a
consumer at the floor, where no 3.2.0 exists. A value below 2.17.0 would claim
support for releases nobody has run these hooks under, so the lowest
measured release is the one the manifest can state truthfully.

## Consequences

The framework path now works on a RHEL 8.10 host, provided pre-commit 2.17.0
is installed there, and the packaging gate can run on the replica.

Raising the minimum again is a compatibility break for those hosts and takes
a major version.
