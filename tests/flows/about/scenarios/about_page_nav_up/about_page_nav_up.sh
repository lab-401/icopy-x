#!/bin/bash
# About — UP from page 2 navigates back to page 1
# Ground truth: QEMU about_up_no_nav run state 4 shows 1/2 after UP from page 2
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="about_page_nav_up"
FLOW="about"
source "${PROJECT}/tests/includes/common.sh"

SCENARIO_DIR="${RESULTS_DIR}/${FLOW}/scenarios/${SCENARIO}"
SCREENSHOTS_DIR="${SCENARIO_DIR}/screenshots"
LOG_FILE="${SCENARIO_DIR}/logs/scenario_log.txt"
ABOUT_SCENARIO_DIR="${PROJECT}/tests/flows/about/scenarios/${SCENARIO}"

source "${PROJECT}/tests/flows/about/includes/about_common.sh"

raw_dir="/tmp/raw_about_${SCENARIO}"
fixture_path="${ABOUT_SCENARIO_DIR}/fixture.py"

check_env
clean_scenario
mkdir -p "${raw_dir}"
boot_qemu "${fixture_path}"

if ! wait_for_hmi 40; then
    report_fail "HMI not ready"
    cleanup_qemu; rm -rf "${raw_dir}"; exit 1
fi
sleep 1

frame_idx=0

# Navigate to About
send_key "GOTO:10"
sleep 3
frame_idx=$((frame_idx + 1))
capture_frame_with_state "${raw_dir}" "${frame_idx}"

# Gate 1: Wait for page 1
if ! wait_for_ui_trigger "content:1/2" 15 "${raw_dir}" frame_idx; then
    report_fail "Could not reach page 1"
    cleanup_qemu; rm -rf "${raw_dir}"; exit 1
fi

# Gate 2: Navigate to page 2
send_key "DOWN"
sleep 2
if ! wait_for_ui_trigger "content:2/2" 15 "${raw_dir}" frame_idx; then
    report_fail "DOWN did not reach page 2"
    cleanup_qemu; rm -rf "${raw_dir}"; exit 1
fi

# Gate 3: UP from page 2 → should go to page 1
send_key "UP"
sleep 2
if ! wait_for_ui_trigger "content:1/2" 15 "${raw_dir}" frame_idx; then
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
    report_fail "UP did not return to page 1 (${DEDUP_COUNT} states)"
    cleanup_qemu; rm -rf "${raw_dir}"; exit 1
fi

# Capture final frames
for i in $(seq 1 3); do
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"
    sleep 0.5
done

dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
# Validate against expected.json
if [ -f "${ABOUT_SCENARIO_DIR}/expected.json" ] && [ -f "${SCENARIO_DIR}/scenario_states.json" ]; then
    _val_out=$(python3 "${PROJECT}/tests/includes/validate_common.py" "${SCENARIO_DIR}/scenario_states.json" "${ABOUT_SCENARIO_DIR}/expected.json" 2>&1)
    _val_rc=$?
    echo "${_val_out}"
    if [ "${_val_rc}" -ne 0 ]; then
        report_fail "validation: ${_val_out}"
        cleanup_qemu; rm -rf "${raw_dir}"; exit 1
    fi
fi

report_pass "UP from page 2 navigated to page 1 (${DEDUP_COUNT} states)"
cleanup_qemu
rm -rf "${raw_dir}"
