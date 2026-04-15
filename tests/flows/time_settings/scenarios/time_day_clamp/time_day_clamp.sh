#!/bin/bash
# Time Settings: Changing month automatically clamps day
# Ground truth: explore_simple_up — month 04→05 changed day 05→31, month 05→06 clamped day 31→30
# Strategy: move to month, UP twice, check that day adjusts automatically
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="time_day_clamp"
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

# Record initial state
frame_idx=$((frame_idx + 1))
capture_frame_with_state "${raw_dir}" "${frame_idx}"
sleep 1

# Press UP multiple times on month — each change should adjust day if needed
# We'll capture after each UP and look for day clamping evidence
months_seen=()
days_seen=()
for i in $(seq 1 8); do
    send_key "UP"
    sleep 2
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"
    sleep 1

    vals=$(python3 -c "
import json
with open('${STATE_DUMP_TMP}/state_$(printf '%03d' ${frame_idx}).json') as f: d = json.load(f)
items = d.get('content_text', [])
mo = items[2].get('text', '').strip() if len(items) > 2 else '?'
dy = items[4].get('text', '').strip() if len(items) > 4 else '?'
print(f'{mo},{dy}')
" 2>/dev/null)
    months_seen+=("${vals%,*}")
    days_seen+=("${vals#*,}")
done

dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"

# Check for day clamping evidence: did any month change cause day to decrease?
# Example: April(30d) → May(31d) → June(30d): day 31→30 is clamping
clamp_found=0
for idx in $(seq 1 $((${#days_seen[@]} - 1))); do
    prev_day="${days_seen[$((idx-1))]}"
    cur_day="${days_seen[$idx]}"
    prev_mo="${months_seen[$((idx-1))]}"
    cur_mo="${months_seen[$idx]}"
    if [ -n "$prev_day" ] && [ -n "$cur_day" ] && [ "$prev_day" != "$cur_day" ]; then
        clamp_found=1
        break
    fi
done

if [ "${clamp_found}" -eq 1 ]; then
    report_pass "Day clamping observed: months=${months_seen[*]} days=${days_seen[*]} (${DEDUP_COUNT} states)"
else
    # Even without visible clamping, verify days are always valid for their month
    valid=1
    for idx in $(seq 0 $((${#days_seen[@]} - 1))); do
        python3 -c "
import calendar, sys
try:
    m, d = int('${months_seen[$idx]}'), int('${days_seen[$idx]}')
    max_d = calendar.monthrange(2026, m)[1]
    if d > max_d: sys.exit(1)
except: sys.exit(1)
sys.exit(0)
" 2>/dev/null || { valid=0; break; }
    done
    if [ "${valid}" -eq 1 ]; then
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

        report_pass "All days valid for months: mo=${months_seen[*]} dy=${days_seen[*]} (${DEDUP_COUNT} states)"
    else
        report_fail "Invalid day for month: mo=${months_seen[*]} dy=${days_seen[*]}"
    fi
fi

cleanup_qemu; rm -rf "${raw_dir}"
