# audit-tree

Read when: you are about to publish a repository and want every tracked
file, commit message and, optionally, every git object checked for terms.

Audits a whole repository, not the staged set. It finds what the commit
hooks cannot: terms already committed. It is also the `audit-tree` hook,
declared at the `manual` stage (`pre-commit run --hook-stage manual
audit-tree`).

    audit-tree [resolution options] [--objects] [--explain] [repo]

`repo` defaults to the current directory, and resolution is anchored there.

## Options

| Option | Meaning |
|---|---|
| `-h`, `--help` | print usage and exit 0 |
| `--objects` | also scan every object in the store, reachable or not |
| `--explain` | print the full resolution table instead of only its summary line, then audit as usual |

The shared options are on
[../resolution-options.md](../resolution-options.md). There is no
`--require-private` here.

## What it scans

1. Every file `git ls-files` lists, read from the working tree.
2. The output of `git log --all --format=%H%n%B`, every commit message on
   every ref, labeled `commit messages:N` (N counts lines in that output).
3. With `--objects`, every object `git cat-file --batch-all-objects` lists:
   blobs, trees and commits, binary ones included, labeled
   `object <first 10 hex digits>`. One `git cat-file -p` runs per object;
   the cost on a large history is unmeasured.

A committed term file, and under `--objects` every staged or committed
version of it, is checked against every other source but not itself.

Removing a term from the working tree does not remove it from history.
Content that passes the default audit can still fail `--objects`.

## Exit status

| Code | Meaning |
|---|---|
| 0 | clean, or no term resolved (stated on stderr) |
| 1 | a term was found, or resolution failed (nothing scanned) |
| 2 | usage error, including a malformed boolean environment variable |

A zero-term run exits 0. Read the summary line, not only the code.

## Output

stdout, always first, the resolution summary (or the whole table under
`--explain`):

    3 terms from 2 sources, 0 skipped, 0 negations honored

Then, when it scanned:

    tracked files scanned: 41
    git objects scanned:   0

and `CLEAN - no identifier found` on success. Hits go to stderr under
`FAIL - identifiers present:`, one `label:line` per matching line, with the
term in brackets only when printable. With no term resolved, stderr says
`No term resolved - nothing to audit against. See --explain.` and the
command exits 0.

## Enforced and stated

Enforced: committed content, commit messages, a clean pass and the orphaned
blob found only by `--objects` (`tests/test_end_to_end.py`); committed team
lists and old versions of them (`tests/test_term_classes.py`); `--explain`
naming no refused term (`tests/test_options.py`). Stated from source only:
the command does not check that `repo` is a git repository; outside one,
git lists nothing and the audit reports clean over zero files.
