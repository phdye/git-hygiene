# The four commands

Read when: you need one command's synopsis, its own options, its exit codes
or its output, and the shared pages have not answered it.

Each page below holds only what belongs to that command. The two scanning
commands, `check-identifiers` and `audit-tree`, also take the shared
resolution options in [../resolution-options.md](../resolution-options.md)
and read the environment in [../environment.md](../environment.md). Every
command accepts `-h`/`--help` and prints its usage.

Every option a command's parser defines appears on its page, or on the
shared resolution-options page for the two scanning commands, as a
backticked spelling in the first column of the page's `Option` table.
`tests/test_doc_ai.py` holds those tables and the parsers equal, and holds
the set of pages here equal to the console scripts in `setup.cfg`.

<!-- route-table:begin -->
| Read when | Page |
|---|---|
| you are about to publish a repository and want every tracked file, commit message and, optionally, every git object checked for terms. | [audit-tree.md](audit-tree.md) |
| a commit was refused by `deny-terms` or `deny-terms-msg`, or you are running the content or message check by hand. | [check-identifiers.md](check-identifiers.md) |
| you need the checks as plain git hooks on a host without `pre-commit`, or are removing hooks that `install-hooks` wrote. | [install-hooks.md](install-hooks.md) |
| the `normalize-file-modes` hook changed a file's mode, refused a commit, or printed a `filemode:` line, or you need file modes normalized on a host without the framework. | [normalize-file-modes.md](normalize-file-modes.md) |
<!-- route-table:end -->
