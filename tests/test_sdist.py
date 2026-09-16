"""The source distribution never ships spike/.

setuptools_scm adds every tracked file to an sdist, and spikes are
evidence for this repository rather than part of the package; MANIFEST.in
prunes them. The working tree's tracked and unignored files are copied
into a fresh repository, committed and tagged, and an sdist is built from
that, so the test sees the tree as a release would.

Kept 3.6.8-clean like the rest of tests/.
"""

import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _have_build_backend():
    # type: () -> bool
    # Any setuptools reads setup.cfg, so only presence matters.
    try:
        import setuptools  # noqa: F401
        import setuptools_scm  # noqa: F401
    except ImportError:
        return False
    return True


needs_backend = pytest.mark.skipif(
    not _have_build_backend(),
    reason="needs setuptools and setuptools_scm in this interpreter (the dev extra)",
)


def _git(*args, cwd):
    # type: (str, Path) -> str
    r = subprocess.run(  # noqa: S603, S607, UP022
        ["git"] + list(args),
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")
    return r.stdout.decode("utf-8", "replace")


@needs_backend
def test_sdist_contains_no_spike(tmp_path):
    # type: (Path) -> None
    listing = _git("ls-files", "-z", "--cached", "--others", "--exclude-standard", cwd=REPO_ROOT)
    files = [f for f in listing.split("\0") if f and (REPO_ROOT / f).is_file()]
    assert any(f.startswith("spike/") for f in files), (
        "no spike to leave out; the test proves nothing"
    )
    copy = tmp_path / "release"
    for rel in files:
        target = copy / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(str(REPO_ROOT / rel), str(target))
    for args in (
        ("init", "-q"),
        ("add", "-A"),
        (
            "-c",
            "user.name=T",
            "-c",
            "user.email=t@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-q",
            "--no-verify",
            "-m",
            "release",
        ),
        ("tag", "v9.9.9"),
    ):
        _git(*args, cwd=copy)

    out = tmp_path / "dist"
    build = subprocess.run(  # noqa: S603, UP022
        [
            sys.executable,
            "-c",
            "import sys, setuptools.build_meta as b; print(b.build_sdist(sys.argv[1]))",
            str(out),
        ],
        cwd=str(copy),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,  # noqa: UP021
        check=False,
    )
    assert build.returncode == 0, build.stderr
    name = build.stdout.strip().splitlines()[-1]
    assert "9.9.9" in name
    with tarfile.open(str(out / name)) as archive:
        members = archive.getnames()
    assert any(m.endswith("/src/git_hygiene/check_identifiers.py") for m in members)
    assert not [m for m in members if "/spike/" in m or m.endswith("/spike")]
