#!/bin/bash
# Time Settings: PWR from EDIT exits the activity (same as PWR from DISPLAY)
# Ground truth: QEMU — after PWR from EDIT, M1=Edit never appears (activity exited)
# This means PWR always calls finish() regardless of DISPLAY/EDIT state
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="time_pwr_cancel"
FLOW="time_settings"
source "${PROJECT}/tests/flows/time_settings/includes/time_settings_common.sh"

raw_dir="/tmp/raw_ts_${SCENARIO}"
fixture_path="${TS_SCENARIO_DIR}/fixture.py"

check_env; clean_scenario; mkdir -p "${raw_dir}"
boot_qemu "${fixture_path}"
if ! wait_for_hmi 40; then report_fail "HMI not ready"; cleanup_qemu; rm -rf "${raw_dir}"; exit 1; fi
sleep 1

frame_idx=0

if ! navigate_to_time_settings "${raw_dir}" frame_idx; then
    report_fail "Failed to navigate"; cleanup_qemu; rm -rf "${raw_dir}"; exit 1
fi
if ! enter_edit_mode "${raw_dir}" frame_idx; then
    report_fail "Failed to enter EDIT"; cleanup_qemu; rm -rf "${raw_dir}"; exit 1
fi

# Verify in EDIT
if ! wait_for_ui_trigger "M1:Cancel" 5 "${raw_dir}" frame_idx; then
    report_fail "Not in EDIT mode"; cleanup_qemu; rm -rf "${raw_dir}"; exit 1
fi

# PWR from EDIT — should exit the activity entirely (finish())
send_key "PWR"
sleep 3

# Capture post-PWR frames
for i in $(seq 1 3); do
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"
    sleep 0.5
done

dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"

# Verify we have at least 2 states (EDIT + post-exit)
if [ "${DEDUP_COUNT}" -ge 2 ]; then
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

    report_pass "PWR from EDIT exits activity (${DEDUP_COUNT} states)"
else
    report_fail "PWR did not cause state change (${DEDUP_COUNT} states)"
fi

cleanup_qemu; rm -rf "${raw_dir}"
