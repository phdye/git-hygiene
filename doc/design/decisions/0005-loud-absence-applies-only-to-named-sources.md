# 0005. A missing public source is fatal only when it was named

Date: 2026-08-16
Status: accepted; amends 0004

## Context

Record 0004 said a public term source that does not exist should fail
loudly: a public list ships with its repository, so its absence means
something is broken. Written that way, though, the rule reaches the probed
repository-root `.deny-terms`. Nearly every repository lacks one. Every
commit in every one of them would fail.

## Decision

Absence is fatal for a source the operator named, through `--terms` or
`GIT_DENY_TERMS`, when its filename is `.deny-terms`. The name is the only
evidence available. A directive cannot be read from a file that is not
there. Probed layers stay silent when absent, whatever they are called.

## Why

Record 0002 says a check the user cannot see must not block their work;
failing every repository without a team list would break that. A named
source is different. Someone expected it, and its absence is a configuration
error worth stopping for.

## Consequences

A named path that is missing and is not called `.deny-terms` is skipped
silently. `tests/test_resolution.py` covers the fatal case and the silent
one.

## Alternatives

The rule as 0004 wrote it. Rejected, for the reason above.
