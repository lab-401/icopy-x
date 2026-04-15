#!/bin/bash
# About — verify "Processing..." toast appears on entry
# Ground truth: QEMU state dump shows toast:Processing... immediately after GOTO:10
# The toast is transient — must capture rapidly right after navigation
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="about_processing"
FLOW="about"
source "${PROJECT}/tests/includes/common.sh"

SCENARIO_DIR="${RESULTS_DIR}/${FLOW}/scenarios/${SCENARIO}"
SCREENSHOTS_DIR="${SCENARIO_DIR}/screenshots"
LOG_FILE="${SCENARIO_DIR}/logs/scenario_log.txt"
ABOUT_SCENARIO_DIR="${PROJECT}/tests/flows/about/scenarios/${SCENARIO}"

source "${PROJECT}/tests/flows/about/includes/about_common.sh"

raw_dir="/tmp/raw_about_${SCENARIO}"
fixture_path="${ABOUT_SCENARIO_DIR}/fixture.py"

check_env
clean_scenario
mkdir -p "${raw_dir}"
boot_qemu "${fixture_path}"

if ! wait_for_hmi 40; then
    report_fail "HMI not ready"
    cleanup_qemu; rm -rf "${raw_dir}"; exit 1
fi
sleep 1

frame_idx=0

# Navigate to About and immediately start rapid capture
send_key "GOTO:10"

# Rapid capture during the first 6 seconds to catch transient Processing toast
for i in $(seq 1 12); do
    sleep 0.5
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"
done

# Check if any frame captured the Processing toast
found_processing=0
found_title=0
for dump_file in "${STATE_DUMP_TMP}"/state_*.json; do
    [ -f "$dump_file" ] || continue
    if python3 -c "
import json, sys
with open('${dump_file}') as f: d = json.load(f)
toast = d.get('toast') or ''
title = d.get('title') or ''
if 'Processing' in str(toast) and 'About' in title: sys.exit(0)
sys.exit(1)
" 2>/dev/null; then
        found_processing=1
        break
    fi
done

# Also verify we eventually see the version info (page 1 content)
if wait_for_ui_trigger "content:iCopy-XS" 15 "${raw_dir}" frame_idx; then
    found_title=1
fi

dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"

if [ "$found_processing" -eq 1 ] && [ "$found_title" -eq 1 ]; then
    report_pass "Processing toast captured + version info visible (${DEDUP_COUNT} states)"
elif [ "$found_processing" -eq 1 ]; then
    # Validate against expected.json
    if [ -f "${ABOUT_SCENARIO_DIR}/expected.json" ] && [ -f "${SCENARIO_DIR}/scenario_states.json" ]; then
        _val_out=$(python3 "${PROJECT}/tests/includes/validate_common.py" "${SCENARIO_DIR}/scenario_states.json" "${ABOUT_SCENARIO_DIR}/expected.json" 2>&1)
        _val_rc=$?
        echo "${_val_out}"
        if [ "${_val_rc}" -ne 0 ]; then
            report_fail "validation: ${_val_out}"
            cleanup_qemu; rm -rf "${raw_dir}"; exit 1
        fi
    fi

    report_pass "Processing toast captured (${DEDUP_COUNT} states)"
else
    report_fail "Processing toast not captured in any of ${frame_idx} frames (${DEDUP_COUNT} states)"
fi

cleanup_qemu
rm -rf "${raw_dir}"
