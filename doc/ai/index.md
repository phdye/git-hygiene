# Using git-hygiene

Read when: your repository uses git-hygiene, or is about to, and you need
its guarantees, how to wire it in, or what a run of it told you.

git-hygiene refuses a commit whose staged content or message contains a
forbidden term, and audits a whole repository for the same terms before it
is published. The terms are identifiers that tie a repository to where it
came from. It ships four `pre-commit` hooks and four console scripts. Every
page here stands alone; read the one that answers the question and stop.
The design, and the reasons behind it, are in
[../design/Architecture.md](../design/Architecture.md).

## What is always true

- A term from a private source is never printed unless the caller asks with
  `--show-private-terms` (or `GIT_HYGIENE_SHOW_PRIVATE_TERMS`). A hit from
  a private source is reported by location only. A term from a public
  source (a file named `.deny-terms`) is printed, unless `--no-show-terms`.
- `--explain` never prints a term, of either class, under any flag. Its
  output is safe to paste into an issue.
- Terms match case-insensitively on word boundaries: `atlas` matches
  `ATLAS` but not `atlas_client`.
- When no term source resolves, `check-identifiers` passes silently. This is
  deliberate: a contributor who clones a public repository has no list.
  `--require-private` (or `GIT_HYGIENE_REQUIRE_PRIVATE`) turns a missing
  private list into a refusal.
- Term lists live outside the repository. A private list that git tracks is
  a fatal error, and nothing is scanned. Never commit one; put `.*.private`
  and `*.private` in `.gitignore`.
- Any resolution error (tracked private list, unauthorized negation, class
  conflict, unreadable list, missing named `.deny-terms`) stops the run
  with exit 1 before anything is scanned.
- The hook ids `deny-terms`, `deny-terms-msg`, `audit-tree`,
  `normalize-file-modes` and the console-script names `check-identifiers`,
  `audit-tree`, `install-hooks`, `normalize-file-modes` are public API. A
  rename, or a change to arguments or exit semantics, is a major version.
- The hooks see staged changes only. Content already committed, including
  content removed from the working tree but still in history, is found only
  by `audit-tree` (`--objects` for the whole object store).
- `normalize-file-modes` writes: it changes modes in the index and in the
  working tree. `install-hooks` writes and removes files under
  `<git dir>/hooks/`. The other two commands only read.
- No runtime dependencies. Python 3.6.8 or newer. The hooks declare
  `minimum_pre_commit_version: "2.17.0"`.

Enforced by the suite: private terms withheld and `--no-show-terms`
(`tests/test_terms.py`, `tests/test_term_classes.py`); `--explain` naming no
refused private term (`tests/test_options.py`); word-boundary matching
(`tests/test_terms.py`); silent pass with no list and the requirement
(`tests/test_end_to_end.py`, `tests/test_hooks.py`); fatal tracked private
lists (`tests/test_resolution.py`); the hook ids and console-script names
(`tests/test_hooks.py`); and that these pages list exactly the commands,
options, environment variables and hook ids the code defines
(`tests/test_doc_ai.py`). Stated and not checked here: the versioning rule,
the absence of runtime dependencies (declared empty in `setup.cfg`), and the
Python floor, which is proven by separate runs described in
[../design/Verification-Plan.md](../design/Verification-Plan.md).

## The halves

    cli/    the four commands, wiring the hooks in, term sources, the
            environment, exit status and output, limits

## Route table

<!-- route-table:begin -->
| Read when | Page |
|---|---|
| you are about to run a git-hygiene command or wire its hooks into a repository, and need the page for that task. | [cli/index.md](cli/index.md) |
<!-- route-table:end -->

## Version described

The package takes its version from git tags through `setuptools_scm`; no
version number is written in the source tree. These pages describe the
interface as of tag `v0.2.0` (commit `c9ac37b`). Pin a tag in `rev:`, never a
branch, and check a pinned tag's behavior against these pages when it
predates that commit.

## Absent halves

There is no `api/` half. The package exposes no Python API for outside
use: the public interface named in the design is the hook ids and the
console scripts, nothing importable. Modules under `git_hygiene` are
implementation and may change without notice.
