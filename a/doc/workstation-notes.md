# git-hygiene — workstation notes

Machine-specific facts for driving this repo from Philip's workstation.
None of this generalizes past this one machine — a contributor working
anywhere else, or an agent other than Claude Desktop bridged through
desktop-commander, gets nothing from this file and should skip it. Read
`AGENTS.md` first; this is supplementary.

## Two Cygwin roots

Workstation is Windows + Cygwin, two roots. `C:\-\rhel\root` is the RHEL
8.10 emulation and, by standing instruction, where all work runs: every
shell, every git invocation, every file write. `C:\-\cygwin\root` is the
primary root; it holds the repositories but is not what you drive from.
cygdrive prefix is `/` in both, so `/c/...` is `C:\...`.

This repo lives at `~/repo/git-hygiene`, and `~/repo` is a symlink through
`~/.primary/self/repo` into the primary root. The same POSIX path reaches
the same tree from either root.

**Start every desktop-commander shell by removing `HOME`:**

    Remove-Item Env:HOME -EA 0 ; & 'C:\-\rhel\root\bin\bash.exe' -lc '...'

`HOME` arrives pointing at the Windows profile `/c/Users/phili`, the wrong
home for both roots. Take it away and Cygwin derives `/home/phili` from the
account database on the first pass.

## Git identity

**Unmodified default.** No `includeIf` in `~/.gitconfig` reaches this path
— that rewrite only applies under `~/azdo`, a different tree one level up
from `~/repo/azdo`. Commits here are Philip Dye &lt;phdye@acm.org&gt;,
which is correct: this is a public tool, not anything client-scoped.
Confirmed live 2026-08-16: `git config user.email` returns `phdye@acm.org`
in this repo.

## Interpreter

**Windows Python, not a Cygwin one.** `.venv/` at the repo root was built
by `C:\Program Files\Python313\python.exe` (3.13.2), is a Windows venv
(`Scripts/`, not `bin/`), and is gitignored. The rhel root's Cygwin Python
is pinned at 3.6.9 to match RHEL 8.10 and cannot serve this package; a
primary-root Cygwin binary cannot even launch from a rhel shell, since the
two roots carry incompatible `cygwin1.dll` builds. `pytest`, `pip`,
`ruff`, and `mypy` all run under the Windows interpreter; hand it `C:\...`
paths, never `/tmp/...`. The declared floor (`requires-python = ">=3.9"`,
`target-version = "py39"` in `pyproject.toml`) is the manifest's business,
not the interpreter's — do not read it as a Cygwin Python requirement. The
actual runtime floor this package targets is RHEL 8.10's Python 3.6.8,
verified separately under the rhel root's 3.6.9 (see `AGENTS.md`'s Working
conventions and `a/doc/floor-checks.md`).

## The old-git test environment, in detail

**RHEL-8.10 emulation, the `C:\-\rhel\root` named above.** git 2.21.0 is
what's there, and it is deliberate: the root is built from a `circa/2019`
Cygwin Time Machine snapshot to match what RHEL 8.10 actually ships, and
raising the git version there would defeat the point of the instance. It
is not a gap to patch over.

`pre-commit try-repo` has never actually succeeded in this environment: git
2.21 blocked it first, then Windows git on PATH produced `bad pack header`
cloning a Cygwin-created repo. Neither failure is a defect in this code.

---

## Tooling constraints (the desktop-commander bridge)

**Applies to a Claude Desktop session only.** This section is about
desktop-commander, which runs `powershell.exe` and shells out from there. A
Claude Code session has a native shell and none of these constraints bind
it, though the two-roots rule and the path facts above still do.

- Invoke bash by absolute path:
  `& 'C:\-\rhel\root\bin\bash.exe' -lc '...'` via `start_process`. Plain
  `bash` inside a DC-invoked shell resolves off DC's PATH to Git Bash, not
  the Cygwin bash you meant — use `/bin/bash` there too.
- DC file tools take Windows paths. Translate POSIX by prepending
  `C:\-\rhel\root` and flipping `/` to `\`. That path resolves through
  native NT symlinks in the `~/.primary` chain; if a link there ever
  regresses to Cygwin's sys format, the tools answer `[NOT_FOUND]` and the
  primary-root spelling (`C:\-\cygwin\root\home\phili\repo\git-hygiene`)
  is the fallback. Both reach the same bytes.
- **The PowerShell-to-bash boundary mangles** single and double quotes, `<`,
  `>`, `|`, `#`, `[`, `]`, `(`, `)`, `$(...)`, heredocs, and `for … done`
  loops. Write logic to a temp script and run it, or redirect to a file and
  read that back. For grep use `-e word`. For multi-line input, write a
  temp file and pass it. This is the mangling AGENTS.md's commit convention
  works around with `git commit -F <tempfile>`.
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
