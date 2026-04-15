#!/bin/bash
# Time Settings: M1 enters EDIT mode — buttons become Cancel/Save
# Gates: navigate to DISPLAY, press M1, verify M1=Cancel + M2=Save
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="time_enter_edit"
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

# Enter EDIT mode (M1)
if ! enter_edit_mode "${raw_dir}" frame_idx; then
    report_fail "Failed to enter EDIT mode"
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
    cleanup_qemu
    rm -rf "${raw_dir}"
    exit 1
fi

# Verify M1=Cancel
if ! wait_for_ui_trigger "M1:Cancel" 5 "${raw_dir}" frame_idx; then
    report_fail "M1 not 'Cancel' in EDIT mode"
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
    cleanup_qemu
    rm -rf "${raw_dir}"
    exit 1
fi

# Verify M2=Save
if ! wait_for_ui_trigger "M2:Save" 5 "${raw_dir}" frame_idx; then
    report_fail "M2 not 'Save' in EDIT mode"
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

report_pass "M1 enters EDIT mode: M1=Cancel, M2=Save (${DEDUP_COUNT} states)"
cleanup_qemu
rm -rf "${raw_dir}"
