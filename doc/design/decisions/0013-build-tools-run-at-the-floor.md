# 0013. Build tools run at the floor

Date: 2026-09-16
Status: accepted

## Context

The first commit declared `setuptools>=61` and `setuptools_scm>=8` as build
requirements and put the package metadata in a `[project]` table. No reason
was recorded. Neither tool runs on Python 3.6: the newest releases that do are
setuptools 59.6.0 and setuptools_scm 6.4.2.

The floor checks never noticed. They import the code from `src/` and never
build the package, so "the code runs on 3.6.9" was proven while "the package
installs on 3.6.9" was not. When it was finally tried on the RHEL 8.10
replica, `pip` stopped with "No matching distribution found for
setuptools>=61.0". The same failure met `pre-commit` when it tried to build a
hook environment from this repository, and it met anyone following the
README's `pip install` on a 3.6 host.

## Decision

`[build-system]` pins setuptools 59.6.0, setuptools_scm 6.4.2 (with its
`toml` extra) and wheel 0.37.1. The metadata moves to `setup.cfg`, which that
setuptools reads; `pyproject.toml` keeps the build pins, the setuptools_scm
settings and the tool configuration.

## Why

Correctness settles it. A package that cannot be built on the hosts it
protects breaks the promise [0007](0007-python-floor-is-3-6-8.md) makes, and
no newer build tool can be configured into running on an interpreter it does
not support. `spike/build-at-floor` measured both candidates on the RHEL
8.10 replica (Python 3.6.9, git 2.43.7) on September 16, 2026. The original
requirements are refused there, because no setuptools>=61 release runs on
that interpreter. With the pins, the same interpreter builds a wheel and an
sdist that leaves out `spike/`, installs the wheel, the source tree and an
editable checkout, and each install runs all three console scripts, with the
version taken from git.

## Consequences

The build tools are old releases that get no fixes. They run only at build
time, and the package has no runtime dependencies, so nothing old is
installed beside it.

Whether these pins also build on current interpreters has not been
measured. Nothing tested today needs that (see
[0014](0014-ci-waits-for-a-rhel-8-10-runner.md)); it becomes a question
again when a newer interpreter joins the verified set.

A `[project]` table must not come back while the floor is 3.6. setuptools
59.6 ignores it, so metadata placed there would be dropped without an error.

The floor checks gain a third one: build and install the package at 3.6.
