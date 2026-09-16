"""normalize-file-modes: set the recorded mode of every staged file.

The rule is carried over from the pre-commit hook this check replaces.
A file whose staged content starts with `#!` is meant to be run and gets
0755; everything else is data, a document or a library and gets 0644.
A repository names exceptions in `.gitmodes-exceptions` at its root, one
path or glob per line, `#` starting a comment; a listed file keeps the
mode its author staged, and each one is announced.

Only the index changes. `git update-index --cacheinfo` records the new
mode against the blob already staged and leaves the working tree alone,
so a partly staged file comes through intact. The staged blob,
not the working file, decides the rule, since it is what is committed.

Exit contract 2: 0 ran, 2 the exceptions file is unusable, 3 no regular
file was staged, 4 not inside a work tree.
"""

import argparse
import subprocess
import sys
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .terms import git, git_toplevel

EXCEPTIONS = ".gitmodes-exceptions"
# A path no repository has; a pattern matching it matches everything.
_PROBE = "__not_a_path_9c1f__/zz.bin"
_BATCH = 100


def _say(line: str) -> None:
    sys.stderr.write(f"filemode: {line}\n")


def read_exceptions(root: Path) -> List[Tuple[int, str]]:
    """(line number, pattern) for every non-empty entry."""
    path = root / EXCEPTIONS
    if not path.is_file():
        return []
    entries = []
    text = path.read_text(encoding="utf-8", errors="replace")
    for lineno, raw in enumerate(text.splitlines(), start=1):
        pattern = raw.split("#", 1)[0].strip()
        if pattern:
            entries.append((lineno, pattern))
    return entries


def staged_modes(root: Path) -> Dict[str, Tuple[str, str]]:
    """path -> (mode, blob id) for staged additions and modifications."""
    names = git("diff", "--cached", "--name-only", "-z", "--diff-filter=ACM", cwd=root)
    wanted = {n for n in names.stdout.decode("utf-8", "replace").split("\0") if n}
    index = git("ls-files", "-s", "-z", cwd=root)
    modes = {}
    for record in index.stdout.decode("utf-8", "replace").split("\0"):
        head, _, path = record.partition("\t")
        fields = head.split()
        if path in wanted and len(fields) == 3 and fields[2] == "0":
            modes[path] = (fields[0], fields[1])
    return modes


def shebang(root: Path, blob_ids: List[str]) -> Dict[str, bool]:
    """blob id -> whether the blob starts with `#!`, read through one
    `git cat-file --batch` process."""
    if not blob_ids:
        return {}
    request = "".join(oid + "\n" for oid in blob_ids).encode("ascii")
    proc = subprocess.run(  # noqa: S603, UP022 - see terms.git()
        ["git", "cat-file", "--batch"],  # noqa: S607
        cwd=str(root),
        input=request,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    out = proc.stdout
    result = {}
    pos = 0
    for oid in blob_ids:
        end = out.index(b"\n", pos)
        header = out[pos:end].decode("ascii", "replace").split()
        pos = end + 1
        if len(header) < 3 or header[1] == "missing":
            result[oid] = False
            continue
        size = int(header[2])
        result[oid] = out[pos : pos + 2] == b"#!"
        pos += size + 1
    return result


def _file_mode_is_on(root: Path) -> bool:
    r = git("config", "--bool", "core.fileMode", cwd=root)
    return r.stdout.decode("utf-8", "replace").strip() != "false"  # unset means true


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Record mode 0755 for staged files that start with #! and 0644 for "
            "the rest, in the index only. Exceptions: .gitmodes-exceptions."
        ),
    )
    parser.parse_args(argv)

    root = git_toplevel()
    if root is None:
        _say("not inside a git work tree; nothing to normalize")
        return 4

    exceptions = read_exceptions(root)
    if exceptions:
        tracked = git("ls-files", "--", EXCEPTIONS, cwd=root).stdout.strip()
        if not tracked:
            _say(f"{EXCEPTIONS} is not tracked. Its exceptions apply here and")
            _say("nowhere else, and its reasons reach nobody. Stage it with this commit.")
        for lineno, pattern in exceptions:
            if fnmatchcase(_PROBE, pattern):
                _say(f"{EXCEPTIONS} line {lineno}: the pattern '{pattern}' matches every")
                _say("path, which turns the mode rule off for the whole repository.")
                _say("Name the files instead, or disable this check. Refusing.")
                return 2

    modes = staged_modes(root)
    regular = {p: v for p, v in modes.items() if v[0] in ("100644", "100755")}
    if not regular:
        return 3

    starts = shebang(root, sorted({oid for _mode, oid in regular.values()}))
    to_set: List[Tuple[str, str, str]] = []
    for path in sorted(regular):
        mode, oid = regular[path]
        if any(fnmatchcase(path, pattern) for _n, pattern in exceptions):
            _say(f"mode exception: {path}")
            continue
        want = "100755" if starts.get(oid) else "100644"
        if want != mode:
            to_set.append((want, oid, path))

    # --cacheinfo names the blob already staged. `--chmod` would not do:
    # given a path, update-index first re-reads the working-tree file, which
    # would commit the unstaged half of a partly staged file.
    changed = 0
    for start in range(0, len(to_set), _BATCH):
        chunk = to_set[start : start + _BATCH]
        args = ["update-index"]
        for want, oid, path in chunk:
            args += ["--cacheinfo", f"{want},{oid},{path}"]
        r = git(*args, cwd=root)
        if r.returncode != 0:
            _say(r.stderr.decode("utf-8", "replace").strip())
            return 4
        for want, _oid, path in chunk:
            _say(f"mode {want[-3:]} on {path}")
            changed += 1

    if changed and _file_mode_is_on(root):
        _say("core.fileMode is true, so `git status` may now show a changed file's")
        _say("working-tree mode differing from the index; the commit records the index mode.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
