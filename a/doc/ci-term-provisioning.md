# Getting a private term list onto CI without revealing it

Status: #1, #2, #3 below are supported today with zero changes to this
project's code - they are consumer-side patterns, documented here because
nothing about them is obvious, not because git-hygiene needs to implement
anything for them to work. #4 is a proposal, deliberately not started; see
its own section.

## The problem, precisely

`GIT_DENY_TERMS` already accepts any path, and `report()` already withholds
a private-source term from stdout/stderr by default (`a/doc/deny-term-
resolution.md`, "Printing matched terms"). So a private list already scans
safely once it is *on the runner*. The actual gap is upstream of that: how
does the list's plaintext get onto a CI runner at all, given that the
runner's own logs, environment dumps, and cache/artifact storage are often
as exposed as the repository this tool protects.

Nothing here changes how `resolve()` or `report()` behave. Every option
below ends the same way: a plaintext file materializes at a path for the
duration of one job, `GIT_DENY_TERMS` points at it, and git-hygiene runs
exactly as it does locally. The difference between the options is only
*how that file gets there* and what trust it costs to get it there.

---

## #1: CI secret, materialized to an ephemeral file (recommended default)

Store the term list's content as a CI **secret**, not a plaintext CI
variable - GitHub Actions Variables are visible in the UI to anyone with
read access to the repo settings; Secrets are not. A setup step writes the
secret to a runner-local temp path and points `GIT_DENY_TERMS` at it. The
runner is destroyed at the end of the job, so no copy persists past it.

GitHub Actions masks secrets in job logs **per line for multi-line
values**, which happens to fit a term-per-line file well: even an
accidental `cat` of the file in a later debug step gets each term
individually redacted rather than the whole blob failing to mask because
one surrounding line didn't match.

```yaml
# .pre-commit-config.yaml consumer's workflow, illustrative
- name: Materialize the private term list
  env:
    DENY_TERMS_CONTENT: ${{ secrets.DENY_TERMS_PRIVATE }}
  run: |
    umask 077
    printf '%s\n' "$DENY_TERMS_CONTENT" > "$RUNNER_TEMP/deny-terms.private"
    echo "GIT_DENY_TERMS=$RUNNER_TEMP/deny-terms.private" >> "$GITHUB_ENV"

- name: Run the hooks
  run: check-identifiers --staged
```

`umask 077` before the write, not a `chmod` after: a `chmod` leaves a
window, however brief, where the file existed at a wider mode. Delete is
unnecessary - `RUNNER_TEMP` does not survive the job - but an explicit
`rm -f` at the end of the job is cheap insurance against a workflow that
later grows a step that runs after this one and does not need the file.

This is the default recommendation: no added dependency, no key
management beyond what the CI provider's secret store already gives you,
and it is the correct answer for the common case of one team, one private
list, one or a handful of repos.

## #2: Encrypted blob committed to the repo, one key as the only secret

Worth it once a private list needs to be shared across many repositories,
or its *history* needs to be auditable - a ciphertext diff shows *when*
the list changed even though it cannot show *what* changed. Encrypt with
`age` or `sops`, commit the ciphertext (this is safe: it is not the
plaintext, and git-hygiene's own tracked-private-file hard error does not
apply to an encrypted blob, since it is not itself a term file the tool
would ever load directly). One symmetric or asymmetric key is the only
secret in CI, shared across every repo that needs the list rather than
duplicating the term list's plaintext into N secrets that must all be
rotated together.

```yaml
- name: Decrypt the private term list
  env:
    AGE_KEY: ${{ secrets.DENY_TERMS_AGE_KEY }}
  run: |
    umask 077
    echo "$AGE_KEY" > "$RUNNER_TEMP/age.key"
    age --decrypt -i "$RUNNER_TEMP/age.key" \
        -o "$RUNNER_TEMP/deny-terms.private" \
        .ci/deny-terms.txt.age
    rm -f "$RUNNER_TEMP/age.key"
    echo "GIT_DENY_TERMS=$RUNNER_TEMP/deny-terms.private" >> "$GITHUB_ENV"
```

Costs a real dependency (`age` or `sops`) in the CI job. That is fine
there - it is not the RHEL 8.10 floor this project's own code is pinned
to (`a/doc/instructions.md`); the floor governs `git_hygiene`'s own
runtime, not what a consumer's CI job is allowed to install.

## #3: Self-hosted runner, bind-mounted from host-controlled storage

If the runners are self-hosted rather than provider-hosted, skip the CI
provider's secret store for this entirely: bind-mount the term file from
host storage the same way `~/.config/git/deny-terms.txt` already works on
a workstation, and point `GIT_DENY_TERMS` at the mounted path. Highest
trust of the three, since the plaintext never transits the CI provider's
infrastructure at all - but only applicable when self-hosting is already
the setup, not a reason to switch to it on its own.

---

## #4: Hash-based matching - proposal, not started

A meaningfully different approach: never let plaintext terms reach CI at
all. Store a salted hash of each term instead of the term itself; scanning
tokenizes the candidate text and checks token hashes for membership rather
than running the term as a substring/regex match.

Recorded here as a real option for a future major version, not as
something #1-#3 are a stopgap for. It solves a different threat model -
not trusting the CI *provider* itself, rather than trusting the provider's
secret store but wanting the plaintext to exist for as short a time as
possible. Most teams do not need that; #1 already keeps the window to one
job's lifetime.

Why it is not being built now:

- **Tokenization has to reproduce today's matching exactly, or it is a
  silent behavior change.** The current word-boundary regex
  (`\bterm\b`, case-insensitive) matches substrings within a boundary,
  handles multi-word terms like `"Some Project"` as a literal phrase, and
  is exercised by `tests/test_terms.py`. A tokenize-then-hash scheme has
  to either reduce to exactly that or document a real behavior change,
  and multi-word terms in particular do not tokenize cleanly into
  independent hashable units.
- **The salt is itself a secret needing exactly the protection this
  proposal exists to avoid needing.** A leaked salt plus a plausible
  guess at a term (a company name, a project codename) makes the hash
  reversible by trial; the salt has to be provisioned by one of #1-#3
  regardless, which makes this an addition on top of them rather than a
  replacement.
- **It changes what `--show-private-terms` can promise.** Today it prints
  the term because the term was read. A hash-only scheme cannot recover
  the original term to print it, which breaks the "an operator who wants
  the full report can have it" guarantee in `a/doc/deny-term-
  resolution.md`.

If this becomes worth building, it is a new term-file format (a `.hashed`
declaration alongside `public`/`private`) and a new matching path in
`terms.py`, not a change to resolution layering - it composes with
everything in `a/doc/deny-term-resolution.md` rather than replacing it.
