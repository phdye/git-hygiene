Project root:  Cygwin ~/repo/git-hygiene   (session docs: ~/repo/git-hygiene/a/)

# git-hygiene — working instructions

`pre-commit` hooks that keep engagement-specific identifiers — client and
organization names, project and repository names, internal codenames — out of
repositories. Built after a real leak in a sibling package (`~/repo/azdo`):
a client organization name and project name sat in test fixtures from the
first commit until an audit caught them, days before publication. The standing
"no client identifiers" rule had been written down the whole time and did not
prevent it. `README.md` has the full design story; this file is about doing
the work, not about the tool's own behavior.

Read this top to bottom before touching anything. Where a section is thin,
that is because nothing has been established yet — say so rather than filling
it in from memory of another project.

This file on disk is the authoritative copy. `CLAUDE.md` at the repository
root imports it, so a Claude Code session picks it up without being asked. A
copy held as Claude Project knowledge is a snapshot and goes stale the moment
this one changes; re-uploading it is part of editing it, not a separate chore.
Where the two disagree, the disk wins.

No roles are assigned in this project yet — it is small enough that one
session has generally owned the whole tree at a time. If that changes, borrow
`~/repo/azdo`'s pattern (`a/doc/roles.md`, `a/doc/concurrency.md`) rather than
inventing a new one; do not build role machinery here speculatively.

## Read first — the things that are expensive or dangerous to get wrong

1. **This repo is client-agnostic and stays that way, doubly so.** No
   organization, project, repo, user principal, host, or engagement name from
   any engagement — not in code, not in tests, not in fixtures, not in a
   comment, not in a commit message. This is the tool that enforces that
   property elsewhere; a leak here is the worst possible advertisement for it.

2. **The term list lives outside every repository, on purpose.** A denylist
   committed to a public repo publishes exactly what it conceals. The code
   here names no terms; the term file is `~/.config/git/deny-terms.txt`,
   never committed, anywhere. Do not add a bundled or example term list, even
   a "safe" one — the pattern of loading one from inside the repo is the
   mistake, regardless of what the example file contains.

3. **Two behaviors are load-bearing, not stylistic — do not "simplify" them.**
   The tool reports a file and line but never the matched term, since
   printing it would recreate the leak in scrollback, CI logs, and pasted
   error reports. And it matches on word boundaries, since substring matching
   fires on ordinary API names and a guard that cries wolf gets switched off.
   Both have tests.

4. **Silent pass when no term file exists is deliberate, not a bug.** Anyone
   cloning a public repo will not have `~/.config/git/deny-terms.txt`, and a
   check they cannot see must never block their work.

5. **Hook ids are a public API.** `deny-terms`, `deny-terms-msg`, `audit-tree`.
   A consumer pins `rev:` and names an id; renaming one breaks their config.

---

## The open blocker: pre-commit cannot run under the rhel root's git

**`pre-commit` 4.6.2 will not run against git 2.21, and the rhel root's git is
2.21.0.** Measured in `~/repo/azdo` under the rhel root: `git ls-files -z
--deduplicate` fails with `error: unknown option 'deduplicate'`.
`--deduplicate` arrived in git 2.31. The rhel root is a deliberate RHEL 8.10
emulation and its git version is the point of the instance, not a gap to patch
over — see the personal notes on the rhel root's pinning.

This code's own git usage is 2.21-clean (`diff --cached`, `show`, `ls-files`,
`cat-file --batch-all-objects --batch-check`, `log --all --format` — all
predate 2.21). The 19 end-to-end tests create real repositories and drive real
git directly, not through `pre-commit`, and they pass under 2.21. Only the
`pre-commit` runner itself is the incompatible piece.

Recorded options, none chosen yet (`a/handoff/initial.md` has the full
reasoning): pin an old `pre-commit` where git is old; ship a plain
`.git/hooks/pre-commit` shim calling the console scripts directly, needing no
`pre-commit` at all; treat `audit-tree` as the rhel root's manual pre-publish
gate; or run these hooks only on the workstation's modern git and treat the
rhel replica as a deployment target, not a development one. Read the handoff
before picking one — do not re-decide this from scratch without it.

`pre-commit try-repo` has never actually succeeded in this environment: git
2.21 blocked it first, then Windows git on PATH produced `bad pack header`
cloning a Cygwin-created repo. Neither failure is a defect in this code. The
CI `packaging` job is the only place this has been proven, and prove it there
before trusting a local `try-repo` run.

---

## Environment & machines

Workstation is Windows + Cygwin, two roots. `C:\-\rhel\root` is the RHEL 8.10
emulation and, by standing instruction, where all work runs: every shell,
every git invocation, every file write. `C:\-\cygwin\root` is the primary
root; it holds the repositories but is not what you drive from. cygdrive
prefix is `/` in both, so `/c/...` is `C:\...`.

This repo lives at `~/repo/git-hygiene`, and `~/repo` is a symlink through
`~/.primary/self/repo` into the primary root. The same POSIX path reaches the
same tree from either root.

**Start every desktop-commander shell by removing `HOME`:**

    Remove-Item Env:HOME -EA 0 ; & 'C:\-\rhel\root\bin\bash.exe' -lc '...'

`HOME` arrives pointing at the Windows profile `/c/Users/phili`, the wrong
home for both roots. Take it away and Cygwin derives `/home/phili` from the
account database on the first pass.

**Git identity here is the default one, unmodified.** No `includeIf` in
`~/.gitconfig` reaches this path — that rewrite only applies under `~/azdo`,
a different tree one level up from `~/repo/azdo`. Commits here are Philip Dye
&lt;phdye@acm.org&gt;, which is correct: this is a public tool, not anything
client-scoped. Confirmed live 2026-08-16: `git config user.email` returns
`phdye@acm.org` in this repo.

**The interpreter is Windows Python, not a Cygwin one.** `.venv/` at the repo
root was built by `C:\Program Files\Python313\python.exe` (3.13.2), is a
Windows venv (`Scripts/`, not `bin/`), and is gitignored. The rhel root's
Cygwin Python is pinned at 3.6.9 to match RHEL 8.10 and cannot serve this
package; a primary-root Cygwin binary cannot even launch from a rhel shell,
since the two roots carry incompatible `cygwin1.dll` builds. `pytest`, `pip`,
`ruff`, and `mypy` all run under the Windows interpreter; hand it `C:\...`
paths, never `/tmp/...`. The declared floor (`requires-python = ">=3.9"`,
`target-version = "py39"` in `pyproject.toml`) is the manifest's business, not
the interpreter's — do not read it as a Cygwin Python requirement.

---

## Layout & doc placement

| Path | Holds |
|---|---|
| `src/git_hygiene/` | the library: term loading, scanning, reporting, and the three console scripts (`check-identifiers`, `audit-tree`, `install-hooks`). |
| `tests/` | unit and end-to-end by default; `pytest -m packaging` needs a real `pre-commit` install and is slow. |
| `.pre-commit-hooks.yaml` | the public hook manifest — `deny-terms`, `deny-terms-msg`, `audit-tree`. |
| `.github/workflows/` | lint, test matrix, packaging job. CI runs on `ubuntu-latest` with a current git and is unaffected by the rhel-root blocker above. |
| `a/` | everything about *doing* the work. Never exported, never packaged. |

Within `a/`:

| Path | Holds |
|---|---|
| `a/doc/` | designs and standing instructions, including this file |
| `a/handoff/` | session handoffs — read the latest one before starting |
| `a/issue/` | findings about a defect or a decision (create as needed; none yet) |
| `a/open-items/` | the living worklist (create as needed; none yet) |

**A document recording a decision not to do something is prefixed
`rejected-`.** The point of such a file is to stop the question being
reopened, and a neutral name defeats that: the reader has to open it to learn
they did not need to. The prefix puts the verdict in the directory listing.
The file's own first lines then state the decision and the single condition
that would reopen it, before any of the reasoning. `a/doc/rejected-pre-commit-git-2.21-backport.md`
is the pattern.

Applies to a settled negative decision, not to an open question leaning
negative. Something still undecided belongs in open items above, or in
`a/issue/`, under its own neutral name.

There is no `doc/` at the repo root yet, unlike `~/repo/azdo`. If design
material grows past what fits in `README.md`, start one rather than letting
`a/doc/` absorb material that would survive being handed to a stranger with no
context about this workstation or how the work gets done.

---

## Working conventions

- **Commits:** conventional `type(scope): summary`, imperative, present
  tense, first line under 72 characters, body explains why and not what, one
  logical phase per commit, no `Co-Authored-By`. Commit via
  `git commit -F <tempfile>`; inline `-m` gets mangled crossing the
  PowerShell boundary from a desktop-commander session. That is a
  desktop-commander workaround; a native shell can use `-m` normally.
- **Design-first.** Update `README.md` or the governing decision doc in the
  same change, first or alongside the code, never after. For this repo the
  README *is* the design doc — it is small enough that a separate
  `doc/Design.md` would just duplicate it.
- **Verify against real source at a known ref** (`git show <ref>:path`), not
  memory.
- **Verify by computing.** Run the test, the `pytest -m packaging` job, the
  `pre-commit validate-manifest`. Do not report a coverage number or a test
  count from memory — read it off the actual run.
- **Ask clarifying questions before detailed answers or large changes;**
  state assumptions when proceeding unattended. Do not re-ask something
  already answered in the session.
- **AI Writing Instructions apply to on-disk prose** — docs, comments, commit
  messages. Banned-word list, prose over bullets, at most two em dashes per
  thousand words, norm stated first and exception second. Exempt:
  AI-instruction files, meaning this file and `CLAUDE.md`.
- **Code comments are minimal.** Explain the non-obvious choice, not the
  obvious mechanism. Docstring bloat gets trimmed on sight.
- `pre-commit install` once per clone, on a machine whose git is new enough —
  see the blocker above before assuming this works on the rhel root.

---

## Tooling constraints (the workstation bridge)

**Applies to a Claude Desktop session only.** This section is about
desktop-commander, which runs `powershell.exe` and shells out from there. A
Claude Code session has a native shell and none of these constraints bind it,
though the rhel-root rule and the path facts above still do.

- Invoke bash by absolute path:
  `& 'C:\-\rhel\root\bin\bash.exe' -lc '...'` via `start_process`. Plain
  `bash` inside a DC-invoked shell resolves off DC's PATH to Git Bash, not the
  Cygwin bash you meant — use `/bin/bash` there too.
- DC file tools take Windows paths. Translate POSIX by prepending
  `C:\-\rhel\root` and flipping `/` to `\`. That path resolves through native
  NT symlinks in the `~/.primary` chain; if a link there ever regresses to
  Cygwin's sys format, the tools answer `[NOT_FOUND]` and the primary-root
  spelling (`C:\-\cygwin\root\home\phili\repo\git-hygiene`) is the fallback.
  Both reach the same bytes.
- **The PowerShell-to-bash boundary mangles** single and double quotes, `<`,
  `>`, `|`, `#`, `[`, `]`, `(`, `)`, `$(...)`, heredocs, and `for … done`
  loops. Write logic to a temp script and run it, or redirect to a file and
  read that back. For grep use `-e word`. For multi-line input, write a temp
  file and pass it.
- **DC gets no user environment block.** A variable set in `HKCU\Environment`
  reads empty in a DC-spawned PowerShell even though the machine environment
  arrives intact. Set anything depended on explicitly in the script —
  relevant here for `GIT_DENY_TERMS`, which this tool itself reads.
- Files written through DC land mode `100755`. For source and docs that should
  be `100644`, run `chmod 644 <files>` then
  `git update-index --chmod=-x <files>` before committing, and verify with
  `git ls-files -s <path>`. `edit_block` rewrites the file and resets the
  staged blob and mode, so redo that after editing a staged file.
- `write_file` refuses to create a file whose parent directory does not
  exist — `mkdir -p` first. It nags above 30 lines and refuses to overwrite
  without an explicit mode. Chunked writes are not atomic; a mid-write
  disconnect leaves a truncated file.
- The bridge is flaky. Four-minute `read_file` timeouts and transient
  `502 origin_bad_gateway` both recover on retry; reload tool schemas after a
  reconnect.
- `python3 -i` through PowerShell hits the Microsoft Store shim and fails.
  Use Cygwin bash `python3` for anything that needs the rhel root's
  interpreter; this package's own dev tooling needs Windows Python instead
  (see above), invoked with a `C:\...` path.

---

## Open items

- **The native git-hook front end is built.** `install-hooks` (new console
  script, `src/git_hygiene/install_hooks.py`) writes `.git/hooks/pre-commit`
  and `.git/hooks/commit-msg` shims that call `check-identifiers` directly -
  no framework, no floor above git's own 2.21. Idempotent by reseeding, marks
  its own files so a foreign hook is left alone without `--force`, and
  supports `--dry-run` and `--uninstall`. Verified against a real commit under
  both Cygwin git 2.21 (rhel root) and Git for Windows - a term match blocks
  the commit, clean content does not. **Packaging now proven, not just
  claimed:** pushed to `https://github.com/phdye/git-hygiene` (public,
  created 2026-08-16) and CI run #1 on `7182367` passed clean - lint,
  `packaging` (the `pre-commit try-repo` job that has never once succeeded
  locally, per `a/doc/rejected-pre-commit-git-2.21-backport.md` and the
  `core.worktree` finding in `a/issue/`), and the full test matrix across
  Python 3.9 through 3.13. `origin` is now this repo over SSH.
- **`tests/` is now 3.6.8-clean, decided and done.** No `from __future__
  import annotations`, no runtime PEP 585/604 generics, no
  `capture_output=`/`text=` (3.7+ only) - type comments and explicit
  `stdout`/`stderr`/`universal_newlines=` in their place, matching how
  `git_hygiene.terms.git()` already handled this in `src/`. Proven, not just
  compiled: `PYTHONPATH=src python3 -m pytest tests` under the rhel root's
  Python 3.6.9 with its pinned pytest 4.6.11 - 27 passed, 2 skipped (the
  packaging tests, correctly, since that path needs pre-commit and git >=
  2.31 by design). `test_installed_hook_actually_blocks_a_commit` now builds
  its own portable `check-identifiers` shim from `sys.executable` rather than
  assuming `pip install -e .` was run, so it passed there too without any
  package installed under that interpreter.
- **v0.2.0 deny-term resolution is designed but not built.** See
  `a/doc/deny-term-resolution.md`. Suggested order: native front end first,
  then `--explain` against the current single-file model as a v0.1.1, then the
  resolution module with the tracked-private-file test written first.
- Anything larger than a line gets its own file under `a/issue/` and is
  referenced from here.
