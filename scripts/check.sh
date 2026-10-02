#!/usr/bin/env bash
# Use the same checks for git checkouts and downloaded source archives.
# Usage: bash scripts/check.sh        from any working directory.
set -euo pipefail
cd "$(dirname "$0")/.."
exec "${PYTHON:-python3}" scripts/check.py
