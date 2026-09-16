#!/usr/bin/env bash
#
# Rerun every spike and hold each result to its committed transcript. A spike
# reproduces its findings, not its measurements: verdict words and case labels
# must come back identical, while numbers, dates, versions and the provenance
# header are free to move. A spike may report a negative finding by exiting
# non-zero, so the exit status is not the test; producing no transcript, or
# different findings, is.
#
# A row marked SKIP is not applicable and does not affect the verdict. A row
# whose input is absent went unchecked, which makes the run INCOMPLETE and
# fails it rather than letting it pass in silence.
#
# Usage: spike-regen.sh [-o FILE] [SPIKE...]
#   With no SPIKE every row of the manifest runs; otherwise only the named
#   spike directories. The manifest is $SPIKE_MANIFEST if set, else
#   test/spike-regen.tsv.
# Exit: 0 only if every applicable spike regenerated its findings.

set -u
prog=spike-regen
here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/.." && pwd)
manifest=${SPIKE_MANIFEST:-$here/spike-regen.tsv}

out=-
while [ $# -gt 0 ] && [ "${1#-}" != "$1" ]; do
	case $1 in
		-o) shift; out=${1:?-o wants a file}; shift ;;
		-h|--help) sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
		*) echo "$prog: unknown option $1" >&2; exit 2 ;;
	esac
done
only=" $* "
[ "$out" = - ] || exec > "$out" 2>&1

# Findings: drop blank lines, comments and the provenance header (keys
# aligned by two or more spaces), collapse temp paths, dates and numbers,
# squeeze whitespace, sort.
findings() {
	grep -avE '^[[:space:]]*($|#)|^[[:space:]]*(script|date|host|python|pip|git|source_ref)[[:space:]]{2,}' "$1" 2>/dev/null \
	| sed -E '
	    s@[^[:space:]]*/[Tt][Mm][Pp]/[^[:space:]]*@TMPPATH@g;
	    s/[0-9]{4}-[0-9]{2}-[0-9]{2}(T[0-9:]+Z?)?/DATE/g;
	    s/[0-9]+(\.[0-9]+)*/N/g;
	    s/[[:space:]]+/ /g;
	    s/^ //; s/ $//' \
	| sort
}

pass=0; fail=0; na=0; absent=0
printf '# spike regeneration -- %s\n\n' "$(date +%F)"

while IFS=$'\t' read -r dir needs txt cmd <&3; do
	case $dir in ''|\#*) continue ;; esac
	[ "$only" = "  " ] || case "$only" in *" $dir "*) ;; *) continue ;; esac
	needs=$(eval "printf '%s' \"$needs\"")
	sdir=$root/spike/$dir
	if [ ! -d "$sdir" ]; then
		printf '%-24s UNMET no such spike directory\n' "$dir"; absent=$((absent+1)); continue
	fi
	if [ "$needs" = SKIP ]; then
		printf '%-24s n/a   not applicable here\n' "$dir"; na=$((na+1)); continue
	fi
	if [ "$needs" != - ] && [ ! -e "$needs" ]; then
		printf '%-24s UNMET not checked, input absent: %s\n' "$dir" "$needs"; absent=$((absent+1)); continue
	fi

	fresh=$(mktemp)
	( cd "$sdir" && eval "$cmd" ) > "$fresh" 2>/dev/null
	if [ ! -s "$fresh" ]; then
		printf '%-24s FAIL  rotted: no transcript\n' "$dir"; fail=$((fail+1)); rm -f "$fresh"; continue
	fi
	# Newest by name, since a fresh clone gives every file the same mtime.
	committed=$(ls -1 "$sdir"/$txt 2>/dev/null | sort -r | head -1)
	if [ -z "$committed" ]; then
		printf '%-24s FAIL  no committed transcript matches %s\n' "$dir" "$txt"; fail=$((fail+1)); rm -f "$fresh"; continue
	fi
	if [ "$(findings "$committed")" = "$(findings "$fresh")" ]; then
		printf '%-24s ok    regenerates %s\n' "$dir" "$(basename "$committed")"; pass=$((pass+1))
	else
		printf '%-24s FAIL  findings moved from %s:\n' "$dir" "$(basename "$committed")"; fail=$((fail+1))
		diff <(findings "$committed") <(findings "$fresh") | sed 's/^/     /'
	fi
	rm -f "$fresh"
done 3< "$manifest"

printf '\n%s: %d regenerated, %d rotted or moved, %d not applicable, %d not checked\n' \
	"$prog" "$pass" "$fail" "$na" "$absent"
[ "$absent" -gt 0 ] && printf '%s: INCOMPLETE, %d spike(s) unchecked\n' "$prog" "$absent"
[ "$fail" = 0 ] && [ "$absent" = 0 ]
