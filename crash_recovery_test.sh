#!/usr/bin/env bash
# Crash recovery test: start controller, kill it mid-run on D3, restart, verify completion.
set -euo pipefail

SIM_URL="${1:-http://127.0.0.1:8700}"
LOG_DIR="$(dirname "$0")/reports"
LOG_FILE="$LOG_DIR/crash_recovery.log"
mkdir -p "$LOG_DIR"

echo "=== Crash recovery test: $(date) ===" | tee "$LOG_FILE"
echo "Simulator: $SIM_URL" | tee -a "$LOG_FILE"

# Remove any stale state
rm -f controller.db

# Start controller in background
echo "[1] Starting controller..." | tee -a "$LOG_FILE"
python -m controller --url "$SIM_URL" >> "$LOG_FILE" 2>&1 &
CTRL_PID=$!
echo "    Controller PID: $CTRL_PID" | tee -a "$LOG_FILE"

# Let it run until approximately D3 (about 20 seconds of wall clock)
sleep 20

# Check how far we got
CALLS_BEFORE=$(python -c "
import sqlite3
try:
    conn = sqlite3.connect('controller.db')
    n = conn.execute('SELECT COUNT(*) FROM calls').fetchone()[0]
    print(n)
except:
    print(0)
" 2>/dev/null)
echo "[2] Calls ingested before kill: $CALLS_BEFORE" | tee -a "$LOG_FILE"

# Kill the controller
echo "[3] Killing controller (PID $CTRL_PID) at $(date)..." | tee -a "$LOG_FILE"
kill "$CTRL_PID" 2>/dev/null || true
sleep 2

# Confirm dead
if kill -0 "$CTRL_PID" 2>/dev/null; then
    kill -9 "$CTRL_PID" 2>/dev/null || true
fi
echo "    Controller killed." | tee -a "$LOG_FILE"

# Show DB state survived
python -c "
import sqlite3, json
conn = sqlite3.connect('controller.db')
calls = conn.execute('SELECT COUNT(*) FROM calls').fetchone()[0]
props = conn.execute(\"SELECT COUNT(*) FROM proposals WHERE status='pending'\").fetchone()[0]
exps  = conn.execute(\"SELECT COUNT(*) FROM experiments WHERE status='active'\").fetchone()[0]
print(f'  calls={calls}  pending_proposals={props}  active_experiments={exps}')
" 2>/dev/null | tee -a "$LOG_FILE"

# Restart
echo "[4] Restarting controller at $(date)..." | tee -a "$LOG_FILE"
python -m controller --url "$SIM_URL" >> "$LOG_FILE" 2>&1
EXIT_CODE=$?
echo "[5] Controller exited with code $EXIT_CODE at $(date)" | tee -a "$LOG_FILE"

if [ $EXIT_CODE -eq 0 ]; then
    CALLS_AFTER=$(python -c "
import sqlite3
conn = sqlite3.connect('controller.db')
print(conn.execute('SELECT COUNT(*) FROM calls').fetchone()[0])
" 2>/dev/null)
    echo "    Calls after restart: $CALLS_AFTER (ingested $((CALLS_AFTER - CALLS_BEFORE)) more)" | tee -a "$LOG_FILE"
    echo "PASS: Scenario completed after restart." | tee -a "$LOG_FILE"
else
    echo "FAIL: Controller exited with non-zero code." | tee -a "$LOG_FILE"
fi
echo "Log saved to: $LOG_FILE"
