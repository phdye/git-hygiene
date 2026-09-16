# 0012. One hook front end dispatches every check

Date: 2026-09-16
Status: accepted, implemented 2026-09-16

## Context

Three tools installed git hooks on the development workstation, and each
wrote its own hook file, so a repository ran the checks of whichever tool
installed last. The only composition point was a drop-in directory offered by
one of them, and it disappeared when that tool was removed from a repository
on September 16, 2026. The same day, a merge that resolved a single binary file
was refused by a gate that could not tell "nothing to scan" from "could not
scan", and the only way past was `--no-verify`, which turned every check off.
The full argument is in
[the multi-check proposal](../../proposal/2026-09-16.multi-check-hooks.md).

## Decision

Each installed hook is a shim that runs `git-hygiene run <hook>`. The
dispatcher reads a registry of checks, each a console script on `PATH` plus a
declaration naming its hooks, paths, order, default enablement and
requirement, whether it changes the index, and its exit contract. The package
declares `filemode`, `deny-terms` and `deny-terms-msg` itself; other packages
drop declaration files into `$XDG_DATA_HOME/git-hygiene/checks/` or a
system data directory.

Exit contract 1 is 0 pass, 1 refuse, 2 usage error. Contract 2 adds 3, not
applicable, which never refuses, and 4, could not run, which refuses only when
the check is required. A declaration without a contract is contract 1, and a
code outside the declared contract always refuses.

Settings are layered: declaration, system, user, the tracked `.git-hygiene`,
the per-clone `.git/info/git-hygiene`, environment, then flags. A setting may
enable, disable, require or make optional a registered check, and nothing
else. Files are git-config syntax read with `--no-includes`.

`filemode` sets the index mode of staged regular files from their staged
content (a `#!` start means 0755, anything else 0644), with the exceptions
file carried over from the tool it replaces. It is enabled by default, runs
before any check that reads the staged set, and changes nothing but the index
mode. `deny-terms` marked required refuses when no private term source
resolves.

## Why

Settled on September 16, 2026, each by the tier named.

git-config syntax (battle-tested): the package has no runtime dependencies
and a 3.6.8 floor, which rules out TOML and YAML, and git's parser is already
a dependency. The file names follow `.deny-terms` (default). A repository may
enable a check (flexibility), because ids resolve only to checks the person
installed, so the worst a hostile repository can do is refuse its own commits.
Index-changing checks are limited to mode metadata (correctness): anything
that rewrote content would need a stash step to be correct for a partly staged
file. Checks stay separate packages registered by declaration file
(correctness): one must remain installable alone, and Python entry points are
invisible across the interpreters this workstation uses. The dispatcher is
named `git-hygiene` with a `run` subcommand (default, accepted by the
operator).

The `pre-commit` framework was not adopted as the single front end. Its
current release requires Python 3.10 or newer
(`spike/pre-commit-python-floor/`), and it cannot express a required check
distinct from an optional one.

## Consequences

`install-hooks` now writes shims that need `git-hygiene` on `PATH` and
refuse without it. It also installs a shim for every hook a registered
declaration names, and removes shims it wrote for hooks no longer in use.

`check-identifiers` gained `--exit-contract 2`; direct callers keep contract 1
and see no change. The hook ids in `.pre-commit-hooks.yaml` are unchanged.

A repository whose tracked settings require `deny-terms` cannot be committed
to on a machine without a private list. That is the intended cost of opting
in, and the default stays optional.

`filemode` uses `git update-index --cacheinfo` rather than `--chmod`, since
`--chmod` given a path re-reads the working file and would commit the unstaged
half of a partly staged file. The hook it replaces had that defect.

## Alternatives

Keeping three tools with extension points: ordering across tools is undefined
and an extension point vanishes with its host. Adopting the `pre-commit`
framework: see above. A shell drop-in directory: no declaration, so no
applicability, no requirement, and no way to tell a missing step from a
passing one. One console script with a subcommand per check: the checks do
not share dependencies or release cadence.

## Superseded

Replaced on September 16, 2026, by
[0016](0016-pre-commit-is-the-hook-front-end.md), before any release carried
the dispatcher.
