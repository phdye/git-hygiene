Project root:  Cygwin ~/repo/git-hygiene   (session docs: ~/repo/git-hygiene/a/)

# git-hygiene — working instructions

`pre-commit` hooks that keep engagement-specific identifiers — client and
organization names, project and repository names, internal codenames — out
of repositories. Built after a real leak in a sibling package: a client
organization name and project name sat in test fixtures from the first
commit until an audit caught them, days before publication. The standing "no client identifiers" rule had been written
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
quirks, which interpreter resolves where — lives apart in the untracked
working notes and is not repeated here.

No roles are assigned in this project yet — it is small enough that one
session has generally owned the whole tree at a time. If that changes,
adopt an established roles/concurrency pattern rather than inventing a new
one; do not build role machinery here speculatively.

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
   them.** A term from a private source is never printed unless the caller
   asks, and `--explain` never prints a term at all, since printing one
   would recreate the leak in scrollback, CI logs, and pasted error
   reports (decision 0006). And it matches on word boundaries, since
   substring matching fires on ordinary API names and a guard that cries
   wolf gets switched off (decision 0003). Both have tests.

4. **Silent pass when no term file exists is deliberate, not a bug.**
   Anyone cloning a public repo will not have
   `~/.config/git/deny-terms.txt`, and a check they cannot see must never
   block their work.

5. **Hook ids are a public API.** `deny-terms`, `deny-terms-msg`,
   `audit-tree`, `normalize-file-modes`. A consumer pins `rev:` and names
   an id; renaming one breaks their config. The same holds for the
   console-script names.

6. **`pre-commit` is the front end (decision 0016).** Do not rebuild a
   dispatcher, a check registry or a settings layer here; a check is a
   console script plus a manifest entry. The manifest's
   `minimum_pre_commit_version` stays at 2.17.0, the newest release that
   installs on Python 3.6 (decision 0015).

---

## The framework at the floor

`pre-commit` 2.17.0 runs these hooks on the RHEL 8.10 replica
(`spike/pre-commit-at-floor`). `install-hooks` remains for a host with no
framework, writing shims that call `check-identifiers` directly. The
framework is deliberately not patched; decision 0008 has the reasoning. Its
4.6.1 and later releases need git 2.31, which 2.17.0 does not.

## CI is set aside

No CI until a RHEL 8.10 (Cygwin) runner exists; decision 0014. Do not treat
a CI result as verification, and do not shape a change to keep
`.github/workflows/ci.yml` green. The only `pre-commit try-repo` success on
record on CI is run #1 (2026-08-16). The packaging tests now run on the
replica with `pre-commit` 2.17.0 on `PATH`.

## Build tools are pinned to the floor

`[build-system]` pins setuptools 59.6.0, setuptools_scm 6.4.2 and wheel
0.37.1, the newest releases that run on Python 3.6.8; decision 0013. Package
metadata lives in `setup.cfg`, because that setuptools ignores a `[project]`
table. Never reintroduce `[project]` or raise these pins while the floor is
3.6. After touching either file, build and install at the floor
(`Verification-Plan.md`, "Floor, build").

---

## Layout & doc placement

| Path | Holds |
|---|---|
| `src/git_hygiene/` | the library: term loading, scanning, reporting, and the three console scripts (`check-identifiers`, `audit-tree`, `install-hooks`). |
| `tests/` | unit and end-to-end by default; `pytest -m packaging` needs a real `pre-commit` install and is slow. |
| `.pre-commit-hooks.yaml` | the public hook manifest — `deny-terms`, `deny-terms-msg`, `audit-tree`. |
| `setup.cfg` | package metadata, console scripts, extras (decision 0013). `pyproject.toml` holds the build pins and tool configuration. |
| `.github/workflows/` | lint, test matrix, packaging job on `ubuntu-latest`. Set aside; see "CI is set aside" above. |
| `doc/design/` | the specification, kept current: `Architecture.md` (what the package is) and `Verification-Plan.md` (how each claim is proven). |
| `doc/design/decisions/` | decision records, numbered, append-only, listed one-to-one in `index.md`; `tests/test_design_docs.py` enforces the listing. |
| `spike/<question>/` | one measurement per directory: a script, pinned inputs, dated `results-*.txt` transcripts. Never shipped (`MANIFEST.in`). |
| `test/spike-regen.tsv`, `test/spike-regen.sh` | the spike register and the runner that certifies every spike still reproduces. Run on the replica. |
| `doc/proposal/` | change proposals, one per file, named `<YYYY-MM-DD>.<topic>.md`. A proposal carries a status line and is kept when abandoned, never deleted; a withdrawn one moves to `doc/proposal/retired/`. |

The design tree is tracked (decision 0001). A change that alters behavior
amends `doc/design/` in the same commit; a settled question gets a new
record and an index row; a substantial or hard-to-undo change starts as a
proposal and waits for acceptance before any code.

Working notes — drafts, issue write-ups, session handoffs, the
worklist — are kept **outside version control** and are
deliberately not part of this repository or its history. They are local
to a working copy and are covered by a global ignore rule, so they never
reach a clone, a release artifact, or a published commit. Their layout and
filing conventions are documented with the notes themselves rather than
here, so that this file stays about the project rather than about how one
workstation is arranged.

Design material intended for maintainers belongs under `doc/`; `README.md`
is for the person installing the hooks. The test is whether a maintainer
with no history on this project would still want it; if the answer is no,
it is a working note, not documentation. A working note that passes the test
is rewritten for that reader and filed under `doc/`, never cited in place.

---

## Working conventions

- **Commits:** conventional `type(scope): summary`, imperative, present
  tense, first line under 72 characters, body explains why and not what,
  one logical phase per commit, no `Co-Authored-By`. Where a session is
  running through a tool bridge that mangles inline `-m`, commit via
  `git commit -F <tempfile>` instead; a native shell can use `-m` normally.
- **Design-first.** Update `doc/design/` (and `README.md` where users see
  the change) in the same commit as the code, never after.
- **Verify against real source at a known ref** (`git show <ref>:path`), not
  memory.
- **Verify by computing.** Run the test, the `pytest -m packaging` job, the
  `pre-commit validate-manifest`. Do not report a coverage number or a test
  count from memory — read it off the actual run. **Running something is
  necessary and not sufficient**: read `doc/design/Verification-Plan.md`
  before claiming anything is verified. It records the failure shapes this
  project has actually produced — assertions that a broken implementation
  would also satisfy, untested cells of an environment cross-product,
  limitations inferred rather than tried, and summaries stated at a coarser
  grain than the work. Four defects reached `main` in one session through
  those, every one of them while "verify by computing" was being followed.
  For the 3.6.8 floor specifically, the same document gives the two
  checks needed and why running the suite is not one of them on its own.
- **Ask clarifying questions before detailed answers or large changes;**
  state assumptions when proceeding unattended. Do not re-ask something
  already answered in the session.
- **AI Writing Instructions apply to on-disk prose** — docs, comments,
  commit messages. Banned-word list, prose over bullets, at most two em
  dashes per thousand words, norm stated first and exception second.
  Exempt: AI-instruction files, meaning this file, `CLAUDE.md`, and
  the working notes.
- **Code comments are minimal.** Explain the non-obvious choice, not the
  obvious mechanism. Docstring bloat gets trimmed on sight.
- `pre-commit install` once per clone.

---

## Open items

- **The native git-hook front end is built.** `install-hooks` (new console
  script, `src/git_hygiene/install_hooks.py`) writes `.git/hooks/pre-commit`
  and `.git/hooks/commit-msg` shims that call `check-identifiers` directly -
  no framework, and no dependence on git's own version. Idempotent by
  reseeding, marks
  its own files so a foreign hook is left alone without `--force`, and
  supports `--dry-run` and `--uninstall`. Verified against a real commit
  under two different git installations on this machine - an old one
  (2.21) and a current Windows one - a term match blocks the commit, clean
  content does not. **Packaging now proven, not just claimed:** pushed to
  `https://github.com/phdye/git-hygiene` (public, created 2026-08-16) and
  CI run #1 on `7182367` passed clean - lint, `packaging` (the `pre-commit
  try-repo` job that has never once succeeded locally, per
  the backport decision record and the `core.worktree` finding), and the
  full test matrix across Python 3.9
  through 3.13. `origin` is now this repo over SSH. CI has since been set
  aside (decision 0014), so that run is history, not a standing proof.
- **`tests/` is now 3.6.8-clean, decided and done.** No `from __future__
  import annotations`, no runtime PEP 585/604 generics, no
  `capture_output=`/`text=` (3.7+ only) - type comments and explicit
  `stdout`/`stderr`/`universal_newlines=` in their place, matching how
  `git_hygiene.terms.git()` already handled this in `src/`. Proven, not just
  compiled: `PYTHONPATH=src python3 -m pytest tests` under the project's
  pinned 3.6.9 test interpreter with its pinned pytest 4.6.11 - 27 passed,
  2 skipped (the
  packaging tests, correctly, since that path needs pre-commit and git >=
  2.31 by design). `test_installed_hook_actually_blocks_a_commit` now builds
  its own portable `check-identifiers` shim from `sys.executable` rather than
  assuming `pip install -e .` was run, so it passed there too without any
  package installed under that interpreter.
- **v0.2.0 deny-term resolution is built.** `src/git_hygiene/resolution.py`
  implements the layered, classified model from the design notes;
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
- **Filename-authoritative classes are built** (2026-09-16; decisions
  0004/0006 amended). The multi-check dispatcher built the same day was
  replaced by the `pre-commit` front end (decision 0016, superseding 0012);
  both proposals carry implementation decision logs. The two sibling tools'
  checks become entries in each repository's `.pre-commit-config.yaml`,
  written in those tools' own repositories.
- Anything larger than a line gets its own file in the working notes and is
  referenced from here.
