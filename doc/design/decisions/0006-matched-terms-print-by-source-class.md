# 0006. A matched term is printed when its source is public

Date: 2026-08-16
Status: accepted; supersedes the v0.1 rule that no term is ever printed

## Context

Version 0.1 reported a file and line, never the matched term. Printing it
would copy the identifier into scrollback, CI logs, and pasted error
reports.

Record 0004 then introduced public lists, and the old rule started hiding
terms that sit, tracked, in the same checkout. The cost showed most in
object audits. A hit such as `object 3f9a2c1b0e:12` names a blob that cannot
be opened by path; without the term, the reader searches the list by hand.

## Decision

A term from a public source is printed by default, after the location. A
term from a private source is withheld unless `--show-private-terms` is
given. `--no-show-terms` suppresses both. `--explain`, whatever the flags,
prints no term at all.

## Why

A report nobody can act on is a poor report. Printing a public term
discloses nothing the checkout does not already hold.

Private terms stay hidden by default, because the default should be the
cautious one. An operator may still ask to see them. Where that output goes,
and how long it is kept, is the operator's call rather than the tool's.

What the tool does enforce is narrower: a private term never becomes a
commit. A saved transcript containing one fails the hook like any other
leak. The guarantee concerns repositories, not screens.

`--explain` is excluded outright. Its output is what people paste when they
ask why a hook did or did not fire.

## Consequences

Each hit carries its pattern's source and class, so the reporter decides
hit by hit. The design also named an environment variable,
`GIT_HYGIENE_SHOW_PRIVATE_TERMS`, for the flag. It is not implemented.

## Alternatives

Keeping the v0.1 rule for every class. Rejected for the cost above.

## Addendum, 2026-09-16

The environment variable is implemented; see 0010.
