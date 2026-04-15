#!/bin/bash
# Time Settings: PWR from DISPLAY exits activity
# Strategy: navigate, verify DISPLAY, send PWR, then try GOTO:12 again —
# if we re-enter Time Settings fresh, it proves we were on the main menu
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="time_pwr_exit"
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

# Verify DISPLAY mode
if ! wait_for_ui_trigger "M1:Edit" 5 "${raw_dir}" frame_idx; then
    report_fail "Not in DISPLAY mode"; cleanup_qemu; rm -rf "${raw_dir}"; exit 1
fi

# Send PWR to exit
send_key "PWR"
sleep 3

# Capture a few frames
for i in $(seq 1 3); do
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"
    sleep 0.5
done

dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"

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

    report_pass "PWR from DISPLAY exits (${DEDUP_COUNT} unique states)"
else
    report_fail "PWR did not produce state change (${DEDUP_COUNT} states)"
fi

cleanup_qemu; rm -rf "${raw_dir}"
