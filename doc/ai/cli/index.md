# The command line

Read when: you are about to run a git-hygiene command or wire its hooks
into a repository, and need the page for that task.

Four console scripts make up the whole interface. Two of them scan for
terms and share one set of resolution options; two do not scan at all.

    check-identifiers (--staged | --message FILE) [options]   the hook check
    audit-tree [options] [repo]                               pre-publish audit
    install-hooks [-f] [-n] [-u] [repo]                       hooks without pre-commit
    normalize-file-modes                                      the mode hook

Most consumers never type these. They name hook ids in
`.pre-commit-config.yaml`, and the framework runs the commands. The pages
below cover each command, then the topics the commands share.

A typical first session:

    check-identifiers --staged --explain     # which lists were found, no terms printed
    audit-tree --objects                     # before publishing

Enforced and stated: each page says which test holds its claims. The
option and command lists on these pages are checked against the code by
`tests/test_doc_ai.py`.

<!-- route-table:begin -->
| Read when | Page |
|---|---|
| you are setting git-hygiene behavior for a whole machine, shell or CI job, or a command behaves as though it was given an option it was not. | [environment.md](environment.md) |
| you are wiring the hooks into a repository (hook ids, `args:`, `.pre-commit-config.yaml`), including on a Python 3.6 host or one without `pre-commit`. | [hooks.md](hooks.md) |
| you are deciding how far to trust a pass, running git-hygiene under Windows or Cygwin, or reviewing what a repository's hook configuration can make a commit run. | [limits.md](limits.md) |
| a git-hygiene command exited non-zero or printed something, and you need to know what it means and whether a term could have been shown. | [output-and-exit.md](output-and-exit.md) |
| you need a resolution option shared by `check-identifiers` and `audit-tree` (`--terms`, `--no-inherit`, `--no-walk`, `--walk-to`, `--show-private-terms`, `--no-show-terms`), or a command acts as though one was given. | [resolution-options.md](resolution-options.md) |
| you are writing the lines of a term file, or a term does not match the text you expected it to match. | [term-files.md](term-files.md) |
| you need to know which term lists a run loads, their class and precedence, why a negation was refused, or why a hook passed when you expected a refusal. | [term-sources.md](term-sources.md) |
| you need one command's synopsis, its own options, its exit codes or its output, and the shared pages have not answered it. | [command/index.md](command/index.md) |
<!-- route-table:end -->
