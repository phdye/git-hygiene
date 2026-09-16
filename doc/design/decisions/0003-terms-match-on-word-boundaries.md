# 0003. Terms match case-insensitively on word boundaries

Date: 2026-08-16
Status: accepted

## Context

Many identifiers worth forbidding are short. Short strings turn up inside
ordinary words, in API names, everywhere.

## Decision

Each term compiles to `\b<escaped term>\b` with `re.IGNORECASE`. The term
is escaped, so it is matched literally; there is no pattern syntax in a term
file.

## Why

Substring matching fires on unrelated names. A guard that raises false
alarms gets bypassed or switched off, and then it protects nothing.

## Consequences

A term will not match when it is glued to other word characters, as in
`fooClient` for the term `client`, so a compound has to be listed as a term
of its own.

Tests hold the behavior. Changing it would alter exit semantics for every
consumer, which takes a major version.

## Alternatives

Plain substring search, rejected for the false positives above.
