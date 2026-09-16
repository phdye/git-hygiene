"""The check registry: what checks exist and how each is to be run.

A check is a console script plus a declaration. The package declares its
own three in code; any other package registers one by dropping a file
in git-config syntax into a data directory:

    $XDG_DATA_HOME/git-hygiene/checks/*.conf   (default ~/.local/share)
    <each of $XDG_DATA_DIRS>/git-hygiene/checks/*.conf
                                        (default /usr/local/share:/usr/share)

    [check "secret-scan"]
        command = scrub-check        # a name found on PATH, never a path
        args = --quiet
        hook = pre-commit            # repeatable
        paths = *                    # repeatable glob; pre-commit only
        order = 60
        enabled = true
        required = false
        mutates-index = false
        contract = 1

Every declaration is validated before any check runs, and any error is a
usage error: a registry that is half understood cannot be run safely.
"""

import os
import re
import shlex
from pathlib import Path
from typing import Dict, List, NamedTuple, Tuple

from . import gitconfig
from .gitconfig import ConfigError

KNOWN_HOOKS = (
    "applypatch-msg",
    "pre-applypatch",
    "post-applypatch",
    "pre-commit",
    "pre-merge-commit",
    "prepare-commit-msg",
    "commit-msg",
    "post-commit",
    "pre-rebase",
    "post-checkout",
    "post-merge",
    "pre-push",
    "pre-receive",
    "update",
    "proc-receive",
    "post-receive",
    "post-update",
    "reference-transaction",
    "push-to-checkout",
    "pre-auto-gc",
    "post-rewrite",
    "sendemail-validate",
    "post-index-change",
)

# Hooks that read the staged set, where a `paths` filter means something.
STAGED_HOOKS = ("pre-commit", "pre-merge-commit")

CONTRACTS = ("1", "2")
_COMMAND = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]*$")
_KEYS = (
    "command",
    "args",
    "hook",
    "paths",
    "order",
    "enabled",
    "required",
    "mutates-index",
    "contract",
)


class Check(NamedTuple):
    id: str
    command: str
    args: Tuple[str, ...]
    hooks: Tuple[str, ...]
    paths: Tuple[str, ...]
    order: int
    enabled: bool
    required: bool
    mutates_index: bool
    contract: str
    origin: str  # "built-in" or the declaration file


BUILT_IN = (
    Check(
        "filemode",
        "normalize-file-modes",
        (),
        ("pre-commit",),
        ("*",),
        10,
        True,
        False,
        True,
        "2",
        "built-in",
    ),
    Check(
        "deny-terms",
        "check-identifiers",
        ("--staged", "--exit-contract", "2"),
        ("pre-commit",),
        ("*",),
        50,
        True,
        False,
        False,
        "2",
        "built-in",
    ),
    Check(
        "deny-terms-msg",
        "check-identifiers",
        ("--exit-contract", "2", "--message"),
        ("commit-msg",),
        ("*",),
        50,
        True,
        False,
        False,
        "2",
        "built-in",
    ),
)


def declaration_dirs() -> List[Path]:
    """Where declaration files are looked for, lowest precedence first.
    Precedence only matters for listing order: an id declared twice is
    an error wherever the two declarations sit."""
    data_home = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    data_dirs = os.environ.get("XDG_DATA_DIRS") or os.pathsep.join(
        ["/usr/local/share", "/usr/share"]
    )
    # os.pathsep rather than the specification's colon, which would split
    # a Windows drive letter off its path.
    system = [Path(d) for d in data_dirs.split(os.pathsep) if d.strip()]
    return [d / "git-hygiene" / "checks" for d in reversed(system)] + [
        Path(data_home) / "git-hygiene" / "checks"
    ]


def _one(values: List[str], where: str) -> str:
    if len(values) != 1:
        raise ConfigError(f"{where}: must be given exactly once")
    return values[0]


def _parse_check(check_id: str, fields: Dict[str, List[str]], origin: str) -> Check:
    where = f"{origin}: check {check_id!r}"
    if not gitconfig.ID_PATTERN.match(check_id):
        raise ConfigError(f"{where}: not a valid check id")
    for key in fields:
        if key not in _KEYS:
            raise ConfigError(f"{where}: unknown key {key!r}")
    if "command" not in fields:
        raise ConfigError(f"{where}: no command")
    command = _one(fields["command"], where + " command")
    if not _COMMAND.match(command):
        raise ConfigError(f"{where}: command {command!r} must be a name found on PATH, not a path")
    hooks = tuple(fields.get("hook", []))
    if not hooks:
        raise ConfigError(f"{where}: no hook")
    for hook in hooks:
        if hook not in KNOWN_HOOKS:
            raise ConfigError(f"{where}: unknown git hook {hook!r}")
    contract = _one(fields.get("contract", ["1"]), where + " contract").strip()
    if contract not in CONTRACTS:
        raise ConfigError(
            f"{where}: unknown exit contract {contract!r} (known: {', '.join(CONTRACTS)})"
        )
    order_text = _one(fields.get("order", ["50"]), where + " order")
    try:
        order = int(order_text)
    except ValueError:
        raise ConfigError(f"{where}: order {order_text!r} is not an integer") from None
    try:
        args = tuple(shlex.split(_one(fields.get("args", [""]), where + " args")))
    except ValueError as exc:
        raise ConfigError(f"{where}: args: {exc}") from None

    def flag(name: str, default: bool) -> bool:
        if name not in fields:
            return default
        return gitconfig.boolean(_one(fields[name], f"{where} {name}"), f"{where} {name}")

    return Check(
        id=check_id,
        command=command,
        args=args,
        hooks=hooks,
        paths=tuple(fields.get("paths", ["*"])),
        order=order,
        enabled=flag("enabled", True),
        required=flag("required", False),
        mutates_index=flag("mutates-index", False),
        contract=contract,
        origin=origin,
    )


def load_file(path: Path) -> List[Check]:
    fields: Dict[str, Dict[str, List[str]]] = {}
    for entry in gitconfig.read(path):
        section, subsection, name = gitconfig.split_key(entry.key)
        if section != "check" or subsection is None:
            raise ConfigError(f"{path}: unexpected key {entry.key!r}")
        # A bare key reads as "true" for booleans, and as nothing otherwise.
        value = "true" if entry.value is None else entry.value
        fields.setdefault(subsection, {}).setdefault(name, []).append(value)
    return [_parse_check(cid, f, str(path)) for cid, f in fields.items()]


def registry() -> Dict[str, Check]:
    """Every known check by id. Raises ConfigError on any bad or
    duplicate declaration."""
    found: Dict[str, Check] = {c.id: c for c in BUILT_IN}
    for directory in declaration_dirs():
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.conf")):
            for check in load_file(path):
                if check.id in found:
                    raise ConfigError(
                        f"{path}: check {check.id!r} is already declared by "
                        f"{found[check.id].origin}"
                    )
                found[check.id] = check
    return found


def run_order(checks: List[Check]) -> List[Check]:
    """Index-changing checks first, then by declared order, then by id,
    so a new id never reorders the existing ones."""
    return sorted(checks, key=lambda c: (not c.mutates_index, c.order, c.id))
