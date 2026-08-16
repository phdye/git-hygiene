# git-hygiene

`pre-commit` hooks that keep engagement-specific identifiers out of
repositories - client and organization names, project and repository
names, internal codenames.

Built after a real leak: a client organization name and project name
sat in a package's test fixtures from its first commit until an audit
caught them, three days before it was due to be published. The
standing "no client identifiers" rule had been written down the whole
time. A mechanical check catches what discipline does not.

## The design constraint

A denylist committed to a public repository publishes exactly what it
conceals. So:

- **The code lives here** and names no terms. Safe to publish.
- **The term list lives outside every repository**, at
  `~/.config/git/deny-terms.txt`. Never committed, anywhere.

That split is the whole idea. Everything else follows from it.

## Use

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/phdye/git-hygiene
    rev: v0.1.0          # pin a tag, never a branch
    hooks:
      - id: deny-terms
      - id: deny-terms-msg
```

Then create your term list:

```bash
mkdir -p ~/.config/git
$EDITOR ~/.config/git/deny-terms.txt
chmod 600 ~/.config/git/deny-terms.txt
```

One term per line; blank lines and `#` comments ignored. Matching is
case-insensitive and on word boundaries.

**Without that file the hooks pass silently.** A contributor cloning
your repository will not have one, and a check they cannot see must
never block their work. It is a local safety net, not a project
requirement.

## Use without `pre-commit`

`pre-commit` needs git 2.31 or newer (it calls `git ls-files
--deduplicate`). If your git is older - RHEL 8.10 ships 2.21 - install
the hooks directly instead, with no framework involved:

```bash
pip install git-hygiene
install-hooks             # writes .git/hooks/pre-commit and commit-msg
```

Each installed hook is a small shell shim that calls `check-identifiers`
on PATH, so it needs the package installed somewhere that shim can find
it, but nothing else. Re-running `install-hooks` is safe - it reseeds
its own hook files and leaves anything it did not install alone unless
you pass `--force`. `install-hooks --dry-run` shows what would change
without writing, and `install-hooks --uninstall` removes only the hooks
this tool manages.

## Hooks

| id | stage | what it does |
|---|---|---|
| `deny-terms` | pre-commit | Refuses staged content matching a term. |
| `deny-terms-msg` | commit-msg | Refuses a commit message matching a term. Message-only leaks are real; content alone is not enough. |
| `audit-tree` | manual | Audits the whole repository, optionally every git object. For pre-publish, not per-commit. |

## Auditing before you publish

The hooks see staged changes only. They prevent new leaks; they cannot
find what is already committed. Before making a repository public:

```bash
audit-tree                 # tracked files and commit messages
audit-tree --objects       # every git object, including unreachable history
```

`--objects` matters more than it sounds. Content removed from the
working tree survives in the object store until the history itself is
rewritten, and neither a file scan nor `git log -S` will show it in a
deleted blob. This project's own test suite demonstrates the case: a
repository that passes the default audit and fails the object scan.

If the audit finds something, removing it from the working tree is not
enough - the history needs rewriting, and the old objects expiring and
pruning.

## Two deliberate behaviors

**It reports a file and line number, never the matched term.** Printing
it would put the identifier into terminal scrollback, CI logs, and any
pasted error report - recreating the leak the tool exists to prevent.

**It matches on word boundaries.** A short term will not fire inside an
unrelated longer word. Substring matching produces false positives on
ordinary API names, and a guard that cries wolf gets switched off.

## A path trap worth knowing

The term file is resolved through Python's `Path.home()`. On Windows
that is the user profile, which is **not** the same directory as a
Cygwin or MSYS shell's `~`. Put the file where `Path.home()` looks, or
set `GIT_DENY_TERMS` explicitly.

Get this wrong and the hook finds no terms and passes everything -
failure that reads as success. That is the worst failure mode a check
like this can have, so it is worth verifying once:

```bash
# should report a location, not pass
echo "a-term-from-your-list" > /tmp/probe.md
git add /tmp/probe.md 2>/dev/null || true
pre-commit run deny-terms --all-files
```

## Using a private term list in CI

The term file is a local workstation convention by default, but
`GIT_DENY_TERMS` works anywhere, including CI - the question is only how a
*private* list's plaintext gets onto a runner without ending up in its
logs, environment dumps, or cache storage. Short version: a CI secret,
materialized to a runner-local temp file for the job's lifetime, with
`GIT_DENY_TERMS` pointed at it - no git-hygiene code involved, since
`report()` already withholds a private term from output by default. Full
writeup, including an encrypted-blob variant for sharing one list across
many repos and a self-hosted-runner variant: `a/doc/ci-term-provisioning.md`.

A working example lives at
[phdye/git-hygiene-ci-demo](https://github.com/phdye/git-hygiene-ci-demo).
It installs git-hygiene from a tag the way any consumer would, provisions a
(fake) private term list two different ways, and proves in its own CI logs
both that GitHub masks the secret and that the hook still refuses the
commit without naming the term.

## Development

```bash
pip install -e .[dev]
pytest                 # unit and end-to-end
pytest -m packaging    # does pre-commit actually install and run these?
```

That second one is not optional before tagging. Unit tests prove the
logic; only `pre-commit try-repo` proves the packaging. An earlier
iteration of this facility passed every unit test and could not run as
an installed hook, because the entry point pointed at a path that did
not exist from the consumer's working directory.

## Versioning

Hook ids are a public API. Once someone pins `rev:` and names an id,
renaming it breaks their config. New hook is a minor version; changed
arguments or exit semantics is a major one. Tag every release and pin
tags, never branches - a moving `main` changes behavior under
consumers who did not choose it.

## License

MIT or Apache-2.0, at your option.
