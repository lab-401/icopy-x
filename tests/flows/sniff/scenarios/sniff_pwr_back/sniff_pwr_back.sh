#!/bin/bash
# Scenario: PWR back from Sniff TRF — custom flow (no sniff started)
# Flow: GOTO:4 → capture sniff list → PWR → capture main menu
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="sniff_pwr_back"
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
sleep 3

# Capture sniff type selection list (multiple frames for stability)
for i in 1 2 3; do
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"
    sleep 0.5
done

# Gate: verify SniffActivity entered
if ! wait_for_ui_trigger "title:Sniff TRF" 15 "${raw_dir}" frame_idx; then
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
    report_fail "SniffActivity not entered (${DEDUP_COUNT} states)"
    cleanup_qemu; rm -rf "${raw_dir}"; exit 1
fi

# Press PWR to go back to main menu
# PWR key: hmi_driver expects _PWR_CAN_PRES!, not PWR_PRES!
send_key "_PWR_CAN"
sleep 3

# Capture main menu (multiple frames to ensure transition is caught)
for i in 1 2 3; do
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"
    sleep 0.5
done

# Gate: verify returned to main menu
if ! wait_for_ui_trigger "title:Main Page" 10 "${raw_dir}" frame_idx; then
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
    report_fail "Main menu not reached after PWR (${DEDUP_COUNT} states)"
    cleanup_qemu; rm -rf "${raw_dir}"; exit 1
fi

# Deduplicate
dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"

# Expect at least 2 unique states: sniff list + main menu
if [ "${DEDUP_COUNT}" -ge 2 ]; then
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
    report_fail "${DEDUP_COUNT} unique states (expected >= 2)"
fi

cleanup_qemu
rm -rf "${raw_dir}"
