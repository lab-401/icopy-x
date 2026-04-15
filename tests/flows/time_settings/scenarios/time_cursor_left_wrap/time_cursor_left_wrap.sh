#!/bin/bash
# Time Settings: LEFT from year (first field) wraps to second (last field)
# Gates: enter EDIT (cursor on year), press LEFT, verify still in EDIT mode
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="time_cursor_left_wrap"
FLOW="time_settings"
source "${PROJECT}/tests/flows/time_settings/includes/time_settings_common.sh"

raw_dir="/tmp/raw_ts_${SCENARIO}"
fixture_path="${TS_SCENARIO_DIR}/fixture.py"

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

# Navigate to Time Settings
if ! navigate_to_time_settings "${raw_dir}" frame_idx; then
    report_fail "Failed to navigate to Time Settings"
    cleanup_qemu
    rm -rf "${raw_dir}"
    exit 1
fi

# Enter EDIT mode (cursor defaults to year = first field)
if ! enter_edit_mode "${raw_dir}" frame_idx; then
    report_fail "Failed to enter EDIT mode"
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
    cleanup_qemu
    rm -rf "${raw_dir}"
    exit 1
fi

# Press LEFT — should wrap from year to second
send_key "LEFT"
sleep 1
frame_idx=$((frame_idx + 1))
capture_frame_with_state "${raw_dir}" "${frame_idx}"
sleep 0.5

# Verify still in EDIT mode (M1=Cancel)
if ! wait_for_ui_trigger "M1:Cancel" 5 "${raw_dir}" frame_idx; then
    report_fail "Not in EDIT mode after LEFT wrap"
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
    cleanup_qemu
    rm -rf "${raw_dir}"
    exit 1
fi

dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"

if [ "${DEDUP_COUNT}" -lt 2 ]; then
    report_fail "Need at least 2 unique states (got ${DEDUP_COUNT})"
    cleanup_qemu
    rm -rf "${raw_dir}"
    exit 1
fi

# Validate against expected.json
if [ -f "${TS_SCENARIO_DIR}/expected.json" ] && [ -f "${SCENARIO_DIR}/scenario_states.json" ]; then
    _val_out=$(python3 "${PROJECT}/tests/includes/validate_common.py" "${SCENARIO_DIR}/scenario_states.json" "${TS_SCENARIO_DIR}/expected.json" 2>&1)
    _val_rc=$?
    echo "${_val_out}"
    if [ "${_val_rc}" -ne 0 ]; then
        report_fail "validation: ${_val_out}"
        cleanup_qemu; rm -rf "${raw_dir}"; exit 1
    fi
fi

report_pass "LEFT from year wraps to second, still in EDIT (${DEDUP_COUNT} states)"
cleanup_qemu
rm -rf "${raw_dir}"
