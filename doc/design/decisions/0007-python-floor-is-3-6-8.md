# 0007. The Python floor is 3.6.8

Date: 2026-08-16
Status: accepted

## Context

The hooks must run on the machines they protect. Some of those are RHEL
8.10 hosts, where the newest interpreter is the system `python3`, version
3.6.8.

## Decision

`requires-python = ">=3.6.8"`. Source and tests are both written for it,
which rules out several things: `from __future__ import annotations`, PEP
585 and 604 generics at runtime, `dataclasses`, and
`subprocess.run(capture_output=...)`. Records are `typing.NamedTuple`.
Annotations naming `typing.Pattern` sit under `if TYPE_CHECKING:`, since
`re.Pattern` first appeared in 3.8 while `typing.Pattern` was removed in
3.12.

There are no runtime dependencies.

## Why

A published floor is a promise. Here, the oldest host the hooks must run on
sets it; anything higher leaves that host unprotected.

## Consequences

The development tools cannot check this floor. Ruff targets 3.7 at the
oldest, so one of its upgrade rules is suppressed on the single line where
it misfires. Current mypy refuses any target below 3.10; CI therefore
type-checks for 3.10 on Linux, and an older mypy checks the floor on a
workstation. No CI runner offers 3.6. `Verification-Plan.md` gives the two
checks that hold the floor instead.

## Alternatives

None were written down.
