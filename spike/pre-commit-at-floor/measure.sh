#!/usr/bin/env bash
#
# What does pre-commit 2.17.0, the newest release that installs on Python
# 3.6, do with this repository's hooks at the floor?
#
# Settles the value of minimum_pre_commit_version in .pre-commit-hooks.yaml
# by measuring both candidates, 3.2.0 (shipped until decision 0015) and
# 2.17.0, through `pre-commit try-repo` against a clone of HEAD with the
# manifest rewritten. A planted term proves the hook ran rather than passing
# unrun. Also records how the framework treats a hook that changes only the
# mode recorded in the index, under core.fileMode true and false, and one
# that gives the working file the same mode, including for a partly staged
# file (decision 0016).
#
# Run it on the RHEL 8.10 replica, offline from the pins in packages.tsv.
#
# Usage: measure.sh [-v]    transcript on stdout; -v echoes tool output
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
term=zorblaxquintet

say() { printf '%s\n' "$*" | tee -a "$work/findings"; }
run() {
    if [ $verbose = 1 ]; then "$@" 2>&1 | tee -a "$log" >&2; return "${PIPESTATUS[0]}"; fi
    "$@" >>"$log" 2>&1
}
capture() { "$@" > "$work/out" 2>&1; local rc=$?; cat "$work/out" >>"$log"; [ $verbose = 1 ] && cat "$work/out" >&2; return $rc; }

say "script      pre-commit-at-floor 1.1"
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

export PIP_NO_INDEX=1 PIP_FIND_LINKS=$cache PIP_DISABLE_PIP_VERSION_CHECK=1
export PRE_COMMIT_HOME=$work/pre-commit-home
export GIT_CONFIG_NOSYSTEM=1 GIT_AUTHOR_NAME=spike GIT_AUTHOR_EMAIL=spike@example.invalid
export GIT_COMMITTER_NAME=spike GIT_COMMITTER_EMAIL=spike@example.invalid

v=$work/venv
if $py -m venv "$v" \
   && run "$v/bin/python" -m pip install -q pip==21.3.1 \
   && run "$v/bin/python" -m pip install -q setuptools==59.6.0 wheel==0.37.1 \
   && run "$v/bin/python" -m pip install -q --no-build-isolation pre-commit==2.17.0; then
    say "install_pre_commit=pass version=$("$v/bin/pre-commit" --version | cut -d' ' -f2)"
else
    say "install_pre_commit=fail"; say "verdict=unmeasured"; exit 2
fi
export PATH=$v/bin:$PATH

# The term file is named explicitly and inheritance is off, so nothing from
# the operator's own lists takes part.
printf '%s\n' "$term" > "$work/terms.txt"
export GIT_DENY_TERMS=$work/terms.txt GIT_HYGIENE_NO_INHERIT=1

consumer() {
    local d=$1
    git init -q "$d"
    git -C "$d" config core.fileMode true
}

# --- minimum_pre_commit_version candidates -------------------------------
for minimum in 3.2.0 2.17.0; do
    hooks=$work/hooks-$minimum
    git clone -q "$root" "$hooks"
    sed -i "s/minimum_pre_commit_version: \"[0-9.]*\"/minimum_pre_commit_version: \"$minimum\"/" \
        "$hooks/.pre-commit-hooks.yaml"
    run git -C "$hooks" commit -q --allow-empty -am "spike: minimum $minimum"
    key=min_${minimum//./_}

    c=$work/clean-$minimum; consumer "$c"
    printf 'ordinary content\n' > "$c/file.md"; git -C "$c" add file.md
    if (cd "$c" && capture pre-commit try-repo "$hooks" deny-terms --all-files); then
        say "${key}_clean=passed"
    elif grep -q "requires pre-commit version $minimum" "$work/out"; then
        say "${key}_clean=refused (hook requires a newer pre-commit)"
    else
        say "${key}_clean=failed (other)"
    fi

    d=$work/dirty-$minimum; consumer "$d"
    printf 'mentions %s here\n' "$term" > "$d/file.md"; git -C "$d" add file.md
    if (cd "$d" && capture pre-commit try-repo "$hooks" deny-terms --all-files); then
        say "${key}_planted=passed"
    elif grep -q "requires pre-commit version $minimum" "$work/out"; then
        say "${key}_planted=refused (hook requires a newer pre-commit)"
    elif grep -q BLOCKED "$work/out"; then
        say "${key}_planted=blocked by the hook"
    else
        say "${key}_planted=failed (other)"
    fi
done

# --- a hook that changes only the index mode ----------------------------
mkdir -p "$work/bin"
cat > "$work/bin/fix-mode" <<'EOF'
#!/bin/sh
git diff --cached --name-only --diff-filter=AM -- '*.sh' | while read -r f; do
    git update-index --chmod=+x -- "$f"
done
EOF
chmod 755 "$work/bin/fix-mode"
cat > "$work/bin/fix-mode-both" <<'EOF'
#!/bin/sh
git diff --cached --name-only --diff-filter=AM -- '*.sh' | while read -r f; do
    git update-index --chmod=+x -- "$f"
    chmod +x -- "$f"
done
EOF
chmod 755 "$work/bin/fix-mode-both"
export PATH=$work/bin:$PATH

for mode in true false; do
    m=$work/mode-$mode; consumer "$m"
    git -C "$m" config core.fileMode "$mode"
    cat > "$m/.pre-commit-config.yaml" <<'EOF'
repos:
- repo: local
  hooks:
  - id: fix-mode
    name: fix-mode
    entry: fix-mode
    language: system
    pass_filenames: false
    always_run: true
EOF
    (cd "$m" && run pre-commit install)
    printf 'echo hi\n' > "$m/run.sh"; chmod 644 "$m/run.sh"
    git -C "$m" add -A
    if (cd "$m" && capture git commit -q -m first); then
        first=landed
    elif grep -q 'files were modified by this hook' "$work/out"; then
        first="refused (files were modified by this hook)"
    else
        first="refused (other)"
    fi
    second=not-needed
    if [ "$first" != landed ]; then
        if (cd "$m" && capture git commit -q -m second); then second=landed; else second=refused; fi
    fi
    recorded=$(git -C "$m" ls-tree HEAD run.sh 2>/dev/null | cut -d' ' -f1)
    say "filemode_${mode}_first_commit=$first"
    say "filemode_${mode}_second_commit=$second"
    say "filemode_${mode}_recorded_mode=${recorded:-none}"
done

# Both modes set, with core.fileMode true: a fully staged file and a partly
# staged one, whose unstaged line must survive the framework's stash.
b=$work/mode-both; consumer "$b"
cat > "$b/.pre-commit-config.yaml" <<'EOF'
repos:
- repo: local
  hooks:
  - id: fix-mode-both
    name: fix-mode-both
    entry: fix-mode-both
    language: system
    pass_filenames: false
    always_run: true
EOF
(cd "$b" && run pre-commit install)
printf 'echo one\n' > "$b/whole.sh"
printf 'echo staged\n' > "$b/part.sh"
chmod 644 "$b/whole.sh" "$b/part.sh"
git -C "$b" add -A
printf 'echo unstaged\n' >> "$b/part.sh"
if (cd "$b" && capture git commit -q -m first); then first=landed; else first=refused; fi
say "filemode_true_both_first_commit=$first"
say "filemode_true_both_recorded_modes=$(git -C "$b" ls-tree HEAD whole.sh part.sh 2>/dev/null | cut -d' ' -f1 | sort -u | tr '\n' ' ')"
if [ "$(git -C "$b" show HEAD:part.sh 2>/dev/null)" = "echo staged" ]; then
    say "filemode_true_both_partial_commit=staged half only"
else
    say "filemode_true_both_partial_commit=other"
fi
if grep -q '^echo unstaged$' "$b/part.sh"; then
    say "filemode_true_both_partial_worktree=unstaged half kept"
else
    say "filemode_true_both_partial_worktree=unstaged half lost"
fi

say ""
f=$work/findings
if grep -q '^min_3_2_0_clean=refused' "$f" && grep -q '^min_2_17_0_clean=passed' "$f" \
   && grep -q '^min_2_17_0_planted=blocked' "$f" \
   && grep -q '^filemode_true_both_first_commit=landed' "$f" \
   && grep -q '^filemode_true_both_partial_worktree=unstaged half kept' "$f"; then
    say "verdict=pre-commit 2.17.0 runs these hooks only when the manifest admits 2.17.0; a mode fix that sets both modes lands on the first commit"
else
    say "verdict=not established"
    exit 1
fi
