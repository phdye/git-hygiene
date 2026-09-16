# 0009. Every resolution error is fatal, and a refused private term stays unnamed

Date: 2026-09-16
Status: proposed; completes 0004
Settled by: the decision ladder, tier 1 (correctness)

## Context

Record 0004 said an unauthorized negation "is not silently dropped" but is
"an error naming both sources", and that a file holding both `term` and
`!term` "is an error". The `check-identifiers` docstring listed the first
among the hard errors that stop a check before it scans. The implementation
did something else. Both cases were appended to an error list without
setting the fatal flag, and the commands print that list only when
resolution is fatal. A refused negation therefore kept its term in force
while nobody was told, and a conflicting file contributed nothing, also
without a word outside `--explain`.

The same error list carried one more case: a term file that exists but
cannot be read.

## Decision

All three are fatal. The run stops before scanning and prints each error.

The message for a refused negation names both files. It names the term only
when `--show-private-terms` is in effect, and never under `--explain`.

## Why

Four candidates were considered: leave the behavior and document it; print
a warning and scan on; show the error in `--explain` alone; make it fatal.

The ladder settled it at tier 1. Correctness here is what record 0004
already accepted: the error must reach the person, and the class of failure
it guards against is a negation that appears to work and does not. Leaving
it silent fails that outright. A warning, or an `--explain`-only row, would
also reach the person, but either would be a different design from the one
accepted, and a fix does not get to redesign. Fatal is the one candidate that
matches both the record and the module's own documented contract.

The unreadable file falls under the same tier for a different reason. A list
that exists and contributes nothing, silently, is failure that reads as
success, the outcome record 0002 names as the worst available.

The term is withheld because a refused negation always cancels a term from a
private source, and record 0006 prints private terms only on request. The
public file that tried to cancel it does contain the word. Printing it,
though, would confirm that the word is on somebody's private list, which is
the disclosure 0004's class rule exists to prevent.

## Consequences

Exit semantics change for these inputs: a commit that used to pass now
fails. The project's policy makes that a major version. Version 0.2.0,
which introduced the behavior being corrected, has not been tagged, so the
fix lands inside it and no further increment is owed.

`resolve()` gained a `show_private_terms` argument, which affects error text
only. `--explain` now writes fatal errors to stderr after its table.
