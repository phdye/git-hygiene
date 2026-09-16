# Term files

A term file is a list of the identifiers this tool refuses to let into a
repository. One term per line, blank lines and `#` comments ignored, matched
case-insensitively on word boundaries so that a term like `atlas` catches
`ATLAS` but not `atlas_client`.

Everything the tool does follows from two questions about such a file: where it
sits, and whether it may be committed. This document answers both. For the
normative rules, including the full precedence table and the exact behavior of
each setting, see [design/Architecture.md](design/Architecture.md). For getting
a private list to a CI runner, see
[ci-term-provisioning.md](ci-term-provisioning.md).

## The two kinds

Whether a list may be committed is a property of the terms, which only the
author knows, so the author says it by naming the file. A file called
`.deny-terms` is public. A file called `.deny-terms.private` is private, and so
is the system file, your personal file, and the one under `.git/info/`, because
of where they live. Any other name you hand to `--terms` or `GIT_DENY_TERMS` is
private too. Nothing inside the file changes its class, so `ls`, `git status`
and `.gitignore` all see the same answer the tool does.

A first line of `# git-hygiene: public` or `# git-hygiene: private` is still
allowed, as documentation. It has to agree with the name. If it does not, the
tool stops and names the file and both claims rather than picking one.

A **public** list holds identifiers that are safe to read. A retired product
codename, a decommissioned hostname, the name of a company before an
acquisition: all worth blocking, none secret. A team wants these enforced on
every clone, so the list belongs in the repository, reviewed and versioned
alongside the code it protects.

A **private** list holds identifiers that are themselves sensitive. Committing
one publishes exactly what it conceals, which is the failure this project
exists to prevent. Such a list is never tracked, and the tool treats a tracked
private file as fatal rather than as a warning.

## What the class changes

The class is not a label. Three behaviors depend on it, and each has no single
answer that is right for both kinds.

A tracked file is expected of a public list and fatal for a private one. A
matched term is printed for a public source, since the term already sits in a
file the reader has checked out, and withheld for a private source unless the
caller passes `--show-private-terms`. An absent file is silently skipped when
private, because a contributor cloning a public repository will not have one
and a check they cannot see must never block their work.

Absence is the subtle one. A named source that is missing and called
`.deny-terms`, a name that implies public, is fatal, because such a file ships
with the repository and its absence means something is broken. The probed
repository-root layer is exempt, since nearly no repository has one and making
it fatal would block every commit everywhere
([0005](design/decisions/0005-loud-absence-applies-only-to-named-sources.md)).

## Choosing a location

Six places are consulted and their contents merged as a union, so a narrower
scope never silently drops what a broader scope forbids. The full table is in
Architecture; what follows is how to pick.

For a list that everyone working in one repository should share, and that is
safe to publish, put `.deny-terms` at the repository root and commit it. A team
list is never checked against itself, since it naturally contains the terms it
forbids. It is checked against every other list, though, so a private term
pasted into it by mistake still refuses the commit, without being printed.

For a private list covering one clone, use `<git dir>/info/deny-terms`. Nothing
inside `.git/` can be committed, so the guarantee is structural rather than a
matter of remembering.

For a private list at the top of one working tree, `.deny-terms.private` at the
repository root works as well, provided the ignore rule below is in place.

For a private list spanning many repositories under one directory, use
`.deny-terms.private` in a common ancestor. The walk collects it from every
parent up to the stopping boundary, outermost first. This and the root-level
file are the cases where a private list sits in an ordinary directory rather
than inside `.git/`, so they are the ones that need the ignore rule below.

For a list belonging to one person across everything they do, use
`~/.config/git/deny-terms.txt`, honoring `$XDG_CONFIG_HOME` when set. For a
list belonging to a machine, such as a shared build host,
`/etc/git-hygiene/deny-terms`.

For a single run, name the file with `--terms` or `GIT_DENY_TERMS`. Both accept
several paths and both take precedence over everything probed.

## Keeping a private list out of the index

A private list in a working tree is one `git add -A` away from being committed,
and the tool's own check fires only once the file is already staged. Ignore it
by name. This repository's `.gitignore` carries:

    .deny-terms.private

with the public `.deny-terms` deliberately absent from the list, since that one
is meant to be committed. Any repository where someone might place a private
ancestor list wants the same rule. Note that a pattern written for the older
`deny-terms.txt` convention will not match `.deny-terms.private`, because it
has no `.txt` suffix. That gap existed in this repository until it was found
and closed, which is the reason this section exists.

## Merging, and the one way to remove a term

Layers accumulate. A term introduced anywhere applies everywhere below it, and
the only way to take one back is a negation, written `!term`.

A negation is honored only if it comes from a layer at least as broad as the
one that introduced the term, and from a source at least as strict in class. A
public file therefore cannot cancel a term a private file introduced. Without
that rule, a committed list could disable a secret one, and the cancellation
would be readable by everyone while the term it cancelled was not. An
unauthorized negation is an error naming both sources rather than a line that
quietly does nothing
([0004](design/decisions/0004-term-sources-are-layered-classified-and-unioned.md)).

## Finding out what was actually loaded

The worst outcome available to a tool like this is finding no terms and
reporting success, which looks identical to finding terms and matching none.
`--explain` distinguishes them. It prints every candidate path, its class, its
status, and how many terms came from it, then stops without scanning.

It is not a standalone mode. `check-identifiers` still requires `--staged` or
`--message FILE`, so the usual invocation is `check-identifiers --explain
--staged`; without one of those the command exits 2 with a usage error.

It never prints a term, from either class, whatever `--show-private-terms` says.
That output is what people paste into issues
([0006](design/decisions/0006-matched-terms-print-by-source-class.md)).

Reach for it whenever a hook seems not to fire, before assuming the terms are
wrong. Most often the file is somewhere other than where it was thought to be.
