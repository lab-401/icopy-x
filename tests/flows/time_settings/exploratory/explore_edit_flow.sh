#!/bin/bash
# Targeted exploration: verify OK→UP/DOWN editing flow for Time Settings
set +e
PROJECT="${PROJECT:-$(cd "$(dirname "$0")/../../../.." && pwd)}"
FLOW="explore_ts_edit"
SCENARIO="ts_edit"
source "${PROJECT}/tests/includes/common.sh"

FIXTURE="${PROJECT}/tests/flows/time_settings/exploratory/fixture_noop.py"
RAW_DIR="/tmp/raw_explore_ts_edit"
EXPLORE_RESULTS="${RESULTS_DIR}/explore_ts_edit"

rm -rf "${RAW_DIR}" "${EXPLORE_RESULTS}"
mkdir -p "${RAW_DIR}" "${EXPLORE_RESULTS}" "${SCENARIO_DIR}/screenshots" "${SCENARIO_DIR}/logs"
check_env; > "${KF}"

echo "=== Exploring Time Settings EDIT flow ==="
boot_qemu "${FIXTURE}"
if ! wait_for_hmi 40; then echo "[FAIL] HMI not ready"; cleanup_qemu; exit 1; fi
sleep 2

frame_idx=0
cap() {
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${RAW_DIR}" "${frame_idx}"
    sleep 1
    echo "[CAP] Frame ${frame_idx}: $1"
}

# Navigate to Time Settings
send_key "GOTO:12"
sleep 3
cap "DISPLAY mode"

# Enter EDIT
send_key "M1"
sleep 1
cap "EDIT mode entered (cursor on field)"

# Press OK to enter value-edit on year
send_key "OK"
sleep 1
cap "After OK (value-edit mode?)"

# Now UP should change the digit
send_key "UP"
sleep 1
cap "After UP in value-edit"

send_key "UP"
sleep 1
cap "After 2nd UP"

# RIGHT to move to next digit within year
send_key "RIGHT"
sleep 1
cap "RIGHT within year (next digit)"

send_key "UP"
sleep 1
cap "UP on 2nd digit of year"

# OK to confirm year value
send_key "OK"
sleep 1
cap "OK to confirm year"

# Now should be back at field level — RIGHT to month
send_key "RIGHT"
sleep 1
cap "RIGHT to month field"

# OK to enter month value-edit
send_key "OK"
sleep 1
cap "OK on month (value-edit)"

# UP to change month
send_key "UP"
sleep 1
cap "UP on month digit"

# OK to confirm
send_key "OK"
sleep 1
cap "OK to confirm month"

# Test: what happens with UP/DOWN WITHOUT OK (should be no-op on values)
send_key "UP"
sleep 1
cap "UP without OK (should be no-op)"

send_key "DOWN"
sleep 1
cap "DOWN without OK (should be no-op)"

# Cancel and exit
send_key "M1"
sleep 1
cap "M1 Cancel back to DISPLAY"

send_key "PWR"
sleep 2
cap "PWR exit from DISPLAY"

# Assemble states
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
print('Assembled %d states → %s' % (len(all_states), out))
"

cleanup_qemu; rm -rf "${RAW_DIR}"
echo "=== DONE ==="
