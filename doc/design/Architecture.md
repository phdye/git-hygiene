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
| `install_hooks.py` | Console script `install-hooks`: writes hook shims into `.git/hooks/` that run the dispatcher, without the framework. |
| `gitconfig.py` | Reads git-config syntax through `git config --no-includes`. |
| `checks.py` | The check registry: built-in declarations, declaration files, validation, run order. |
| `settings.py` | Which checks are enabled and required, resolved from layered settings. |
| `dispatch.py` | Console script `git-hygiene`: `run HOOK` runs the selected checks and reads their exit contracts. |
| `filemode.py` | Console script `normalize-file-modes`: sets staged files' index modes from their content. |

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

The console scripts are `check-identifiers`, `audit-tree`, `install-hooks`,
`git-hygiene` and `normalize-file-modes`, and the check ids `filemode`,
`deny-terms` and `deny-terms-msg` are named in repository settings, so they
are public on the same terms as the hook ids.

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
| 4 | `<anchor>/.deny-terms`, then `<anchor>/.deny-terms.private` | probed |
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
| `--no-show-terms` | | none, by decision |
| `--exit-contract N` (`check-identifiers` only) | | `GIT_HYGIENE_EXIT_CONTRACT` |

A boolean variable accepts `1`, `true`, `yes`, `on` and `0`, `false`, `no`,
`off`, in any case. Empty means unset. Any other value is a usage error that
names the variable, because a mistyped setting must not quietly read as off.

### Classes

A term file is `public` or `private`, and its name or location decides which.
Nothing inside the file does.

| Source | Class |
|---|---|
| `.deny-terms`, wherever it sits | public |
| `.deny-terms.private` | private |
| `/etc/git-hygiene/deny-terms`, the user file, `<git dir>/info/deny-terms` | private, by location |
| any other name given to `--terms` or `GIT_DENY_TERMS` | private |

The class is therefore known before the file is read, and `.gitignore`, `ls`
and a reviewer all see the same thing the resolver does. A first line of
`# git-hygiene: public` or `# git-hygiene: private` is still accepted as an
assertion. It must agree with the name; a disagreement is a fatal error that
names the file and both claims, and the file contributes nothing.

| | private | public |
|---|---|---|
| Tracked by git | fatal error, nothing scanned | expected |
| Matched term printed | only with `--show-private-terms` | yes, unless `--no-show-terms` |

A tracked private file stops the run before any scan. A run that reported
clean while a private list sat in the index would be worse than no run.
Tracking is tested with `git ls-files --error-unmatch` on the path relative to
the anchor, spelled with forward slashes so that a Cygwin git answers
correctly for a Windows interpreter.

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
(compared case-insensitively) keeps its provenance, and every later source
holding the same term is recorded beside it.

A line `!term` removes an inherited term. The negating source must be at
least as strict as every source holding the term, so a public file can never
cancel a term a private file holds, even when a public file introduced it
first; the cancellation would be readable where the term was not. An
unauthorized negation leaves the term in force and makes resolution fatal.
The error names both files; it names the term only under
`--show-private-terms`, since the refused term always comes from a private
source.

A file that exists but cannot be used is fatal too: one carrying both `term`
and `!term`, or one that cannot be read. Its `--explain` row shows an
`error:` status. Every fatal case stops the run before anything is scanned
([0009](decisions/0009-resolution-errors-are-fatal.md)).

### Trust

Ancestor files, the two repository-root files, and any file called
`.deny-terms` sit in directories nobody in particular controls. On POSIX,
such a file is skipped, with the reason in its `--explain` row and a count in the summary line, when it is
world-writable or owned by neither the invoking user nor root. On Windows
those properties cannot be read from `os.stat`, so the check is not made at
all and every such file is trusted.

### Explain

`--explain` prints one row per candidate (path, derived class, status, term
count; the class is shown even for a file that does not exist)
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
cannot show is skipped. Binary blobs are scanned too, decoded with
replacement characters.

A term file the resolver loaded is not scanned against its own entries: a list
naturally contains the terms it denies. It is still scanned against every
other loaded source, private ones included, and a match there is reported
under that source's class. A committed team list that picked up a private
term by a paste therefore refuses the commit without printing the term. The
exclusion is by resolved path. `audit-tree` applies it to tracked files and,
under `--objects`, to every staged or committed version of such a file.

## Exit status

| Code | Meaning |
|---|---|
| 0 | Nothing found, or no term resolved |
| 1 | A term was found, or resolution was fatal |
| 2 | Usage error, including a malformed boolean environment variable |

That is contract 1, and it is what `check-identifiers` speaks unless it is
given `--exit-contract 2` (or `GIT_HYGIENE_EXIT_CONTRACT=2`). Under contract 2
it adds two codes. It exits 3 when nothing it can read as text was staged;
binaries are still scanned, and a match in one still exits 1. It exits 4 when
no private term source loaded, after scanning against whatever public terms
did load, naming every private location it probed and no term; with
`--message`, a missing message file is also 4. Contract 1 callers, the
`pre-commit` framework among them, see no change.

`install-hooks` is the exception. It exits 1 when a hook it would write
belongs to something else and `--force` was not given.

## Hooks without the framework

`pre-commit` needs git 2.31 or newer, and its current release needs Python
3.10 (`spike/pre-commit-python-floor/`). `install-hooks` covers hosts where
the framework cannot run
([0008](decisions/0008-old-git-gets-native-hooks-not-a-patched-framework.md)).
Each shim is a short POSIX shell script that finds `git-hygiene` on `PATH`,
refuses the commit when it is absent, and hands over with
`exec git-hygiene run <hook> "$@"`. Shims hold no logic. A package upgrade
replaces everything except them.

A shim is written for `pre-commit` and `commit-msg`, and for any other hook a
registered check declares. Every run rewrites each shim from a fixed template
and removes marked shims for hooks no longer in that set. A file lacking the
installer's marker comment belongs to someone else and is left alone unless
`--force` is given; `--uninstall` removes every marked file and nothing else,
and `--dry-run` writes nothing. The shim is written as bytes, so a Windows
interpreter cannot turn its line endings into CRLF. A registry the installer
cannot read is a usage error (exit 2).

## One front end for every check

`git-hygiene run [options] HOOK [ARG...]` runs every enabled check whose
declaration names HOOK, passing git's arguments after the declared ones
([0012](decisions/0012-one-front-end-dispatches-every-check.md)). `git hygiene
run` reaches the same program. Options go before HOOK.

| Option | Environment | Effect |
|---|---|---|
| `-v`, `--verbose` | `GIT_HYGIENE_VERBOSE` | also report checks that stood down |
| `-t`, `--terse` | `GIT_HYGIENE_TERSE` | omit the closing "refused by" line |
| `-d`, `--debug` | `GIT_HYGIENE_DEBUG` | show each command as it is started |
| `--explain` | | print each check's settings and their origin; run nothing |
| `--enable ID`, `--disable ID` | `GIT_HYGIENE_ENABLE`, `GIT_HYGIENE_DISABLE` | switch a check on or off |
| `--require ID`, `--optional ID` | `GIT_HYGIENE_REQUIRE`, `GIT_HYGIENE_OPTIONAL` | set whether it may stand down |

The environment variables take comma- or space-separated ids. Naming one id
for both halves of a pair in the same layer is a usage error.

### Checks and declarations

A check is a console script plus a declaration. The package declares three:

| id | hook | command | order | notes |
|---|---|---|---|---|
| `filemode` | pre-commit | `normalize-file-modes` | 10 | changes the index |
| `deny-terms` | pre-commit | `check-identifiers --staged --exit-contract 2` | 50 | |
| `deny-terms-msg` | commit-msg | `check-identifiers --exit-contract 2 --message` | 50 | |

Other packages register checks with files matching `*.conf` in
`git-hygiene/checks/` under `$XDG_DATA_HOME` (default `~/.local/share`) or
each entry of `$XDG_DATA_DIRS` (default `/usr/local/share` and `/usr/share`;
both lists are split on `os.pathsep`). A declaration is git-config syntax:

    [check "secret-scan"]
        command = scrub-check
        args = --quiet
        hook = pre-commit
        paths = *
        order = 60
        enabled = true
        required = false
        mutates-index = false
        contract = 1

`command` must be a bare name, resolved on `PATH` when the check runs. `args`
is split as a POSIX shell would split it. `hook` and `paths` may repeat;
`paths` filters only the staged-set hooks (`pre-commit`, `pre-merge-commit`),
and a check none of whose globs match a staged path is not run and counts as
not applicable. Every declaration is validated before anything runs. An
unknown key, an unknown hook, an unknown contract, a path for a command, or an
id declared twice is a usage error (exit 2), and no check runs.

Checks run with index-changing ones first, then by `order`, then by id, so a
new id never reorders the others. Every enabled check runs even after one
refuses, so a single commit attempt reports everything. A check receives
`GIT_HYGIENE_HOOK` and `GIT_HYGIENE_CHECK` in its environment, and standard
input only for the hooks git feeds it to (`pre-push`, `post-rewrite` and the
server-side hooks).

### Exit contracts

| Code | Contract 1 | Contract 2 |
|---|---|---|
| 0 | pass | pass |
| 1 | refuse | refuse |
| 2 | usage error, refuse | usage error, refuse |
| 3 | undefined, refuse | not applicable, pass |
| 4 | undefined, refuse | could not run: refuse if required, else pass |
| other, or a signal | undefined, refuse | undefined, refuse |

A declaration without `contract` is contract 1, so an unconverted check keeps
its old meaning. A code outside the declared contract refuses whether or not
the check is required, and the message names the check, the code and the
contract. A command that is not on `PATH` refuses too, whatever the check's
requirement, since the declaration promised it.

The dispatcher captures what each check prints. Output from a pass or a
refusal is replayed. Output from a check that was not applicable, or that
could not run and is optional, is replayed only under `--verbose`, together
with a line saying why the check stood down. The dispatcher exits 0 when
nothing refused, 1 when something did, and 2 on a usage or configuration
error.

### Settings

Which checks run, and which are required, is resolved per repository from
these layers, each overriding the one before:

| Layer | Source |
|---|---|
| declaration | the check's own `enabled` and `required` |
| system | `/etc/git-hygiene.conf`, then `git-hygiene/config` under each `$XDG_CONFIG_DIRS` entry (default `/etc/xdg`) |
| user | `$XDG_CONFIG_HOME/git-hygiene/config`, default `~/.config/git-hygiene/config` |
| repository | `<work tree>/.git-hygiene`, tracked |
| clone | `<git dir>/info/git-hygiene` |
| environment | `GIT_HYGIENE_ENABLE`, `_DISABLE`, `_REQUIRE`, `_OPTIONAL` |
| flag | `--enable`, `--disable`, `--require`, `--optional` |

Files are git-config syntax, read with `git config --file NAME --no-includes
--null --list` from the file's own directory. Only `check.<id>.enabled` and
`check.<id>.required` are accepted. The id must be registered. Anything else,
including a subsection that is a path or a key that would name a command, is a
configuration error reported before any check runs; that restriction is what
keeps cloning a repository from running code out of it. An `include` or
`includeIf` key is ignored with a warning. `--explain` prints, per check, the
layer each effective setting came from.

A tracked setting may require a check whose input lives outside the
repository. For `deny-terms`, required means at least one private term source
must load. Without one, `check-identifiers` exits 4 after scanning against any
public terms, naming every private location it probed (including
`.deny-terms.private` in each ancestor the walk visited) and no term, and the
dispatcher refuses. Unrequired, the same outcome is a silent pass, which keeps
decision 0002's promise to contributors who have no list.

### File-mode normalization

`normalize-file-modes` looks at staged additions and modifications whose
index mode is 100644 or 100755. A staged blob beginning with `#!` should be
100755, anything else 100644. Paths matching a glob in `.gitmodes-exceptions`
at the work-tree root (one per line, `#` comments, matched with
`fnmatchcase`) keep their staged mode and are announced as exceptions. An
untracked exceptions file draws a warning; a pattern that matches every path
is refused with exit 2.

The new mode is written with `git update-index --cacheinfo MODE,BLOB,PATH`,
against the blob already staged. The working tree and the staged content are
untouched, so a partly staged file commits exactly what was staged. Each
changed path is printed on every run, and when `core.fileMode` is true a note
says `git status` may show the working file's mode differing from the index.
It exits 3 when no regular file was staged and 4 outside a work tree.

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
usage is limited to long-established commands: `diff --cached`, `show`,
`ls-files` (with `-s` and `-z`), `cat-file --batch-all-objects --batch-check`,
`cat-file -p`, `cat-file --batch`, `log --all --format` and `--raw`,
`rev-parse --show-cdup`, `rev-parse --git-dir`, `update-index --cacheinfo
MODE,BLOB,PATH` (the comma form arrived in 2.0), and `config --file
--no-includes --null --list`. The tested floor is 2.43.7, what RHEL 8.10
ships. The
framework path needs git 2.31; the native path does not. How each of these is
proven is in `Verification-Plan.md`.

## Known limits

`audit-tree --objects` runs a separate `git cat-file -p` for every object.
Its cost on a large history is unmeasured. Blobs, trees and commits are all
scanned. Binary objects are not skipped; they are decoded with replacement
characters and searched like text.

## Not yet decided

Whether `/etc/git-hygiene/deny-terms` should also accept a `.d/` directory,
for configuration tools that prefer dropping files to editing one. Deferred
until something asks for it.

Whether a public list should be able to require a minimum tool version, so a
list using newer syntax fails loudly on an old client instead of being read as
terms.
