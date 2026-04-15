#!/bin/bash
# Time Settings: DOWN decrements the current field directly (no OK needed)
# Ground truth: UP works directly, DOWN should work symmetrically
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="time_decrement_field"
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

# Read year before DOWN
sleep 1
frame_idx=$((frame_idx + 1))
capture_frame_with_state "${raw_dir}" "${frame_idx}"
sleep 1

before=$(python3 -c "
import json
with open('${STATE_DUMP_TMP}/state_$(printf '%03d' ${frame_idx}).json') as f: d = json.load(f)
items = d.get('content_text', [])
print(items[0].get('text', '').strip() if items else '')
" 2>/dev/null)

# DOWN to decrement year
send_key "DOWN"
sleep 2
frame_idx=$((frame_idx + 1))
capture_frame_with_state "${raw_dir}" "${frame_idx}"
sleep 1

after=$(python3 -c "
import json
with open('${STATE_DUMP_TMP}/state_$(printf '%03d' ${frame_idx}).json') as f: d = json.load(f)
items = d.get('content_text', [])
print(items[0].get('text', '').strip() if items else '')
" 2>/dev/null)

dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"

if [ -n "${before}" ] && [ -n "${after}" ] && [ "${before}" != "${after}" ]; then
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

    report_pass "DOWN decrements year: ${before} -> ${after} (${DEDUP_COUNT} states)"
else
    report_fail "Year did not change after DOWN (before=${before}, after=${after})"
fi
cleanup_qemu; rm -rf "${raw_dir}"
