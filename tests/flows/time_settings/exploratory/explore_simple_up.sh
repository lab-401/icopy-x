#!/bin/bash
# Minimal test: EDIT → UP with long waits, then EDIT → OK → UP
set +e
PROJECT="${PROJECT:-$(cd "$(dirname "$0")/../../../.." && pwd)}"
FLOW="explore_ts_up"
SCENARIO="ts_up"
source "${PROJECT}/tests/includes/common.sh"

FIXTURE="${PROJECT}/tests/flows/time_settings/exploratory/fixture_noop.py"
RAW_DIR="/tmp/raw_explore_ts_up"
EXPLORE_RESULTS="${RESULTS_DIR}/explore_ts_up"

rm -rf "${RAW_DIR}" "${EXPLORE_RESULTS}"
mkdir -p "${RAW_DIR}" "${EXPLORE_RESULTS}" "${SCENARIO_DIR}/screenshots" "${SCENARIO_DIR}/logs"
check_env; > "${KF}"

boot_qemu "${FIXTURE}"
if ! wait_for_hmi 40; then echo "FAIL HMI"; cleanup_qemu; exit 1; fi
sleep 2

frame_idx=0
cap() {
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${RAW_DIR}" "${frame_idx}"
    sleep 1.5
    echo "[CAP $frame_idx] $1"
}

send_key "GOTO:12"
sleep 3
cap "DISPLAY"

# Test 1: EDIT → UP directly (no OK)
send_key "M1"
sleep 2
cap "EDIT (cursor on year)"

send_key "UP"
sleep 2
cap "UP #1 on year (no OK)"

send_key "UP"
sleep 2
cap "UP #2 on year (no OK)"

# Cancel back to DISPLAY
send_key "M1"
sleep 2
cap "Cancel → DISPLAY"

# Test 2: EDIT → RIGHT to month → UP
send_key "M1"
sleep 2
cap "EDIT again"

send_key "RIGHT"
sleep 2
cap "RIGHT to month"

send_key "UP"
sleep 2
cap "UP on month (no OK)"

send_key "UP"
sleep 2
cap "UP #2 on month (no OK)"

# Cancel
send_key "M1"
sleep 2
cap "Cancel → DISPLAY"

# Test 3: EDIT → OK → UP (with OK)
send_key "M1"
sleep 2
cap "EDIT #3"

send_key "OK"
sleep 2
cap "OK on year"

send_key "UP"
sleep 2
cap "UP after OK on year"

send_key "M1"
sleep 2
cap "Cancel → DISPLAY"

sleep 1
python3 -c "
import json, glob, os
dump_dir = '${STATE_DUMP_TMP}'
all_states = []
for f in sorted(glob.glob(os.path.join(dump_dir, 'state_*.json'))):
    try:
        with open(f) as fh: d = json.load(fh)
        all_states.append(d)
    except: pass
out = '${EXPLORE_RESULTS}/all_states.json'
with open(out, 'w') as f: json.dump(all_states, f, indent=2, default=str)
print('Assembled %d states' % len(all_states))
"
cleanup_qemu; rm -rf "${RAW_DIR}"
echo "=== DONE ==="
