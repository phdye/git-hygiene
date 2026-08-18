# Blockers to consuming this package as a dependency

**Found, not fixed.** Recorded 2026-08-16 by the `azdo` session, which
evaluated replacing its own duplicated copy of the deny-term check with a
dependency on this package and concluded it cannot yet. Written here rather
than in the consumer because every item is a property of this repository.

`azdo` currently carries `scripts/check-identifiers.py`, a copy taken before
this package gained its 3.6.8 floor and its native front end. It is already
stale, which is the argument for consuming rather than vendoring: one copy,
one day, and it had drifted. The intent is to delete it. What follows is what
stands in the way.

## Hard blockers

### 1. No remote

There is no remote configured. Both consumption mechanisms need a fetchable
URL:

- `pre-commit`'s `repo:` + `rev:` wants a git URL it can clone.
- A `pyproject.toml` dev extra wants `git-hygiene @ git+https://...@tag`.

A `file:///` path works on one machine and breaks for every other clone. A
consumer that is itself intended to be public cannot carry a dependency that
only resolves on its author's workstation.

**Resolves when:** this repository is pushed somewhere fetchable and a tag is
pushed with it.

### 2. The native front end is currently broken

`install-hooks` writes CRLF line endings, so every hook it installs fails
under Cygwin bash before running anything. See
`a/issue/install-hooks-writes-crlf.md`. Since the native front end is the
only consumption path available below git 2.31, adopting this package today
would replace a working stale copy with a non-working current one.

**Resolves when:** that issue is fixed and verified under Cygwin bash
specifically, not only under Git for Windows' bash, which tolerates CRLF.

### 3. The idiomatic mechanism is unavailable where the work happens

`pre-commit` 4.6.2 invokes `git ls-files -z --deduplicate`, which arrived in
git 2.31. The rhel root is pinned at git 2.21 by design. So `repo:`/`rev:` -
the mechanism a hooks repository exists to be consumed through - cannot run
there at all, and that is not a git-hygiene defect; see
`a/doc/rejected-pre-commit-git-2.21-backport.md`.

Consumption must therefore be a dev dependency plus `install-hooks`, which
makes item 2 load bearing rather than incidental.

**Resolves when:** nothing here. This is a permanent constraint of the
environment, and the native front end is the accepted answer to it.

### 4. Nothing is published, and the interface has already broken once

`v0.1.0` is the only tag, and the commits after it include a `feat!` -
layered, classified term resolution - which changes behavior a consumer would
pin against. A consumer needs a tag it can rely on, and hook ids plus the
term-file contract are the public API. Pinning `v0.1.0` today would pin a
revision that predates the front end the consumer actually needs.

**Resolves when:** a tag exists that includes the front end, the CRLF fix,
and whatever the resolution rework settles into, with the API surface stated.

## Disinclinations, not blockers

These would not stop adoption but should be settled before it, because each
is easier to get right at the point of adoption than afterwards.

### 5. A missing dependency fails silently, exactly like a missing term file

Silence when no term file is present is deliberate and correct - a
contributor without one must not be blocked. But it means a dependency that
is absent, unimportable, or broken produces the same silence. The consumer's
guard would then fail open, quietly, in precisely the way that let the
original leak through and motivated this package.

Vendoring has the same failure mode, so this does not favor either option.
It does argue that a consumer should assert the tool is importable somewhere
loud - a one-line CI step - so that absence is noisy even though a missing
term list is not.

### 6. CI cannot exercise the check the consumer most wants exercised

Term lists are deliberately local and unpublished, so a public consumer's CI
has no list to check against and the hook passes vacuously there. That is the
correct behavior and still leaves the consumer's strongest gate - the one
that runs where the code is published from - unable to catch anything.
`a/doc/ci-term-provisioning.md` addresses this; whichever approach it settles
on needs to exist and be documented before a consumer relies on CI for this.

### 7. The consumer's own hook framework does not run locally either

`azdo` has a `.pre-commit-config.yaml` covering lint, type checking and
secret scanning, and it fails on the same git 2.31 requirement as everything
else - meaning it has likely never executed on the machine where the work
happens. Adopting `install-hooks` for the deny-term check alone would leave
that unchanged and slightly obscure it, since the repository would then have
one working native hook and a framework config that does not run.

Not this package's problem to solve, but a consumer deciding to adopt the
native front end should decide at the same time what happens to the rest of
its hooks. Recorded here because the decision surfaces during adoption.

## What adoption looks like once these clear

In one commit, in the consumer: add the dependency pinned to a tag, delete
the duplicated script and its local hook entry, run `install-hooks`, and add
the importability assertion from item 5. Doing it before items 1, 2 and 4
clear trades a working copy for a broken dependency.
