#!/bin/bash
# Negative test: RIGHT during Auto-Copy SCAN phase should NOT open console
# Console is only available during the read portion, not the scan.
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="autocopy_mf1k_no_console_during_scan"
FLOW="auto-copy"
PM3_DELAY=5.0
BOOT_TIMEOUT=600
source "${PROJECT}/tests/includes/common.sh"

# Re-derive paths for auto-copy flow
SCENARIO_DIR="${RESULTS_DIR}/${FLOW}/scenarios/${SCENARIO}"
SCREENSHOTS_DIR="${SCENARIO_DIR}/screenshots"
LOG_FILE="${SCENARIO_DIR}/logs/scenario_log.txt"
AC_SCENARIO_DIR="${PROJECT}/tests/flows/auto-copy/scenarios/${SCENARIO}"

check_env
clean_scenario

RAW_DIR="/tmp/raw_ac_console_neg_${SCENARIO}"
mkdir -p "${RAW_DIR}"

boot_qemu "${AC_SCENARIO_DIR}/fixture.py"

if ! wait_for_hmi 30; then
    report_fail "HMI not ready"
    cleanup_qemu
    rm -rf "${RAW_DIR}"
    exit 1
fi
sleep 1

FRAME=0

# Enter Auto-Copy (GOTO:0) — scan starts automatically
send_key "GOTO:0"

# With PM3_DELAY=5.0, the first scan command (hf 14a info) takes 5s.
# We capture during this scan phase, BEFORE the read starts.
sleep 2

# Capture baseline during scan phase
FRAME=$((FRAME+1))
capture_frame_with_state "${RAW_DIR}" "${FRAME}"
sleep 0.5

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

dedup_screenshots "${RAW_DIR}" "${SCREENSHOTS_DIR}"

# Verdict: PASS if RIGHT did not change the screen during scan
if [ "${BASELINE_HASH}" = "${AFTER_HASH}" ]; then
    # Validate against expected.json
    if [ -f "${AUTOCOPY_SCENARIO_DIR}/expected.json" ] && [ -f "${SCENARIO_DIR}/scenario_states.json" ]; then
        _val_out=$(python3 "${PROJECT}/tests/includes/validate_common.py" "${SCENARIO_DIR}/scenario_states.json" "${AUTOCOPY_SCENARIO_DIR}/expected.json" 2>&1)
        _val_rc=$?
        echo "${_val_out}"
        if [ "${_val_rc}" -ne 0 ]; then
            report_fail "validation: ${_val_out}"
            cleanup_qemu; rm -rf "${raw_dir}"; exit 1
        fi
    fi

    report_pass "RIGHT had no effect during AC scan phase (${DEDUP_COUNT} states)"
else
    report_fail "Screen changed after RIGHT during AC scan (hash mismatch, ${DEDUP_COUNT} states)"
fi

cleanup_qemu
rm -rf "${RAW_DIR}"
