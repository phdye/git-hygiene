# REJECTED: emulating `git ls-files --deduplicate` for git 2.21

**Decision: do not build this. Nothing here needs revisiting.** Investigated
2026-08-16 and declined. The floor is already covered by the native git-hook
front end, which needs no framework at all.

**Superseded the same day, and the conclusion is unchanged.** This document
opened by asserting that git 2.21 was this project's floor "matching RHEL
8.10". That was wrong: RHEL 8.10 ships git 2.43, and the 2.21 came from the
2019 Cygwin Time Machine snapshot the verification replica was built from,
not from the deployment target. The replica has since been moved to git
2.43.7, so no environment in play is below 2.31 any more.

That strengthens the rejection rather than weakening it. The emulation was
declined on maintenance grounds - patching someone else's tool in the
consumer's environment - and those grounds did not depend on the version
number. What changes is urgency: there is now no environment here that needs
it at all, so the reopening condition below has become correspondingly less
likely rather than more.

Read the rest only for the measurements. Where it says the floor is 2.21
matching RHEL 8.10, read "the 2019 snapshot pinned 2.21; RHEL 8.10 ships
2.43".

You do not need to read further unless a consumer has appeared that requires
the pre-commit framework specifically and cannot move off git 2.21. That is
the single condition that reopens this, and it is spelled out at the end.

The rest of this file exists only so the measurements do not have to be taken
again if that happens. It is a record, not an open question.

---

## The question

This project's git floor is 2.21, matching RHEL 8.10. The pre-commit framework
cannot run there: it calls `git ls-files -z --deduplicate`, and `--deduplicate`
arrived in git 2.31.0, released 2021-03-15. Could the missing flag be emulated
so the framework runs at the floor after all?

Technically yes. It is one flag, one call site, and the emulation is exact.
It is still not worth shipping, for reasons that are about maintenance rather
than difficulty.

## Measurement 1: it is the only blocker

Surveyed every git invocation in pre-commit 4.6.2 as installed, roughly forty
call sites across `git.py`, `commands/`, `staged_files_only.py` and `store.py`.
`--deduplicate` at `git.py:155` is the only one that exceeds 2.21.

Everything else clears the floor comfortably:

- `rev-parse --git-common-dir` is 2.5, and pre-commit already carries an
  explicit fallback path for older git.
- `tag --points-at` is 2.7.
- `rev-list --max-parents=0`, `ls-files --unmerged`, `diff-index --binary`,
  `add --intent-to-add`, `commit --no-gpg-sign`, `diff --staged`,
  `--no-ext-diff`, `--ignore-submodules` all predate 2.21.
- `NO_FS_MONITOR` passes `-c core.useBuiltinFSMonitor=false`. An unknown
  config key is silently ignored by old git, so it is harmless.

This was a static survey of one installed version. It is not a guarantee about
any other version, which is the crux of the decision below.

## Measurement 2: the emulation is exact

`--deduplicate` suppresses duplicate names arising from multiple index stages
during a merge, and has no effect when `-t`, `-u` or `-s` is in use. Dropping
the flag and applying an order-preserving deduplication reproduces it.

Verified differentially. A repository was built under git 2.21 with a real
merge conflict, so `ls-files -z` emitted the conflicted path three times, once
per stage. Reference output came from `ls-files -z --deduplicate` under git
2.55; the emulation was `ls-files -z` under 2.21 piped through
`awk '!seen[$0]++'`. The two were byte identical.

That is the whole feature. There is no subtlety being glossed over.

## Why it is not implemented

**The floor is already covered.** git 2.21 being a fixed floor makes the
native git-hook front end mandatory, not optional. That front end installs a
plain `.git/hooks/pre-commit` calling the console scripts directly, needs no
framework, and blocks commits through git's own hook mechanism exactly as the
framework path does. Once it exists, a backport adds a second and more fragile
route to protection the first route already provides in full.

**The audit does not stay done.** Today it is one flag because that is what
pre-commit 4.6.2 happens to call. Nothing obliges any future version to stay
2.21-compatible in any other respect, so each upgrade means re-running the
forty-call-site survey. The cost is recurring and the benefit is convenience.

**The failure mode is the wrong one.** A shim that silently stops matching the
tool it patches yields a hook that appears to run. This project treats
failure-that-reads-as-success as the worst available outcome, and would be
introducing one to gain a distribution convenience.

## What was rejected, and how

For the record, so these are not re-proposed:

- **A `git` wrapper earlier on PATH.** Shims git for every process inheriting
  that PATH. On this workstation it is worse than that: the framework runs
  under Windows Python, which resolves `git` through `CreateProcess` and will
  not honor a Cygwin shebang script, so the wrapper would have to be Windows
  git against Cygwin-created repositories. That is the `bad pack header`
  failure already recorded in `a/handoff/initial.md`.
- **A `sitecustomize.py` monkeypatch** of `pre_commit.git.get_all_files`.
  Process-scoped, so no PATH hazard, but coupled to a private function and
  silently inert if it is renamed.
- **A vendored fork** pinned to a known version. Honest, inspectable, and a
  fork of someone else's tool to maintain.

## What would change the decision

A consumer that requires the framework specifically and cannot move off git
2.21. In that case the monkeypatch is the least bad of the three, it must fail
loudly when the patched function is absent rather than proceeding, and it must
be pinned to an exact pre-commit version with the survey above repeated for it.

Also worth revisiting if the native front end turns out to need per-repo
configuration that the framework already solves well, since that is the one
capability gap the native path does not close for free.
