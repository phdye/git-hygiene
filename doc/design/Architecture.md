# Architecture

What git-hygiene is today and why it has this shape. The document is kept
current: when a change lands, this file is amended in the same commit, so it
can be read without the proposals that led here. Settled questions are in
`decisions/`, one per file; proposals still under discussion are in
`../proposal/`.

## Purpose

The package refuses a commit when its staged content or its message contains
a term the operator has forbidden, and it audits a whole repository for the
same terms before publication. The terms are client and organization names,
project and repository names, internal codenames: anything tying a public
repository to the engagement it came from.

One constraint shapes everything else. A denylist committed to a public
repository publishes exactly what it conceals, so the code here names no
terms and ships no example list ([0002](decisions/0002-term-lists-live-outside-the-repository.md)).
Terms come from elsewhere. They reach the tool from files the operator
controls.

## Components

| Module | Role |
|---|---|
| `terms.py` | Primitives: compiling a term, scanning text, reporting hits, running git. Knows nothing of layers or classes. |
| `resolution.py` | Finds every term source, classifies it, merges the terms, and describes the result for `--explain`. |
| `check_identifiers.py` | Console script `check-identifiers`: `--staged` scans staged blobs, `--message FILE` scans a commit message. |
| `audit_tree.py` | Console script `audit-tree`: tracked files, all commit messages, and with `--objects` every object in the store. |
| `install_hooks.py` | Console script `install-hooks`: writes `pre-commit` and `commit-msg` shims into `.git/hooks/` without the framework. |

It has no runtime dependencies. A hook that pulls in a dependency
tree breaks in somebody else's environment, and this one has to run on the
machines it protects.

## Public interface

Three hook ids are declared in `.pre-commit-hooks.yaml`. They are an API.
A consumer pins `rev:` and names one.

| id | Stage | Entry |
|---|---|---|
| `deny-terms` | pre-commit | `check-identifiers --staged` |
| `deny-terms-msg` | commit-msg | `check-identifiers --message` |
| `audit-tree` | manual | `audit-tree` |

A new hook is a minor version. A renamed hook, or a change to arguments or
exit semantics, is a major one; the console-script names are public on the
same terms, since the native hooks and any direct caller invoke them by
name.

## Term resolution

Resolution runs once per invocation, anchored at the work-tree root, and the
merged set is reused for every file, blob and message scanned. Per-directory
resolution in the manner of `.gitignore` is not done; a deny term belongs to
the repository, not to a subdirectory. The model is recorded in
[0004](decisions/0004-term-sources-are-layered-classified-and-unioned.md).

Sources, lowest precedence first:

| # | Source | Probed or named |
|---|---|---|
| 1 | `/etc/git-hygiene/deny-terms` | probed |
| 2 | `$XDG_CONFIG_HOME/git/deny-terms.txt`, else `~/.config/git/deny-terms.txt` | probed |
| 3 | `.deny-terms` and `.deny-terms.private` in ancestors of the anchor, outermost first | probed |
| 4 | `<anchor>/.deny-terms` | probed |
| 5 | `<git dir>/info/deny-terms` | probed |
| 6 | `GIT_DENY_TERMS`, `os.pathsep`-separated | named |
| 7 | `--terms FILE`, repeatable | named |

`--no-inherit` keeps only the highest named layer (`--terms`, else the
environment). `--no-walk` drops layer 3, and `--walk-to DIR` bounds it. The
walk otherwise stops at `$HOME` or the filesystem root.

### Settings

Both scanning commands take the same resolution settings, each from the
command line or the environment, the command line winning
([0010](decisions/0010-every-resolution-setting-has-an-environment-variable.md)).

| Option | Negation | Environment |
|---|---|---|
| `--terms FILE` | | `GIT_DENY_TERMS` |
| `--no-inherit` | `--inherit` | `GIT_HYGIENE_NO_INHERIT` |
| `--no-walk` | `--walk` | `GIT_HYGIENE_NO_WALK` |
| `--walk-to DIR` | | `GIT_HYGIENE_WALK_TO` |
| `--show-private-terms` | `--no-show-private-terms` | `GIT_HYGIENE_SHOW_PRIVATE_TERMS` |
| `--no-show-terms` | | none |

A boolean variable accepts `1`, `true`, `yes`, `on` and `0`, `false`, `no`,
`off`, in any case. Empty means unset. Any other value is a usage error that
names the variable, because a mistyped setting must not quietly read as off.

### Classes

A term file is `public` or `private`, declared on its first non-blank line as
`# git-hygiene: public` or `# git-hygiene: private`. Undeclared means
private. That default keeps every existing personal list working unchanged.

| | private | public |
|---|---|---|
| Tracked by git | fatal error, nothing scanned | expected |
| Matched term printed | only with `--show-private-terms` | yes, unless `--no-show-terms` |

A tracked private file stops the run before any scan. A run that reported
clean while a private list sat in the index would be worse than no run.

### Absence

A probed source that does not exist is skipped without comment. Named
sources get one exception. When the missing file is called `.deny-terms`,
a name that implies public, resolution is fatal and the error names the
path; any other missing named file is skipped.
The rule is narrower than "a missing public source is loud" because the
probed repository-root layer is absent from nearly every repository
([0005](decisions/0005-loud-absence-applies-only-to-named-sources.md)).

When no term resolves at all, `check-identifiers` passes silently. A
contributor who clones a public repository has no list, and a check they
cannot see must never block their work. `audit-tree` says on stderr that it
had nothing to audit against, then exits 0.

### Merge and negation

Terms merge as a union. Across layers, the first source to introduce a term
(compared case-insensitively) keeps its provenance.

A line `!term` removes an inherited term. The negating source must be at
least as strict as the introducing one, so a public file can never cancel a
private file's term; the cancellation would be readable where the term was
not. An unauthorized negation leaves the term in force and makes resolution
fatal. The error names both files; it names the term only under
`--show-private-terms`, since the refused term always comes from a private
source.

A file that exists but cannot be used is fatal too: one carrying both `term`
and `!term`, or one that cannot be read. Its `--explain` row shows an
`error:` status. Every fatal case stops the run before anything is scanned
([0009](decisions/0009-resolution-errors-are-fatal.md)).

### Trust

Ancestor files and the repository-root `.deny-terms` sit in directories
nobody in particular controls. On POSIX, such a file is skipped, with the
reason in its `--explain` row and a count in the summary line, when it is
world-writable or owned by neither the invoking user nor root. On Windows
those properties cannot be read from `os.stat`, so the check is not made at
all and every such file is trusted.

### Explain

`--explain` prints one row per candidate (path, class, status, term count)
and a summary line, followed on stderr by any fatal errors. It never prints a
term, of either class and under any flag, because this is the output people
paste into bug reports. `audit-tree` prints the summary
line on every run: whether a pre-publish audit ran against zero terms is the
question it exists to answer.

## Matching and reporting

A term compiles to a case-insensitive regular expression bounded by `\b` on
both sides ([0003](decisions/0003-terms-match-on-word-boundaries.md)). Each
line is reported once. The first pattern to match it supplies the term.

A hit is reported as `label:line`. The term follows in brackets when the
source is public, or when it is private and `--show-private-terms` was given
([0006](decisions/0006-matched-terms-print-by-source-class.md)).
`check-identifiers` scans the staged blob (`git show :path`), not the working
file, because the staged version is what would be committed. A blob git
cannot show is skipped.

## Exit status

| Code | Meaning |
|---|---|
| 0 | Nothing found, or no term resolved |
| 1 | A term was found, or resolution was fatal |
| 2 | Usage error, including a malformed boolean environment variable |

`install-hooks` is the exception. It exits 1 when a hook it would write
belongs to something else and `--force` was not given.

## Hooks without the framework

`pre-commit` needs git 2.31 or newer. `install-hooks` covers older git and
hosts where the framework cannot be installed
([0008](decisions/0008-old-git-gets-native-hooks-not-a-patched-framework.md)).
Each shim is a short POSIX shell script that finds `check-identifiers` on
`PATH`, fails loudly when it is absent, and hands over. Shims hold no logic.
A package upgrade replaces everything except them.

Every run rewrites the shim from a fixed template. A file lacking the
installer's marker comment belongs to someone else and is left alone unless
`--force` is given; `--uninstall` removes only marked files, and `--dry-run`
writes nothing. The shim is written as bytes, so a Windows interpreter cannot
turn its line endings into CRLF.

## Paths across interpreters

The anchor comes from `git rev-parse --show-cdup` joined onto the
interpreter's own working directory, not from `--show-toplevel`. Under Cygwin
git the latter is a POSIX path that a native Windows interpreter can neither
open nor spawn in. That failure is silent. Every layer probe answers
"absent", and the scan passes. The git directory is resolved the same way,
with a fallback to `<anchor>/.git` when git's absolute answer does not exist
for this interpreter.

`Path.home()` is the user profile under Windows Python, which differs from a
Cygwin shell's `~`. Setting `XDG_CONFIG_HOME` or `GIT_DENY_TERMS` removes the
ambiguity, and `--explain` shows which file was actually read.

## Supported environments

Python 3.6.8 and newer ([0007](decisions/0007-python-floor-is-3-6-8.md)). Git
usage is limited to commands that long predate 2.21: `diff --cached`, `show`,
`ls-files`, `cat-file --batch-all-objects --batch-check`, `cat-file -p`,
`log --all --format`, `rev-parse --show-cdup` and `rev-parse --git-dir`. The
framework path needs git 2.31; the native path does not. How each of these is
proven is in `Verification-Plan.md`.

## Known limits

`audit-tree --objects` runs a separate `git cat-file -p` for every object.
Its cost on a large history is unmeasured. Blobs, trees and commits are all
scanned. Binary objects are not skipped; they are decoded with replacement
characters and searched like text.
