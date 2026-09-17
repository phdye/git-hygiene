"""normalize-file-modes: set the recorded mode of every staged file.

The rule is carried over from the pre-commit hook this check replaces.
A file whose staged content starts with `#!` is meant to be run and gets
0755; everything else is data, a document or a library and gets 0644.
A repository names exceptions in `.gitmodes-exceptions` at its root, one
path or glob per line, `#` starting a comment; a listed file keeps the
mode its author staged, and each one is announced.

The staged blob, not the working file, decides the rule, since it is
what is committed. `git update-index --cacheinfo` records the new mode
against the blob already staged, so a partly staged file commits exactly
what was staged. The working file is then given the same mode, because
the pre-commit framework fails any hook whose run changes `git diff`, and
an index mode the working file lacks is such a change when core.fileMode
is on. Where the working file still holds exactly the staged blob (always
the case under the framework, which sets unstaged changes aside first),
git itself rewrites it with `checkout-index`; otherwise only its
permission bits are changed.

Exit codes: 0 ran, 1 could not update the index or is outside a work
tree, 2 the exceptions file is unusable.
"""

import argparse
import contextlib
import os
import stat
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


def _working_blobs(root: Path, paths: List[str]) -> Dict[str, str]:
    """path -> blob id of the working file as `git add` would store it."""
    present = [p for p in paths if (root / p).is_file() and not (root / p).is_symlink()]
    if not present:
        return {}
    r = git("hash-object", "--", *present, cwd=root)
    ids = r.stdout.decode("ascii", "replace").split()
    return dict(zip(present, ids)) if r.returncode == 0 and len(ids) == len(present) else {}


def sync_working_modes(root: Path, changed: List[Tuple[str, str, str]]) -> List[str]:
    """Give each changed path's working file the mode now in the index.
    Returns the paths whose working mode still differs afterwards."""
    paths = [path for _want, _oid, path in changed]
    working = _working_blobs(root, paths)
    same = [path for _want, oid, path in changed if working.get(path) == oid]
    for start in range(0, len(same), _BATCH):
        git("checkout-index", "-f", "--", *same[start : start + _BATCH], cwd=root)
    for want, _oid, path in changed:
        if path in same or path not in working:
            continue
        target = root / path
        bits = stat.S_IMODE(target.stat().st_mode)
        if want == "100755":
            bits |= (bits & 0o444) >> 2
        else:
            bits &= ~0o111
        with contextlib.suppress(OSError):
            os.chmod(str(target), bits)
    if not paths:
        return []
    r = git("diff", "--raw", "-z", "--", *paths, cwd=root)
    fields = r.stdout.decode("utf-8", "replace").split("\0")
    left = []
    for head, name in zip(fields[0::2], fields[1::2]):
        parts = head.split()
        if len(parts) >= 2 and parts[0].lstrip(":") != parts[1]:
            left.append(name)
    return left


def _file_mode_is_on(root: Path) -> bool:
    r = git("config", "--bool", "core.fileMode", cwd=root)
    return r.stdout.decode("utf-8", "replace").strip() != "false"  # unset means true


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Record mode 0755 for staged files that start with #! and 0644 for "
            "the rest, in the index and the working file. Exceptions: .gitmodes-exceptions."
        ),
    )
    parser.parse_args(argv)

    root = git_toplevel()
    if root is None:
        _say("not inside a git work tree; cannot normalize")
        return 1

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
        return 0

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
            return 1
        for want, _oid, path in chunk:
            _say(f"mode {want[-3:]} on {path}")
            changed += 1

    left = sync_working_modes(root, to_set) if changed else []
    if left and _file_mode_is_on(root):
        for path in left:
            _say(f"could not give the working file {path} its new mode;")
        _say(
            "`git status` will show it differing from the index. The commit records the index mode."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
