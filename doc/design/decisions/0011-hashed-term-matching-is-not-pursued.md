# 0011. Hashed term matching is not pursued

Date: 2026-09-16
Status: accepted

## Context

A draft proposal of August 16, 2026, sketched matching salted hashes of terms
instead of plaintext, so that a CI runner would never hold a private list. It
was marked as deliberately not started and kept surfacing as an open question
in the architecture document.

## Decision

The idea is withdrawn. The proposal moves to `doc/proposal/retired/` and the
open question is removed. CI provisioning stays with the plaintext patterns in
`doc/ci-term-provisioning.md`.

## Why

It buys little. The terms worth hiding are short and guessable, so a salt
that leaks turns every hash back into its term by trial, and the salt has to
reach the runner through one of the plaintext patterns anyway. It also costs
real behavior: multi-word terms match as phrases today and do not split into
independently hashable tokens, and `--show-private-terms` could not print a
term that was never read, which breaks the promise in
[0006](0006-matched-terms-print-by-source-class.md). No consumer has asked
for it.

## Consequences

A CI provider is trusted with a private list for the length of one job. That
is the stated boundary, not an oversight.

One condition reopens this: a consumer who cannot trust its provider's secret
store and asks for the capability. A new proposal starts from the retired one
rather than reviving it in place.
