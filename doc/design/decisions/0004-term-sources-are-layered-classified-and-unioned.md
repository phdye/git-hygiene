# 0004. Term sources are layered, classified, and merged by union

Date: 2026-08-16
Status: accepted, implemented in v0.2.0 (see 0005 for one deviation)

## Context

Version 0.1 read one file, `~/.config/git/deny-terms.txt`, or whatever
`GIT_DENY_TERMS` named. That had two problems.

Resolution was invisible. `Path.home()` differs between Windows Python and a
Cygwin shell, so the file was often not where its owner believed, and the
hook then found no terms and passed everything. The README's workaround was
a manual probe.

One file also forced every term into one scope. Consider a system-wide list
on a build host, a personal list for every repository under a directory, or
a list a team wants enforced on every clone: each has its own owner and
lifetime. They could not coexist.

Some lists are not secret at all: a retired product codename, a
decommissioned host name, a predecessor company's name. A team may want
those committed. Reviewing them with the code they protect is reasonable.

## Decision

Seven layers are consulted, lowest precedence first: a system file, the
personal file, `.deny-terms` and `.deny-terms.private` in ancestor
directories, the repository root's `.deny-terms`, `.git/info/deny-terms`,
`GIT_DENY_TERMS` (now a path list), and repeatable `--terms`. The table is in
`../Architecture.md`.

Every file is `public` or `private`, declared on its first line; an
undeclared file is private. A tracked private file is a fatal error. The
class also governs printing (record 0006).

Terms merge as a union. Nothing overrides. `!term` removes an inherited term only when the
negating source is at least as strict a class as the one that introduced it.
A file with both `term` and `!term` contributes nothing.

Resolution runs once per invocation, anchored at the work-tree root.
Ancestor and repository-root files are skipped on POSIX when world-writable
or owned by someone other than the user or root. `--explain` prints every
candidate with its class, status and term count, and never a term.

## Why

Whether a list may be committed is a property of its terms, which only its
author knows, so it is declared rather than inferred from location.
Defaulting to private is the safe direction and keeps every existing list
working.

Union rather than nearest-wins, because a deny term is a set member: a
narrower scope must not silently drop what a broader scope forbids. Negation
is the only way to reduce protection, so it carries the strictest rule. A
public file able to cancel a private term would publish the cancellation of
a term nobody else can see.

`--explain` replaces inference with observation for the question "did it
find my list".

## Consequences

`GIT_DENY_TERMS` gained list semantics, the silent pass became conditional,
and `scan_text` and `report` changed shape: a major version under this
project's policy. No hook id changed. No consumer had yet pinned a release,
which made the break nearly free at the time.

Every compiled pattern carries its source path and class, so a merged set
can print selectively.

The design intended an unauthorized negation to be a reported error. As
implemented it leaves the term in force but is not printed unless resolution
fails for another reason; `../Architecture.md` records the gap.

## Alternatives

Deepest-match-wins, as `.gitignore` resolves. Right for a boolean about one
path, wrong for a set that must only grow.

Classifying by location (inside a repository means public). Wrong in both
directions: a private list belongs in `.git/info/`, which is inside the
repository, and a public list may sit in a shared parent directory.

A `.local` suffix for private files. It names a scope, not secrecy, and a
name that does not say what it protects gets copied wrong.

Per-directory resolution. A deny term is a property of the repository, and
`audit-tree --objects` already reads every object individually; resolving
per path would multiply that cost for no question anyone asked.
