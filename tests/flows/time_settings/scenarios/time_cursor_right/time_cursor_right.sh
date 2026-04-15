#!/bin/bash
# Time Settings: RIGHT moves cursor through all 6 editable fields
# Gates: enter EDIT, press RIGHT 5 times, verify still in EDIT mode (M1=Cancel)
# Cursor fields: year(0) -> month(2) -> day(4) -> hour(5) -> minute(7) -> second(9)
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="time_cursor_right"
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

# Enter EDIT mode
if ! enter_edit_mode "${raw_dir}" frame_idx; then
    report_fail "Failed to enter EDIT mode"
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
    cleanup_qemu
    rm -rf "${raw_dir}"
    exit 1
fi

# Press RIGHT 5 times (year -> month -> day -> hour -> minute -> second)
for i in $(seq 1 5); do
    send_key "RIGHT"
    sleep 0.8
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"
    sleep 0.3
done

# Verify still in EDIT mode after all RIGHT presses
if ! wait_for_ui_trigger "M1:Cancel" 5 "${raw_dir}" frame_idx; then
    report_fail "Not in EDIT mode after 5 RIGHT presses"
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

report_pass "RIGHT cursor traversal through 6 fields, still in EDIT (${DEDUP_COUNT} states)"
cleanup_qemu
rm -rf "${raw_dir}"
