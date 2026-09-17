# 0017. Usage docs for other sessions are held to the code

Date: 2026-09-16
Status: accepted

## Context

An AI session working in some other repository needs to use these hooks
correctly without reading this package's source. `README.md` is written for
a person installing them, and `doc/design/` explains why the package has its
shape; neither answers "which option do I pass" in a few hundred tokens.

A tree of short pages answers it. Such a tree also goes stale in the one way
its reader cannot detect, since that reader never opens the code.

## Decision

`doc/ai/` holds the usage documentation. It has a `cli/` half and no `api/`
half, because the public interface is the hook ids plus the console scripts.
Nothing is importable. The four commands sit under `cli/command/`; the
topics they share sit beside that directory.

Every page opens with its title, a blank line, then a `Read when:` line. Each
directory's route table is generated from those lines by the external
`ai-docs-check` tool, never edited by hand.

`tests/test_doc_ai.py` holds the tree to the code in two ways. The interface
test always runs. It fails when the command pages, their option tables, the
environment table or the hook table differ from `setup.cfg`, the parsers,
the source and `.pre-commit-hooks.yaml`. The structure test runs
`ai-docs-check`, found through `AI_DOCS_CHECK` and then `PATH`, and skips
with a reason naming that variable when neither finds it.

## Why

The lists a reader relies on most (options, variables, hook ids) are the
ones that drift when a flag is added. They are compared, not trusted. The parser is captured at the moment
`main()` would parse, which leaves the source untouched.

The structure test skips rather than fails without the checker, as the
packaging tests do without `pre-commit`. A stranger's clone has no checker.
A suite that fails there for a tool this package does not ship would be
the worse default. The replica run sets `AI_DOCS_CHECK`. Its skip reasons
are read like any other.

## Consequences

Adding an option, a variable, a console script or a hook id now fails the
suite until the matching page changes too, which is the point: the person
adding a flag is the only one who knows, at that moment, what a caller in
another repository will need to be told about it. A new page needs `ai-docs-check
--write doc/ai` before the structure test passes.
