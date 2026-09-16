# 0010. Every resolution setting has an environment variable and a negation

Date: 2026-09-16
Status: accepted; completes 0004 and 0006
Settled by: the decision ladder, tier 1 (correctness), with tier 3
(robustness) for malformed values and tier 7 (default) for the accepted
spellings

## Context

Record 0004's interface table gave three settings an environment variable
each: `GIT_HYGIENE_NO_INHERIT`, `GIT_HYGIENE_NO_WALK`, `GIT_HYGIENE_WALK_TO`.
Record 0006 named a fourth, `GIT_HYGIENE_SHOW_PRIVATE_TERMS`. None was
implemented; only the options existed.

## Decision

All four are read, the command line winning. So that a value set in the
environment can be turned off for one run, each boolean gains a negated
option: `--inherit`, `--walk`, `--no-show-private-terms`.

A boolean variable accepts `1`, `true`, `yes`, `on`, `0`, `false`, `no` and
`off`, case-insensitively. Empty is unset. Anything else is a usage error,
exit 2, naming the variable.

The shared options moved into one module, `options.py`, which both scanning
commands call.

## Why

Two candidates: implement the variables, or amend the design to drop them.

Tier 1 settled it. The accepted records name the variables, and the
project's command-line conventions require every setting to be reachable
both ways. Dropping them would redesign rather than fix. The same
conventions require a negated spelling for any boolean the environment can
set; without one, the precedence chain has a hole.

For a value that is neither true nor false, tier 3 applies. Reading an
unknown value as false would let a typo in `GIT_HYGIENE_SHOW_PRIVATE_TERMS`
pass unnoticed, and a typo in `GIT_HYGIENE_NO_WALK` quietly change which
lists load. A defined refusal is the robust behavior.

No tier above 7 separated the spellings. The eight accepted words are the
common set.

## Consequences

Adding options and variables is a minor change under the project's policy.
`--no-show-terms` keeps no variable and no negation. The project's
conventions would give it both, record 0004 gave it neither, and the ladder
could not choose between them; the operator affirmed 0004 on 2026-09-16.
It is the one deliberate exception to the rule above.
