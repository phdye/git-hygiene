# Verification plan

What counts as proof for each property `Architecture.md` claims, and where
that proof runs. A property with no row here is not verified, whatever the
code appears to do.

## The gates

| Gate | Command | Where | Proves |
|---|---|---|---|
| Lint | `ruff check .` and `ruff format --check .` | CI, workstation | style and the selected rule sets |
| Types | `mypy src/git_hygiene` | CI, workstation | ordinary type errors, under `strict` |
| Suite | `pytest` | CI on 3.9 to 3.13, workstation | logic, and end-to-end behavior against real repositories and real git |
| Packaging | `pytest -m packaging` | CI | that `pre-commit try-repo` installs and runs the hooks as a consumer would |
| Manifest | `pre-commit validate-manifest .pre-commit-hooks.yaml` | workstation | that the manifest parses |
| Floor, runtime | the suite under Python 3.6 | workstation | that the code executes at the floor |
| Floor, static | mypy 0.971 with `--python-version 3.6` | workstation | that the code is written for the floor |
| Design docs | `pytest tests/test_design_docs.py` | CI, workstation | that the decision index and the records agree |

Unit tests prove logic; only `try-repo` proves packaging. An earlier version
of this facility passed every unit test and could not run as an installed
hook, because its entry point named a path that did not exist from the
consumer's directory. The packaging gate is required before any tag.

## The floor needs two checks

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
        src/git_hygiene/audit_tree.py src/git_hygiene/install_hooks.py

At 3.6 the available pytest predates `pyproject.toml` support, so
`addopts` is not applied and the packaging tests are collected rather than
deselected. They must then skip, and the skip reason must name the missing
prerequisite. Read the reason, not the count.

GitHub-hosted runners offer no Python 3.6, so neither floor check can run in
CI. Both run before every tag, and after any change touching annotations,
`subprocess` calls, or standard-library usage, the three places where
floor violations have appeared.

## Host platforms

A result from a sandbox or a container does not count. The suite runs in
three places: a RHEL 8.10-equivalent host at Python 3.6, Windows under a
native interpreter, CI on Linux. The Windows cell matters because two
defects lived only there: shims written with CRLF endings, and a POSIX
top-level path from Cygwin git that a Windows interpreter could not use.

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
