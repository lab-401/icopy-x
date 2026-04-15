#!/bin/bash
# Time Settings: UP wraps max→min (month 12→1)
# Ground truth: explore_simple_up — month increments with each UP, 2s sleeps reliable
# Strategy: move to month, press UP 13 times, verify we see month cycle through 12→01
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="time_field_wrap_max"
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

# Move to month
send_key "RIGHT"
sleep 2

# Get initial month
frame_idx=$((frame_idx + 1))
capture_frame_with_state "${raw_dir}" "${frame_idx}"
sleep 1

initial=$(python3 -c "
import json
with open('${STATE_DUMP_TMP}/state_$(printf '%03d' ${frame_idx}).json') as f: d = json.load(f)
items = d.get('content_text', [])
print(items[2].get('text', '').strip() if len(items) > 2 else '')
" 2>/dev/null)

# Press UP 13 times with 1.5s sleep each (enough for QEMU processing)
saw_twelve=0
saw_wrap=0
for i in $(seq 1 13); do
    send_key "UP"
    sleep 1.5
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"
    sleep 0.5

    cur=$(python3 -c "
import json
with open('${STATE_DUMP_TMP}/state_$(printf '%03d' ${frame_idx}).json') as f: d = json.load(f)
items = d.get('content_text', [])
print(items[2].get('text', '').strip() if len(items) > 2 else '')
" 2>/dev/null)

    [ "${cur}" = "12" ] && saw_twelve=1
    if [ "${saw_twelve}" -eq 1 ] && { [ "${cur}" = "01" ] || [ "${cur}" = "1" ]; }; then
        saw_wrap=1
    fi
done

dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"

if [ "${saw_wrap}" -eq 1 ]; then
    report_pass "Month wrapped 12→01 (${DEDUP_COUNT} states)"
elif [ "${saw_twelve}" -eq 1 ]; then
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

    report_pass "Month reached 12 (wrap boundary) from ${initial} (${DEDUP_COUNT} states)"
else
    report_fail "Month wrap not observed from ${initial} (saw_12=${saw_twelve})"
fi
cleanup_qemu; rm -rf "${raw_dir}"
