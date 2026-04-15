#!/bin/bash
# Scenario: T5577 Sniff — password 20206666 extracted from write commands (auto-finish)
# Flow: GOTO:4 → DOWN×4 → OK → M1 start → auto-stop via 125k_sniff_finished → result → save
# Ground truth: sniff_strings.txt regex "Default pwd write\s+\|\s+([A-Fa-f0-9]{8})\s\|"
# NOTE: Fixture has 125k_sniff_finished marker — do NOT press M2 Finish.
#       The .so auto-stops when it detects the marker.
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="sniff_t5577_password_found"
FLOW="sniff"
source "${PROJECT}/tests/includes/common.sh"
source "${PROJECT}/tests/flows/sniff/includes/sniff_common.sh"

SCENARIO_DIR="${RESULTS_DIR}/${FLOW}/scenarios/${SCENARIO}"
SCREENSHOTS_DIR="${SCENARIO_DIR}/screenshots"
LOG_FILE="${SCENARIO_DIR}/logs/scenario_log.txt"
SNIFF_SCENARIO_DIR="${PROJECT}/tests/flows/sniff/scenarios/${SCENARIO}"

fixture_path="${SNIFF_SCENARIO_DIR}/fixture.py"
raw_dir="/tmp/raw_sniff_${SCENARIO}"
PM3_DELAY=0.5

check_env
clean_scenario
mkdir -p "${raw_dir}"
boot_qemu "${fixture_path}"

if ! wait_for_hmi 30; then
    report_fail "HMI not ready"
    cleanup_qemu; rm -rf "${raw_dir}"; exit 1
fi
sleep 1

frame_idx=0

# Navigate to Sniff TRF → T5577
send_key "GOTO:4"
sleep 2
frame_idx=$((frame_idx + 1))
capture_frame_with_state "${raw_dir}" "${frame_idx}"

for i in $(seq 1 4); do send_key "DOWN"; sleep 0.5; done
sleep 0.5
frame_idx=$((frame_idx + 1))
capture_frame_with_state "${raw_dir}" "${frame_idx}"

# Select T5577
send_key "OK"
sleep 2
frame_idx=$((frame_idx + 1))
capture_frame_with_state "${raw_dir}" "${frame_idx}"

# Gate: INSTRUCTION
if ! wait_for_ui_trigger "M1:Start" 10 "${raw_dir}" frame_idx; then
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
    report_fail "Instruction not reached (${DEDUP_COUNT} states)"
    cleanup_qemu; rm -rf "${raw_dir}"; exit 1
fi

# Start sniffing — do NOT press M2. Auto-stop via 125k_sniff_finished.
send_key "M1"

# Wait for auto-stop: M2 changes to "Save"
if ! wait_for_ui_trigger "M2:Save" 30 "${raw_dir}" frame_idx; then
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
    report_fail "Auto-stop not reached (M2:Save) (${DEDUP_COUNT} states)"
    cleanup_qemu; rm -rf "${raw_dir}"; exit 1
fi

# Gate: TraceLen in result
if ! wait_for_ui_trigger "content:TraceLen" 10 "${raw_dir}" frame_idx; then
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
    report_fail "TraceLen not in result (${DEDUP_COUNT} states)"
    cleanup_qemu; rm -rf "${raw_dir}"; exit 1
fi

# Capture result
for i in $(seq 1 3); do
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"
    sleep 0.5
done

# Save trace
send_key "M2"
if ! wait_for_ui_trigger "toast:Trace file" 15 "${raw_dir}" frame_idx; then
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
    report_fail "Save toast not reached (${DEDUP_COUNT} states)"
    cleanup_qemu; rm -rf "${raw_dir}"; exit 1
fi

for i in $(seq 1 3); do
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"
    sleep 0.3
done

send_key "TOAST_CANCEL"
sleep 1
frame_idx=$((frame_idx + 1))
capture_frame_with_state "${raw_dir}" "${frame_idx}"

dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
if [ "${DEDUP_COUNT}" -lt 5 ]; then
    report_fail "${DEDUP_COUNT} unique states (expected >= 5)"
    cleanup_qemu; rm -rf "${raw_dir}"; exit 1
fi

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
report_pass "${DEDUP_COUNT} unique states, validated"
cleanup_qemu; rm -rf "${raw_dir}"
