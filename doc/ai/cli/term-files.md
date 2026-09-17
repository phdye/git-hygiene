# The term file format

Read when: you are writing the lines of a term file, or a term does not
match the text you expected it to match.

A term file is UTF-8 text (undecodable bytes are replaced, not refused).

- One term per line. Surrounding whitespace is stripped; the rest of the
  line, spaces included, is the term.
- Blank lines are ignored. A line whose first non-blank character is `#`
  is a comment. A `#` later in a line is part of the term.
- A line `!term` removes an inherited term (rules on
  [term-sources.md](term-sources.md)). A file that both lists and negates
  one term is a fatal error.
- The first non-blank line may be `# git-hygiene: public` or
  `# git-hygiene: private` (case-insensitive). It asserts the class the
  file's name already gives, and must agree with it.

```
# git-hygiene: private
retired-codename
old build host
!legacy-name
```

## Matching

Each term becomes a case-insensitive regular expression with the term
escaped literally and `\b` on both sides, so it matches only on word
boundaries: `atlas` matches `ATLAS` and `atlas.` but not `atlas_client` or
`catlas`. Hyphenated and multi-word terms match as written. A line is
reported once, under the first term that matches it.

Choose terms long enough to be specific. A term that fires on ordinary
words is a term people learn to bypass.

## Where to put one

| Want | File |
|---|---|
| a public list the whole team shares | `.deny-terms` at the repository root, committed |
| a private list for one clone | `<git dir>/info/deny-terms` |
| a private list for everything under a directory | `.deny-terms.private` in that directory, ignored by name |
| a personal list for everything you do | `~/.config/git/deny-terms.txt`, or under `$XDG_CONFIG_HOME` |
| a machine-wide list | `/etc/git-hygiene/deny-terms` |
| one run, or CI | any path in `--terms` or `GIT_DENY_TERMS` |

A private list in a working tree is one `git add -A` from being committed;
add `.deny-terms.private` to the repository's `.gitignore`. A pattern for
`deny-terms.txt` does not match it. More on choosing a location is in
[../../term-files.md](../../term-files.md).

## Enforced and stated

Enforced by `tests/test_terms.py`: case-insensitivity, word boundaries,
hyphenated and multi-word terms, one report per line.
`tests/test_resolution.py` holds the term/negation conflict and directive
handling. Stated from source only: whitespace stripping and that a
mid-line `#` is part of the term.
