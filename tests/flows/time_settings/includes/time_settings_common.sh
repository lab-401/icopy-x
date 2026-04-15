#!/bin/bash
# Time Settings flow shared infrastructure.
# Expects: PROJECT, SCENARIO set before sourcing.
#
# The Time Settings flow (verified by QEMU STATE_DUMP captures 20260405):
#   GOTO:12 → TimeSyncActivity
#     → DISPLAY: title "Time Settings", M1=Edit, M2=Edit
#       Content: 11 items [year, -, month, -, day, hour, :, minute, :, second, ^]
#     → EDIT: M1=Cancel, M2=Save, time frozen, cursor on field
#     → SAVE: "Synchronization successful!" toast (3s), returns to DISPLAY
#     → CANCEL (M1/PWR from EDIT): re-reads system time, returns to DISPLAY
#
# Content indices (0-based):
#   0=year  1=-  2=month  3=-  4=day  5=hour  6=:  7=minute  8=:  9=second  10=^

FLOW="time_settings"
source "${PROJECT}/tests/includes/common.sh"

SCENARIO_DIR="${RESULTS_DIR}/${FLOW}/scenarios/${SCENARIO}"
SCREENSHOTS_DIR="${SCENARIO_DIR}/screenshots"
LOG_FILE="${SCENARIO_DIR}/logs/scenario_log.txt"
TS_SCENARIO_DIR="${PROJECT}/tests/flows/time_settings/scenarios/${SCENARIO}"

PM3_DELAY="${PM3_DELAY:-0.5}"
BOOT_TIMEOUT="${BOOT_TIMEOUT:-120}"
TS_TRIGGER_WAIT="${TS_TRIGGER_WAIT:-30}"

# === wait_for_ui_trigger ===
wait_for_ui_trigger() {
    local trigger="$1"
    local max_wait="${2:-60}"
    local raw_dir="$3"
    local -n _fidx=$4

    local field="${trigger%%:*}"
    local value="${trigger#*:}"

    for attempt in $(seq 1 $((max_wait * 2))); do
        sleep 0.5
        _fidx=$((_fidx + 1))
        capture_frame_with_state "${raw_dir}" "${_fidx}"
        sleep 0.2
        local dump_file="${STATE_DUMP_TMP}/state_$(printf '%03d' ${_fidx}).json"
        if [ -f "$dump_file" ]; then
            if python3 -c "
import json, sys
with open('${dump_file}') as f: d = json.load(f)
field, value = '${field}', '${value}'
if field in ('M1','M2','toast'):
    actual = d.get(field) or ''
    if value in str(actual): sys.exit(0)
elif field == 'title':
    actual = d.get('title') or ''
    if value in actual: sys.exit(0)
elif field == 'content':
    for item in d.get('content_text', []):
        if value in item.get('text', ''): sys.exit(0)
elif field in ('M1_active', 'M2_active', 'M1_visible', 'M2_visible'):
    expected = value.lower() == 'true'
    if d.get(field) == expected: sys.exit(0)
sys.exit(1)
" 2>/dev/null; then
                return 0
            fi
        fi
    done
    return 1
}

# === Navigate to Time Settings and wait for DISPLAY mode ===
# Sets frame_idx, raw_dir
navigate_to_time_settings() {
    local raw="$1"
    local -n _fi=$2

    send_key "GOTO:12"
    sleep 3
    _fi=$((_fi + 1))
    capture_frame_with_state "${raw}" "${_fi}"

    if ! wait_for_ui_trigger "title:Time Settings" 15 "${raw}" _fi; then
        return 1
    fi
    if ! wait_for_ui_trigger "M1:Edit" 5 "${raw}" _fi; then
        return 1
    fi
    return 0
}

# === Enter EDIT mode and verify ===
enter_edit_mode() {
    local raw="$1"
    local -n _fi=$2

    send_key "M1"
    sleep 1
    _fi=$((_fi + 1))
    capture_frame_with_state "${raw}" "${_fi}"

    if ! wait_for_ui_trigger "M1:Cancel" 10 "${raw}" _fi; then
        return 1
    fi
    if ! wait_for_ui_trigger "M2:Save" 5 "${raw}" _fi; then
        return 1
    fi
    return 0
}

# === Validate scenario states against expected.json ===
# Call after dedup_screenshots, before final report_pass.
# Args:
#   $1 = scenario_dir (flow scenario dir with expected.json)
#   $2 = results_scenario_dir (SCENARIO_DIR with scenario_states.json)
# Returns: 0 if valid/no expected.json, 1 if validation failed
validate_scenario_states() {
    local scenario_src_dir="$1"
    local scenario_results_dir="$2"
    local expected_path="${scenario_src_dir}/expected.json"
    local states_path="${scenario_results_dir}/scenario_states.json"
    local validator="${PROJECT}/tests/includes/validate_common.py"
    if [ -f "${expected_path}" ] && [ -f "${states_path}" ]; then
        local validate_output
        validate_output=$(python3 "${validator}" "${states_path}" "${expected_path}" 2>&1)
        local validate_rc=$?
        echo "${validate_output}"
        if [ "${validate_rc}" -ne 0 ]; then
            return 1
        fi
        return 0
    fi
    return 0
}
