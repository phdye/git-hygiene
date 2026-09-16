# Sourced by the spikes, not run. Fetches every file named in a packages.tsv
# into a cache directory and checks it against its recorded sha256.
#
# fetch_pinned PYTHON TSV CACHE LOG
#   Returns non-zero if any file is missing or does not match its hash.
#   A file already in the cache is not fetched again, but is still checked.

fetch_pinned() {
    local py=$1 tsv=$2 cache=$3 log=$4 f sum name ver ok=0
    mkdir -p "$cache"
    while IFS=$'\t' read -r f sum; do
        case $f in ''|\#*) continue ;; esac
        if [ ! -f "$cache/$f" ]; then
            name=${f%%-[0-9]*}
            ver=${f#"$name"-}; ver=${ver%%-*}; ver=${ver%.tar.gz}
            PIP_NO_INDEX= PIP_FIND_LINKS= "$py" -m pip download -q --no-deps \
                -d "$cache" "$name==$ver" >>"$log" 2>&1
        fi
        if [ "$(sha256sum < "$cache/$f" 2>/dev/null | cut -d' ' -f1)" != "$sum" ]; then
            echo "fetch_pinned: missing or hash mismatch: $f" >>"$log"
            ok=1
        fi
    done < "$tsv"
    return $ok
}
