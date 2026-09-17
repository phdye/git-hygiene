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
| `install_hooks.py` | Console script `install-hooks`: writes `pre-commit` and `commit-msg` shims that call `check-identifiers`, for a host without the framework. |
| `filemode.py` | Console script `normalize-file-modes`: sets staged files' modes from their content, in the index and the working tree. |
| `options.py` | The resolution options and environment variables both scanning commands share. |

The `pre-commit` framework is the front end
([0016](decisions/0016-pre-commit-is-the-hook-front-end.md)). It composes,
orders and runs the checks named in a repository's `.pre-commit-config.yaml`,
this package's and anybody else's, and it sets unstaged changes aside while
they run. The package supplies checks and nothing that decides which of them
run.

It has no runtime dependencies. A hook that pulls in a dependency
tree breaks in somebody else's environment, and this one has to run on the
machines it protects.

## Public interface

Four hook ids are declared in `.pre-commit-hooks.yaml`. They are an API.
A consumer pins `rev:` and names one. Each declares
`minimum_pre_commit_version: "2.17.0"`, the newest release that installs on
Python 3.6 ([0015](decisions/0015-hooks-admit-pre-commit-2-17.md)).

| id | Stage | Entry |
|---|---|---|
| `deny-terms` | pre-commit | `check-identifiers --staged` |
| `deny-terms-msg` | commit-msg | `check-identifiers --message` |
| `audit-tree` | manual | `audit-tree` |
| `normalize-file-modes` | pre-commit | `normalize-file-modes` |

The console scripts are `check-identifiers`, `audit-tree`, `install-hooks`
and `normalize-file-modes`.

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
walk otherwise stops at `$HOME` or the filesystem root. Both bounds are
compared after resolving symlinks, so a bound named through a link still
holds.

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
| `--require-private` (`check-identifiers` only) | `--no-require-private` | `GIT_HYGIENE_REQUIRE_PRIVATE` |

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
cannot see must never block their work.

`--require-private` reverses that for one repository or one machine. A
repository adds it to the hook's `args:` in its tracked config; a machine sets
`GIT_HYGIENE_REQUIRE_PRIVATE`. With it, `check-identifiers` refuses when no
private source loaded, after scanning against whatever public terms did load,
and names every private location it probed (including `.deny-terms.private`
in each ancestor the walk visited) and no term. A public list alone does not
satisfy it. A staged set with nothing readable as text still passes, since
there was nothing to check, and so does a missing message file. The commit
message is text, so `deny-terms-msg` applies the requirement to every commit
it runs on. `audit-tree` says on stderr that it
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
| 0 | Nothing found, or no term resolved and none was required |
| 1 | A term was found, resolution was fatal, or a required private list is missing |
| 2 | Usage error, including a malformed boolean environment variable |

`install-hooks` exits 1 when a hook it would write belongs to something else
and `--force` was not given. `normalize-file-modes` exits 1 outside a work
tree or when git refuses the index update, and 2 for an unusable exceptions
file.

## File-mode normalization

`normalize-file-modes` looks at staged additions and modifications whose
index mode is 100644 or 100755. A staged blob beginning with `#!` should be
100755, anything else 100644. Paths matching a glob in `.gitmodes-exceptions`
at the work-tree root (one per line, `#` comments, matched with
`fnmatchcase`) keep their staged mode and are announced as exceptions. An
untracked exceptions file draws a warning; a pattern that matches every path
is refused with exit 2. A commit that stages no regular file passes.

The new mode is written with `git update-index --cacheinfo MODE,BLOB,PATH`,
against the blob already staged, so a partly staged file commits exactly what
was staged. `--chmod` is not used: given a path it re-reads the working file
and would commit the unstaged half.

The working file then gets the same mode. The framework compares `git diff`
before and after each hook and fails one that changed it, and with
`core.fileMode` true an index mode the working file lacks is such a change;
the commit would be refused once and land on the second try. Where the working
file holds exactly the staged blob, which is always so under the framework
because it sets unstaged changes aside first, `git checkout-index -f`
rewrites it, so git's own notion of the executable bit applies. Otherwise the
permission bits are changed directly. Each changed path is printed on every
run. A path whose working mode still differs afterwards, with `core.fileMode`
true, is named with a note that `git status` will show it.

## Hooks without the framework

`install-hooks` covers a host that cannot have the framework
([0008](decisions/0008-old-git-gets-native-hooks-not-a-patched-framework.md)).
None is known; the command is kept because `v0.1.0` published it. It writes
two shims, `pre-commit` running `check-identifiers --staged` and `commit-msg`
running `check-identifiers --message "$1"`. Each finds `check-identifiers` on
`PATH` and refuses the commit when it is absent. File-mode normalization and
other tools' checks need the framework.

Every run rewrites each shim from a fixed template and removes any other file
carrying the installer's marker comment, which includes shims an unreleased
dispatcher wrote for other hooks. A file lacking the marker belongs to someone
else and is left alone unless `--force` is given; `--uninstall` removes every
marked file and nothing else, and `--dry-run` writes nothing. The shim is
written as bytes, so a Windows interpreter cannot turn its line endings into
CRLF.

## Floor hosts

A RHEL 8.10 host runs `pre-commit` 2.17.0. The manifest's hooks use
`language: python`, so on first use per revision the framework clones this
repository and builds the package into a virtual environment. The build needs
the pinned setuptools, setuptools_scm and wheel
([0013](decisions/0013-build-tools-run-at-the-floor.md)) from PyPI, or from a
local directory named in `PIP_FIND_LINKS` with `PIP_NO_INDEX=1`. A host that
can reach neither installs the package once and names its commands in a
`repo: local` entry with `language: system`. The spikes under `spike/` pin
the framework's dependency closure by hash, which is also a usable wheelhouse
list.

## Security surface

A repository's `.pre-commit-config.yaml` decides what runs at commit time, and
a `repo: local` entry can name any command. Nothing runs until someone runs
`pre-commit install` in the clone, but afterwards a pull that changes the file
changes what the next commit runs. That is the framework's standing model and
this project accepts it (decision 0016); pinning `rev:` to tags and reading
changes to the config file are the mitigations.

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
MODE,BLOB,PATH` (the comma form arrived in 2.0), `hash-object`,
`checkout-index -f`, and `diff --raw -z`. The tested floor is 2.43.7, what
RHEL 8.10 ships, with `pre-commit` 2.17.0. The framework's releases from
4.6.1 on need git 2.31; 2.17.0 and the native path do not. How each of these is
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
