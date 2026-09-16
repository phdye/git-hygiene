"""Resolution options shared by check-identifiers and audit-tree.

Each setting is reachable from the command line and from the
environment, the option winning. Every boolean has a negated spelling,
so a value set in the environment can be turned back off for one run.
"""

import argparse
import os
from typing import Optional

from .terms import env_flag

# option dest -> environment variable
_FLAGS = {
    "no_inherit": "GIT_HYGIENE_NO_INHERIT",
    "no_walk": "GIT_HYGIENE_NO_WALK",
    "show_private_terms": "GIT_HYGIENE_SHOW_PRIVATE_TERMS",
}
_WALK_TO = "GIT_HYGIENE_WALK_TO"


def add_resolution_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--terms",
        action="append",
        metavar="FILE",
        help="explicit term source, repeatable (env: GIT_DENY_TERMS)",
    )
    parser.add_argument(
        "--no-inherit",
        dest="no_inherit",
        action="store_true",
        default=None,
        help="use only the highest explicit source (--terms, else GIT_DENY_TERMS)"
        " (env: GIT_HYGIENE_NO_INHERIT)",
    )
    parser.add_argument(
        "--inherit", dest="no_inherit", action="store_false", help="undo --no-inherit"
    )
    parser.add_argument(
        "--no-walk",
        dest="no_walk",
        action="store_true",
        default=None,
        help="skip the ancestor walk (env: GIT_HYGIENE_NO_WALK)",
    )
    parser.add_argument("--walk", dest="no_walk", action="store_false", help="undo --no-walk")
    parser.add_argument(
        "--walk-to", metavar="DIR", help="bound the ancestor walk (env: GIT_HYGIENE_WALK_TO)"
    )
    parser.add_argument(
        "--show-private-terms",
        dest="show_private_terms",
        action="store_true",
        default=None,
        help="also print matched terms from private sources (env: GIT_HYGIENE_SHOW_PRIVATE_TERMS)",
    )
    parser.add_argument(
        "--no-show-private-terms",
        dest="show_private_terms",
        action="store_false",
        help="undo --show-private-terms",
    )
    parser.add_argument(
        "--no-show-terms",
        action="store_true",
        help="suppress all term printing; locations only",
    )


def apply_environment(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> argparse.Namespace:
    """Fill each setting the command line left unset from the
    environment, then from the built-in default. A malformed value is a
    usage error (exit 2), named, rather than a silent default."""
    for dest, var in _FLAGS.items():
        if getattr(args, dest) is not None:
            continue
        try:
            value: Optional[bool] = env_flag(var)
        except ValueError as exc:
            parser.error(str(exc))
        setattr(args, dest, bool(value))
    if not args.walk_to:
        args.walk_to = os.environ.get(_WALK_TO) or None
    return args
