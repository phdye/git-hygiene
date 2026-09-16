# Decision records

One settled question per record, so it can be found without reading the
argument that settled it. Records are append-only: a reversal is a new
record naming the one it replaces. Each record stands alone, whether or not
the proposal behind it survives.

`tests/test_design_docs.py` holds this table and the record files
one-to-one.

| # | Decision | Date |
|---|---|---|
| [0001](0001-design-documents-under-doc-design.md) | Design documents live under `doc/design/`, with proposals beside it | 2026-09-16 |
| [0002](0002-term-lists-live-outside-the-repository.md) | Term lists live outside the repository, and their absence passes | 2026-08-16 |
| [0003](0003-terms-match-on-word-boundaries.md) | Terms match case-insensitively on word boundaries | 2026-08-16 |
| [0004](0004-term-sources-are-layered-classified-and-unioned.md) | Term sources are layered, classified, and merged by union | 2026-08-16 |
| [0005](0005-loud-absence-applies-only-to-named-sources.md) | A missing public source is fatal only when it was named | 2026-08-16 |
| [0006](0006-matched-terms-print-by-source-class.md) | A matched term is printed when its source is public | 2026-08-16 |
| [0007](0007-python-floor-is-3-6-8.md) | The Python floor is 3.6.8 | 2026-08-16 |
| [0008](0008-old-git-gets-native-hooks-not-a-patched-framework.md) | Old git gets native hooks, not a patched framework | 2026-08-16 |
| [0009](0009-resolution-errors-are-fatal.md) | Every resolution error is fatal, and a refused private term stays unnamed | 2026-09-16 |
| [0010](0010-every-resolution-setting-has-an-environment-variable.md) | Every resolution setting has an environment variable and a negation | 2026-09-16 |
