# Exit status and output

Read when: a git-hygiene command exited non-zero or printed something, and
you need to know what it means and whether a term could have been shown.

## Exit status

| Code | `check-identifiers` | `audit-tree` | `install-hooks` | `normalize-file-modes` |
|---|---|---|---|---|
| 0 | no match, or nothing to check | clean, or no term resolved | all hooks handled | ran |
| 1 | match, fatal resolution, or required private list missing | match, or fatal resolution | not a repository, or a foreign hook skipped | not a work tree, or index update refused |
| 2 | usage, or malformed boolean variable | usage, or malformed boolean variable | usage | usage, or match-everything exception |

Exit 0 does not prove a check ran against anything: with no term resolved,
both scanning commands exit 0. Read `check-identifiers --staged --explain`,
or `audit-tree`'s summary line, before trusting a pass.

A hook that refuses and a hook that crashed both leave no commit. Tell them
apart by the text: `BLOCKED` or `FAIL` from a refusal, a traceback or a
shell syntax error from a crash.

## What goes where

| Command | stdout | stderr |
|---|---|---|
| `check-identifiers` | `--explain` table only | `BLOCKED: ...` reports and resolution errors |
| `audit-tree` | summary or table, scan counts, `CLEAN - ...` | `FAIL - ...` reports, resolution errors, the no-term notice |
| `install-hooks` | one line per hook | the non-repository error |
| `normalize-file-modes` | nothing | `filemode: ...` lines |

## Hit lines

A hit is `label:line`, two spaces of indent, one per matching line:

    src/app.py:12  [retired-name]
    notes/plan.md:40

The bracketed term appears only when `--no-show-terms` is absent and
either the matching term's source is public or `--show-private-terms` was
given. A term held by several sources is reported under the first one that
introduced it, except in a term file itself, where it is reported under
the first other holder.

## Never printed

- A term from a private source, unless `--show-private-terms` or
  `GIT_HYGIENE_SHOW_PRIVATE_TERMS` asked for it.
- Any term, under `--explain`, whatever else was given.
- Any term in the missing-private-list refusal, which names paths only.
- The term of a refused negation, unless `--show-private-terms` was given
  (and never under `--explain`).

A refusal that withheld a term says so and points at
`--show-private-terms`. Passing it prints the identifier into the terminal
and any log that captures it; prefer finding the line by location.

## Enforced and stated

Enforced: report contents and withholding (`tests/test_terms.py`,
`tests/test_term_classes.py`), refused-negation text
(`tests/test_options.py`, `tests/test_resolution.py`), `BLOCKED` asserted
on real commits (`tests/test_hooks.py`). Exit codes per command are held by
the tests named on each command page.
