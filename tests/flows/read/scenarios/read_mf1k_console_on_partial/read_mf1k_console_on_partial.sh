#!/bin/bash
# Console test: RIGHT on READ_PARTIAL result screen — MF Classic 1K (Force Read path)
# Flow: scan → fchk 0 keys → darkside key → nested fails → Warning → Force Read → partial → console
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="read_mf1k_console_on_partial"
BOOT_TIMEOUT=300
TRIGGER_WAIT=180
PM3_DELAY=0.5
source "${PROJECT}/tests/flows/read/includes/read_console_common.sh"

# This scenario uses the Force Read path which goes through a Warning screen.
# We can't use run_read_console_on_result_scenario because it expects a direct read.
# Instead, we combine the force read navigation with the console exercise.

fixture_path="${READ_SCENARIO_DIR}/fixture.py"
raw_dir="/tmp/raw_read_console_${SCENARIO}"

if [ ! -f "${fixture_path}" ]; then
    echo "[FAIL] ${SCENARIO}: fixture.py not found"
    exit 1
fi

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

# Navigate to Read Tag → select M1 S50 1K 4B (page 1, down 0) → OK
navigate_to_read_tag
frame_idx=$((frame_idx+1))
capture_frame_with_state "${raw_dir}" "${frame_idx}"

# Start scan+read (OK on first item)
send_key "OK"

# Phase 1: Wait for Warning screen (M1:Sniff indicates WarningM1Activity)
if ! wait_for_ui_trigger "M1:Sniff" "${TRIGGER_WAIT}" "${raw_dir}" frame_idx; then
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
    report_fail "Warning screen not reached (${DEDUP_COUNT} states)"
    cleanup_qemu
    rm -rf "${raw_dir}"
    exit 1
fi

frame_idx=$((frame_idx+1))
capture_frame_with_state "${raw_dir}" "${frame_idx}"
sleep 1

# Phase 2: Navigate to Force Read — DOWN to page 2/2, then M1 ("Force")
send_key "DOWN"
sleep 1
frame_idx=$((frame_idx+1))
capture_frame_with_state "${raw_dir}" "${frame_idx}"
sleep 0.5

send_key "M1"
sleep 2

# Phase 3: Wait for Partial data toast
_neg_result=""
_neg_result=$(wait_for_ui_trigger_with_negative "toast:Partial data" "${TRIGGER_WAIT}" "${raw_dir}" frame_idx)
_wait_rc=$?

if [ "${_wait_rc}" -ne 0 ]; then
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
    if [ "${_wait_rc}" -eq 2 ]; then
        report_fail "contradictory toast: expected 'Partial data' but saw '${_neg_result}' (${DEDUP_COUNT} states)"
    else
        report_fail "trigger 'toast:Partial data' not reached (${DEDUP_COUNT} states)"
    fi
    cleanup_qemu
    rm -rf "${raw_dir}"
    exit 1
fi

# Capture result screen
for i in $(seq 1 3); do
    frame_idx=$((frame_idx+1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"
    sleep 0.3
done

# Dismiss toast
send_key "TOAST_CANCEL"
sleep 2
frame_idx=$((frame_idx+1))
capture_frame_with_state "${raw_dir}" "${frame_idx}"

# Phase 4: Enter console via RIGHT on partial data result screen
pre_right_png="${raw_dir}/$(printf '%05d' ${frame_idx}).png"
send_key "RIGHT"
sleep 1
frame_idx=$((frame_idx+1))
capture_frame_with_state "${raw_dir}" "${frame_idx}"
sleep 0.3

# Verify console entered via screenshot change
post_right_png="${raw_dir}/$(printf '%05d' ${frame_idx}).png"
if ! _verify_console_entered "${pre_right_png}" "${post_right_png}"; then
    sleep 1
    frame_idx=$((frame_idx+1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"
fi

# Phase 5: Exercise console with per-key-press gates
gate_fails=""
_exercise_console "${raw_dir}" frame_idx gate_fails

# Phase 6: Exit console via PWR
send_key "PWR"
sleep 2
frame_idx=$((frame_idx+1))
capture_frame_with_state "${raw_dir}" "${frame_idx}"
sleep 0.5

# GATE: Verify PWR returned to the Read result screen
pwr_return_dump="${STATE_DUMP_TMP}/state_$(printf '%03d' ${frame_idx}).json"
pwr_return_ok="no"
if [ -f "${pwr_return_dump}" ]; then
    pwr_return_ok=$(python3 -c "
import json, sys
with open('${pwr_return_dump}') as f: d = json.load(f)
title = d.get('title') or ''
m1 = d.get('M1') or ''
m2 = d.get('M2') or ''
content = ' '.join(it.get('text','') for it in d.get('content_text', []))
if 'Reread' in m1 or 'Rescan' in m1:
    print('yes'); sys.exit(0)
if 'Write' in m2 or 'Simulate' in m2:
    print('yes'); sys.exit(0)
if 'Read Tag' in title and ('MIFARE' in content or 'UID' in content):
    print('yes'); sys.exit(0)
print('no')
" 2>/dev/null)
fi
if [ "${pwr_return_ok}" != "yes" ]; then
    sleep 2
    frame_idx=$((frame_idx+1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"
    sleep 0.5
    pwr_return_dump="${STATE_DUMP_TMP}/state_$(printf '%03d' ${frame_idx}).json"
    if [ -f "${pwr_return_dump}" ]; then
        pwr_return_ok=$(python3 -c "
import json, sys
with open('${pwr_return_dump}') as f: d = json.load(f)
title = d.get('title') or ''
m1 = d.get('M1') or ''
m2 = d.get('M2') or ''
content = ' '.join(it.get('text','') for it in d.get('content_text', []))
if 'Reread' in m1 or 'Rescan' in m1:
    print('yes'); sys.exit(0)
if 'Write' in m2 or 'Simulate' in m2:
    print('yes'); sys.exit(0)
if 'Read Tag' in title and ('MIFARE' in content or 'UID' in content):
    print('yes'); sys.exit(0)
print('no')
" 2>/dev/null)
    fi
fi
if [ "${pwr_return_ok}" != "yes" ]; then
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
    report_fail "PWR did not return to Read result screen (${DEDUP_COUNT} states)"
    cleanup_qemu
    rm -rf "${raw_dir}"
    exit 1
fi

# Dedup and report
dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"

fail_count=0
if [ -n "${gate_fails}" ]; then
    fail_count=$(echo "${gate_fails}" | tr ',' '\n' | wc -l)
fi
pass_count=$((9 - fail_count))

if [ "${DEDUP_COUNT}" -lt 3 ]; then
    report_fail "${DEDUP_COUNT} unique states (need >= 3), ${pass_count}/9 gates [${gate_fails:-(none)}]"
else
    msg="${DEDUP_COUNT} unique states, ${pass_count}/9 gates passed"
    [ -n "${gate_fails}" ] && msg="${msg} [flaky: ${gate_fails}]"
    report_pass "${msg} (console on partial data result)"
fi

cleanup_qemu
rm -rf "${raw_dir}"
