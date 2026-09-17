# Resolution options

Read when: you need a resolution option shared by `check-identifiers` and
`audit-tree` (`--terms`, `--no-inherit`, `--no-walk`, `--walk-to`,
`--show-private-terms`, `--no-show-terms`), or a command acts as though
one was given.

Both scanning commands take the same options, defined once in the source.
Each boolean has a negated spelling, so a value set in the environment can
be turned off for one run. The command line wins over the environment,
which wins over the default (off).

## Options

| Option | Environment | Meaning |
|---|---|---|
| `--terms FILE` | `GIT_DENY_TERMS` | add a named term source; repeatable; highest precedence |
| `--no-inherit` | `GIT_HYGIENE_NO_INHERIT` | use only `--terms`, else only `GIT_DENY_TERMS`; nothing probed |
| `--inherit` | | undo `--no-inherit` |
| `--no-walk` | `GIT_HYGIENE_NO_WALK` | skip the ancestor-directory layer |
| `--walk` | | undo `--no-walk` |
| `--walk-to DIR` | `GIT_HYGIENE_WALK_TO` | stop the ancestor walk at DIR |
| `--show-private-terms` | `GIT_HYGIENE_SHOW_PRIVATE_TERMS` | also print matched terms from private sources |
| `--no-show-private-terms` | | undo `--show-private-terms` |
| `--no-show-terms` | none, by decision | print locations only, even for public terms |

`--terms` and `GIT_DENY_TERMS` are separate layers: giving `--terms` does
not drop the variable's files unless `--no-inherit` is also given, in which
case `--terms` alone is used. `--no-inherit` with neither resolves no term
and so passes silently.

`--show-private-terms` also lets an unauthorized-negation error name its
term. It has no effect on `--explain`, which never prints a term.

`--no-show-terms` makes the report add the note that private matches are
not shown, whatever the sources were.

How the layers, classes and negations behave is on
[term-sources.md](term-sources.md). Accepted boolean spellings are on
[environment.md](environment.md).

## Enforced and stated

Enforced by `tests/test_options.py`: each variable reaching resolution, the
negations overriding the environment, a malformed boolean exiting 2, and
`--no-inherit` from the environment. `--no-inherit` with explicit terms and
the walk bound are in `tests/test_resolution.py`; `--no-show-terms` is in
`tests/test_terms.py`. This table is held equal to the parser by
`tests/test_doc_ai.py`.
