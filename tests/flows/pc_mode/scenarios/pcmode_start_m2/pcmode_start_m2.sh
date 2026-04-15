#!/bin/bash
# PC Mode — M2 also triggers start from IDLE, buttons become disabled
# Real device: M2 from IDLE → STARTING (labels stay Start/Start, disabled)
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="pcmode_start_m2"
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

# Wait for IDLE state with M2=Start
if ! wait_for_ui_trigger "M2:Start" 15 "${raw_dir}" frame_idx; then
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
    report_fail "IDLE state not reached (M2 not Start)"
    cleanup_qemu; rm -rf "${raw_dir}"; exit 1
fi

# Send M2 to start
send_key "M2"
sleep 3

# Capture post-start frames
for i in $(seq 1 4); do
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"
    sleep 0.5
done

# Verify buttons are disabled (STARTING state — labels stay Start)
if ! wait_for_ui_trigger "M1_active:false" 10 "${raw_dir}" frame_idx; then
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
    report_fail "Buttons not disabled after M2 start"
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

report_pass "M2 start verified: buttons disabled (${DEDUP_COUNT} states)"
cleanup_qemu
rm -rf "${raw_dir}"
