#!/bin/bash
# PC Mode — verify IDLE state displays title "PC-Mode", M1=Start, M2=Start, content "connect"
# Ground truth: QEMU captures 20260405 — GOTO:6 reaches IDLE with expected labels
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="pcmode_idle"
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

# Verify title is PC-Mode
if ! wait_for_ui_trigger "title:PC-Mode" 15 "${raw_dir}" frame_idx; then
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
    report_fail "Title not PC-Mode"
    cleanup_qemu; rm -rf "${raw_dir}"; exit 1
fi

# Verify M1=Start
if ! wait_for_ui_trigger "M1:Start" 5 "${raw_dir}" frame_idx; then
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
    report_fail "M1 not Start"
    cleanup_qemu; rm -rf "${raw_dir}"; exit 1
fi

# Verify M2=Start
if ! wait_for_ui_trigger "M2:Start" 5 "${raw_dir}" frame_idx; then
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
    report_fail "M2 not Start"
    cleanup_qemu; rm -rf "${raw_dir}"; exit 1
fi

# Verify content contains "connect"
if ! wait_for_ui_trigger "content:connect" 5 "${raw_dir}" frame_idx; then
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
    report_fail "Content missing 'connect' text"
    cleanup_qemu; rm -rf "${raw_dir}"; exit 1
fi

# Capture a few final frames
for i in $(seq 1 3); do
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"
    sleep 0.5
done

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

report_pass "IDLE state verified: title=PC-Mode, M1=Start, M2=Start, content has 'connect' (${DEDUP_COUNT} states)"
cleanup_qemu
rm -rf "${raw_dir}"
