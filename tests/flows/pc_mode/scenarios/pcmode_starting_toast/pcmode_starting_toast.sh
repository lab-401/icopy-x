#!/bin/bash
# PC Mode — STARTING state shows "Processing..." toast
# Ground truth: QEMU captures 20260405 — after start, toast="Processing..."
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="pcmode_starting_toast"
FLOW="pc_mode"
source "${PROJECT}/tests/flows/pc_mode/includes/pc_mode_common.sh"

raw_dir="/tmp/raw_pc_${SCENARIO}"
fixture_path="${PC_SCENARIO_DIR}/fixture.py"

check_env
clean_scenario
mkdir -p "${raw_dir}"
boot_qemu "${fixture_path}"

if ! wait_for_hmi 40; then
    report_fail "HMI not ready"
    cleanup_qemu
    rm -rf "${raw_dir}"
    exit 1
fi
sleep 1

frame_idx=0

# Navigate to PC Mode
send_key "GOTO:6"
sleep 3
frame_idx=$((frame_idx + 1))
capture_frame_with_state "${raw_dir}" "${frame_idx}"

# Wait for IDLE
if ! wait_for_ui_trigger "title:PC-Mode" 15 "${raw_dir}" frame_idx; then
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
    report_fail "Could not reach PC-Mode IDLE"
    cleanup_qemu; rm -rf "${raw_dir}"; exit 1
fi

# Start via M1
send_key "M1"
sleep 2

# Capture frames rapidly to catch toast
for i in $(seq 1 6); do
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"
    sleep 0.3
done

# Verify toast contains "Processing"
if ! wait_for_ui_trigger "toast:Processing" 10 "${raw_dir}" frame_idx; then
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
    report_fail "Toast 'Processing...' not found after start"
    cleanup_qemu; rm -rf "${raw_dir}"; exit 1
fi

dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
# Validate against expected.json
if [ -f "${PC_SCENARIO_DIR}/expected.json" ] && [ -f "${SCENARIO_DIR}/scenario_states.json" ]; then
    _val_out=$(python3 "${PROJECT}/tests/includes/validate_common.py" "${SCENARIO_DIR}/scenario_states.json" "${PC_SCENARIO_DIR}/expected.json" 2>&1)
    _val_rc=$?
    echo "${_val_out}"
    if [ "${_val_rc}" -ne 0 ]; then
        report_fail "validation: ${_val_out}"
        cleanup_qemu; rm -rf "${raw_dir}"; exit 1
    fi
fi

report_pass "STARTING toast verified: 'Processing...' shown (${DEDUP_COUNT} states)"
cleanup_qemu
rm -rf "${raw_dir}"
