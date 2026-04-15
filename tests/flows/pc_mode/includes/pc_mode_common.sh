#!/bin/bash
# PC Mode flow shared infrastructure.
#
# The PC Mode flow (verified by QEMU STATE_DUMP captures 20260405):
#   GOTO:6 → PCModeActivity
#     → IDLE: title "PC-Mode", M1=Start, M2=Start, content "connect to computer"
#     → M1/M2 starts → STARTING: toast "Processing...", M1=Stop, M2=Button, active=False
#     → OK does NOT start from IDLE (verified: 5 frames after OK, still IDLE)
#     → STARTING hangs under QEMU (gadget_linux.so fails on modprobe)
#     → PWR from IDLE: finish()
#
# Key finding: buttons change to Stop/Button IMMEDIATELY on STARTING (before thread completes)
# but are disabled (active=False)

FLOW="pc_mode"
source "${PROJECT}/tests/includes/common.sh"

SCENARIO_DIR="${RESULTS_DIR}/${FLOW}/scenarios/${SCENARIO}"
SCREENSHOTS_DIR="${SCENARIO_DIR}/screenshots"
LOG_FILE="${SCENARIO_DIR}/logs/scenario_log.txt"
PC_SCENARIO_DIR="${PROJECT}/tests/flows/pc_mode/scenarios/${SCENARIO}"

PM3_DELAY="${PM3_DELAY:-0.5}"
BOOT_TIMEOUT="${BOOT_TIMEOUT:-120}"

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

# === Validate scenario states against expected.json ===
# Call after dedup_screenshots, before final report_pass.
# Args:
#   $1 = scenario_dir (flow scenario dir with expected.json)
#   $2 = results_scenario_dir (SCENARIO_DIR with scenario_states.json)
# Returns: 0 if valid/no expected.json, 1 if validation failed (already reported)
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
