"""A configurable stand-in for a check, run by the dispatcher in tests.

    fake-check [--exit N] [--log FILE] [--marker FILE]
               [--expect-mode PATH MODE] [--say TEXT] [ARG...]

--log appends the check id the dispatcher exported; --marker records
that the check ran; --expect-mode exits 1 unless the index records MODE
for PATH. Anything after the options (a commit message path, say) is
accepted and ignored. Kept 3.6.8-clean.
"""

import argparse
import os
import subprocess
import sys


def main():
    # type: () -> int
    parser = argparse.ArgumentParser()
    parser.add_argument("--exit", type=int, default=0)
    parser.add_argument("--log")
    parser.add_argument("--marker")
    parser.add_argument("--expect-mode", nargs=2)
    parser.add_argument("--say")
    parser.add_argument("rest", nargs="*")
    args = parser.parse_args()
    check_id = os.environ.get("GIT_HYGIENE_CHECK", "?")
    if args.log:
        with open(args.log, "a") as handle:
            handle.write(check_id + "\n")
    if args.marker:
        with open(args.marker, "w") as handle:
            handle.write("ran\n")
    if args.say:
        sys.stderr.write(args.say + "\n")
    if args.expect_mode:
        path, mode = args.expect_mode
        out = subprocess.run(  # noqa: S603, S607, UP022
            ["git", "ls-files", "-s", "--", path],
            stdout=subprocess.PIPE,
            check=False,
        ).stdout.decode("utf-8", "replace")
        found = out.split()[0] if out.split() else "absent"
        if found != mode:
            sys.stderr.write(f"fake-check: {path} is {found} in the index, expected {mode}\n")
            return 1
        sys.stderr.write(f"fake-check: {path} is {found} in the index\n")
    return args.exit


if __name__ == "__main__":
    sys.exit(main())
