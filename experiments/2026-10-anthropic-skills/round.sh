#!/usr/bin/env bash
# round.sh N PREV_RESULTS: owner agents propose -> merge -> cycle -> score on dev.json.
# Run from the work directory (see README).
set -e
D="$(cd "$(dirname "$0")" && pwd)"; S="$D/scripts"; T="${TREE:-$PWD/tree/lib}"
N=$1; PREV=$2
python3 -u "$S/owners.py" "$N" "$PREV" > "own$N.log" 2>&1
cp cards.py "cards_pre$N.py"; cp "$T/synonyms.md" "syn_pre$N.md"
python3 -u "$S/merge.py" "proposals_r$N.json" > "merge$N.log" 2>&1
"$D/cycle.sh" > "cycle$N.log" 2>&1
SENTS=dev.json python3 "$S/evalrun.py" "dev_r$N.json" > /dev/null 2>&1
python3 -u "$S/score.py" "dev_r$N.json" > "r$N.log"
cat "cycle$N.log" "r$N.log"
