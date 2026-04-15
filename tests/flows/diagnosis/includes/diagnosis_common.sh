#!/bin/bash
# Diagnosis-flow specific test logic.
# Shared by all diagnosis scenario scripts.
#
# Expects: PROJECT, SCENARIO set before sourcing.
# Provides: run_diagnosis_scenario()
#
# The Diagnosis flow (verified under QEMU):
#   Main menu pos 7 → DiagnosisActivity
#     → ITEMS_MAIN: item 0 "User diagnosis", item 1 "Factory diagnosis"
#     → OK selects "User diagnosis" → ITEMS_TEST (9 sub-tests)
#     → M2 "Start" runs ALL 5 PM3 tests as a batch automatically
#
# PM3 test batch (order from real trace):
#   1. hf tune          (timeout=8888) — HF antenna voltage
#   2. lf tune          (timeout=8888) — LF antenna voltage
#   3. hf 14a reader    (timeout=5888) — HF reader check
#   4. lf sea           (timeout=8888) — LF reader check
#   5. mem spiffs load  (timeout=5888) — Flash test
#   6. mem spiffs wipe  (timeout=5888) — Flash cleanup
#
# After tests complete, results show pass/fail for each test.
# Interactive sub-tests (USB, Buttons, Screen, Sound) are NOT part of batch.
#
# UI triggers:
#   title:Diagnosis  — DiagnosisActivity visible
#   M2:Start         — ready to run tests (ITEMS_TEST state)
#   content:Memory:  — results visible ("Flash Memory: √" or "Flash Memory: X")

FLOW="diagnosis"

# Save per-scenario overrides BEFORE common.sh sets defaults
_SCENARIO_BOOT_TIMEOUT="${BOOT_TIMEOUT}"
_SCENARIO_DIAG_TRIGGER_WAIT="${DIAG_TRIGGER_WAIT}"

# Source shared infrastructure
source "${PROJECT}/tests/includes/common.sh"

# Apply flow-level defaults
FLOW="diagnosis"
PM3_DELAY="${PM3_DELAY:-0.1}"
BOOT_TIMEOUT="${_SCENARIO_BOOT_TIMEOUT:-300}"
DIAG_TRIGGER_WAIT="${_SCENARIO_DIAG_TRIGGER_WAIT:-120}"

# Re-derive paths with FLOW="diagnosis"
SCENARIO_DIR="${RESULTS_DIR}/${FLOW}/scenarios/${SCENARIO}"
SCREENSHOTS_DIR="${SCENARIO_DIR}/screenshots"
LOG_FILE="${SCENARIO_DIR}/logs/scenario_log.txt"

# Scenario fixture directory
DIAG_SCENARIO_DIR="${PROJECT}/tests/flows/diagnosis/scenarios/${SCENARIO}"

# === wait_for_ui_trigger ===
# Polls state dumps for a specific UI field:value match.
# Supports: M1, M2, toast, title, content
wait_for_ui_trigger() {
    local trigger="$1"
    local max_wait="${2:-60}"
    local raw_dir="$3"
    local -n _fidx=$4

    local field="${trigger%%:*}"
    local value="${trigger#*:}"

    for attempt in $(seq 1 $((max_wait * 2))); do
        sleep 0.5
        _fidx=$((_fidx + 1))
        capture_frame_with_state "${raw_dir}" "${_fidx}"
        sleep 0.2
        local dump_file="${STATE_DUMP_TMP}/state_$(printf '%03d' ${_fidx}).json"
        if [ -f "$dump_file" ]; then
            if python3 -c "
import json, sys
with open('${dump_file}') as f: d = json.load(f)
field, value = '${field}', '${value}'
if field in ('M1','M2','toast'):
    actual = d.get(field) or ''
    if value in actual: sys.exit(0)
elif field == 'title':
    actual = d.get('title') or ''
    if value in actual: sys.exit(0)
elif field == 'content':
    for item in d.get('content_text', []):
        if value in item.get('text', ''): sys.exit(0)
sys.exit(1)
" 2>/dev/null; then
                return 0
            fi
        fi
    done
    return 1
}

# === Run a single diagnosis scenario ===
# Args:
#   $1 = min_unique: minimum unique states to PASS (default 3)
#   $2 = result_trigger: trigger to detect tests complete (default "content:Memory:")
run_diagnosis_scenario() {
    local min_unique="${1:-3}"
    local result_trigger="${2:-content:Memory:}"
    local raw_dir="/tmp/raw_diag_${SCENARIO}"
    local fixture_path="${DIAG_SCENARIO_DIR}/fixture.py"

    # Validate fixture exists
    if [ ! -f "${fixture_path}" ]; then
        echo "[FAIL] ${SCENARIO}: fixture.py not found at ${fixture_path}"
        return 1
    fi

    # Setup
    check_env
    clean_scenario
    mkdir -p "${raw_dir}"

    # Create /tmp/test_pm3_mem.nikola (2 bytes) needed by mem spiffs load test
    printf '\x4E\x4B' > /tmp/test_pm3_mem.nikola

    # Boot QEMU with per-scenario fixture
    boot_qemu "${fixture_path}"

    # Wait for HMI
    if ! wait_for_hmi 30; then
        report_fail "HMI not ready"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi
    sleep 1

    local frame_idx=0

    # ==========================================
    # PHASE 1: Navigate to Diagnosis (menu pos 7)
    # ==========================================
    send_key "GOTO:7"
    sleep 2

    # Capture Diagnosis screen
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    # Wait for DiagnosisActivity to be visible
    if ! wait_for_ui_trigger "title:Diagnosis" 15 "${raw_dir}" frame_idx; then
        # Fallback: try manual navigation if GOTO:7 fails
        send_key "PWR"; sleep 1
        for i in $(seq 1 6); do send_key "DOWN"; sleep 0.3; done
        send_key "OK"; sleep 2
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
        if ! wait_for_ui_trigger "title:Diagnosis" 10 "${raw_dir}" frame_idx; then
            report_fail "Could not reach Diagnosis screen"
            cleanup_qemu
            rm -rf "${raw_dir}"
            return 1
        fi
    fi

    # ==========================================
    # PHASE 2: Select "User diagnosis" (item 0, already selected)
    # ==========================================
    # OK selects "User diagnosis" → transitions to ITEMS_TEST list
    send_key "OK"
    sleep 2

    # Wait for M2:Start to confirm we're in ITEMS_TEST
    if ! wait_for_ui_trigger "M2:Start" 15 "${raw_dir}" frame_idx; then
        report_fail "ITEMS_TEST not reached (M2:Start not found)"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi

    # Capture test list screen
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    # ==========================================
    # PHASE 3: Start all tests (M2 = "Start")
    # ==========================================
    send_key "M2"
    sleep 1

    # Capture test-in-progress state
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    # ==========================================
    # PHASE 4: Wait for tests to complete
    # ==========================================
    # All 6 PM3 commands run automatically as a batch.
    # When complete, results show "Flash Memory: √" or "Flash Memory: X".
    if ! wait_for_ui_trigger "${result_trigger}" "${DIAG_TRIGGER_WAIT}" "${raw_dir}" frame_idx; then
        # Even if trigger not reached, capture what we have
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
        sleep 0.5
        dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
        report_fail "diagnosis trigger '${result_trigger}' not reached (${DEDUP_COUNT} states)"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi

    # Capture result screen (multiple frames to catch pass/fail indicators)
    for i in $(seq 1 5); do
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
        sleep 0.5
    done

    # ==========================================
    # Final: dedup and evaluate
    # ==========================================
    # Deduplicate
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"

    # Evaluate
    if [ "${DEDUP_COUNT}" -lt "${min_unique}" ]; then
        report_fail "${DEDUP_COUNT} unique states (expected >= ${min_unique})"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi

    # Validate against expected.json
    local expected_path="${DIAG_SCENARIO_DIR}/expected.json"
    local states_path="${SCENARIO_DIR}/scenario_states.json"
    local validator="${PROJECT}/tests/includes/validate_common.py"
    if [ -f "${expected_path}" ] && [ -f "${states_path}" ]; then
        local validate_output
        validate_output=$(python3 "${validator}" "${states_path}" "${expected_path}" 2>&1)
        local validate_rc=$?
        echo "${validate_output}"
        if [ "${validate_rc}" -ne 0 ]; then
            report_fail "validation: ${validate_output}"
            cleanup_qemu; rm -rf "${raw_dir}"; return 1
        fi
        report_pass "${DEDUP_COUNT} unique states, validated"
    else
        report_pass "${DEDUP_COUNT} unique states"
    fi

    # Cleanup
    cleanup_qemu
    rm -rf "${raw_dir}"
}
