#!/bin/bash
# PC Mode — OK does NOT start from IDLE (verified: 5 frames after OK, still IDLE)
# Ground truth: QEMU captures 20260405 — OK key has no effect on IDLE state
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="pcmode_ok_noop_idle"
FLOW="pc_mode"
source "${PROJECT}/tests/flows/pc_mode/includes/pc_mode_common.sh"

raw_dir="/tmp/raw_pc_${SCENARIO}"
fixture_path="${PC_SCENARIO_DIR}/fixture.py"

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

# Navigate to PC Mode
send_key "GOTO:6"
sleep 3
frame_idx=$((frame_idx + 1))
capture_frame_with_state "${raw_dir}" "${frame_idx}"

# Wait for IDLE state with M1=Start
if ! wait_for_ui_trigger "M1:Start" 15 "${raw_dir}" frame_idx; then
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
    report_fail "IDLE state not reached (M1 not Start)"
    cleanup_qemu; rm -rf "${raw_dir}"; exit 1
fi

# Send OK — should have no effect
send_key "OK"
sleep 3

# Capture 4 frames after OK to verify no state change
for i in $(seq 1 4); do
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"
    sleep 0.5
done

# Check that M1 is still "Start" (not "Stop") — proving OK did nothing
last_dump="${STATE_DUMP_TMP}/state_$(printf '%03d' ${frame_idx}).json"
sleep 1

ok_result=$(python3 -c "
import json, sys, glob, os
dump_dir = '${STATE_DUMP_TMP}'
# Check the last few dumps — all should still show M1=Start
dumps = sorted(glob.glob(os.path.join(dump_dir, 'state_*.json')))
if not dumps:
    print('no_dumps'); sys.exit(0)
# Check the last 3 dumps
for f in dumps[-3:]:
    try:
        with open(f) as fh:
            d = json.load(fh)
        m1 = d.get('M1', '')
        if 'Stop' in str(m1):
            print('changed_to_stop'); sys.exit(0)
    except: pass
print('still_start')
" 2>/dev/null)

dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"

if [ "${ok_result}" = "still_start" ]; then
    # Validate against expected.json
    if [ -f "${PC_SCENARIO_DIR}/expected.json" ] && [ -f "${SCENARIO_DIR}/scenario_states.json" ]; then
        _val_out=$(python3 "${PROJECT}/tests/includes/validate_common.py" "${SCENARIO_DIR}/scenario_states.json" "${PC_SCENARIO_DIR}/expected.json" 2>&1)
        _val_rc=$?
        echo "${_val_out}"
        if [ "${_val_rc}" -ne 0 ]; then
            report_fail "validation: ${_val_out}"
            cleanup_qemu; rm -rf "${raw_dir}"; exit 1
        fi
    fi

    report_pass "OK is no-op from IDLE: M1 still 'Start' after OK (${DEDUP_COUNT} states)"
elif [ "${ok_result}" = "changed_to_stop" ]; then
    report_fail "OK unexpectedly triggered start (M1 changed to Stop)"
else
    report_fail "Could not verify OK no-op (no state dumps found)"
fi

cleanup_qemu
rm -rf "${raw_dir}"
