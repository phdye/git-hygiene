# git-hygiene — workstation notes

Project-specific machine facts only. General workstation setup — Cygwin
roots, `HOME` handling, desktop-commander quirks, which interpreter or
binary resolves where — is already covered by the global `CLAUDE.md` that
loads in every project session and isn't repeated here. See that file, not
this one, for anything that would be true of any repo on this machine.
Read `AGENTS.md` first regardless; this is supplementary.

## This package's own dev environment

`.venv/` at the repo root was built by
`C:\Program Files\Python313\python.exe` (3.13.2), is a Windows venv
(`Scripts/`, not `bin/`), and is gitignored. `pytest`, `pip`, `ruff`, and
`mypy` all run under that interpreter for this package specifically; hand
it `C:\...` paths, never `/tmp/...`.

The declared floor (`requires-python = ">=3.9"`, `target-version = "py39"`
in `pyproject.toml`) is the manifest's business, not the interpreter's —
do not read it as a Cygwin Python requirement. The actual runtime floor
this package targets is RHEL 8.10's Python 3.6.8, verified separately (see
`AGENTS.md`'s Working conventions and `a/doc/floor-checks.md`).

## The old-git test environment

This machine's oldest available git (2.21.0) is a deliberate RHEL 8.10
emulation choice, not a gap — see the global environment notes for why.
What's specific to this package: `pre-commit try-repo` has never actually
succeeded against it. The old git blocked it first; a different, current
git installation on the same machine then produced `bad pack header`
cloning a repo the old git had created. Neither failure is a defect in
this code.
