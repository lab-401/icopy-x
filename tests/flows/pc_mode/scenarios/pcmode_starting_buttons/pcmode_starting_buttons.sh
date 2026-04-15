#!/bin/bash
# PC Mode — STARTING state: labels stay Start/Start, both disabled (active=False)
# Real device: buttons keep their labels when disabled during STARTING
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="pcmode_starting_buttons"
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
sleep 3

# Capture STARTING state frames
for i in $(seq 1 4); do
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"
    sleep 0.5
done

# Verify M1 still says Start (labels unchanged during STARTING)
if ! wait_for_ui_trigger "M1:Start" 10 "${raw_dir}" frame_idx; then
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
    report_fail "M1 label changed during STARTING (expected Start)"
    cleanup_qemu; rm -rf "${raw_dir}"; exit 1
fi

# Verify M1_active=false (buttons disabled)
if ! wait_for_ui_trigger "M1_active:false" 5 "${raw_dir}" frame_idx; then
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
    report_fail "M1 still active in STARTING state (expected disabled)"
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

report_pass "STARTING buttons verified: M1=Start, M2=Start, M1_active=false (${DEDUP_COUNT} states)"
cleanup_qemu
rm -rf "${raw_dir}"
