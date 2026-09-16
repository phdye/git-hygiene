# 0001. Design documents live under `doc/design/`, with proposals beside it

Date: 2026-09-16
Status: accepted

## Context

Until now the README served as the design document, and everything else a
maintainer would want (why term sources are layered, why old git gets its own
hook installer, how the Python floor is proven) sat in untracked working
notes. A clone got the conclusions. It did not get the reasons. The first
tracked proposal, filed under `doc/design/proposal/`, had to ask in its own
open questions whether a tracked `doc/` was even the right home for it.

## Decision

`doc/design/` holds the specification: `Architecture.md` for what the
package is and `Verification-Plan.md` for how each claim is proven. Both are
kept current, amended in the commit that changes the behavior they describe.

`doc/design/decisions/` holds one record per settled question, numbered, with
`index.md` listing every record exactly once. Records are append-only; a
reversal is a new record that names the one it replaces.

`doc/proposal/` holds proposals, one per file, named
`<YYYY-MM-DD>.<topic>.md`, each opening with a status line. A proposal is
kept when abandoned and is not edited once accepted, except by a dated
addendum at its end.

The README stays the user's document.

## Why

A specification with no deltas loses the argument behind each choice, and a
pile of deltas makes every reader rebuild the present from its history. Both
are needed, split by role. The records exist so that the reasoning survives
in a clone, where the working notes never go.

Nesting records under `doc/design/` gives a design reader one directory to
open. The proposals sit beside it rather than inside because they describe
transitions, not the current design, and a reader of `doc/design/` should be
able to trust everything there as current.

## Consequences

The existing proposal moved from `doc/design/proposal/` to `doc/proposal/`.
Records 0002 to 0008 were written from decisions already made and already
implemented, dated on the day each was made. A test holds the index and the
record files one-to-one.

## Alternatives

A single `doc/design.md`. Adequate at this size, but it would mix the
architecture with the proof plan, which changes on its own schedule.

Leaving the README as the design document. It is written for someone
installing the hooks, and the reasoning a maintainer needs would either bury
that reader or stay untracked.

Keeping proposals at `doc/design/proposal/`. It put a document that may be
abandoned inside the directory meant to read as current.
