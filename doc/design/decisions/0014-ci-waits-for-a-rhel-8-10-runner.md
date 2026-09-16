# 0014. CI waits for a RHEL 8.10 runner

Date: 2026-09-16
Status: accepted

## Context

The workflow in `.github/workflows/ci.yml` runs on `ubuntu-latest` across
Python 3.9 to 3.13. None of that is the platform these hooks are built for.
GitHub-hosted runners offer no Python 3.6, so every floor check has always
been a workstation job, and CI has been proving a range the project does
not ship to. A CI environment emulating RHEL 8.10 on Cygwin is planned.

## Decision

CI is not attempted until that environment exists. The workflow file stays
in the repository but no result from it counts as verification, and no
change is held back or shaped to keep it passing. Verification runs on the
RHEL 8.10 replica, as `Verification-Plan.md` describes.

## Why

A gate that runs somewhere the product does not is evidence about the
wrong thing, and keeping it green costs work that buys nothing for the
hosts that matter. [0013](0013-build-tools-run-at-the-floor.md) is the first
change whose effect on those runners was never measured.

## Consequences

The one run that ever proved `pre-commit try-repo` against this repository
was on CI, on August 16, 2026. That proof is now historical. The packaging
gate has to be re-established on the replica before the next tag.

This record is replaced, not amended, when the RHEL 8.10 runner is ready.
