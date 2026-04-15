#!/bin/bash
# Time Settings: M1 from EDIT cancels and returns to DISPLAY mode
# Gates: enter EDIT (M1=Cancel, M2=Save), press M1, verify M1=Edit + M2=Edit
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="time_cancel_edit"
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

# Press M1 (Cancel) to return to DISPLAY
send_key "M1"
sleep 1.5

# Verify returned to DISPLAY mode: M1=Edit
if ! wait_for_ui_trigger "M1:Edit" 10 "${raw_dir}" frame_idx; then
    report_fail "M1 not 'Edit' after Cancel — did not return to DISPLAY"
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
    cleanup_qemu
    rm -rf "${raw_dir}"
    exit 1
fi

# Verify M2=Edit
if ! wait_for_ui_trigger "M2:Edit" 5 "${raw_dir}" frame_idx; then
    report_fail "M2 not 'Edit' after Cancel"
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
    cleanup_qemu
    rm -rf "${raw_dir}"
    exit 1
fi

# Verify title still Time Settings
if ! wait_for_ui_trigger "title:Time Settings" 5 "${raw_dir}" frame_idx; then
    report_fail "Title not 'Time Settings' after Cancel"
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

report_pass "M1 Cancel returns to DISPLAY: M1=Edit, M2=Edit (${DEDUP_COUNT} states)"
cleanup_qemu
rm -rf "${raw_dir}"
