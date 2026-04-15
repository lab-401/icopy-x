#!/bin/bash
# Scenario: T5577 Sniff — auto-finish via 125k_sniff_finished marker (custom flow)
# Flow: GOTO:4 → DOWN×4 → OK (select T5577) → M1 (Start) →
#       [auto-stop: 125k_sniff_finished detected by onData()] →
#       Result (M2=Save) → M2 (Save) → toast "Trace file saved"
# Note: NO manual M2=Finish press! The .so auto-stops when it detects the marker.
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="sniff_t5577_auto_finish"
FLOW="sniff"
source "${PROJECT}/tests/includes/common.sh"

# Re-derive paths with FLOW="sniff"
SCENARIO_DIR="${RESULTS_DIR}/${FLOW}/scenarios/${SCENARIO}"
SCREENSHOTS_DIR="${SCENARIO_DIR}/screenshots"
LOG_FILE="${SCENARIO_DIR}/logs/scenario_log.txt"
SNIFF_SCENARIO_DIR="${PROJECT}/tests/flows/sniff/scenarios/${SCENARIO}"

# Source sniff_common for wait_for_ui_trigger
source "${PROJECT}/tests/flows/sniff/includes/sniff_common.sh"

fixture_path="${SNIFF_SCENARIO_DIR}/fixture.py"
raw_dir="/tmp/raw_sniff_${SCENARIO}"

PM3_DELAY=0.5

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

# Gate: INSTRUCTION — M1 active, M2 inactive, T5577 content
if ! wait_for_ui_trigger "M1:Start" 10 "${raw_dir}" frame_idx; then
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
    report_fail "Instruction not reached (${DEDUP_COUNT} states)"
    cleanup_qemu; rm -rf "${raw_dir}"; exit 1
fi
if ! wait_for_ui_trigger "content:Click start" 5 "${raw_dir}" frame_idx; then
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
    report_fail "T5577 instruction text not found (${DEDUP_COUNT} states)"
    cleanup_qemu; rm -rf "${raw_dir}"; exit 1
fi
if ! wait_for_ui_trigger "M2_active:false" 5 "${raw_dir}" frame_idx; then
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
    report_fail "M2 not inactive in INSTRUCTION (${DEDUP_COUNT} states)"
    cleanup_qemu; rm -rf "${raw_dir}"; exit 1
fi

# Start sniffing (M1) — do NOT press M2 to finish!
# The 125k_sniff_finished marker in the fixture should auto-stop.
send_key "M1"

# Wait for auto-stop: M2 should change to "Save" without pressing M2=Finish
if ! wait_for_ui_trigger "M2:Save" 30 "${raw_dir}" frame_idx; then
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"
    sleep 0.5
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
    report_fail "auto-stop trigger 'M2:Save' not reached (${DEDUP_COUNT} states)"
    cleanup_qemu
    rm -rf "${raw_dir}"
    exit 1
fi

# Result is displayed! Capture it.
for i in $(seq 1 3); do
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"
    sleep 0.5
done

# Gate: TraceLen in result, M1 active
if ! wait_for_ui_trigger "content:TraceLen" 10 "${raw_dir}" frame_idx; then
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
    report_fail "TraceLen not in auto-stop result (${DEDUP_COUNT} states)"
    cleanup_qemu; rm -rf "${raw_dir}"; exit 1
fi
if ! wait_for_ui_trigger "M1_active:true" 5 "${raw_dir}" frame_idx; then
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
    report_fail "M1 not active in RESULT (${DEDUP_COUNT} states)"
    cleanup_qemu; rm -rf "${raw_dir}"; exit 1
fi

# Save trace
send_key "M2"

# Wait for save toast
if ! wait_for_ui_trigger "toast:Trace file" 15 "${raw_dir}" frame_idx; then
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
    report_fail "Save toast not reached (${DEDUP_COUNT} states)"
    cleanup_qemu; rm -rf "${raw_dir}"; exit 1
fi

# Capture save result
for i in $(seq 1 3); do
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"
    sleep 0.3
done

# Final cleanup
send_key "TOAST_CANCEL"
sleep 1
frame_idx=$((frame_idx + 1))
capture_frame_with_state "${raw_dir}" "${frame_idx}"

# Deduplicate
dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"

# Expect at least 4 unique states: type list, instruction, auto-result, save toast
if [ "${DEDUP_COUNT}" -ge 4 ]; then
    report_pass "${DEDUP_COUNT} unique states"
else
    report_fail "${DEDUP_COUNT} unique states (expected >= 4)"
fi

cleanup_qemu
rm -rf "${raw_dir}"
