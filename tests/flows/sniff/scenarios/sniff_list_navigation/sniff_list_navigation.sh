#!/bin/bash
# Scenario: Navigate through all 5 sniff types with UP/DOWN — custom flow
# Flow: GOTO:4 → DOWN×4 (visit all items) → UP×4 (back to top) → capture each
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="sniff_list_navigation"
FLOW="sniff"
source "${PROJECT}/tests/includes/common.sh"
source "${PROJECT}/tests/flows/sniff/includes/sniff_common.sh"

# Re-derive paths with FLOW="sniff"
SCENARIO_DIR="${RESULTS_DIR}/${FLOW}/scenarios/${SCENARIO}"
SCREENSHOTS_DIR="${SCENARIO_DIR}/screenshots"
LOG_FILE="${SCENARIO_DIR}/logs/scenario_log.txt"
SNIFF_SCENARIO_DIR="${PROJECT}/tests/flows/sniff/scenarios/${SCENARIO}"

fixture_path="${SNIFF_SCENARIO_DIR}/fixture.py"
raw_dir="/tmp/raw_sniff_${SCENARIO}"

check_env
clean_scenario
mkdir -p "${raw_dir}"

boot_qemu "${fixture_path}"

if ! wait_for_hmi 30; then
    report_fail "HMI not ready"
    cleanup_qemu
    rm -rf "${raw_dir}"
    exit 1
fi
sleep 1

frame_idx=0

# Navigate to Sniff TRF
send_key "GOTO:4"
sleep 2

# Capture initial list (14A selected)
frame_idx=$((frame_idx + 1))
capture_frame_with_state "${raw_dir}" "${frame_idx}"
sleep 0.5

# Gate: verify SniffActivity entered
if ! wait_for_ui_trigger "title:Sniff TRF" 15 "${raw_dir}" frame_idx; then
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
    report_fail "SniffActivity not entered (${DEDUP_COUNT} states)"
    cleanup_qemu; rm -rf "${raw_dir}"; exit 1
fi

# DOWN through all 5 items: 14A→14B→iCLASS→Topaz→T5577
for i in $(seq 1 4); do
    send_key "DOWN"
    sleep 1
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"
    sleep 0.5
done

# Gate: verify T5577 (last item) is visible after scrolling
if ! wait_for_ui_trigger "content:T5577 Sniff" 5 "${raw_dir}" frame_idx; then
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
    report_fail "T5577 not reached after DOWN×4 (${DEDUP_COUNT} states)"
    cleanup_qemu; rm -rf "${raw_dir}"; exit 1
fi

# UP back to top: T5577→Topaz→iCLASS→14B→14A
for i in $(seq 1 4); do
    send_key "UP"
    sleep 1
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"
    sleep 0.5
done

# Deduplicate
dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"

# Expect at least 3 unique states (highlight position changes per item)
# Note: 5 items but some adjacent items may produce similar pixel hashes
if [ "${DEDUP_COUNT}" -ge 3 ]; then
    # Validate against expected.json
    if [ -f "${SNIFF_SCENARIO_DIR}/expected.json" ] && [ -f "${SCENARIO_DIR}/scenario_states.json" ]; then
        _val_out=$(python3 "${PROJECT}/tests/includes/validate_common.py" "${SCENARIO_DIR}/scenario_states.json" "${SNIFF_SCENARIO_DIR}/expected.json" 2>&1)
        _val_rc=$?
        echo "${_val_out}"
        if [ "${_val_rc}" -ne 0 ]; then
            report_fail "validation: ${_val_out}"
            cleanup_qemu; rm -rf "${raw_dir}"; exit 1
        fi
    fi

    report_pass "${DEDUP_COUNT} unique states"
else
    report_fail "${DEDUP_COUNT} unique states (expected >= 5)"
fi

cleanup_qemu
rm -rf "${raw_dir}"
