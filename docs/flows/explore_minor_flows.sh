#!/bin/bash
# Exploratory ground-truth captures for About, Time Settings, PC Mode flows.
# Runs against original firmware, captures STATE_DUMPs at every step.
# Usage: TEST_TARGET=original bash tests/flows/explore_minor_flows.sh
set +e

PROJECT="${PROJECT:-$(cd "$(dirname "$0")/../.." && pwd)}"
FLOW="explore"
SCENARIO="minor_flows"
source "${PROJECT}/tests/includes/common.sh"

FIXTURE="${PROJECT}/tests/flows/about/exploratory/fixture_noop.py"
RAW_DIR="/tmp/raw_explore_minor"
EXPLORE_RESULTS="${RESULTS_DIR}/explore_minor"

rm -rf "${RAW_DIR}" "${EXPLORE_RESULTS}"
mkdir -p "${RAW_DIR}" "${EXPLORE_RESULTS}/about" "${EXPLORE_RESULTS}/time_settings" "${EXPLORE_RESULTS}/pc_mode"
mkdir -p "${SCENARIO_DIR}/screenshots" "${SCENARIO_DIR}/logs"

check_env
> "${KF}"

echo "=== Exploratory: Booting QEMU ==="
boot_qemu "${FIXTURE}"

if ! wait_for_hmi 40; then
    echo "[FAIL] HMI not ready"
    cleanup_qemu
    exit 1
fi
echo "=== HMI ready ==="
sleep 2

frame_idx=0

# Helper: capture + dump
cap() {
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${RAW_DIR}" "${frame_idx}"
    sleep 0.7
    echo "[CAP] Frame ${frame_idx}: $1"
}

# =============================================
# ABOUT FLOW (GOTO:10)
# =============================================
echo ""
echo "=========================================="
echo "  EXPLORING: ABOUT (GOTO:10)"
echo "=========================================="

send_key "GOTO:10"
sleep 3
cap "About: entry (check for Processing toast)"
sleep 1
cap "About: after 1s"
sleep 1
cap "About: after 2s (should be Page 1 now)"
sleep 1
cap "About: Page 1 stable"

# Check buttons
cap "About: Page 1 — checking M1/M2 state"

# Navigate to page 2
send_key "DOWN"
sleep 1
cap "About: Page 2 after DOWN"
sleep 0.5
cap "About: Page 2 stable"

# Navigate back to page 1
send_key "UP"
sleep 1
cap "About: Back to Page 1 after UP"

# Try M1 from page 1 (should be no-op)
send_key "M1"
sleep 1
cap "About: After M1 from Page 1"

# Go to page 2 and try M1 (should go back to page 1)
send_key "DOWN"
sleep 1
cap "About: Page 2 again"
send_key "M1"
sleep 1
cap "About: After M1 from Page 2 (should be Page 1)"

# Try OK from page 1 — should launch UpdateActivity
send_key "OK"
sleep 2
cap "About: After OK (should be UpdateActivity or error)"
sleep 1
cap "About: UpdateActivity stable?"

# If we got to UpdateActivity, try PWR to go back
send_key "PWR"
sleep 2
cap "About: After PWR from UpdateActivity (should be back to About)"

# Try M2 from About page 1
send_key "M2"
sleep 2
cap "About: After M2 (should launch UpdateActivity)"
sleep 1
cap "About: UpdateActivity via M2?"

# If in UpdateActivity, press M2/OK to try install (no IPK → "No update available")
send_key "M2"
sleep 3
cap "About: After M2 in UpdateActivity (search for IPK)"
sleep 2
cap "About: IPK search result?"

# PWR to exit whatever state we're in
send_key "PWR"
sleep 2
cap "About: After PWR exit attempt"
send_key "PWR"
sleep 2
cap "About: After second PWR (should be at main menu)"

# =============================================
# TIME SETTINGS (GOTO:12)
# =============================================
echo ""
echo "=========================================="
echo "  EXPLORING: TIME SETTINGS (GOTO:12)"
echo "=========================================="

send_key "GOTO:12"
sleep 3
cap "TimeSettings: entry DISPLAY mode"
sleep 1
cap "TimeSettings: DISPLAY stable"

# Enter edit mode with M1
send_key "M1"
sleep 1
cap "TimeSettings: EDIT mode after M1 (cursor on year)"

# Cursor RIGHT through all 6 fields
for field in month day hour minute second; do
    send_key "RIGHT"
    sleep 0.5
    cap "TimeSettings: cursor on ${field}"
done

# Cursor RIGHT one more — should wrap to year
send_key "RIGHT"
sleep 0.5
cap "TimeSettings: cursor wrapped to year"

# Cursor LEFT — should wrap to second
send_key "LEFT"
sleep 0.5
cap "TimeSettings: cursor LEFT to second (wrap)"

# Move to year and test UP increment
send_key "RIGHT"
sleep 0.3
cap "TimeSettings: back on year"

send_key "UP"
sleep 0.5
cap "TimeSettings: year after UP (increment)"

send_key "DOWN"
sleep 0.5
cap "TimeSettings: year after DOWN (decrement back)"

# Move to month, test wrapping
send_key "RIGHT"
sleep 0.3
# We need to know current month to test wrapping — just increment many times
for i in $(seq 1 12); do
    send_key "UP"
    sleep 0.2
done
cap "TimeSettings: month after 12 UPs (should have wrapped)"

# Test day clamping — move to day, go to month Feb
send_key "LEFT"  # back to month
sleep 0.3
# Set month to February (month=2): need to know current to calculate, just capture state
cap "TimeSettings: current month value"
send_key "RIGHT"  # to day
sleep 0.3
cap "TimeSettings: current day value"

# Cancel edit
send_key "M1"
sleep 1
cap "TimeSettings: after Cancel (back to DISPLAY)"

# Enter edit with M2
send_key "M2"
sleep 1
cap "TimeSettings: EDIT mode after M2"

# Save
send_key "M2"
sleep 1
cap "TimeSettings: after Save M2 (syncing toast?)"
sleep 1
cap "TimeSettings: after Save (sync ok toast?)"
sleep 2
cap "TimeSettings: after Save (back to DISPLAY?)"

# PWR to cancel from EDIT
send_key "M2"  # enter edit again
sleep 1
cap "TimeSettings: EDIT mode again"
send_key "PWR"
sleep 1
cap "TimeSettings: after PWR in EDIT (should return to DISPLAY)"

# PWR from DISPLAY to exit
send_key "PWR"
sleep 2
cap "TimeSettings: after PWR from DISPLAY (should be main menu)"

# =============================================
# PC MODE (GOTO:6)
# =============================================
echo ""
echo "=========================================="
echo "  EXPLORING: PC MODE (GOTO:6)"
echo "=========================================="

send_key "GOTO:6"
sleep 3
cap "PCMode: entry IDLE state"
sleep 1
cap "PCMode: IDLE stable"

# Check buttons in IDLE
cap "PCMode: IDLE buttons (M1=Start, M2=Start)"

# Try OK to start
send_key "OK"
sleep 2
cap "PCMode: after OK (STARTING/Processing toast?)"
sleep 2
cap "PCMode: after OK +2s (RUNNING?)"
sleep 2
cap "PCMode: after OK +4s (RUNNING stable?)"

# If RUNNING, check buttons (M1=Stop, M2=Button)
cap "PCMode: RUNNING buttons?"

# Try OK in RUNNING — should be no-op
send_key "OK"
sleep 1
cap "PCMode: after OK in RUNNING (should be no-op)"

# Stop with M1
send_key "M1"
sleep 3
cap "PCMode: after M1 stop (STOPPING → exit?)"
sleep 2
cap "PCMode: after stop +2s (should be main menu)"

# Re-enter PC Mode
send_key "GOTO:6"
sleep 3
cap "PCMode: re-enter IDLE"

# Start with M2
send_key "M2"
sleep 4
cap "PCMode: after M2 start (RUNNING?)"

# Stop with PWR
send_key "PWR"
sleep 3
cap "PCMode: after PWR stop from RUNNING"
sleep 2
cap "PCMode: after PWR stop +2s"

# Re-enter and test PWR from IDLE
send_key "GOTO:6"
sleep 3
cap "PCMode: re-enter IDLE for PWR test"
send_key "PWR"
sleep 2
cap "PCMode: after PWR from IDLE (should exit)"

# =============================================
# DONE — collect state dumps
# =============================================
echo ""
echo "=========================================="
echo "  CAPTURE COMPLETE: ${frame_idx} frames"
echo "=========================================="

sleep 2

# Copy all state dumps
cp -r "${STATE_DUMP_TMP}/"*.json "${EXPLORE_RESULTS}/" 2>/dev/null || true

# List all captured state dumps
echo ""
echo "=== State dumps ==="
ls -la "${STATE_DUMP_TMP}/"*.json 2>/dev/null | wc -l
echo "state dump files"

# Assemble a combined JSON with ALL state data
python3 -c "
import json, glob, os
dump_dir = '${STATE_DUMP_TMP}'
all_states = []
for f in sorted(glob.glob(os.path.join(dump_dir, 'state_*.json'))):
    try:
        with open(f) as fh:
            d = json.load(fh)
            all_states.append(d)
    except: pass

out = '${EXPLORE_RESULTS}/all_states.json'
with open(out, 'w') as f:
    json.dump(all_states, f, indent=2, default=str)
print('Assembled %d states → %s' % (len(all_states), out))
"

cleanup_qemu
rm -rf "${RAW_DIR}"
echo ""
echo "=== Results in: ${EXPLORE_RESULTS} ==="
echo "=== DONE ==="
