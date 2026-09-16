# 0002. Term lists live outside the repository, and their absence passes

Date: 2026-08-16
Status: accepted

## Context

The package exists because of a leak. A client organization name and a
project name sat in a sibling package's test fixtures from its first commit
until an audit found them, shortly before publication. A written rule
against client identifiers had been in place the whole time.

A mechanical check needs the forbidden terms. That is the difficulty:
wherever they are stored, they are exactly what is being protected.

## Decision

The code names no terms. No term list, sample list or example file is
bundled, whatever it contains; loading a list from inside the package is
the mistake, independent of the list's content. Terms are read from files
the operator places, by default `~/.config/git/deny-terms.txt`.

When no term resolves, `check-identifiers` exits 0. It prints nothing.

## Why

A denylist committed to a public repository publishes what it conceals.
Keep them apart, and the code becomes publishable.

The silent pass follows from the same split. Someone who clones a public
repository that uses these hooks will not have the maintainer's list. A
check they cannot see, and cannot satisfy, must not block their commits. The
hooks are a safety net on the maintainer's machine, not a project
requirement.

## Consequences

A misplaced list fails open: the hook finds nothing and passes. That is the
worst failure a check like this can have, and later work exists to make it
observable rather than to make it loud (`--explain`, record 0004).

Record 0004 later allowed a list to be committed when it declares itself
public. That refines this decision rather than reversing it: the package
still ships no terms, and a private list may never be tracked.

## Alternatives

A bundled example list. Rejected even when harmless, because it teaches the
pattern of keeping terms beside the code.

Failing when no list exists. Rejected: it would block every contributor
who is not the maintainer.
