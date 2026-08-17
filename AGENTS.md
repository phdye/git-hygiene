Project root:  Cygwin ~/repo/git-hygiene   (session docs: ~/repo/git-hygiene/a/)

# git-hygiene — working instructions

`pre-commit` hooks that keep engagement-specific identifiers — client and
organization names, project and repository names, internal codenames — out
of repositories. Built after a real leak in a sibling package
(`~/repo/azdo`): a client organization name and project name sat in test
fixtures from the first commit until an audit caught them, days before
publication. The standing "no client identifiers" rule had been written
down the whole time and did not prevent it. `README.md` has the full
design story; this file is about doing the work, not about the tool's own
behavior.

Read this top to bottom before touching anything. Where a section is thin,
that is because nothing has been established yet — say so rather than
filling it in from memory of another project.

This file is the authoritative record of the project's working conventions
and is written to be read by any AI coding agent, not one vendor's tool —
that is what the `AGENTS.md` name signals. `CLAUDE.md` at the repository
root is a one-line `@AGENTS.md` import, so a Claude Code session loads
this file automatically with nothing to keep in sync separately.
Machine-specific setup for this particular workstation — paths, shell
quirks, which interpreter resolves where — lives apart in
`a/doc/workstation-notes.md` and is not repeated here.

No roles are assigned in this project yet — it is small enough that one
session has generally owned the whole tree at a time. If that changes,
borrow `~/repo/azdo`'s pattern (`a/doc/roles.md`, `a/doc/concurrency.md`)
rather than inventing a new one; do not build role machinery here
speculatively.

## Read first — the things that are expensive or dangerous to get wrong

1. **This repo must itself stay client-agnostic, doubly so.** No
   organization, project, repo, user principal, host, or engagement name
   from any engagement — not in code, not in tests, not in fixtures, not in
   a comment, not in a commit message. This is the tool that enforces that
   property elsewhere; a leak here is the worst possible advertisement for
   it.

2. **The term list lives outside every repository, on purpose.** A denylist
   committed to a public repo publishes exactly what it conceals. The code
   here names no terms; the term file is `~/.config/git/deny-terms.txt`,
   never committed, anywhere. Do not add a bundled or example term list,
   even a "safe" one — the pattern of loading one from inside the repo is
   the mistake, regardless of what the example file contains.

3. **Two behaviors are load-bearing, not stylistic — do not "simplify"
   them.** The tool reports a file and line but never the matched term,
   since printing it would recreate the leak in scrollback, CI logs, and
   pasted error reports. And it matches on word boundaries, since substring
   matching fires on ordinary API names and a guard that cries wolf gets
   switched off. Both have tests.

4. **Silent pass when no term file exists is deliberate, not a bug.**
   Anyone cloning a public repo will not have
   `~/.config/git/deny-terms.txt`, and a check they cannot see must never
   block their work.

5. **Hook ids are a public API.** `deny-terms`, `deny-terms-msg`,
   `audit-tree`. A consumer pins `rev:` and names an id; renaming one
   breaks their config.

---

## The open blocker: pre-commit cannot run against an old git

**`pre-commit` 4.6.2 will not run against git 2.21**, and the oldest git
available in this project's own test environment is 2.21.0 (`git ls-files
-z --deduplicate` fails there with `error: unknown option 'deduplicate'`;
`--deduplicate` arrived in git 2.31). See `a/doc/workstation-notes.md` for
why that particular old version is what gets tested against here.

This code's own git usage is 2.21-clean (`diff --cached`, `show`,
`ls-files`, `cat-file --batch-all-objects --batch-check`, `log --all
--format` — all predate 2.21). The 19 end-to-end tests create real
repositories and drive real git directly, not through `pre-commit`, and
they pass under 2.21. Only the `pre-commit` runner itself is the
incompatible piece.

Recorded options, none chosen yet (`a/handoff/initial.md` has the full
reasoning): pin an old `pre-commit` where git is old; ship a plain
`.git/hooks/pre-commit` shim calling the console scripts directly, needing
no `pre-commit` at all; treat `audit-tree` as a manual pre-publish gate on
old-git machines; or run these hooks only where git is modern and treat an
old-git environment as a deployment target, not a development one. Read
the handoff before picking one — do not re-decide this from scratch
without it.

`pre-commit try-repo` has never actually succeeded against the old-git
test environment: the git version blocked it first, then a different git
installation on the same machine produced `bad pack header` cloning a
repo it had created. Neither failure is a defect in this code. The CI
`packaging` job (current git, `ubuntu-latest`) is the only place this has
been proven, and prove it there before trusting a local `try-repo` run.

---

## Layout & doc placement

| Path | Holds |
|---|---|
| `src/git_hygiene/` | the library: term loading, scanning, reporting, and the three console scripts (`check-identifiers`, `audit-tree`, `install-hooks`). |
| `tests/` | unit and end-to-end by default; `pytest -m packaging` needs a real `pre-commit` install and is slow. |
| `.pre-commit-hooks.yaml` | the public hook manifest — `deny-terms`, `deny-terms-msg`, `audit-tree`. |
| `.github/workflows/` | lint, test matrix, packaging job. CI runs on `ubuntu-latest` with a current git and is unaffected by the old-git blocker above. |
| `a/` | everything about *doing* the work. Never exported, never packaged. |

Within `a/`:

| Path | Holds |
|---|---|
| `a/doc/` | designs and standing instructions. `verification-discipline.md` (the failure shapes this project actually produces — read before claiming something is verified), `floor-checks.md` (the two checks that hold the 3.6.8 floor), `deny-term-resolution.md` (v0.2.0 design), `ci-term-provisioning.md` (getting a private list onto CI safely), `rejected-pre-commit-git-2.21-backport.md`, `workstation-notes.md`. |
| `a/handoff/` | session handoffs — read the latest one before starting |
| `a/issue/` | findings about a defect or a decision (create as needed; none yet) |
| `a/open-items/` | the living worklist (create as needed; none yet) |

**A document recording a decision not to do something is prefixed
`rejected-`.** The point of such a file is to stop the question being
reopened, and a neutral name defeats that: the reader has to open it to
learn they did not need to. The prefix puts the verdict in the directory
listing. The file's own first lines then state the decision and the single
condition that would reopen it, before any of the reasoning.
`a/doc/rejected-pre-commit-git-2.21-backport.md` is the pattern.

Applies to a settled negative decision, not to an open question leaning
negative. Something still undecided belongs in open items above, or in
`a/issue/`, under its own neutral name.

There is no `doc/` at the repo root yet, unlike `~/repo/azdo`. If design
material grows past what fits in `README.md`, start one rather than
letting `a/doc/` absorb material that would survive being handed to a
maintainer with no history on this project — which is also why
workstation-specific material is kept out of `a/doc/`'s main files and
confined to `workstation-notes.md`.

---

## Working conventions

- **Commits:** conventional `type(scope): summary`, imperative, present
  tense, first line under 72 characters, body explains why and not what,
  one logical phase per commit, no `Co-Authored-By`. Where a session is
  running through a tool bridge that mangles inline `-m` (see
  `a/doc/workstation-notes.md`), commit via `git commit -F <tempfile>`
  instead; a native shell can use `-m` normally.
- **Design-first.** Update `README.md` or the governing decision doc in the
  same change, first or alongside the code, never after. For this repo the
  README *is* the design doc — it is small enough that a separate
  `doc/Design.md` would just duplicate it.
- **Verify against real source at a known ref** (`git show <ref>:path`), not
  memory.
- **Verify by computing.** Run the test, the `pytest -m packaging` job, the
  `pre-commit validate-manifest`. Do not report a coverage number or a test
  count from memory — read it off the actual run. **Running something is
  necessary and not sufficient**: read `a/doc/verification-discipline.md`
  before claiming anything is verified. It records the failure shapes this
  project has actually produced — assertions that a broken implementation
  would also satisfy, untested cells of an environment cross-product,
  limitations inferred rather than tried, and summaries stated at a coarser
  grain than the work. Four defects reached `main` in one session through
  those, every one of them while "verify by computing" was being followed.
  For the 3.6.8 floor specifically, `a/doc/floor-checks.md` gives the two
  checks needed and why running the suite is not one of them on its own.
- **Ask clarifying questions before detailed answers or large changes;**
  state assumptions when proceeding unattended. Do not re-ask something
  already answered in the session.
- **AI Writing Instructions apply to on-disk prose** — docs, comments,
  commit messages. Banned-word list, prose over bullets, at most two em
  dashes per thousand words, norm stated first and exception second.
  Exempt: AI-instruction files, meaning this file, `CLAUDE.md`, and
  `a/doc/workstation-notes.md`.
- **Code comments are minimal.** Explain the non-obvious choice, not the
  obvious mechanism. Docstring bloat gets trimmed on sight.
- `pre-commit install` once per clone, on a machine whose git is new enough
  — see the blocker above before assuming this works everywhere.

---

## Open items

- **The native git-hook front end is built.** `install-hooks` (new console
  script, `src/git_hygiene/install_hooks.py`) writes `.git/hooks/pre-commit`
  and `.git/hooks/commit-msg` shims that call `check-identifiers` directly -
  no framework, no floor above git's own 2.21. Idempotent by reseeding, marks
  its own files so a foreign hook is left alone without `--force`, and
  supports `--dry-run` and `--uninstall`. Verified against a real commit
  under two different git installations on this machine - an old one
  (2.21) and a current Windows one - a term match blocks the commit, clean
  content does not. **Packaging now proven, not just claimed:** pushed to
  `https://github.com/phdye/git-hygiene` (public, created 2026-08-16) and
  CI run #1 on `7182367` passed clean - lint, `packaging` (the `pre-commit
  try-repo` job that has never once succeeded locally, per
  `a/doc/rejected-pre-commit-git-2.21-backport.md` and the `core.worktree`
  finding in `a/issue/`), and the full test matrix across Python 3.9
  through 3.13. `origin` is now this repo over SSH.
- **`tests/` is now 3.6.8-clean, decided and done.** No `from __future__
  import annotations`, no runtime PEP 585/604 generics, no
  `capture_output=`/`text=` (3.7+ only) - type comments and explicit
  `stdout`/`stderr`/`universal_newlines=` in their place, matching how
  `git_hygiene.terms.git()` already handled this in `src/`. Proven, not just
  compiled: `PYTHONPATH=src python3 -m pytest tests` under the project's
  pinned 3.6.9 test interpreter (see `a/doc/workstation-notes.md` for where
  that lives) with its pinned pytest 4.6.11 - 27 passed, 2 skipped (the
  packaging tests, correctly, since that path needs pre-commit and git >=
  2.31 by design). `test_installed_hook_actually_blocks_a_commit` now builds
  its own portable `check-identifiers` shim from `sys.executable` rather than
  assuming `pip install -e .` was run, so it passed there too without any
  package installed under that interpreter.
- **v0.2.0 deny-term resolution is built.** `src/git_hygiene/resolution.py`
  implements the layered, classified model in `a/doc/deny-term-resolution.md`;
  `terms.py` is now primitives beneath it (`compile_term`, `scan_text`,
  `report`, git helpers) and carries no layering knowledge. One deliberate
  deviation from the design, recorded at the top of that doc: loud-absence
  applies only to explicitly named sources, since making the auto-probed
  repo-root `.deny-terms` fatal would block every commit in every repo that
  lacks one. 47 tests pass under the project's pinned 3.6.9 interpreter, and
  `--explain`, class-aware printing and `--show-private-terms` were each
  driven by hand against a real repo there. Still to do before tagging:
  `--no-inherit`/`--no-walk`/`--walk-to` have tests but no hand-verification,
  `audit-tree --objects` performance against a large history remains
  unmeasured (a pre-existing gap, now with more per-hit work), and
  `.pre-commit-hooks.yaml` descriptions still describe the v0.1 behavior.
- Anything larger than a line gets its own file under `a/issue/` and is
  referenced from here.
