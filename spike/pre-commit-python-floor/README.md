# pre-commit Python floor

This spike records one fact: whether the wheel for `pre-commit` 4.6.2
declares, through its `Requires-Python` metadata, that it can be installed
on Python 3.6.8. The multi-check proposal relies on that fact, so it is
kept here in a form anyone can rerun.

`check-floor.py` pins the pre-commit version, the wheel filename and the
wheel's sha256. It downloads the wheel through PyPI, refuses it if the
checksum differs, reads `Requires-Python` from the wheel's `METADATA`, and
evaluates that specifier against 3.6.8 with a small PEP 440 comparison
limited to release-only versions. A specifier it cannot parse, such as a
wildcard `==3.6.*`, stops the run with exit status 2 instead of a guess.
It needs only the standard library and runs under Python 3.6.8 or newer.

`results-2026-09-16.txt` is the transcript of a run under Python 3.6.9.
The final line of output is the verdict; the lines above it (date,
interpreter, checksum, raw specifier) are context for a reader.

The script reads package metadata only and never installs or imports
pre-commit, so the answer does not depend on the host. Running it off the
designated host is a valid rerun.

To rerun:

    python3 spike/pre-commit-python-floor/check-floor.py

To rerun and check the recorded result:

    python3 spike/pre-commit-python-floor/check-floor.py \
        --compare spike/pre-commit-python-floor/results-2026-09-16.txt

Only the verdict line is compared; the header lines are expected to differ
between runs. Exit status is 0 when the verdicts match, 1 when they differ
or the download or checksum fails, and 2 when input cannot be parsed.
