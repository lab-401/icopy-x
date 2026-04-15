#!/bin/bash
# About — M1 from page 2 is a no-op (buttons hidden, no navigation)
# Ground truth: QEMU parallel run — M1 from page 2 stays on 2/2
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="about_page_nav_m1"
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

# Navigate to About
send_key "GOTO:10"
sleep 3
frame_idx=$((frame_idx + 1))
capture_frame_with_state "${raw_dir}" "${frame_idx}"

# Gate 1: Wait for page 1
if ! wait_for_ui_trigger "content:1/2" 15 "${raw_dir}" frame_idx; then
    report_fail "Could not reach page 1"
    cleanup_qemu; rm -rf "${raw_dir}"; exit 1
fi

# Gate 2: Navigate to page 2
send_key "DOWN"
sleep 2
if ! wait_for_ui_trigger "content:2/2" 15 "${raw_dir}" frame_idx; then
    report_fail "DOWN did not reach page 2"
    cleanup_qemu; rm -rf "${raw_dir}"; exit 1
fi

# Press M1 from page 2 — should be a no-op
send_key "M1"
sleep 3

# Capture several frames to verify page stays at 2/2
for i in $(seq 1 4); do
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"
    sleep 0.5
done

# Check that the LAST frame still shows 2/2
still_page2=0
last_dump="${STATE_DUMP_TMP}/state_$(printf '%03d' ${frame_idx}).json"
if [ -f "$last_dump" ]; then
    if python3 -c "
import json, sys
with open('${last_dump}') as f: d = json.load(f)
for item in d.get('content_text', []):
    if '2/2' in item.get('text', ''): sys.exit(0)
sys.exit(1)
" 2>/dev/null; then
        still_page2=1
    fi
fi

dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"

if [ "$still_page2" -eq 1 ]; then
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

    report_pass "M1 from page 2 is a no-op — stays on 2/2 (${DEDUP_COUNT} states)"
else
    report_fail "M1 from page 2 navigated away (expected to stay on 2/2)"
fi

cleanup_qemu
rm -rf "${raw_dir}"
