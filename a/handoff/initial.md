# Session handoff: git-hygiene

Written 2026-08-16 by the session that created this repository. That
session has stopped work here; whoever picks this up owns it.

> **Superseded on one load-bearing point, same day.** This document states
> that git 2.21 is a fixed floor "matching RHEL 8.10 as the Python floor
> does". That is wrong. RHEL 8.10 ships **git 2.43**; the 2.21 came from the
> 2019 Cygwin Time Machine snapshot the verification replica was built from,
> not from the deployment target. The replica has since been moved to git
> 2.43.7. The Python 3.6.8 floor is unaffected and remains correct.
>
> Read every 2.21-as-floor claim below as historical. The practical
> consequence: the native `install-hooks` front end is a **fallback** for
> genuinely old git and for hosts where the framework cannot be installed,
> not the only usable path. See `a/doc/rejected-pre-commit-git-2.21-backport.md`,
> which records why the conclusion there survives the corrected premise.

## What this is

`pre-commit` hooks that keep engagement-specific identifiers -- client
and organization names, project and repository names, internal
codenames -- out of repositories.

It exists because of a real leak. A sibling package (`~/repo/azdo`)
carried a client organization name and a project name in its test
fixtures from its first commit until an audit caught them, shortly
before that package was to be published. The standing "no client
identifiers" rule had been written down the whole time and did not
prevent it.

The design constraint that shapes everything: **a denylist committed
to a public repository publishes exactly what it conceals.** So the
code lives here and names no terms, and the term list lives outside
every repository at `~/.config/git/deny-terms.txt`. `.gitignore`
refuses a term file defensively.

## State

One commit, `29215de`, tagged `v0.1.0`. No remote. Working tree has one
uncommitted modification, `tests/test_packaging.py` -- see the blocker
below for why it should probably be reverted rather than finished.

    .pre-commit-hooks.yaml          public interface, three hooks
    pyproject.toml                  console scripts, no runtime deps
    src/git_hygiene/terms.py        term loading, scanning, reporting
    src/git_hygiene/check_identifiers.py   staged content + commit message
    src/git_hygiene/audit_tree.py   whole-repo and object-store audit
    tests/                          19 passing, 2 packaging (deselected)
    .github/workflows/ci.yml        lint, test matrix, packaging job

## The blocker, and it is the reason this stopped

**`pre-commit` 4.6.2 cannot run against git 2.21, and git 2.21 is a
hard requirement here.**

Measured, not inferred. In `~/repo/azdo` under the rhel root:

    $ git --version
    git version 2.21.0
    $ python -m pre_commit run --all-files
    An unexpected error has occurred: CalledProcessError:
      command: ('C:\\-\\rhel\\root\\bin\\git.EXE', 'ls-files', '-z', '--deduplicate')
      return code: 129
      stderr: error: unknown option `deduplicate'

`git ls-files --deduplicate` arrived in git 2.31. The rhel root is a
deliberate RHEL 8.10 emulation built from a 2019 package snapshot, and
its git is 2.21.0. That is not an accident to be upgraded away -- it
is the point of that instance, and the machine's own notes say so.

So every hook in this repository is currently unreachable in the
environment it most needs to protect. The scripts themselves are fine;
the runner is not.

### What is and is not affected

- **`git_hygiene`'s own git usage is 2.21-clean.** It uses only
  `diff --cached --name-only --diff-filter`, `show :path`, `ls-files`,
  `cat-file --batch-all-objects --batch-check`, `cat-file -p`, and
  `log --all --format`. All predate 2.21 comfortably. The 19
  end-to-end tests create real repositories and drive real git, and
  they pass in a bash login shell where 2.21 is the default. Treat
  that as verified.
- **`pre-commit` is the incompatible piece**, not this code.
- **CI is unaffected** -- `ubuntu-latest` has a current git.

### Options, none of them chosen

1. **Pin an older `pre-commit`** in environments on git 2.21. Find the
   last release that does not use `--deduplicate` and document a
   floor. Costs: an old pre-commit everywhere, and this only holds
   until some other new-git dependency appears.
2. **Ship plain git hooks as an alternative front end.** A
   `.git/hooks/pre-commit` shim calling `check-identifiers` directly
   needs no pre-commit at all, and the console scripts already work on
   2.21. Loses pre-commit's environment isolation and `autoupdate`.
   This is probably the honest answer for the rhel replica.
3. **Accept that the rhel replica does not get pre-commit** and rely
   on `audit-tree` there as a manual pre-publish gate. Weakest, since
   it is not automatic.
4. **Do not run these hooks on the rhel replica at all** -- run them
   on the workstation, which has modern git, and treat the replica as
   a deployment target rather than a development one. Whether that is
   true is a question about the replica's role, not about this code.

Option 2 plus 4 in combination is my read, but it was not decided and
the person who owns this should decide it rather than inherit a guess.

## The uncommitted change, and why to look at it sceptically

`tests/test_packaging.py` is modified but not committed. It adds a
`MIN_GIT = (2, 30)` skip so the packaging tests skip rather than fail
on old git.

**That was written before the git 2.21 requirement was understood, and
it now encodes the wrong assumption.** Skipping on old git quietly
declares 2.21 out of scope, which is the opposite of what is wanted.
Reverting it and instead making the packaging test assert something
true on 2.21 -- or marking it clearly as "modern git only, by
necessity, because pre-commit requires it" -- is the better shape.

Either way it should be a deliberate decision, not the leftover of an
interrupted one.

## What is verified, and what is not

Verified:

- 19 unit and end-to-end tests pass, under git 2.21.
- 86% line coverage.
- `ruff check`, `ruff format --check`, `mypy --strict` all clean.
- `pre-commit validate-manifest` accepts `.pre-commit-hooks.yaml`.
- Both console scripts (`check-identifiers`, `audit-tree`) install as
  real executables and are invokable by name.
- The term list, applied to a sibling repository, produced zero false
  positives across 16 terms and 44 files.

Not verified:

- **`pre-commit try-repo` has never succeeded here.** Two separate
  environment failures masked each other: git 2.21 lacking
  `--deduplicate`, and then, with Windows git 2.55 on PATH, `fatal:
  protocol error: bad pack header` from cloning a Cygwin-created
  repository with a different git. Neither is a defect in this code,
  and neither has been cleared. The CI `packaging` job is currently
  the only place this would be proven, and CI has never run.
- **No consumer has ever installed these hooks from a `rev:` pin.**
  The intended usage in `README.md` is untested end to end.
- **`audit-tree --objects` has not been run against a large
  repository.** It reads every object individually; performance on a
  real history is unknown.

## Things worth knowing before changing anything

**Hook ids are a public API.** `deny-terms`, `deny-terms-msg`,
`audit-tree`. Once a consumer pins `rev:` and names an id, renaming it
breaks their config. New hook is a minor version, changed arguments or
exit semantics a major one.

**Two behaviors are load-bearing, not stylistic.** The tool reports a
file and line but never the matched term, because printing it would
put the identifier into scrollback, CI logs and any pasted error
report -- recreating the leak. And it matches on word boundaries,
because substring matching fires on ordinary API names, and a guard
that cries wolf gets switched off. Both have tests. Do not "simplify"
either.

**Silent success when no term file exists is deliberate.** Anyone
cloning a public repository will not have one, and a check they cannot
see must never block their work.

**`Path.home()` is a trap on this machine.** Under Windows Python it
is the user profile, not the Cygwin home. Getting it wrong makes the
hook find no terms and pass everything -- failure that reads as
success, the worst outcome available. `GIT_DENY_TERMS` overrides it.
That is documented in the README and worth keeping prominent.

**This repository must itself stay client-agnostic.** It is intended
to be public, and it is the tool that enforces exactly that property
elsewhere. Nothing in it names a term, an organization, a project or
an engagement, and nothing should. The sibling package's history had
to be rewritten from its root to remove identifiers that had been
committed on day one; do not repeat that here.

## Suggested first moves

1. Decide the git 2.21 question. It gates whether this facility is
   usable where it is most needed, and everything else is smaller.
2. Resolve `tests/test_packaging.py` -- revert or rewrite, but do not
   leave the interrupted version.
3. Push to a remote and let CI run. The `packaging` job is the only
   thing that has ever been able to prove the packaging works, and it
   has not run.
4. Only then consider a consumer. `~/repo/azdo` currently carries its
   own copy of this check at `scripts/check-identifiers.py` with a
   `language: system` hook entry; converting it to consume this
   repository by tag is the obvious first adoption, and would delete
   that script. Do not start that until 1 and 3 are settled -- a
   consumer pinned to hooks that cannot install is worse than the
   duplicated script it replaces.

## Relationship to ~/repo/azdo

Sibling, not parent. `azdo` is an Azure DevOps client library and has
its own session, roles and instructions under its own `a/` tree. The
only coupling is that `azdo` is the intended first consumer of these
hooks and currently duplicates one of them locally.

Nothing here should acquire an `azdo` dependency, in either direction.
