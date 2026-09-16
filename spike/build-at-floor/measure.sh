#!/usr/bin/env bash
#
# Can git-hygiene be built and installed at the Python floor?
#
# Two candidates for [build-system] are measured on the same interpreter.
# "original" is what the package shipped with until decision 0013:
# setuptools>=61, setuptools_scm>=8, metadata in a [project] table. It is
# resolved against the live index, because the question is whether any
# release it admits runs here. "pinned" is the committed tree at HEAD, built
# offline from the hash-checked wheels in packages.tsv.
#
# Run it on the RHEL 8.10 replica, whose python3 is the floor series.
#
# Usage: measure.sh [-v]    transcript on stdout; -v echoes pip to stderr
# Environment: GIT_HYGIENE_SPIKE_CACHE (optional) is where fetched inputs
#   are kept; default ~/.cache/git-hygiene-spike.
set -u
here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/../.." && pwd)
. "$here/../fetch-pinned.sh"
cache=${GIT_HYGIENE_SPIKE_CACHE:-$HOME/.cache/git-hygiene-spike}
verbose=0; [ "${1:-}" = -v ] && verbose=1
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
log=$work/log
py=python3

say() { printf '%s\n' "$*" | tee -a "$work/findings"; }
run() {
    if [ $verbose = 1 ]; then "$@" 2>&1 | tee -a "$log" >&2; return "${PIPESTATUS[0]}"; fi
    "$@" >>"$log" 2>&1
}

say "script      build-at-floor 1.0"
say "date        $(date -u +%Y-%m-%dT%H:%M:%SZ)"
say "host        $(uname -sr)"
say "python      $($py --version 2>&1)"
say "git         $(git --version)"
say "source_ref  $(git -C "$root" describe --always --dirty)"
say ""

case $($py -c 'import sys; print("%d.%d" % sys.version_info[:2])') in
    3.6) say "interpreter_series=floor" ;;
    *)   say "interpreter_series=not-floor" ;;
esac

if fetch_pinned "$py" "$here/packages.tsv" "$cache" "$log"; then
    say "inputs_verified=yes"
else
    say "inputs_verified=no"; say "verdict=unmeasured"; exit 2
fi

# --- candidate: original -------------------------------------------------
orig=$work/original
git clone -q "$root" "$orig"
git -C "$root" show 99ccb60:pyproject.toml > "$orig/pyproject.toml"
rm -f "$orig/setup.cfg" "$orig/MANIFEST.in"
if run $py -m pip wheel -q --no-deps -w "$work/dist-orig" "$orig"; then
    say "original_wheel=pass"
elif grep -q 'No matching distribution found for setuptools>=61' "$log"; then
    say "original_wheel=refused (no setuptools>=61 release runs on this interpreter)"
else
    say "original_wheel=fail (other)"
fi

# --- candidate: pinned ---------------------------------------------------
export PIP_NO_INDEX=1 PIP_FIND_LINKS=$cache PIP_DISABLE_PIP_VERSION_CHECK=1
src=$work/pinned
git clone -q "$root" "$src"
dist=$work/dist

if run $py -m pip wheel -q --no-deps -w "$dist" "$src"; then
    say "pinned_wheel=pass"
else
    say "pinned_wheel=fail"
fi
whl=$(ls "$dist"/*.whl 2>/dev/null | head -1)
if [ -n "$whl" ]; then
    meta=$(unzip -p "$whl" '*/METADATA')
    rp=$(printf '%s\n' "$meta" | sed -n 's/^Requires-Python: //p')
    if [ "$rp" = ">=3.6.8" ]; then say "wheel_requires_python=floor"; else say "wheel_requires_python=other"; fi
    ver=$(printf '%s\n' "$meta" | sed -n 's/^Version: //p')
    case $ver in
        0.0.0*|'') say "wheel_version=fallback" ;;
        *) say "wheel_version=from-git" ;;
    esac
    eps=$(unzip -p "$whl" '*/entry_points.txt' | sed -n 's/ =.*//p' | sort | tr '\n' ' ')
    say "wheel_console_scripts=$eps"
fi

venv() {
    $py -m venv "$1" && run "$1/bin/python" -m pip install -q "pip==21.3.1"
}

scripts_run() {
    local s bad=0
    for s in check-identifiers audit-tree install-hooks; do
        "$1/bin/$s" --help >/dev/null 2>&1 || bad=1
    done
    if [ $bad = 0 ]; then echo run; else echo fail; fi
}

# The sdist goes through the backend directly, in a venv holding the pins.
bv=$work/venv-build
if venv "$bv" \
   && run "$bv/bin/python" -m pip install -q setuptools==59.6.0 "setuptools_scm[toml]==6.4.2" wheel==0.37.1 \
   && (cd "$src" && run "$bv/bin/python" -c "from setuptools import build_meta as b; b.build_sdist('$dist')"); then
    say "pinned_sdist=pass"
    tgz=$(ls "$dist"/*.tar.gz | head -1)
    if tar tzf "$tgz" | grep -qE '^[^/]+/spike/'; then say "sdist_contains_spike=yes"; else say "sdist_contains_spike=no"; fi
else
    say "pinned_sdist=fail"
fi

wv=$work/venv-wheel
if [ -n "$whl" ] && venv "$wv" && run "$wv/bin/python" -m pip install -q "$whl"; then
    say "install_wheel=pass scripts=$(scripts_run "$wv")"
else
    say "install_wheel=fail"
fi

sv=$work/venv-source
if venv "$sv" && run "$sv/bin/python" -m pip install -q "$src"; then
    say "install_source=pass scripts=$(scripts_run "$sv")"
else
    say "install_source=fail"
fi

ev=$work/venv-editable
if venv "$ev" && run "$ev/bin/python" -m pip install -q -e "$src"; then
    where=$("$ev/bin/python" -c 'import git_hygiene; print(git_hygiene.__file__)')
    case $where in "$src"/*) loc=source-tree ;; *) loc=elsewhere ;; esac
    say "install_editable=pass scripts=$(scripts_run "$ev") imports_from=$loc"
else
    say "install_editable=fail"
fi

say ""
f=$work/findings
if grep -q '^original_wheel=refused' "$f" \
   && grep -q '^pinned_wheel=pass' "$f" && grep -q '^pinned_sdist=pass' "$f" \
   && grep -q '^sdist_contains_spike=no' "$f" \
   && grep -q '^install_wheel=pass scripts=run' "$f" \
   && grep -q '^install_source=pass scripts=run' "$f" \
   && grep -q '^install_editable=pass scripts=run' "$f"; then
    say "verdict=pinned builds and installs at the floor; original does not"
else
    say "verdict=not established"
    exit 1
fi
