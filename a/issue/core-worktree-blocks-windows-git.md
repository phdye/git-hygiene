# core.worktree was set by hand in every repo of this cohort, and is now removed

**Resolved 2026-08-17.** Originally filed 2026-08-16 as "found, not fixed"
after `pytest -m packaging` failed locally. The diagnosis recorded then was
wrong about the cause and wrong about the risk of removing it. Both are
corrected below. The setting is gone from this repository and from six
others.

## What was seen

`git ls-files`, or any other Windows-git command, run directly against this
working copy from a plain PowerShell shell:

    PS> git ls-files
    fatal: Invalid path '/c': No such file or directory

`.git/config` carried:

    [core]
        worktree = /c/-/cygwin/root/home/phili/repo/git-hygiene

A POSIX cygdrive-style path. Cygwin git read it; Git for Windows could not
parse it and failed before doing anything else.

## The original diagnosis was wrong

This file previously stated the value was "recorded because the repository
was `git init`'d from a Cygwin shell" through the `.primary` symlink chain.
That is not how git behaves. Tested against the rhel root's git 2.21.0,
none of the following writes `core.worktree`:

- plain `git init`
- `git --git-dir=X/.git --work-tree=X init`
- `git init` inside a symlinked path
- `git init` inside a two-hop symlink chain, mimicking `.primary`
- `git init <dir>` given a directory argument
- `git clone` into a symlinked path

Git resolves the physical path for its own use - `rev-parse --show-toplevel`
returns the real path, not the symlinked one - but it does not write that
path to config. The key was set explicitly, by hand, per repository.

## How it spread

Seven repositories carried it, all created between 2026-08-16 09:58 and
2026-08-17 22:52, and no repository created before that window has it:

1. `git-hygiene` - 2026-08-16 09:58
2. `git-hygiene-ci-demo` - 2026-08-16 13:15
3. `scan-dll-closure` - 2026-08-17 04:43
4. `my-standards` - 2026-08-17 05:14
5. `cli-standards` - 2026-08-17 06:30
6. `multi-language` - 2026-08-17 08:23
7. `cygwin-install-no-admin`, now `cygwin/no-admin` - 2026-08-17 22:52

This repository is first, and the others were modeled on it by request.
Each carries its own path rather than this one's, so the propagation was
not a file copy - the pattern was read off this repository's `.git/config`
and reproduced with the new name substituted. Modeling copies what is
present, defects included.

Writing this note on 2026-08-16 did not stop it: repo 7 acquired the key
the following night. A note in `a/issue/` describes the exemplar; it does
not change the exemplar. The config had to be fixed for the copying to
stop.

## Removing it was safe

The previous version of this note declined to remove the line, on the
theory it might be load bearing for Cygwin, and asked that someone first
verify `rev-parse --show-toplevel` still resolved. Verified on all seven,
2026-08-17. After `git config --unset core.worktree`, every one resolves to
its own path through the `.primary` spelling, `git status` works, and
`git stash` works.

`git stash` is the tell. It failed with "cannot be used without a working
tree" *before* any of this was touched, because the recorded path used the
primary-root spelling while work happens through `/home/phili/...`, and git
compares those as strings. Commands that read only the index and object
store - `log`, `remote`, `ls-files` - kept working, which is why the repos
looked healthy. The setting was never load bearing; it was breaking Windows
git completely and Cygwin git partially.

## Consequences elsewhere

`a/handoff/initial.md` and `a/doc/rejected-pre-commit-git-2.21-backport.md`
both attribute a `pre-commit try-repo` failure to the two gits disagreeing
over a clone:

    stderr: remote: fatal: Invalid path '/c': No such file or directory
            fatal: protocol error: bad pack header

That was this. Windows git's `upload-pack`, serving this repository as the
clone source, hit the `core.worktree` parse failure mid-response, and the
truncated output is what the fetching side reported as a corrupted pack.
The `bad pack header` symptom and this cause are one failure seen from two
ends of a single fetch. With the setting gone, that path is worth retesting;
the separate git-2.21 question stands on its own.

CI was never affected. It clones fresh under `ubuntu-latest` and inherits no
local config, so it remained the valid proof of packaging throughout.

## Not to be reintroduced

`.git` lives inside its own working tree in every repository here, which is
the arrangement where `core.worktree` is redundant by definition. Two
spellings reaching one tree - `/home/phili/repo/x` through `.primary`, and
`/c/-/cygwin/root/home/phili/repo/x` directly - is the expected arrangement
on this machine, not a fault to be corrected by pinning a path. Recorded in
the personal machine notes so it does not return with the next repository.
