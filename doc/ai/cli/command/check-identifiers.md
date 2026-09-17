# check-identifiers

Read when: a commit was refused by `deny-terms` or `deny-terms-msg`, or you
are running the content or message check by hand.

Refuses staged content, or a commit message, that matches a resolved term.
It is the entry of the `deny-terms` hook (`check-identifiers --staged`) and
the `deny-terms-msg` hook (`check-identifiers --message`, the framework
appending the message file), and of both shims `install-hooks` writes.

    check-identifiers --staged [resolution options] [--explain] [--require-private]
    check-identifiers --message FILE [resolution options] [--explain] [--require-private]

Exactly one of `--staged` and `--message` is required, even with
`--explain`; without one the command exits 2.

## Options

| Option | Meaning |
|---|---|
| `-h`, `--help` | print usage and exit 0 |
| `--staged` | scan the staged blob of every added, copied, modified or renamed path |
| `--message FILE` | scan the commit message in FILE |
| `--explain` | print the term resolution table and exit; scans nothing |
| `--require-private` | refuse when no private term source loaded (env `GIT_HYGIENE_REQUIRE_PRIVATE`) |
| `--no-require-private` | undo `--require-private` or the environment setting |

The shared options (`--terms`, `--no-inherit`, `--show-private-terms`,
`--no-show-terms` and the rest) are on
[../resolution-options.md](../resolution-options.md).

## What it scans

Resolution is anchored at the work-tree root, or the current directory
outside a work tree. `--staged` reads each path with `git show :path`, the
staged version, not the working file. Binary blobs are scanned too, decoded
with replacement characters. A loaded term file that is itself staged is
scanned against every other source but not its own entries.

`--message` scans the file as text; a missing file passes.

## The requirement

With `--require-private`, and no private source loaded, the command scans
against whatever public terms loaded and then refuses, naming every private
location it probed (each with its status, and `.deny-terms.private` in each
ancestor the walk visited). It never names a term. A public list alone does
not satisfy it. A staged set with nothing readable as text passes, and so
does a missing message file.

## Exit status

| Code | Meaning |
|---|---|
| 0 | no match; or no term resolved and none required; or `--explain` with a clean resolution |
| 1 | a match; a fatal resolution error (also under `--explain`); or a required private list is missing |
| 2 | usage error, including a malformed boolean environment variable; caught before resolution, so nothing is scanned |

## Output

Nothing on success. On a refusal, stderr carries:

    BLOCKED: staged content matches a denylisted identifier.
      src/app.py:12  [retired-name]
      config/hosts.txt:3

    One or more matches are from a private term source and are not shown - pass --show-private-terms to see them.

    Remove the identifier, or if this is a false positive, narrow the term in its term file.

The middle paragraph appears whenever a term was withheld. `label:line` per
matching line, the term in brackets only when printable
(see [../output-and-exit.md](../output-and-exit.md)). A message hit is
labeled `commit message:N`. A fatal resolution prints
`BLOCKED: term resolution failed.` and the errors. A missing required list
prints `BLOCKED: no private term source resolved, and one is required; ...`
and the probed paths. `--explain` writes its table to stdout.

## Enforced and stated

Enforced: staged blob not working file, no-list silent pass, message
checks (`tests/test_end_to_end.py`); the requirement, its environment
variable, its negation, binary-only commits and the missing-message pass
(`tests/test_hooks.py`, `tests/test_term_classes.py`); refused negation
blocking the check without naming the term (`tests/test_options.py`).
Stated from source only: that renamed paths are scanned (`--diff-filter=ACMR`).
