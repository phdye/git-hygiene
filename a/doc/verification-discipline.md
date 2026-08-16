# Verification discipline

Written 2026-08-16, after four defects reached `main` in a single session and
were found afterwards - three of them by a reader other than the session that
wrote the code. This is not a general essay on testing. It records the
specific failure shapes this project has actually produced, so the next
session recognises them rather than rediscovering them.

The project's standing rule is already "verify by computing" and "verify
against real source at a known ref" (`a/doc/instructions.md`). Every defect
below happened *while that rule was being followed*. Running something is
necessary and not sufficient; what follows is about the gap between running
something and having verified the thing you claimed.

---

## Shape 1: asserting the outcome instead of the mechanism

The most productive bug shape this project has. Three instances so far, which
is enough to call it systematic rather than careless:

- `--selfcheck` text-scanned for its own vocabulary, so it passed by
  describing itself.
- `test_packaging.py` validated a manifest that could not actually install.
- `test_installed_hook_actually_blocks_a_commit` asserted `rc != 0` and an
  empty log. A hook that **refuses** and a hook that **crashes with a shell
  syntax error** produce identical values for both, so a completely broken
  front end passed. See `a/issue/install-hooks-writes-crlf.md`.

The third is the instructive one because its shape was right: real temporary
repository, real `git commit` through `subprocess`, real assertion that the
commit did not land. Nothing about it looks lazy. Its docstring called it "the
real proof", and that confident label is part of the problem - it discourages
the next reader from looking harder.

**The test to apply.** Ask what a *wrong* success looks like, and check the
assertion can distinguish it. If a broken implementation would produce the
same observable value, the assertion is measuring the wrong thing. Prefer
asserting on what the mechanism actually said:

    assert "BLOCKED" in r.stderr        # it refused, for the right reason
    assert "syntax error" not in r.stderr

Exit codes and empty-output checks are the weakest available evidence, because
almost every failure mode produces them too.

---

## Shape 2: the untested cell of a cross-product

Every environment-dependent defect this session produced lived in a cell of a
2x2 that was never exercised, while both *axes* were reported as verified.

| Defect | Axis A | Axis B | Cell never run |
|---|---|---|---|
| CRLF hooks | writer: Cygwin vs Windows python | executor: Cygwin bash vs Git-for-Windows bash | Windows-written, Cygwin-executed |
| `os.getuid` | checker host: Windows vs Linux | - | mypy on Linux |
| `re.Pattern` | checker: modern mypy vs mypy-at-3.6 | runtime: 3.6.9 vs 3.13 | static check targeting 3.6 |

The CRLF case is worth stating exactly, because the summary of it was
literally true and substantively false. The claim was "verified under both
Cygwin git 2.21 and Git for Windows". Both halves happened and both passed.
But the Cygwin half installed the hooks with *Cygwin* python, which writes
`\n`; the Windows-written hooks only ever met Git-for-Windows bash, which
tolerates CRLF. Two axes were reported as if independently verified when only
two of four cells had been run - and neither was the cell that ships.

**The rule.** When a verification depends on two environment choices, write
the grid down and say which cells were run. "Verified on A and on B" is not a
claim about A x B. If a cell is untested, name it as untested; that is a
normal and acceptable state, and infinitely better than a summary that implies
otherwise.

---

## Shape 3: a capability reasoned away instead of tried

`pyproject.toml` recorded, correctly, that mypy 2.x refuses `python_version`
below 3.10. That fact was silently generalised into "a static check targeting
3.6 is impossible", and the possibility of an *older* mypy was never
considered. One untested inference closed off the only tool class capable of
finding a whole category of floor violations.

When it was finally tried, it took four commands, and found a real defect on
its first run: `re.Pattern` (3.8+) used at a 3.6.8 floor, in a quoted
annotation that is never evaluated, so 48 passing tests on 3.6.9 could not
possibly have caught it. Details in `a/doc/floor-checks.md`.

**The rule.** "X cannot be done here" is a claim, subject to the same
verify-by-computing rule as any other. Cheap to test, and the cost of being
wrong is a permanently missing gate. Record the probe result rather than the
inference.

---

## Shape 4: evidence standards that vary with the desired answer

The pattern worth naming most bluntly, because it is about judgement rather
than technique. Across this session, weak evidence was accepted when it
pointed toward *finished* and strong evidence demanded when it pointed toward
*more work*:

- A stale browser tab title was accepted as proof a repository had been
  created. It had not. Three later signals disagreed.
- Workflow YAML was written and documented as "supported today" without ever
  having been run.
- Installing mypy at the floor was judged "probably not worth it" without
  trying; it found a real bug immediately.

**The rule.** Notice which answer the evidence is pointing toward, and apply
the *same* standard either way. Convenient conclusions warrant more scrutiny,
not less, precisely because there is no internal friction to catch them.

---

## Shape 5: reporting at a coarser grain than the work

A recurring aggravator rather than a defect in itself. Each summary above was
assembled from true statements and lost the distinction that mattered:
"verified under Cygwin" dropped *which python wrote the file*, "all tests
pass" dropped *which tests were skipped and why*.

**The rule.** State what was run precisely enough that a reader can spot the
gap. "48 passed, 2 skipped, and the 2 are `test_packaging` skipping for the
stated reason `needs pre-commit and git >= 2.31 (found git 2.21)`" is a
verifiable claim. "All tests pass" is not, and is the form that hides
accidental skips.

Skips deserve specific suspicion: a test that silently stops running looks
exactly like a test that passes.

---

## Practical checklist

Before claiming something is verified:

1. Could a broken implementation produce this same observable result?
2. Which environment axes does this depend on, and which cells did I run?
3. Am I inferring a limitation I have not tested?
4. Would I demand this much evidence if the conclusion were inconvenient?
5. Does my summary preserve the detail that would reveal a gap - especially
   skips, and especially which interpreter or host did the work?

None of this is exotic. All four defects were found within minutes once the
right question was asked; the failure was never capability, only which
question got asked.
