"""git-hygiene: one hook front end that runs every selected check.

Each installed git hook is a shim that runs `git-hygiene run <hook>`.
The dispatcher loads the check registry (checks.py) and the layered
settings (settings.py), picks the checks enabled for that hook, runs
them in order, and reads each exit code through the contract its
declaration names:

    contract 1   0 pass, 1 refuse, 2 usage error
    contract 2   as 1, plus 3 not applicable, 4 could not run

A 3 never refuses. A 4 refuses only when the check is required. Any
code outside the declared contract refuses, whether or not the check is
required, because a code nobody defined cannot be read as a pass.
Everything a check prints is captured and replayed, so a check that
stood down quietly stays quiet unless --verbose is given.
"""

import argparse
import fnmatch
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional

from . import checks, settings
from .gitconfig import ConfigError
from .terms import env_flag, git, git_toplevel

# Hooks git feeds on standard input; every other hook gets none.
_STDIN_HOOKS = (
    "pre-push",
    "pre-receive",
    "post-receive",
    "post-rewrite",
    "reference-transaction",
    "proc-receive",
)

CLEAN = "pass"
REFUSE = "refuse"
USAGE = "usage"
NOT_APPLICABLE = "not applicable"
COULD_NOT_RUN = "could not run"
UNDEFINED = "undefined"

_MEANING = {
    "1": {0: CLEAN, 1: REFUSE, 2: USAGE},
    "2": {0: CLEAN, 1: REFUSE, 2: USAGE, 3: NOT_APPLICABLE, 4: COULD_NOT_RUN},
}


class Outcome(NamedTuple):
    check_id: str
    meaning: str
    code: Optional[int]
    refused: bool


def meaning(code: int, contract: str) -> str:
    return _MEANING[contract].get(code, UNDEFINED)


def refuses(what: str, required: bool) -> bool:
    if what in (CLEAN, NOT_APPLICABLE):
        return False
    if what == COULD_NOT_RUN:
        return required
    return True


def _version() -> str:
    # importlib.metadata arrived in 3.8; below that the version is not
    # worth a dependency.
    if sys.version_info >= (3, 8):
        from importlib.metadata import PackageNotFoundError, version

        try:
            return version("git-hygiene")
        except PackageNotFoundError:
            return "unknown"
    return "unknown"


class Options(NamedTuple):
    verbose: bool
    terse: bool
    debug: bool


def _say(line: str) -> None:
    sys.stderr.write(f"git-hygiene: {line}\n")


def _staged_paths() -> List[str]:
    out = git("diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR")
    return [p for p in out.stdout.decode("utf-8", "replace").split("\0") if p]


def run_check(
    eff: settings.Effective,
    hook: str,
    hook_args: List[str],
    stdin: Optional[bytes],
    opts: Options,
) -> Outcome:
    check = eff.check
    required = eff.required

    if hook in checks.STAGED_HOOKS and check.paths != ("*",):
        staged = _staged_paths()
        if not any(fnmatch.fnmatchcase(p, pat) for p in staged for pat in check.paths):
            if opts.verbose:
                _say(f"{check.id}: not applicable (no staged path matches its paths)")
            return Outcome(check.id, NOT_APPLICABLE, None, False)

    exe = shutil.which(check.command)
    if exe is None:
        _say(f"{check.id}: command '{check.command}' is not on PATH; refusing.")
        _say(f"{check.id}: install the package that provides it, or disable the check.")
        return Outcome(check.id, COULD_NOT_RUN, None, True)

    argv = [exe, *check.args, *hook_args]
    if opts.debug:
        _say(f"{check.id}: running {argv!r}")
    env = dict(os.environ)
    env["GIT_HYGIENE_HOOK"] = hook
    env["GIT_HYGIENE_CHECK"] = check.id
    try:
        proc = subprocess.run(  # noqa: S603, UP022 - argv from an installed declaration; 3.6
            argv,
            input=stdin if stdin is not None else b"",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            check=False,
        )
    except OSError as exc:
        _say(f"{check.id}: cannot start {exe}: {exc}; refusing.")
        return Outcome(check.id, COULD_NOT_RUN, None, True)

    what = meaning(proc.returncode, check.contract)
    refused = refuses(what, required)
    quiet = what == NOT_APPLICABLE or (what == COULD_NOT_RUN and not required)
    if not quiet or opts.verbose:
        sys.stdout.flush()
        sys.stdout.buffer.write(proc.stdout)
        sys.stdout.buffer.flush()
        sys.stderr.flush()
        sys.stderr.buffer.write(proc.stderr)
        sys.stderr.buffer.flush()

    code = proc.returncode
    tag = f"exit {code}, contract {check.contract}"
    if what == UNDEFINED:
        _say(
            f"{check.id}: exited {code}, which contract {check.contract} does not define; refusing."
        )
    elif what == REFUSE:
        _say(f"{check.id}: refused ({tag}).")
    elif what == USAGE:
        _say(f"{check.id}: reported a usage error ({tag}); refusing.")
    elif what == COULD_NOT_RUN and required:
        _say(f"{check.id}: is required and could not run ({tag}); refusing.")
    elif opts.verbose:
        suffix = "; optional, so not refusing" if what == COULD_NOT_RUN else ""
        _say(f"{check.id}: {what} ({tag}){suffix}.")
    return Outcome(check.id, what, code, refused)


def explain(effective: Dict[str, settings.Effective], hook: Optional[str]) -> None:
    ordered = checks.run_order([e.check for e in effective.values()])
    for check in ordered:
        if hook is not None and hook not in check.hooks:
            continue
        eff = effective[check.id]
        print(f"{check.id}")
        print(f"  hooks      {', '.join(check.hooks)}")
        print(f"  command    {check.command} {' '.join(check.args)}".rstrip())
        print(
            f"  contract   {check.contract}    order {check.order}"
            f"    changes index: {'yes' if check.mutates_index else 'no'}"
        )
        print(f"  enabled    {'yes' if eff.enabled else 'no':<4} from {eff.enabled_from}")
        print(f"  required   {'yes' if eff.required else 'no':<4} from {eff.required_from}")
        print(f"  declared   {check.origin}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="git-hygiene",
        description="Run the git-hygiene checks selected for a git hook.",
    )
    parser.add_argument("--version", action="version", version="git-hygiene " + _version())
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True
    run = sub.add_parser(
        "run",
        help="run every enabled check for HOOK",
        description=(
            "Run every enabled check for HOOK, in order. Options go before HOOK; "
            "anything after it is passed to each check, as git passed it to the hook."
        ),
    )
    run.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=None,
        help="also report checks that stood down (env: GIT_HYGIENE_VERBOSE)",
    )
    run.add_argument(
        "-t",
        "--terse",
        action="store_true",
        default=None,
        help="print only what checks print and why a commit was refused (env: GIT_HYGIENE_TERSE)",
    )
    run.add_argument(
        "-d",
        "--debug",
        action="store_true",
        default=None,
        help="show each command as it is run (env: GIT_HYGIENE_DEBUG)",
    )
    run.add_argument(
        "--explain",
        action="store_true",
        help="print each check's effective settings and where they came from; run nothing",
    )
    for action in settings.ACTIONS:
        run.add_argument(
            f"--{action}",
            action="append",
            default=[],
            metavar="ID",
            help=f"{action} a registered check (env: GIT_HYGIENE_{action.upper()})",
        )
    run.add_argument("hook", metavar="HOOK", help="the git hook being run, e.g. pre-commit")
    run.add_argument(
        "hook_args",
        nargs=argparse.REMAINDER,
        metavar="ARG",
        help="arguments git passed to the hook",
    )
    return parser


def _option(args: argparse.Namespace, name: str, parser: argparse.ArgumentParser) -> bool:
    given = getattr(args, name)
    if given is not None:
        return bool(given)
    try:
        return bool(env_flag("GIT_HYGIENE_" + name.upper()))
    except ValueError as exc:
        parser.error(str(exc))
    return False  # not reached; parser.error exits


def main(argv: Optional[List[str]] = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    opts = Options(
        verbose=_option(args, "verbose", parser),
        terse=_option(args, "terse", parser),
        debug=_option(args, "debug", parser),
    )
    hook = args.hook
    if hook not in checks.KNOWN_HOOKS:
        parser.error(f"unknown git hook {hook!r}")

    anchor = git_toplevel() or Path.cwd()
    try:
        registry = checks.registry()
        flags = {action: getattr(args, action) for action in settings.ACTIONS}
        effective = settings.resolve(registry, anchor, flags)
    except ConfigError as exc:
        _say(f"{exc}")
        _say("configuration error; no check was run.")
        return 2

    if args.explain:
        explain(effective, hook)
        return 0

    selected = checks.run_order(
        [e.check for e in effective.values() if e.enabled and hook in e.check.hooks]
    )
    stdin = None
    if hook in _STDIN_HOOKS and not sys.stdin.isatty():
        stdin = sys.stdin.buffer.read()

    outcomes = [run_check(effective[c.id], hook, args.hook_args, stdin, opts) for c in selected]
    refused = [o.check_id for o in outcomes if o.refused]
    if refused:
        if not opts.terse:
            _say(f"{hook} refused by: {', '.join(refused)}")
        return 1
    if opts.verbose:
        _say(f"{hook}: {len(outcomes)} check{'' if len(outcomes) == 1 else 's'} run, none refused")
    return 0


if __name__ == "__main__":
    sys.exit(main())
