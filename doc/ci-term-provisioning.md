# Using a private term list in CI

A private list scans safely once it is on the runner: `GIT_DENY_TERMS`
accepts any path, and a term from a private source is withheld from the
report unless `--show-private-terms` is given. The hard part, then, comes earlier.
How does the list's plaintext reach a runner whose logs, environment dumps
and caches may be as widely readable as the repository being protected?

Each pattern below ends the same way. A plaintext file exists at a
runner-local path for the length of one job, `GIT_DENY_TERMS` points at it,
and git-hygiene runs exactly as it does on a workstation. None of them needs
anything from git-hygiene beyond that. They differ in how the file gets there
and what that costs in trust.

The first two are demonstrated end to end in
[phdye/git-hygiene-ci-demo](https://github.com/phdye/git-hygiene-ci-demo),
which installs git-hygiene from a tag as any consumer would. On 2026-08-16
its workflow passed both jobs. A step that deliberately echoed the secret
showed `***` in the log, and a staged file containing the term was refused
without the term being printed.

## 1. A CI secret, written to a temporary file

The default. Store the list's content as a CI secret, not as a plain
variable. The reason is visibility: on GitHub, repository variables are visible to anyone who can read
the settings, and secrets are not. A setup step writes the secret to the
runner's temporary directory and exports the path.

```yaml
- name: Materialize the private term list
  env:
    DENY_TERMS_CONTENT: ${{ secrets.DENY_TERMS_PRIVATE }}
  run: |
    umask 077
    printf '%s\n' "$DENY_TERMS_CONTENT" > "$RUNNER_TEMP/deny-terms.private"
    echo "GIT_DENY_TERMS=$RUNNER_TEMP/deny-terms.private" >> "$GITHUB_ENV"

- name: Scan
  run: check-identifiers --staged
```

Set the `umask` before writing. A `chmod` afterwards leaves a moment in which
the file existed with wider permissions. `RUNNER_TEMP` does not outlive the
job, so deletion is optional; an `rm -f` at the end is still cheap insurance
against a later step that has no business reading the file.

GitHub masks a multi-line secret line by line. For a file with one term per
line that is the right grain: an accidental `cat` in a debug step shows each
term redacted.

There is nothing extra to install. There are no keys, either, beyond the
secret store. It suits one team, with one list, across a few repositories.

## 2. An encrypted list in the repository, with one key in CI

Worth the extra step once one private list serves many repositories, or once
its history matters. A ciphertext diff shows when the list changed, if not
what changed. Encrypt with `age` or `sops` and commit the ciphertext; the key
is the only CI secret, shared by every repository that needs the list,
instead of N copies of the plaintext to rotate together.

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

The committed ciphertext does not trip the tracked-private-file error, since
git-hygiene never loads it as a term file; only the decrypted copy is read.
The cost is a dependency, `age` or `sops`, in the CI job. That is the
consumer's job to install and has no bearing on git-hygiene's own Python
floor.

## 3. A self-hosted runner reading host storage

If the runners are already self-hosted, skip the provider's secret store.
It adds nothing here. Mount the list from storage the host controls and point
`GIT_DENY_TERMS` at the mounted path. The plaintext never passes through the
CI provider at all, which makes this the highest-trust option. It is not,
however, a reason to move to self-hosting.

This was not run separately. To git-hygiene, after all, it is a file on
local disk named by `GIT_DENY_TERMS`, a case the test suite covers
throughout.

## What none of these do

They keep plaintext on the runner for one job; they do not keep it away from
the CI provider. A scheme that matches salted hashes instead of terms would,
and is written up as a draft proposal in
`proposal/2026-08-16.hashed-term-matching.md`.
