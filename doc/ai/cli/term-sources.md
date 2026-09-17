# Term sources and resolution

Read when: you need to know which term lists a run loads, their class and
precedence, why a negation was refused, or why a hook passed when you
expected a refusal.

Resolution runs once per invocation, anchored at the work-tree root
(`audit-tree`: its `repo` argument), and the merged set is used for every
file, blob and message scanned. The normative rules are in
[../../design/Architecture.md](../../design/Architecture.md), "Term
resolution".

## Layers

Lowest precedence first. Terms from every layer are merged as a union.

| # | Source | Class | Kind |
|---|---|---|---|
| 1 | `/etc/git-hygiene/deny-terms` | private | probed |
| 2 | `$XDG_CONFIG_HOME/git/deny-terms.txt`, else `~/.config/git/deny-terms.txt` | private | probed |
| 3 | `.deny-terms` and `.deny-terms.private` in each ancestor of the anchor, outermost first | by name | probed |
| 4 | `<anchor>/.deny-terms`, then `<anchor>/.deny-terms.private` | by name | probed |
| 5 | `<git dir>/info/deny-terms` | private | probed |
| 6 | each path in `GIT_DENY_TERMS`, split on `os.pathsep` | by name | named |
| 7 | each `--terms FILE` | by name | named |

The ancestor walk starts at the anchor's parent and stops at `--walk-to`
(if given), at `$HOME`, or at the filesystem root, whichever comes first.
`--no-walk` drops layer 3. `--no-inherit` keeps only layer 7, or layer 6
when layer 7 is empty.

## Classes

The class comes from the name or location, never from content: a file
named `.deny-terms` is public wherever it sits; layers 1, 2 and 5 are
private by location; every other name, including any file given to
`--terms` or `GIT_DENY_TERMS`, is private.

| | private | public |
|---|---|---|
| tracked by git | fatal, nothing scanned | expected |
| matched term printed | only with `--show-private-terms` | yes, unless `--no-show-terms` |
| missing | skipped silently | skipped, except a named one (layer 6 or 7): fatal |

An optional first line `# git-hygiene: public` or `# git-hygiene: private`
must agree with the class, or resolution is fatal and the file contributes
nothing.

## Merge and negation

A term is compared case-insensitively. The first source to introduce it
keeps its spelling; later holders are recorded beside it. A line `!term`
removes an inherited term only when the negating source is at least as
strict as every source holding it: a public file can never cancel a term a
private file holds. An unauthorized negation keeps the term and is fatal;
its error names both files, and the term only under
`--show-private-terms`. A negation of a term nothing introduced is ignored.

## Trust

On POSIX, an ancestor file, either root file, or any file named
`.deny-terms` is skipped when it is world-writable or owned by neither the
invoking user nor root. On Windows the check is not made and such files
are trusted.

## Fatal errors

Each stops the run with exit 1 before scanning: a tracked private list; a
class conflict; a file that cannot be read; a file holding both `term` and
`!term`; an unauthorized negation; a missing named `.deny-terms`.

## Seeing what loaded

`--explain` prints one row per candidate, then a summary, and never a term:

    source                                        class    status      terms
    /etc/git-hygiene/deny-terms                    private  absent          0
    (walk) /work/repo/.deny-terms                  public   loaded          4

    4 terms from 1 sources, 0 skipped, 0 negations honored

`(walk)` marks layers 3 and 4. The class is shown even for an absent file.
Statuses: `loaded`, `absent`, `skipped:<reason>`, `error:missing`,
`error:class-conflict`, `error:tracked`, and `error:<reason>` for a file
that could not be parsed or read. Fatal errors follow on stderr.
`check-identifiers --explain` stops there; `audit-tree --explain` goes on
to audit, and `audit-tree` prints the summary line on every run.

## Enforced and stated

Enforced: layers, union, absence, negation, tracking, `--no-inherit`, the
walk bound, trust and the summary (`tests/test_resolution.py`); classes by
name, directives, team lists and `--explain` classes
(`tests/test_term_classes.py`). Stated from source only: the Windows trust
behavior, which no test exercises.
