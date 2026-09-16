# Verification plan

What counts as proof for each property `Architecture.md` claims, and where
that proof runs. A property with no row here is not verified, whatever the
code appears to do.

## The gates

| Gate | Command | Where | Proves |
|---|---|---|---|
| Lint | `ruff check .` and `ruff format --check .` | workstation | style and the selected rule sets |
| Types | `mypy src/git_hygiene` | workstation | ordinary type errors, under `strict` |
| Suite | `pytest` | workstation | logic, and end-to-end behavior against real repositories and real git |
| Packaging | `pytest -m packaging` with pre-commit 2.17.0 on `PATH` | replica | that `pre-commit try-repo` installs and runs the hooks as a consumer would |
| Manifest | `pre-commit-validate-manifest .pre-commit-hooks.yaml` (2.17.0; `pre-commit validate-manifest` from 2.19.0) | replica | that the manifest parses |
| Floor, runtime | the suite under Python 3.6 | workstation | that the code executes at the floor |
| Floor, static | mypy 0.971 with `--python-version 3.6` | workstation | that the code is written for the floor |
| Floor, build | `pip wheel`, then install the wheel and the source tree, under Python 3.6 | workstation | that the package builds and installs at the floor |
| Design docs | `pytest tests/test_design_docs.py` | workstation | that the decision index and the records agree |
| Sdist | `pytest tests/test_sdist.py` | workstation (needs `setuptools_scm` in the interpreter) | that a tagged build ships no `spike/` path |
| Spikes | `test/spike-regen.sh` | replica | that every spike a decision cites still reproduces its findings |

CI is not a gate for now. The workflow runs on hosted Linux runners at
Python 3.9 to 3.13, which is not where these hooks are deployed, and it waits
for a RHEL 8.10 runner ([0014](decisions/0014-ci-waits-for-a-rhel-8-10-runner.md)).
The packaging gate moved to the replica, where pre-commit 2.17.0 is the
newest release that installs
([0015](decisions/0015-hooks-admit-pre-commit-2-17.md)).

The checks' criteria live in `tests/test_hooks.py`, the term-class
reproductions in `tests/test_term_classes.py`, and the framework's in the
packaging tests, which pin a snapshot of the working tree and commit through
an installed `pre-commit`. All of them keep every location the package reads
outside the repository inside the test's own directory (`tests/helpers.py`). The
sdist test skips, with a reason naming the dev extra, on an interpreter
without `setuptools_scm`. At the floor, `spike/build-at-floor` covers the
same property.

Unit tests prove logic; only `try-repo` proves packaging. An earlier version
of this facility passed every unit test and could not run as an installed
hook, because its entry point named a path that did not exist from the
consumer's directory. The packaging gate is required before any tag.

## The floor needs three checks

Running the suite at Python 3.6 shows the code runs there. It cannot show
the code is written for 3.6, because Python never evaluates a quoted
annotation. A field annotated `"re.Pattern[str]"` (a 3.8 name) passed every
test at 3.6 and would have failed anything that resolved the hint. Only a
type checker targeting 3.6 finds that class of defect.

Current mypy refuses any target below 3.10, so the static check needs mypy
0.971, which still accepts 3.6. It is a pure-Python wheel. Its `typed_ast`
dependency builds from source, which needs the Python development headers.
List the source files explicitly rather than passing the package directory,
so that the generated `_version.py` (which uses a 3.7 import) is left out:

    python3 -m mypy --python-version 3.6 --strict --no-incremental \
        src/git_hygiene/__init__.py src/git_hygiene/terms.py \
        src/git_hygiene/resolution.py src/git_hygiene/check_identifiers.py \
        src/git_hygiene/audit_tree.py src/git_hygiene/install_hooks.py \
        src/git_hygiene/options.py src/git_hygiene/filemode.py

At 3.6 the available pytest predates `pyproject.toml` support, so
`addopts` is not applied and the packaging tests are collected rather than
deselected. With `pre-commit` 2.17.0 on `PATH` they run; without it they
skip, and the skip reason must name the missing prerequisite. Read the
reason, not the count.

Neither of those builds anything. The suite imports the code straight from
`src/`, which is how a package that could not be built at 3.6 went unnoticed
from the first commit: its build requirements named setuptools and
setuptools_scm releases that need a newer interpreter
([0013](decisions/0013-build-tools-run-at-the-floor.md)).
The third check builds a wheel with `pip wheel --no-deps`, installs it into a
fresh virtual environment, installs the source tree the way the README
describes, and runs each console script's `--help`. Confirm that the
version it reports came from git rather than a fallback.

All three run before every tag. The first two also run after any change
touching annotations, `subprocess` calls, or standard-library usage, the
places where floor violations have appeared; the third runs after any change
to `pyproject.toml` or `setup.cfg`.

## Host platforms

A result from a sandbox or a container does not count. The suite runs on a
RHEL 8.10-equivalent host at Python 3.6. It has also run on Windows under a
native interpreter and, until CI was set aside, on hosted Linux. The Windows
cell matters because two defects lived only there: shims written with CRLF
endings, and a POSIX top-level path from Cygwin git that a Windows
interpreter could not use.

### The cell that ships

The hooks cross three independent choices, and a result on each axis says
nothing about their combination. The combination used on the development
workstation has to be run as one, with a real `git commit`:

| Axis | Value that ships |
|---|---|
| Interpreter that runs the framework and the checks | native Windows Python |
| Shell that runs the hook | Cygwin bash |
| git that runs the commit | Cygwin git |

The test stand-ins for console scripts come in two forms, an extensionless
shell script for bash to find and a `.cmd` file for a native interpreter to
start, so that the shims' tests hold in both cells. The framework under
Windows Python has not been run in this cell; `normalize-file-modes` relies
on `git checkout-index` there, since a native `os.chmod` cannot set the bit
Cygwin git reads.

Both defects named above passed every other cell. Check the outcome by what
the hook printed (`BLOCKED` for a refusal, no `syntax error`, no traceback),
not only by its exit status.

## Rules for claiming something is verified

Five questions, asked before a result is reported.

1. Could a broken implementation produce the same observable result? A hook
   that refuses and a hook that dies of a shell syntax error both exit
   non-zero and leave no commit. Assert on what the mechanism said
   (`BLOCKED` on stderr, no `syntax error`), not only on the exit code.
2. Which environment axes does this depend on, and which cells ran? "Works
   on A and on B" says nothing about A crossed with B. The CRLF defect sat
   in the one cell of a two-by-two that was never run: shims written by
   Windows Python and executed by Cygwin bash. Name untested cells as
   untested.
3. Is a limitation being inferred rather than tried? "A 3.6 type check is
   impossible here" was an inference, and trying it found a defect at once.
4. Would the same evidence be accepted if the conclusion were inconvenient?
5. Does the report keep the detail that would expose a gap, above all which
   tests skipped and why, and which interpreter or host did the work?

A test that silently stops running looks exactly like a test that passes.

## Spikes

A decision that rests on how the host or a toolchain behaves cites a spike:
a script under `spike/<question>/` with its dated transcript beside it,
registered in `test/spike-regen.tsv`. A transcript states findings as verdict
words and carries versions and dates in a header. `test/spike-regen.sh`
reruns each spike and fails one whose findings moved, so run it on the
replica before a tag and after any change a spike's decision depends on.
The spikes fetch their inputs from PyPI by pinned hash and need network
access the first time. `spike/` is kept out of the sdist by `MANIFEST.in`.
