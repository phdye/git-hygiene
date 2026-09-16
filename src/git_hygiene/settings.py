"""Which registered checks run, and which are required, for one repository.

A setting may enable or disable a registered check and mark it required
or optional, and nothing else. It can never name an executable: ids
resolve through the registry to console scripts already installed, so
cloning a repository can switch on only what the person installed.

Layers, lowest precedence first; each overrides the ones before it:

    declaration  the check's own `enabled` and `required`
    system       /etc/git-hygiene.conf, then <XDG_CONFIG_DIRS>/git-hygiene/config
    user         $XDG_CONFIG_HOME/git-hygiene/config (default ~/.config/...)
    repository   <work tree>/.git-hygiene              (tracked)
    clone        <git dir>/info/git-hygiene
    environment  GIT_HYGIENE_ENABLE, _DISABLE, _REQUIRE, _OPTIONAL
    flag         --enable, --disable, --require, --optional

Files are git-config syntax, read with includes disabled:

    [check "deny-terms"]
        enabled = true
        required = true
"""

import os
import re
import sys
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Tuple

from . import gitconfig
from .checks import Check
from .gitconfig import ConfigError
from .terms import git_dir

# (setting, value) for each environment variable and flag.
ACTIONS = {
    "enable": ("enabled", True),
    "disable": ("enabled", False),
    "require": ("required", True),
    "optional": ("required", False),
}


class Effective(NamedTuple):
    check: Check
    enabled: bool
    enabled_from: str
    required: bool
    required_from: str


class Layer(NamedTuple):
    name: str
    path: Path


def file_layers(anchor: Path) -> List[Layer]:
    system = [Layer("system", Path("/etc/git-hygiene.conf"))]
    config_dirs = os.environ.get("XDG_CONFIG_DIRS") or "/etc/xdg"
    # os.pathsep, as for XDG_DATA_DIRS in checks.py.
    for directory in reversed([d for d in config_dirs.split(os.pathsep) if d.strip()]):
        system.append(Layer("system", Path(directory) / "git-hygiene" / "config"))
    config_home = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    layers = system + [
        Layer("user", Path(config_home) / "git-hygiene" / "config"),
        Layer("repository", anchor / ".git-hygiene"),
    ]
    gd = git_dir(anchor)
    if gd is not None:
        layers.append(Layer("clone", gd / "info" / "git-hygiene"))
    return layers


def _ids(raw: str) -> List[str]:
    return [part for part in re.split(r"[\s,]+", raw) if part]


def _check_id(check_id: str, registry: Dict[str, Check], where: str) -> None:
    if not gitconfig.ID_PATTERN.match(check_id):
        raise ConfigError(
            f"{where}: {check_id!r} is not a check id; a setting names a check, never a path or a command"
        )
    if check_id not in registry:
        raise ConfigError(f"{where}: {check_id!r} is not a registered check")


def _file_settings(layer: Layer, registry: Dict[str, Check]) -> List[Tuple[str, str, bool]]:
    """(check id, setting, value) from one file, validated."""
    found = []
    for entry in gitconfig.read(layer.path):
        section, subsection, name = gitconfig.split_key(entry.key)
        where = f"{layer.path}: {entry.key}"
        if section in ("include", "includeif"):
            # git was told not to follow it; say so rather than stay quiet.
            sys.stderr.write(
                f"git-hygiene: {layer.path}: {entry.key} ignored; includes are not read\n"
            )
            continue
        if section != "check" or subsection is None or name not in ("enabled", "required"):
            raise ConfigError(
                f"{where}: unsupported setting; only check.<id>.enabled and "
                "check.<id>.required are allowed"
            )
        _check_id(subsection, registry, where)
        found.append((subsection, name, gitconfig.boolean(entry.value, where)))
    return found


def _apply(
    state: Dict[str, Dict[str, Tuple[bool, str]]],
    registry: Dict[str, Check],
    given: Dict[str, List[str]],
    label: str,
) -> None:
    """Apply one environment or flag layer. Naming an id for both
    halves of a pair in the same layer is an error, not a tie to break."""
    chosen: Dict[Tuple[str, str], str] = {}
    for action, ids in given.items():
        name, value = ACTIONS[action]
        where = label.format(action.upper() if label.startswith("env") else action)
        for cid in ids:
            _check_id(cid, registry, where)
            earlier = chosen.get((cid, name))
            if earlier is not None and earlier != where:
                raise ConfigError(f"{where}: {cid!r} is also named by {earlier}")
            chosen[(cid, name)] = where
            state[cid][name] = (value, where)


def resolve(
    registry: Dict[str, Check],
    anchor: Path,
    flags: Optional[Dict[str, List[str]]] = None,
) -> Dict[str, Effective]:
    """The effective settings for every registered check. `flags` maps
    an action in ACTIONS to the ids given for it on the command line.
    Raises ConfigError, naming the file or variable, on anything that
    is not a valid setting for a registered check."""
    state: Dict[str, Dict[str, Tuple[bool, str]]] = {
        cid: {
            "enabled": (c.enabled, "declaration " + c.origin),
            "required": (c.required, "declaration " + c.origin),
        }
        for cid, c in registry.items()
    }

    for layer in file_layers(anchor):
        if not layer.path.is_file():
            continue
        origin = f"{layer.name} {layer.path}"
        for cid, name, value in _file_settings(layer, registry):
            state[cid][name] = (value, origin)

    env = {a: _ids(os.environ.get("GIT_HYGIENE_" + a.upper(), "")) for a in ACTIONS}
    _apply(state, registry, env, "environment GIT_HYGIENE_{}")
    given = {a: [cid for raw in (flags or {}).get(a, []) for cid in _ids(raw)] for a in ACTIONS}
    _apply(state, registry, given, "flag --{}")

    return {
        cid: Effective(
            registry[cid],
            state[cid]["enabled"][0],
            state[cid]["enabled"][1],
            state[cid]["required"][0],
            state[cid]["required"][1],
        )
        for cid in registry
    }
