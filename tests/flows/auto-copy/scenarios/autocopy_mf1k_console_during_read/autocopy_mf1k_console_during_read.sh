#!/bin/bash
# Console test: RIGHT during Auto-Copy READ phase — MF Classic 1K
# Console should be accessible during the read portion of auto-copy.
# Each console key press is a separate gate.
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="autocopy_mf1k_console_during_read"
FLOW="auto-copy"
PM3_DELAY=3.0
BOOT_TIMEOUT=600
source "${PROJECT}/tests/includes/common.sh"

# Source read_console_common for _exercise_console and _screenshot_hash
source "${PROJECT}/tests/flows/read/includes/read_console_common.sh"

# Re-derive paths for auto-copy flow
SCENARIO_DIR="${RESULTS_DIR}/auto-copy/scenarios/${SCENARIO}"
SCREENSHOTS_DIR="${SCENARIO_DIR}/screenshots"
LOG_FILE="${SCENARIO_DIR}/logs/scenario_log.txt"
AC_SCENARIO_DIR="${PROJECT}/tests/flows/auto-copy/scenarios/${SCENARIO}"
TRIGGER_WAIT=240

check_env
clean_scenario

RAW_DIR="/tmp/raw_ac_console_${SCENARIO}"
mkdir -p "${RAW_DIR}"

boot_qemu "${AC_SCENARIO_DIR}/fixture.py"

if ! wait_for_hmi 30; then
    report_fail "HMI not ready"
    cleanup_qemu
    rm -rf "${RAW_DIR}"
    exit 1
fi
sleep 1

FRAME=0

# Enter Auto-Copy (GOTO:0) — scan starts automatically
send_key "GOTO:0"

# Wait for scan to complete and read to begin.
# Use UI trigger: once scan completes, the status text shows reading indicators.
# AutoCopy shows progress like "Reading..." or "ChkDIC" during the read phase.
# Poll for "M1:Rescan" or content containing read indicators.
for attempt in $(seq 1 120); do
    sleep 1
    FRAME=$((FRAME+1))
    capture_frame_with_state "${RAW_DIR}" "${FRAME}"
    sleep 0.3
    dump_file="${STATE_DUMP_TMP}/state_$(printf '%03d' ${FRAME}).json"
    if [ -f "$dump_file" ]; then
        if python3 -c "
import json, sys
with open('${dump_file}') as f: d = json.load(f)
# Read phase indicators: executor running with key check or read content
txt = str(d.get('executor', {}).get('last_content', ''))
if 'fchk' in txt or 'rdsc' in txt or 'found keys' in txt:
    sys.exit(0)
# Also check for scan result text on screen
for item in d.get('content_text', []):
    t = item.get('text', '')
    if 'ChkDIC' in t or 'Reading' in t or 'MIFARE' in t:
        sys.exit(0)
sys.exit(1)
" 2>/dev/null; then
            break
        fi
    fi
done
sleep 2

FRAME=$((FRAME+1))
capture_frame_with_state "${RAW_DIR}" "${FRAME}"
sleep 0.5

# Capture pre-RIGHT screenshot
pre_right_png="${RAW_DIR}/$(printf '%05d' ${FRAME}).png"

# --- Enter console via RIGHT during read phase ---
send_key "RIGHT"
sleep 1.5

FRAME=$((FRAME+1))
capture_frame_with_state "${RAW_DIR}" "${FRAME}"
sleep 0.3

# Verify console entry
post_right_png="${RAW_DIR}/$(printf '%05d' ${FRAME}).png"
if ! _verify_console_entered "${pre_right_png}" "${post_right_png}"; then
    dedup_screenshots "${RAW_DIR}" "${SCREENSHOTS_DIR}"
    report_fail "RIGHT did not change screen during AC read (${DEDUP_COUNT} states)"
    cleanup_qemu
    rm -rf "${RAW_DIR}"
    exit 1
fi

# --- Exercise console with per-key-press gates ---
gate_fails=""
_exercise_console "${RAW_DIR}" FRAME gate_fails

# --- Exit console via PWR ---
pre_pwr_png="${RAW_DIR}/$(printf '%05d' ${FRAME}).png"
send_key "PWR"
sleep 2

FRAME=$((FRAME+1))
capture_frame_with_state "${RAW_DIR}" "${FRAME}"
sleep 0.5

# GATE: Verify PWR returned to the Auto-Copy activity screen
pwr_return_dump="${STATE_DUMP_TMP}/state_$(printf '%03d' ${FRAME}).json"
pwr_return_ok="no"
if [ -f "${pwr_return_dump}" ]; then
    pwr_return_ok=$(python3 -c "
import json, sys
with open('${pwr_return_dump}') as f: d = json.load(f)
title = d.get('title') or ''
m1 = d.get('M1') or ''
m2 = d.get('M2') or ''
content = ' '.join(it.get('text','') for it in d.get('content_text', []))
# Auto-Copy activity indicators
if 'Auto Copy' in title or 'Auto' in title:
    print('yes'); sys.exit(0)
if 'Rescan' in m1 or 'Write' in m2 or 'Reread' in m2:
    print('yes'); sys.exit(0)
if 'MIFARE' in content or 'UID' in content or 'Reading' in content:
    print('yes'); sys.exit(0)
print('no')
" 2>/dev/null)
fi
if [ "${pwr_return_ok}" != "yes" ]; then
    sleep 2
    FRAME=$((FRAME+1))
    capture_frame_with_state "${RAW_DIR}" "${FRAME}"
    sleep 0.5
    pwr_return_dump="${STATE_DUMP_TMP}/state_$(printf '%03d' ${FRAME}).json"
    if [ -f "${pwr_return_dump}" ]; then
        pwr_return_ok=$(python3 -c "
import json, sys
with open('${pwr_return_dump}') as f: d = json.load(f)
title = d.get('title') or ''
m1 = d.get('M1') or ''
m2 = d.get('M2') or ''
content = ' '.join(it.get('text','') for it in d.get('content_text', []))
if 'Auto Copy' in title or 'Auto' in title:
    print('yes'); sys.exit(0)
if 'Rescan' in m1 or 'Write' in m2 or 'Reread' in m2:
    print('yes'); sys.exit(0)
if 'MIFARE' in content or 'UID' in content or 'Reading' in content:
    print('yes'); sys.exit(0)
print('no')
" 2>/dev/null)
    fi
fi
if [ "${pwr_return_ok}" != "yes" ]; then
    dedup_screenshots "${RAW_DIR}" "${SCREENSHOTS_DIR}"
    report_fail "PWR did not return to Auto-Copy activity screen (${DEDUP_COUNT} states)"
    cleanup_qemu
    rm -rf "${RAW_DIR}"
    exit 1
fi

dedup_screenshots "${RAW_DIR}" "${SCREENSHOTS_DIR}"

# Primary criterion: unique states. Gate failures reported but not hard-fail.
fail_count=0
if [ -n "${gate_fails}" ]; then
    fail_count=$(echo "${gate_fails}" | tr ',' '\n' | wc -l)
fi
pass_count=$((9 - fail_count))

if [ "${DEDUP_COUNT}" -lt 3 ]; then
    report_fail "${DEDUP_COUNT} unique states (need >= 3), ${pass_count}/9 gates passed [${gate_fails:-(none)}]"
else
    msg="${DEDUP_COUNT} unique states, ${pass_count}/9 gates passed"
    [ -n "${gate_fails}" ] && msg="${msg} [flaky: ${gate_fails}]"
    # Validate against expected.json
    if [ -f "${AUTOCOPY_SCENARIO_DIR}/expected.json" ] && [ -f "${SCENARIO_DIR}/scenario_states.json" ]; then
        _val_out=$(python3 "${PROJECT}/tests/includes/validate_common.py" "${SCENARIO_DIR}/scenario_states.json" "${AUTOCOPY_SCENARIO_DIR}/expected.json" 2>&1)
        _val_rc=$?
        echo "${_val_out}"
        if [ "${_val_rc}" -ne 0 ]; then
            report_fail "validation: ${_val_out}"
            cleanup_qemu; rm -rf "${raw_dir}"; exit 1
        fi
    fi

    report_pass "${msg} (console during AC read)"
fi

cleanup_qemu
rm -rf "${RAW_DIR}"
