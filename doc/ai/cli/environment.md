# Environment variables

Read when: you are setting git-hygiene behavior for a whole machine, shell
or CI job, or a command behaves as though it was given an option it was
not.

The table is every variable the package reads. A command-line option always
wins over its variable.

| Variable | Read by | Meaning |
|---|---|---|
| `GIT_DENY_TERMS` | `check-identifiers`, `audit-tree` | term source paths, separated by `os.pathsep` (`:` on POSIX, `;` under Windows Python); layer 6 |
| `GIT_HYGIENE_NO_INHERIT` | `check-identifiers`, `audit-tree` | boolean; as `--no-inherit` |
| `GIT_HYGIENE_NO_WALK` | `check-identifiers`, `audit-tree` | boolean; as `--no-walk` |
| `GIT_HYGIENE_WALK_TO` | `check-identifiers`, `audit-tree` | directory; as `--walk-to` |
| `GIT_HYGIENE_SHOW_PRIVATE_TERMS` | `check-identifiers`, `audit-tree` | boolean; as `--show-private-terms` |
| `GIT_HYGIENE_REQUIRE_PRIVATE` | `check-identifiers` | boolean; as `--require-private` |
| `XDG_CONFIG_HOME` | `check-identifiers`, `audit-tree` | when set, the user list is `$XDG_CONFIG_HOME/git/deny-terms.txt` |

## Values

A boolean accepts `1`, `true`, `yes`, `on` and `0`, `false`, `no`, `off`,
in any case, with surrounding whitespace ignored. Empty means unset. Any
other value is a usage error: the command prints the variable, its value
and the accepted words, and exits 2 without scanning. `--no-show-terms` has
no variable, by decision.

An empty `GIT_DENY_TERMS` or `GIT_HYGIENE_WALK_TO` counts as unset, and
empty entries in `GIT_DENY_TERMS` are ignored.

## Read indirectly

`HOME` is not read by name, but Python's `Path.home()` decides the default
user list (`~/.config/git/deny-terms.txt`) and where the ancestor walk
stops. Under Windows Python that is the user profile, not a Cygwin or MSYS
shell's `~`; set `XDG_CONFIG_HOME` or `GIT_DENY_TERMS` when they differ,
and confirm with `--explain`. `PATH` must find `git` for every command, and
`check-identifiers` for the shims `install-hooks` writes. Variables git
itself honors reach the git subprocesses unchanged.

## A private list in CI

Write the list from a CI secret to a runner-local file, with `umask 077`
set first, and export `GIT_DENY_TERMS` pointing at it. Nothing else is
needed: private terms are withheld from the report. Patterns and workflow
snippets are in
[../../ci-term-provisioning.md](../../ci-term-provisioning.md).

## Enforced and stated

Enforced by `tests/test_options.py` (each resolution variable reaching
resolution, the command line winning, malformed booleans) and
`tests/test_hooks.py` (`GIT_HYGIENE_REQUIRE_PRIVATE`, its negation and a
malformed value). `tests/test_doc_ai.py` holds this table equal to the
names read in the source. Stated: the `Path.home()` trap, which is
described in the design and not tested.
