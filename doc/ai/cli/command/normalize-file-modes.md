# normalize-file-modes

Read when: the `normalize-file-modes` hook changed a file's mode, refused a
commit, or printed a `filemode:` line, or you need file modes normalized on
a host without the framework.

Sets the recorded mode of each staged regular file from its staged content:
100755 when the blob starts with `#!`, 100644 otherwise. It is the entry of
the `normalize-file-modes` hook. It takes no term options and reads no
term list.

    normalize-file-modes

## Options

| Option | Meaning |
|---|---|
| `-h`, `--help` | print usage and exit 0 |

No other argument is accepted; the command works on the repository
containing the current directory. It needs no framework: run it after
`git add` and before `git commit`, by hand or from your own `pre-commit`
hook, and it acts on what is staged at that moment.

## What it changes

Only staged additions, copies and modifications (`--diff-filter=ACM`)
whose index mode is 100644 or 100755. Symlinks and submodules are left
alone. The new mode is recorded with
`git update-index --cacheinfo MODE,BLOB,PATH` against the blob already
staged, so a partly staged file commits exactly what was staged.

The working file then gets the same mode, so the framework does not see
`git diff` change and fail the hook. Where the working file holds exactly
the staged blob, `git checkout-index -f` rewrites it; otherwise its
permission bits are changed directly. A path whose working mode still
differs afterwards, with `core.fileMode` on, is named.

## Exceptions

`.gitmodes-exceptions` at the work-tree root lists paths that keep the mode
their author staged: one glob per line, matched with `fnmatchcase` against
the path from the root, `#` starting a comment anywhere on a line. Each
excepted path is announced. An untracked exceptions file draws a warning
to stage it. A pattern that matches every path is refused with exit 2.

## Exit status

| Code | Meaning |
|---|---|
| 0 | ran, including when nothing regular was staged |
| 1 | outside a git work tree, or git refused the index update |
| 2 | `.gitmodes-exceptions` has a match-everything pattern; or a usage error |

## Output

stderr only, each line prefixed `filemode: `:

    filemode: mode 755 on bin/run
    filemode: mode exception: tools/odd.sh
    filemode: not inside a git work tree; cannot normalize

## Enforced and stated

Enforced by `tests/test_hooks.py`: index and working modes corrected, a
partly staged file keeping both halves, nothing staged passing, exceptions
kept and announced, the match-everything refusal, and the refusal outside a
work tree. `tests/test_packaging.py` (the `packaging` marker, run with
`pre-commit` on `PATH`) holds that the fix lands on the first commit under
the framework. Stated from source only: that renamed paths are not
normalized.
