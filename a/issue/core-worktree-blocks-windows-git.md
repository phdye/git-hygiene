# core.worktree is a POSIX path and Windows git cannot read this repo directly

**Found, not fixed.** Discovered running `pytest -m packaging` locally on
2026-08-16 while verifying the new `install-hooks` front end. Left alone
because the fix is a workstation-repo-config change, not a git-hygiene code
change, and it touches the exact symlink chain the personal machine notes
warn about getting wrong.

## What was seen

`git ls-files` (and any other Windows-git command) run directly against this
working copy, from a plain PowerShell shell, fails outright:

    PS> git ls-files
    fatal: Invalid path '/c': No such file or directory

`.git/config` carries:

    [core]
        worktree = /c/-/cygwin/root/home/phili/repo/git-hygiene

That is a POSIX cygdrive-style path, recorded because the repository was
`git init`'d from a Cygwin shell where `/home/phili/repo/git-hygiene` was
reached through the `.primary` symlink chain and git resolved the real
worktree path in Cygwin's own POSIX form. Cygwin git reads it fine. Windows
git - Git for Windows 2.55, the only git this project's own dev tooling can
drive directly, since Windows Python cannot launch a Cygwin binary - cannot
parse it at all and fails before doing anything else.

## Why this matters more than it looks

This is very likely the real, more specific cause behind a failure already
recorded as a git-version problem. `a/handoff/initial.md` and
`a/doc/rejected-pre-commit-git-2.21-backport.md` both describe
`pre-commit try-repo` failing with `bad pack header` when Windows git clones
a Cygwin-created repo, and attribute it to the two gits disagreeing over the
clone. Reproduced again this session, but with a clearer proximate error:

    An unexpected error has occurred: CalledProcessError:
      command: ('C:\\Program Files\\Git\\cmd\\git.EXE', 'fetch', 'origin', '--tags')
      return code: 128
      stderr: remote: fatal: Invalid path '/c': No such file or directory
              fatal: protocol error: bad pack header

Windows git's `upload-pack`, serving this repository as the clone source,
hits the same `core.worktree` parse failure mid-response, and the partial
output is what the fetching side reports as a corrupted pack. The
`bad pack header` symptom and the `core.worktree` cause are the same failure
seen from two ends of one `git fetch`.

**Consequence:** `pre-commit try-repo` against this repository cannot
succeed from a Windows-git shell as long as this config line is present,
independent of the git-2.21 question that also blocks it. Neither is a
defect in git-hygiene's own code - both are about the environment a local
`try-repo` run has to cross. CI clones fresh from a plain `git clone` under
`ubuntu-latest` and never inherits a local `core.worktree` override, so it is
unaffected and remains the valid proof of packaging.

## Why it was not fixed here

`core.worktree` pointing at the primary-root spelling is plausibly load
bearing for Cygwin: if it were removed, Cygwin git would fall back to
deriving the worktree from `.git`'s own location, and whether that still
resolves correctly depends on exactly how the `.primary` symlink chain was
walked at `git init` time - the same symlink fragility the personal machine
notes call out for `.primary/root` needing to be a native NT symlink, not a
Cygwin sys-format one. Editing a `.git/config` `core` setting on the
strength of a guess, in the one repository this session was already
touching for an unrelated feature, was judged not worth the risk of a
regression that would only surface later, in a different session, as
`git status` or a checkout silently doing the wrong thing.

## What would resolve this

Verify, from the rhel root, that `git rev-parse --show-toplevel` without any
`core.worktree` override still resolves to the same tree before removing the
line - a plain `git config --unset core.worktree` if that holds, on a
throwaway clone first rather than this working copy. Out of scope for
git-hygiene itself; if it turns out to affect other repositories under
`~/repo`, it belongs in the personal machine notes, not here.
