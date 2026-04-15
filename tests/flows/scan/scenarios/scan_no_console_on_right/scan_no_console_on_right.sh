#!/bin/bash
# Negative test: RIGHT during Scan flow should NOT open console
# Console is only available during Read and the Read phase of Auto-Copy.
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="scan_no_console_on_right"
FLOW="scan"
source "${PROJECT}/tests/includes/common.sh"

SCAN_SCENARIO_DIR="${PROJECT}/tests/flows/scan/scenarios/${SCENARIO}"

check_env
clean_scenario

RAW_DIR="/tmp/raw_scan_console_${SCENARIO}"
mkdir -p "${RAW_DIR}"

boot_qemu "${SCAN_SCENARIO_DIR}/fixture.py"

if ! wait_for_hmi 30; then
    report_fail "HMI not ready"
    cleanup_qemu
    rm -rf "${RAW_DIR}"
    exit 1
fi
sleep 1

FRAME=0

# Navigate to Scan Tag (GOTO:2)
send_key "GOTO:2"
sleep 3

# Capture baseline during scanning
FRAME=$((FRAME+1))
capture_frame_with_state "${RAW_DIR}" "${FRAME}"
sleep 0.5

# Hash baseline (mask battery)
BASELINE_PNG="${RAW_DIR}/$(printf '%05d' ${FRAME}).png"
BASELINE_HASH=$(convert "${BASELINE_PNG}" -fill black -draw "rectangle 200,0 240,40" rgba:- 2>/dev/null | md5sum | awk '{print $1}')

# Send RIGHT — should have NO effect during scan
send_key "RIGHT"
sleep 1

FRAME=$((FRAME+1))
capture_frame_with_state "${RAW_DIR}" "${FRAME}"
sleep 0.5

AFTER_PNG="${RAW_DIR}/$(printf '%05d' ${FRAME}).png"
AFTER_HASH=$(convert "${AFTER_PNG}" -fill black -draw "rectangle 200,0 240,40" rgba:- 2>/dev/null | md5sum | awk '{print $1}')

# Wait for scan to complete, capture result
sleep 5
FRAME=$((FRAME+1))
capture_frame_with_state "${RAW_DIR}" "${FRAME}"

dedup_screenshots "${RAW_DIR}" "${SCREENSHOTS_DIR}"

# Verdict: PASS if RIGHT did not change the screen
if [ "${BASELINE_HASH}" = "${AFTER_HASH}" ]; then
    report_pass "RIGHT had no effect during scan (${DEDUP_COUNT} states)"
else
    report_fail "Screen changed after RIGHT during scan (hash mismatch, ${DEDUP_COUNT} states)"
fi

cleanup_qemu
rm -rf "${RAW_DIR}"
