#!/bin/bash
# Scenario: Enter Diagnosis, select User diagnosis, PWR exit without starting tests
# Flow: GOTO:7 → Diagnosis → OK (User diagnosis) → PWR → back to ITEMS_MAIN
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="diag_user_enter_exit"
FLOW="diagnosis"
source "${PROJECT}/tests/includes/common.sh"

# Re-derive paths with FLOW="diagnosis"
SCENARIO_DIR="${RESULTS_DIR}/${FLOW}/scenarios/${SCENARIO}"
SCREENSHOTS_DIR="${SCENARIO_DIR}/screenshots"
LOG_FILE="${SCENARIO_DIR}/logs/scenario_log.txt"
DIAG_SCENARIO_DIR="${PROJECT}/tests/flows/diagnosis/scenarios/${SCENARIO}"

fixture_path="${DIAG_SCENARIO_DIR}/fixture.py"
raw_dir="/tmp/raw_diag_${SCENARIO}"

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

# Navigate to Diagnosis (menu pos 7)
send_key "GOTO:7"
sleep 3

# Capture Diagnosis screen (ITEMS_MAIN: User/Factory)
for i in 1 2 3; do
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"
    sleep 0.5
done

# OK to select "User diagnosis" → transitions to ITEMS_TEST list
send_key "OK"
sleep 3

# Capture test list screen (should show M2:Start, tips text)
for i in 1 2 3; do
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"
    sleep 0.5
done

# Press PWR to go back (exit without starting tests)
send_key "PWR"
sleep 3

# Capture after PWR (should be back at ITEMS_MAIN)
for i in 1 2 3; do
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"
    sleep 0.5
done

# Deduplicate
dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"

# Expect at least 2 unique states: ITEMS_MAIN + ITEMS_TEST (after OK)
if [ "${DEDUP_COUNT}" -ge 2 ]; then
    # Validate against expected.json
    if [ -f "${DIAG_SCENARIO_DIR}/expected.json" ] && [ -f "${SCENARIO_DIR}/scenario_states.json" ]; then
        _val_out=$(python3 "${PROJECT}/tests/includes/validate_common.py" "${SCENARIO_DIR}/scenario_states.json" "${DIAG_SCENARIO_DIR}/expected.json" 2>&1)
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
