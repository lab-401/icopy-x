#!/bin/bash
# Time Settings: DISPLAY mode — verify title, Edit/Edit buttons, date/time content
# Gates: title="Time Settings", M1=Edit, M2=Edit, content has year/month/day values
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="time_display"
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

# Navigate to Time Settings (GOTO:12)
if ! navigate_to_time_settings "${raw_dir}" frame_idx; then
    report_fail "Failed to navigate to Time Settings"
    cleanup_qemu
    rm -rf "${raw_dir}"
    exit 1
fi

# Gate 1: title
if ! wait_for_ui_trigger "title:Time Settings" 5 "${raw_dir}" frame_idx; then
    report_fail "Title not 'Time Settings'"
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
    cleanup_qemu
    rm -rf "${raw_dir}"
    exit 1
fi

# Gate 2: M1=Edit
if ! wait_for_ui_trigger "M1:Edit" 5 "${raw_dir}" frame_idx; then
    report_fail "M1 not 'Edit'"
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
    cleanup_qemu
    rm -rf "${raw_dir}"
    exit 1
fi

# Gate 3: M2=Edit
if ! wait_for_ui_trigger "M2:Edit" 5 "${raw_dir}" frame_idx; then
    report_fail "M2 not 'Edit'"
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
    cleanup_qemu
    rm -rf "${raw_dir}"
    exit 1
fi

# Gate 4: content has date/time values (at least 11 items: year - month - day hour : min : sec ^)
# Check for separator "-" in content (always present between date fields)
frame_idx=$((frame_idx + 1))
capture_frame_with_state "${raw_dir}" "${frame_idx}"
sleep 0.5

local_dump="${STATE_DUMP_TMP}/state_$(printf '%03d' ${frame_idx}).json"
content_ok=0
if [ -f "${local_dump}" ]; then
    if python3 -c "
import json, sys
with open('${local_dump}') as f: d = json.load(f)
items = d.get('content_text', [])
# Must have at least 11 items (year - month - day hour : minute : second ^)
if len(items) < 11:
    sys.exit(1)
# Check separators exist
texts = [item.get('text', '') for item in items]
if '-' not in texts:
    sys.exit(1)
if ':' not in texts:
    sys.exit(1)
# Check year looks like a 4-digit number
try:
    year = int(texts[0])
    if year < 2000 or year > 2099: sys.exit(1)
except: sys.exit(1)
sys.exit(0)
" 2>/dev/null; then
        content_ok=1
    fi
fi

if [ "${content_ok}" -ne 1 ]; then
    report_fail "Content does not have expected date/time format"
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
    cleanup_qemu
    rm -rf "${raw_dir}"
    exit 1
fi

dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"

if [ "${DEDUP_COUNT}" -lt 1 ]; then
    report_fail "No unique states captured (got ${DEDUP_COUNT})"
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

report_pass "DISPLAY mode: title=Time Settings, M1=Edit, M2=Edit, content valid (${DEDUP_COUNT} states)"
cleanup_qemu
rm -rf "${raw_dir}"
