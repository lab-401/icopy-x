#!/bin/bash
# PC Mode — all keys ignored during STARTING (PWR, M1, M2 have no effect)
# Ground truth: QEMU captures 20260405 — buttons remain disabled during STARTING
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="pcmode_keys_ignored_starting"
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

# Start via M1 to enter STARTING state
send_key "M1"
sleep 3

# Verify we are in STARTING state (M1_active=false)
if ! wait_for_ui_trigger "M1_active:false" 10 "${raw_dir}" frame_idx; then
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
    report_fail "Did not reach STARTING state (M1 still active)"
    cleanup_qemu; rm -rf "${raw_dir}"; exit 1
fi

# Now send PWR, M1, M2 — all should be ignored
send_key "PWR"
sleep 2
frame_idx=$((frame_idx + 1))
capture_frame_with_state "${raw_dir}" "${frame_idx}"

send_key "M1"
sleep 2
frame_idx=$((frame_idx + 1))
capture_frame_with_state "${raw_dir}" "${frame_idx}"

send_key "M2"
sleep 2
frame_idx=$((frame_idx + 1))
capture_frame_with_state "${raw_dir}" "${frame_idx}"

# Capture final frames
for i in $(seq 1 3); do
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"
    sleep 0.5
done

# Verify buttons are STILL disabled after all key presses
if ! wait_for_ui_trigger "M1_active:false" 5 "${raw_dir}" frame_idx; then
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
    report_fail "M1 became active after key presses (keys were NOT ignored)"
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

report_pass "Keys ignored during STARTING: PWR+M1+M2 had no effect, M1_active still false (${DEDUP_COUNT} states)"
cleanup_qemu
rm -rf "${raw_dir}"
