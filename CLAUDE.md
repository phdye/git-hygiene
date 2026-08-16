# git-hygiene — working instructions

Read `a/doc/instructions.md` before touching anything in this tree. It covers
the environment, the workstation bridge, and where things get filed. This file
exists to point at it.

`a/doc/instructions.md` on disk is the authoritative copy. A copy held as
Claude Project knowledge is a snapshot; when the two disagree, the disk wins.

The two that are expensive to get wrong, stated here so they land first:

- **This repo must itself stay client-agnostic.** It is the tool that
  enforces exactly that property elsewhere, so it is held to it doubly. No
  organization, project, repo, user, host, or engagement name, ever — not in
  code, tests, fixtures, comments, or commit messages.
- **Hook ids are a public API.** `deny-terms`, `deny-terms-msg`, `audit-tree`.
  Renaming one breaks every consumer that pinned `rev:` and named it. New hook
  is a minor version; changed arguments or exit semantics is a major one.

@a/doc/instructions.md
