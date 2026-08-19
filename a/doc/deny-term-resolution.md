# Deny term resolution: layered sources, classification, and merge

Status: **implemented**, 2026-08-16, in `src/git_hygiene/resolution.py` with
`terms.py` reduced to primitives beneath it. Proposal written the same day;
this document was the design and remains the authority on *why*. Targets
v0.2.0, a major behavioral change under the project's own versioning policy.

One deliberate deviation from the proposal below, made during
implementation. The "source file absent" row of the class table says a
missing public source fails loudly. As written that would make the
repo-root `.deny-terms` layer fatal in every repository that does not have
one, which is nearly all of them - it would break `check-identifiers` on
every commit everywhere, the opposite of the "a check they cannot see must
never block their work" rule this project is built on. The loud-absence
rule therefore applies only to a source the operator *explicitly named*
(`--terms`, `GIT_DENY_TERMS`); every auto-probed layer stays silently
absent. Tested both ways in `tests/test_resolution.py`.

Verified under the RHEL 8.10 floor, not just the dev interpreter: 47 tests
pass under the rhel root's Python 3.6.9, and `--explain`, class-aware
printing, and `--show-private-terms` were each exercised by hand against a
real repository there.

## Why

Today one file is consulted: `~/.config/git/deny-terms.txt`, or whatever
`GIT_DENY_TERMS` names. That has two problems.

The resolution is invisible. `Path.home()` differs between Windows Python and a
Cygwin shell, so the file is often not where the user believes it is, and the
result is finding no terms and passing everything. The README already calls
this the worst failure mode available to a check like this, and documents a
manual probe as the workaround. A diagnostic is a better answer than a warning.

The single file also forces every term into one scope. A system-wide list on a
build host, a personal list spanning `~/repo/*`, and a list a team wants
enforced on every clone are different things with different lifetimes and
different audiences, and they cannot currently coexist.

## The classification, and what it is not

The first design constraint of this project is that a denylist committed to a
public repository publishes exactly what it conceals. That is true of some
lists and false of others. A former product codename, a decommissioned internal
hostname, a predecessor company name after an acquisition: all worth enforcing,
none secret, and a team reasonably wants them committed, reviewed and versioned
alongside the code they protect.

So the question is not whether a term file sits inside a repository. It is
whether the file may be committed, and that is a property of the terms, which
only the author knows. It is therefore declared rather than inferred.

Two classes. Every term file belongs to exactly one.

- **`private`**: the list is itself sensitive. Must never be tracked by git.
- **`public`**: the list is safe to publish. Expected to be tracked.

Declared in band, on the first non-blank line:

    # git-hygiene: public

**An undeclared file is `private`.** That is the safe direction, it keeps every
existing `~/.config/git/deny-terms.txt` working unchanged, and it makes
publishing a list an explicit act rather than an accident of file placement.

Filenames reinforce the declaration and do not carry it: `.deny-terms` for
public, `.deny-terms.private` for private. Where name and directive disagree,
the directive wins and the mismatch is reported. `.local` was considered and
rejected: it conveys scope, not secrecy, and a name that fails to say what it
protects is a name that gets copied wrong.

## What the class decides

Classification earns its complexity by resolving three behaviors that have no
single correct answer across both cases.

| | `private` | `public` |
|---|---|---|
| Tracked by git | Hard error, exit non-zero | Expected, no comment |
| Matched term printed | Only with `--show-private-terms` | Yes, by default |
| Source file absent | Silent pass | Fail loudly |

The absent row is the one that could not be decided before. Failing open is
correct for a private list, because a contributor cloning a public repository
will not have one and a check they cannot see must never block their work. It
is wrong for a public list, which ships with the repository, so its absence
means something is broken rather than something is unconfigured. A missing
declared-public source is an error naming the path.

The printing row is covered in its own section below.

## Resolution order

Lowest precedence first. Precedence governs negation authority only; term
accumulation is a union across all layers, so a later layer cannot drop an
earlier layer's terms except through an authorized negation.

| # | Source | Class | Notes |
|---|---|---|---|
| 1 | `/etc/git-hygiene/deny-terms` | declared | System wide. Either class. |
| 2 | `$XDG_CONFIG_HOME/git/deny-terms.txt`, else `~/.config/git/deny-terms.txt` | declared, usually private | The current location. Kept. |
| 3 | ancestor `.deny-terms` / `.deny-terms.private`, outermost first | declared | Walk described below. |
| 4 | repo root `.deny-terms` | public in practice | The committed team list. |
| 5 | `.git/info/deny-terms` | private in practice | Per clone. Uncommittable by construction, beside `.git/info/exclude`. |
| 6 | `GIT_DENY_TERMS` | declared | `os.pathsep` separated list of paths. |
| 7 | `--terms FILE`, repeatable | declared | Highest. |

Layers 4 and 5 are ordinary cases of 3 and of an explicit path; they are listed
separately because they are the two locations that should be documented as
conventional. `.git/info/deny-terms` is the recommended home for a private per
clone list precisely because nothing inside `.git/` can be committed.

A missing source at any layer is skipped silently when private, and is an error
when the file exists but declares public and cannot be read. See the absent row
above for the case of a public source that does not exist at all: that is only
detectable when something names it, which is why layers 4 through 7 are where
it applies.

## Merge semantics

**Union, not override.** `.gitignore` resolves deepest match wins because
ignoring is a boolean decision about one path. A deny term is a set member, and
a narrower scope must not silently drop what a broader scope forbids. Every
layer contributes; the merged set is the union.

**Negation exists and is constrained.** `!term` removes an inherited term, for
genuine false positives where narrowing at the source is not available to the
person hitting it. Because negation is the only way to reduce protection, it
carries the strictest rules in this design.

A negation is honored only when both hold:

- **Scope**: it appears in a layer at or above the layer that introduced the
  term. A repo local file cannot cancel a system wide term.
- **Class**: the negating source is at least as strict as the introducing
  source. A `public` source cannot negate a term introduced by a `private`
  source. Without this, a committed file could cancel a secret term, and the
  cancellation would be readable by everyone while the term itself was not.

An unauthorized negation is not silently dropped. It is an error naming both
sources, because a negation that appears to work and does not is the same
class of failure as a term file that appears to load and does not.

Every honored negation is reported by `--explain`, and counted in the summary
line of `audit-tree`. A silently cancelled term is the failure mode this whole
design exists to make impossible.

**Ordering within a file** does not matter. Terms and negations are collected
per layer, then layers are reduced in precedence order. A `!term` and a `term`
in the same file is an error, not a last-one-wins.

## Printing matched terms

Decided 2026-08-16, Philip, on the principle that user utility is the point and
that a report nobody can act on is a poor report.

**A term from a `public` source is printed by default.** It lives in a tracked
file in the same checkout, so withholding it discloses nothing and only forces
a manual search of the list. Naming it makes the hit actionable immediately,
which matters most on a large `audit-tree --objects` run reporting hits against
blobs that cannot be opened by path.

**A term from a `private` source is withheld by default**, location only, as
today. `--show-private-terms` (env `GIT_HYGIENE_SHOW_PRIVATE_TERMS`) prints
those too. It is opt-in because the default should be the cautious one, not
because the output is forbidden: an operator who wants the full report can have
it, and it is theirs to manage.

**Managing the consequences is the user's call, not the tool's.** CI logs are
long lived and often widely readable, and a private term printed into one is a
real exposure. That is a property of where the operator chose to run the tool
and what they chose to retain, and this project does not get to make that
decision for them by hiding information they asked for. The flag is documented
with the risk stated plainly, once, and then trusted.

**What the tool does not do is let the consequence become a commit.** Printing
a private term is permitted; committing a file that contains one is not, and
that is enforced by the hooks themselves rather than by discretion. A saved
transcript, a captured log, a pasted report: any of these staged in a repo
under `deny-terms` fails the commit exactly as any other leak would. The
guarantee is not that a private term never appears on a screen. It is that it
never reaches a repository, and that guarantee is mechanical.

For the same reason a tracked private term *file* remains a hard error, below.

This requires per pattern provenance: each compiled pattern carries its source
path and that source's class, so a merged set prints selectively rather than
all or nothing.

## A tracked private term file is a hard error

Checked with `git ls-files --error-unmatch <path>` (2.21 safe) for every
resolved source that is or defaults to `private` and lies inside a work tree.
Tracked means the list is committed, which is the exact leak this project
exists to prevent, and it is not something to warn about and continue past.

The error names the path, states that a private term file is tracked, and
exits non-zero. It does **not** print the terms, and it does not print how many
there are beyond a count. Remediation is the same as any leak: untrack it, move
it to `.git/info/deny-terms`, and rewrite history if it was ever pushed.

Scanning does not proceed. A run that reported clean while a private list sat
in the index would be worse than no run at all.

## The ancestor walk, and its guards

From the anchor directory, walk parent by parent collecting `.deny-terms` and
`.deny-terms.private`, then apply outermost first so nearer files hold higher
precedence for negation purposes.

The walk crosses directories nobody in particular controls, so it borrows
ssh's posture on config file trust:

- **Skip and report** any term file that is world writable, or not owned by the
  invoking user or by root. Reported, not silent, because a skipped source is
  a reduction in protection.
- **Stop** at the git top level, at `$HOME`, or at a filesystem boundary,
  whichever comes first. `--walk-to DIR` overrides, `--no-walk` disables.
- Never walk above `/`, and never follow a symlinked directory out of the
  bounded region.

On Windows, ownership and world writability are not meaningfully checkable
through `os.stat` in the way they are on POSIX. The check degrades to a
readability test there, and `--explain` says so rather than implying a
guarantee that was not made.

## Resolve once

Resolution happens exactly once per invocation, anchored at
`git rev-parse --show-toplevel`, falling back to the current directory outside
a work tree. One merged pattern set is built and reused for every file, blob
and commit message.

Per directory resolution in the manner of `.gitignore` is deliberately not
done. A deny term is a property of the repository rather than of a
subdirectory, and `audit-tree --objects` already reads every object
individually, so per path resolution would multiply that cost to answer a
question nobody asked.

## Diagnostics

`--explain` (also `check-identifiers --explain`, and unconditionally in
`audit-tree`'s summary) prints the full resolution, one line per candidate:

    source                                        class    status      terms
    /etc/git-hygiene/deny-terms                    -       absent          -
    /home/phili/.config/git/deny-terms.txt      private    loaded         16
    /home/phili/repo/x/.deny-terms               public    loaded          4
    /home/phili/repo/x/.git/info/deny-terms     private    loaded          2
    (walk) /home/phili/repo/.deny-terms          public    skipped: mode   -
    GIT_DENY_TERMS                                 -       unset           -

    22 terms from 4 sources, 1 skipped, 1 negation honored

Paths, classes, statuses and counts. Never terms, in either class, regardless
of `--show-terms`, because this output is what people paste into issues when
asking why the hook did or did not fire.

`--explain` is what retires the README's manual probe. The question "did it
find my list" stops being an inference from behavior and becomes an
observation. `audit-tree` prints the summary line unconditionally on the same
reasoning: it is a pre publish gate, and whether it audited against zero terms
is the entire question being asked of it.

Exit code for `--explain` is 0 when resolution succeeded even if zero terms
were found, and non-zero for the hard error conditions above. It reports
resolution; it does not scan.

## Interface

Per the project's CLI conventions, every setting has both an option and an
environment variable, option winning.

| Option | Env | Meaning |
|---|---|---|
| `--terms FILE` | `GIT_DENY_TERMS` | Explicit source, repeatable. Env is `os.pathsep` separated. |
| `--no-inherit` | `GIT_HYGIENE_NO_INHERIT` | Use only the highest explicit source. For tests and deterministic CI. |
| `--no-walk` | `GIT_HYGIENE_NO_WALK` | Skip the ancestor walk, keep the fixed layers. |
| `--walk-to DIR` | `GIT_HYGIENE_WALK_TO` | Bound the walk. |
| `--show-private-terms` | `GIT_HYGIENE_SHOW_PRIVATE_TERMS` | Also print matched terms from private sources. Public terms print by default. |
| `--no-show-terms` | - | Suppress all term printing, locations only. For a caller that wants today's behavior. |
| `--explain` | - | Print resolution and exit. |

`GIT_DENY_TERMS` changing from one path to a path list is the breaking change
that makes this v0.2.0. A single path remains valid input, so the common
existing usage keeps working; the semantics around it do not.

## The git floor, and what it forces

Decided 2026-08-16, Philip: keep every git invocation in this design safe on
very old git. `ls-files --error-unmatch` and `rev-parse --show-toplevel` both
long predate any version in play, so the design costs nothing to hold to this.

**Corrected the same day.** This section originally set the floor at 2.21
"matching RHEL 8.10 as the Python floor does". The Python parallel does not
hold: RHEL 8.10 ships Python 3.6.8 *and* git 2.43. The 2.21 came from the 2019
Cygwin Time Machine snapshot the verification replica was built from, and that
replica has since been moved to git 2.43.7. So no environment in play is below
`pre-commit`'s own 2.31 requirement.

The consequence for the front end therefore weakens from *required* to
*prudent*. `pre-commit` still cannot run below git 2.31, so a native git-hook
front end remains the only way to invoke these hooks on genuinely old git, and
on any host where the framework cannot be installed. It is no longer the only
usable path in this project's own environment. The constraint it places on this
design is unchanged and worth keeping: everything must be reachable from a
plain `.git/hooks/pre-commit` shell script with no `pre-commit` present, which
the option and environment surface above already satisfies.

## Implementation notes

**The 3.6.8 floor binds this**, per `pyproject.toml` and `a/doc/instructions.md`.
`dataclasses` is 3.7+, so the source and pattern records are
`typing.NamedTuple`. No `from __future__ import annotations`, no PEP 604 or 585
generics, no `subprocess.run(capture_output=)`. `os.scandir`, `pathlib` and f
strings are all available on 3.6 and fine to use.

Shape:

    class Source(NamedTuple):
        path: Path
        klass: str          # "public" | "private"
        declared: bool      # False means defaulted to private
        status: str         # loaded | absent | skipped:<reason> | error:<reason>
        terms: int

    class Pattern(NamedTuple):
        regex: "Pattern[str]"
        source: Path
        klass: str

`scan_text` returns hits carrying the matching pattern's provenance rather than
a bare location string, so `report` can decide per hit whether the term may be
printed. That is a signature change to two functions that the tests already
exercise heavily.

Word boundary matching and the location only default are unchanged and remain
load bearing.

## Versioning

v0.2.0, major by the project's own policy: `GIT_DENY_TERMS` gains list
semantics, the fail open guarantee becomes conditional on class, and
`scan_text` and `report` change shape. Hook ids do not change, so no consumer
config breaks on names.

The handoff records that no consumer has ever installed these hooks from a
`rev:` pin. That makes this break nearly free today and expensive the moment
anyone adopts, which is an argument for doing it before the first adoption
rather than after.

## Open questions

- Getting a *private* list's plaintext onto a CI runner safely - a
  provisioning question, not a resolution-layering one - is written up
  separately in `a/doc/ci-term-provisioning.md`. Nothing here changes as a
  result of it; `GIT_DENY_TERMS` already accepts any path and `report()`
  already withholds a private term by default, which is the entire surface
  that document builds on.
- Whether `/etc/git-hygiene/deny-terms` should also support a `.d/` directory,
  for configuration management tools that prefer dropping files over editing
  one. Deferred until something asks for it.
- Whether a public source should be able to require a minimum tool version, so
  a team list using a future syntax fails loudly on an old client rather than
  parsing as terms. Probably yes eventually, not now.
- Performance of the walk plus stat calls under `audit-tree --objects` on a
  large history is untested, though resolve once should make it irrelevant.
  The handoff already lists large repository performance as unverified.
