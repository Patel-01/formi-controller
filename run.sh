#!/usr/bin/env bash
# Outcome-first controller. Usage: ./run.sh <SIM_URL>
set -euo pipefail
SIM_URL="${1:?usage: ./run.sh <SIM_URL>}"
exec python -m controller --url "$SIM_URL"
