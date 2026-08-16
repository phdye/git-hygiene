# install-hooks writes CRLF line endings and every installed hook fails

**FIXED 2026-08-16**, in the same session that received this report. The write
is now `target.write_bytes(render(hook_name).encode("utf-8"))`, and two tests
were added: one asserting no `\r\n` in the written hooks, one distinguishing
refusal from crash by asserting on what the hook actually said. Verified in
the combination that was broken - hooks written by **Windows** Python,
executed by **Cygwin** bash on git 2.21: no CR, `bash -n` clean, clean commit
succeeds, dirty commit refused with `BLOCKED` and rc=1 rather than a syntax
error. The regression test was confirmed to fail against the pre-fix code
before being kept.

**One correction to the analysis below.** The closing section supposes the
Cygwin half of `4679667`'s verification "was exercised through something other
than a real `git commit`". It was a real `git commit`, and it really did
refuse. The gap is different, and worth stating precisely because the lesson
differs: **the two verifications used different writers.** The Cygwin check
installed the hooks with `python3 -m git_hygiene.install_hooks` under *Cygwin*
Python 3.6.9, which writes `\n`; the pytest check used *Windows* Python, which
writes `\r\n`, but ran under Git for Windows' bash, which tolerates CRLF. Each
half passed honestly. Neither covered the combination that actually ships on
this workstation - Windows-written hook, Cygwin-executed - and "verified under
both Cygwin git 2.21 and Git for Windows" was true clause by clause while
being false as a whole. A matrix stated as two independent axes had one cell
never tested, and the summary implied all of them were.

Everything below is the original report as received, kept for the record.

---

**Found, not fixed.** Discovered 2026-08-16 by the `azdo` session, which was
reviewing this repository for whether `azdo` should consume it dynamically
rather than keep its own copy of the deny-term check. Not fixed here because
this session holds no role in this repository - see `a/doc/roles.md` and the
handoff at `a/handoff/initial.md`.

## What was seen

`install-hooks` reports success and writes both hook files. Every subsequent
commit then fails, whether its content is clean or dirty:

    === install-hooks ===
    wrote   pre-commit
    wrote   commit-msg
    install exit=0

    === hooks present ===
    -rwxr-xr-x 1 phili phili 382 .git/hooks/commit-msg
    -rwxr-xr-x 1 phili phili 376 .git/hooks/pre-commit

    === commit CLEAN content, expect success ===
    .git/hooks/pre-commit: line 9: syntax error: unexpected end of file
    clean-commit exit=1

    === commit DIRTY content, expect refusal ===
    .git/hooks/pre-commit: line 9: syntax error: unexpected end of file
    dirty-commit exit=1

    === commit clean content, DIRTY message, expect refusal ===
    .git/hooks/pre-commit: line 9: syntax error: unexpected end of file
    dirty-msg exit=1

    === final log ===
    fatal: your current branch 'main' does not have any commits yet

Reproduced against Cygwin git 2.21.0 on the rhel root - this project's own
stated floor and the environment `install-hooks` exists to serve - with
`check-identifiers` on PATH from this repository's own `.venv`, and
`GIT_DENY_TERMS` pointing at a one-term file.

Nothing was committable at all. This is not a false negative or a scoping
problem; it is total breakage of the front end.

## Cause

The hook files carry CRLF line endings. Confirmed directly:

    $ od -c .git/hooks/pre-commit | head -2
    0000000   #   !   /   u   s   r   /   b   i   n   /   e   n   v       b
    0000020   a   s   h  \r  \n   #       m   a   n   a   g   e   d   -   b

`install_hooks.py`, in `install_one()`:

    target.write_text(render(hook_name), encoding="utf-8")

`Path.write_text` opens in **text mode**. On Windows that applies newline
translation, so every `\n` in `_TEMPLATE` becomes `\r\n` on disk. The
package's dev interpreter is native Windows Python, so this is the normal
path, not an edge case.

Cygwin bash does not strip the carriage returns. It reads the `fi\r` line as
a command named `fi\r`, which never closes the `if` opened five lines
earlier, and reports end-of-file at line 9 - the line after the last one in
the template.

The template itself is correct. Only the write is wrong.

## Why the test suite did not catch it

`tests/test_install_hooks.py` has `test_installed_hook_actually_blocks_a_commit`,
which does exactly the right thing in shape: it installs the hooks, stages
content carrying a term, runs a real `git commit` through `subprocess`, and
asserts the commit did not happen.

It passes anyway, because its two assertions are:

    assert r.returncode != 0
    assert git("log", "--oneline", cwd=repo).stdout.strip() == ""

A hook that refuses the commit and a hook that crashes with a syntax error
both produce a non-zero return code and an empty log. The test cannot tell
the two apart, so a completely broken hook satisfies it.

This is the same class of gap already recorded twice in this project's
history - a check that confirms an artifact exists or that an outcome
occurred, without confirming it occurred *for the intended reason*. The
`--selfcheck` text-scan matching its own vocabulary, and `test_packaging.py`
validating a manifest that could not actually install, are the same shape.

The test's own docstring calls itself "the real proof". It is not, quite,
and that gap is worth closing along with the bug.

## What would resolve it

**The write.** `Path.write_text` grew a `newline=` parameter only in Python
3.10, and this project's floor is 3.6.8, so that is not available. Writing
bytes avoids text mode entirely and works on every version back to 3.4:

    target.write_bytes(render(hook_name).encode("utf-8"))

One line, in `install_one()`. `uninstall_one()` and `owned_by_us()` read with
`read_text`, which is fine - universal newline handling on read is harmless
here, and a hook written by an older version of this installer will still
match the marker.

**The test.** Distinguish refusal from crash. The hook's own refusal path
produces `check-identifiers`' message on stderr and exit 1; a shell syntax
error produces bash's message and no `check-identifiers` output at all.
Asserting on what the hook actually said, not merely that something failed,
separates them:

    assert "BLOCKED" in r.stderr          # or whatever the current wording is
    assert "syntax error" not in r.stderr

Worth adding a direct assertion on the bytes as well, since it fails loudly
and locates the problem immediately rather than through a commit's exit code:

    assert b"\r\n" not in target.read_bytes()

**A caution on verifying the fix.** Git for Windows' bundled bash tolerates
CRLF in hook scripts; Cygwin bash does not. A fix confirmed only under Git
for Windows will look correct and still be broken on the rhel root. The
commit that added this front end (`4679667`) records verification "under both
Cygwin git 2.21 on the rhel root and Git for Windows" - that does not
reproduce, and the discrepancy is most simply explained by the Cygwin half
having been exercised through something other than a real `git commit`. Run
the confirmation under Cygwin bash specifically.

## Scope

Affects only the native front end, which is the path for git < 2.31 - so it
affects exactly the environment this project singled out as needing
protection. `check-identifiers` and `audit-tree` invoked directly are
unaffected, and were verified working on git 2.21 during the same session:
every git subcommand this package uses is well inside 2.21, the newest being
`cat-file --batch-all-objects` from git 2.6.
