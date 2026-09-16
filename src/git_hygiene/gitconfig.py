"""Read a file in git-config syntax through git itself.

Both the check declarations and the layered hook settings use this
format (doc/design/Architecture.md, "One front end for every check").
git's own parser is the one this package already depends on, and it
keeps the package free of runtime dependencies at the 3.6.8 floor.
Includes are never followed: a tracked file must not pull in another.
"""

import re
from pathlib import Path
from typing import List, NamedTuple, Optional, Tuple

from .terms import git

_TRUE = ("true", "yes", "on", "1")
_FALSE = ("false", "no", "off", "0", "")

ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class ConfigError(Exception):
    """A file that cannot be used; the message names the file."""


class Entry(NamedTuple):
    key: str  # section[.subsection].name, section and name lowercased
    value: Optional[str]  # None for a key written with no `=`


def read(path: Path) -> List[Entry]:
    """Every entry in `path`, in file order. The file is read with the
    work directory set to its own parent, so the path handed to git is a
    bare name and no path convention can disagree about it."""
    r = git("config", "--file", path.name, "--no-includes", "--null", "--list", cwd=path.parent)
    if r.returncode != 0:
        detail = r.stderr.decode("utf-8", "replace").strip()
        raise ConfigError(f"{path}: cannot be read as git-config syntax: {detail}")
    entries = []
    for record in r.stdout.decode("utf-8", "replace").split("\0"):
        if not record:
            continue
        key, sep, value = record.partition("\n")
        entries.append(Entry(key, value if sep else None))
    return entries


def split_key(key: str) -> Tuple[str, Optional[str], str]:
    """(section, subsection, name). git keeps a subsection's case and
    lowercases the rest."""
    section, _, rest = key.partition(".")
    subsection, dot, name = rest.rpartition(".")
    return section, (subsection if dot else None), name


def boolean(value: Optional[str], where: str) -> bool:
    if value is None:
        return True  # git's rule: a bare key is true
    lowered = value.strip().lower()
    if lowered in _TRUE:
        return True
    if lowered in _FALSE:
        return False
    raise ConfigError(f"{where}: {value!r} is not a boolean")
