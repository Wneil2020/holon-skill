#!/usr/bin/env bash
# Write cards.py into the tree, then sync, validate, lint and replay it.
# Run from the work directory (see README).
set -e
D="$(cd "$(dirname "$0")" && pwd)"; S="$D/scripts"
REPO="${HOLON_REPO:-$(cd "$D/../.." && pwd)}"; T="${TREE:-$PWD/tree/lib}"
python3 "$S/apply.py" "$T" > /dev/null
python3 "$REPO/holon/scripts/holon.py" sync "$T" | tail -1
python3 "$REPO/holon/scripts/holon.py" validate "$T" | tail -1
python3 "$REPO/holon/organizer/scripts/organizer_cli.py" lint "$T" | tail -2
python3 "$REPO/holon/organizer/scripts/organizer_cli.py" replay "$T" | tail -2
