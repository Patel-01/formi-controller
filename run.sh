#!/usr/bin/env bash
# Outcome-first controller. Usage: ./run.sh <SIM_URL>
# Requires: Python 3.11+, packages in requirements.txt
# State: controller.db (SQLite WAL) created in the working directory.
# Restart-safe: re-run this script against the same simulator to resume.
set -euo pipefail
SIM_URL="${1:?usage: ./run.sh <SIM_URL>}"
# prefer python3 if available, fall back to python
PYTHON=$(command -v python3 2>/dev/null || command -v python)
exec "$PYTHON" -m controller --url "$SIM_URL"
