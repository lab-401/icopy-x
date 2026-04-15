#!/bin/bash
# Scenario: T5577 Sniff — PWR abort during active sniffing (custom flow)
# Flow: GOTO:4 → DOWN×4 → OK (select T5577) → M1 (Start) → [sniffing] → PWR (abort)
# Expected: returns to sniff type list or main menu
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="sniff_t5577_pwr_abort"
FLOW="sniff"
source "${PROJECT}/tests/includes/common.sh"

# Re-derive paths with FLOW="sniff"
SCENARIO_DIR="${RESULTS_DIR}/${FLOW}/scenarios/${SCENARIO}"
SCREENSHOTS_DIR="${SCENARIO_DIR}/screenshots"
LOG_FILE="${SCENARIO_DIR}/logs/scenario_log.txt"
SNIFF_SCENARIO_DIR="${PROJECT}/tests/flows/sniff/scenarios/${SCENARIO}"

# Re-source sniff_common for wait_for_ui_trigger
source "${PROJECT}/tests/flows/sniff/includes/sniff_common.sh"

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

# Capture type list
frame_idx=$((frame_idx + 1))
capture_frame_with_state "${raw_dir}" "${frame_idx}"

# Navigate to T5577 (4 DOWNs)
for i in $(seq 1 4); do
    send_key "DOWN"
    sleep 0.5
done
sleep 0.5

# Capture after navigation
frame_idx=$((frame_idx + 1))
capture_frame_with_state "${raw_dir}" "${frame_idx}"

# Select T5577
send_key "OK"
sleep 2

# Capture instruction screen
frame_idx=$((frame_idx + 1))
capture_frame_with_state "${raw_dir}" "${frame_idx}"

# Gate: INSTRUCTION
if ! wait_for_ui_trigger "M1:Start" 10 "${raw_dir}" frame_idx; then
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
    report_fail "Instruction not reached (${DEDUP_COUNT} states)"
    cleanup_qemu; rm -rf "${raw_dir}"; exit 1
fi
if ! wait_for_ui_trigger "M2_active:false" 5 "${raw_dir}" frame_idx; then
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
    report_fail "M2 not inactive in INSTRUCTION (${DEDUP_COUNT} states)"
    cleanup_qemu; rm -rf "${raw_dir}"; exit 1
fi

# Start sniffing (M1) — gate immediately, mock returns fast
send_key "M1"

# Gate: SNIFFING — poll immediately before toast vanishes
if ! wait_for_ui_trigger "toast:Sniffing in progress" 15 "${raw_dir}" frame_idx; then
    # Toast may have auto-dismissed under instant mock — check if we progressed
    if ! wait_for_ui_trigger "M2:Save" 5 "${raw_dir}" frame_idx; then
        dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
        report_fail "Sniffing toast not reached (${DEDUP_COUNT} states)"
        cleanup_qemu; rm -rf "${raw_dir}"; exit 1
    fi
fi

# Capture post-sniff state
sleep 1
frame_idx=$((frame_idx + 1))
capture_frame_with_state "${raw_dir}" "${frame_idx}"

# PWR abort during sniffing
# PWR key: hmi_driver expects _PWR_CAN_PRES!, not PWR_PRES!
send_key "_PWR_CAN"
sleep 2

# Capture state after abort
frame_idx=$((frame_idx + 1))
capture_frame_with_state "${raw_dir}" "${frame_idx}"
sleep 0.5

# Another capture to confirm stable state
frame_idx=$((frame_idx + 1))
capture_frame_with_state "${raw_dir}" "${frame_idx}"

# Gate: back to type list
if ! wait_for_ui_trigger "title:Sniff TRF" 10 "${raw_dir}" frame_idx; then
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
    report_fail "Type list not reached after PWR (${DEDUP_COUNT} states)"
    cleanup_qemu; rm -rf "${raw_dir}"; exit 1
fi

# Deduplicate
dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"

# Expect at least 2 unique states: sniffing + post-abort
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
