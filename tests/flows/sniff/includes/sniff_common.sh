#!/bin/bash
# Sniff-flow specific test logic.
# Shared by all sniff scenario scripts.
#
# Expects: PROJECT, SCENARIO set before sourcing.
# Provides: run_sniff_scenario()
#
# The Sniff TRF flow (verified by real .so behavior in QEMU + FB captures 20260403):
#   GOTO:4 → Type list → OK (select type) → Instruction screen →
#   M1 "Start" (begin sniff) → [Sniffing] → M2 "Finish" (stop) →
#   [Decoding (HF with data)] → Result → M2 "Save" → toast "Trace file saved"
#
# Key sequence (QEMU-verified):
#   OK  = select type from list → shows instruction screen
#   M1  = "Start" → fires PM3 sniff command
#   M2  = "Finish" → stops sniff, fires PM3 list/parse command → shows result
#   M2  = "Save" → saves trace file
#
# Button enablement (FB captures 20260403):
#   INSTRUCTION: M1=Start active, M2=Finish INACTIVE
#   SNIFFING:    M1=Start INACTIVE, M2=Finish active
#   DECODING:    no buttons
#   RESULT:      M1=Start active, M2=Save active (if trace>0) or inactive (if trace=0)
#   POST-SAVE:   M1=Start active, M2=Save INACTIVE
#
# PM3 parse commands (verified by trace_sniff_flow_20260403.txt):
#   14A:    hf list mf     (NOT hf 14a list)
#   14B:    hf list 14b
#   iCLASS: hf list iclass
#   Topaz:  hf list topaz
#   T5577:  none (data in lf t55xx sniff output)

FLOW="sniff"
source "${PROJECT}/tests/includes/common.sh"

# Re-derive paths with FLOW="sniff"
SCENARIO_DIR="${RESULTS_DIR}/${FLOW}/scenarios/${SCENARIO}"
SCREENSHOTS_DIR="${SCENARIO_DIR}/screenshots"
LOG_FILE="${SCENARIO_DIR}/logs/scenario_log.txt"

# Scenario fixture directory
SNIFF_SCENARIO_DIR="${PROJECT}/tests/flows/sniff/scenarios/${SCENARIO}"

# Timing
PM3_DELAY="${PM3_DELAY:-0.5}"
BOOT_TIMEOUT="${BOOT_TIMEOUT:-120}"
SNIFF_WAIT="${SNIFF_WAIT:-30}"

# === wait_for_ui_trigger ===
# Polls state dumps for a specific UI field:value match.
# Supports: M1, M2, toast, title, content, M1_active, M2_active, M1_visible, M2_visible
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
elif field in ('M1_active','M2_active','M1_visible','M2_visible'):
    actual = d.get(field)
    if str(actual).lower() == value.lower(): sys.exit(0)
sys.exit(1)
" 2>/dev/null; then
                return 0
            fi
        fi
    done
    return 1
}

# === Run a single sniff scenario ===
# Args:
#   $1 = down_count: number of DOWN presses to select sniff type (0=14A, 1=14B, 2=iCLASS, 3=Topaz, 4=T5577)
#   $2 = min_unique: minimum unique states to PASS (default 3)
#   $3 = sniff_trigger: trigger to detect sniff started (default "toast:Sniffing in progress")
#   $4 = result_trigger: trigger to detect result displayed (default "M2:Save")
#   $5 = "save" to test save functionality, "no_save" to skip (default "save")
#   $6 = "decoding" to verify Decoding screen appeared (HF trace-result scenarios)
#   $7 = "auto_finish" to skip M2 press — T5577 auto-finishes (trace_sniff_t5577_enhanced_20260404.txt)
run_sniff_scenario() {
    local down_count="${1:-0}"
    local min_unique="${2:-3}"
    local sniff_trigger="${3:-toast:Sniffing in progress}"
    local result_trigger="${4:-M2:Save}"
    local do_save="${5:-save}"
    local check_decoding="${6:-}"
    local finish_mode="${7:-manual}"
    local raw_dir="/tmp/raw_sniff_${SCENARIO}"
    local fixture_path="${SNIFF_SCENARIO_DIR}/fixture.py"

    # Validate fixture exists
    if [ ! -f "${fixture_path}" ]; then
        echo "[FAIL] ${SCENARIO}: fixture.py not found at ${fixture_path}"
        return 1
    fi

    # Setup
    check_env
    clean_scenario
    mkdir -p "${raw_dir}"

    # Boot with per-scenario fixture.py
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
    # PHASE 1: Navigate to Sniff TRF + select type
    # ==========================================
    # Sniff TRF is menu position 4 (0-indexed)
    send_key "GOTO:4"
    sleep 2

    # Capture type selection screen
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    # Gate: verify SniffActivity entered
    # Ground truth: sniff_14a_type_list.png — title "Sniff TRF"
    if ! wait_for_ui_trigger "title:Sniff TRF" 15 "${raw_dir}" frame_idx; then
        dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
        report_fail "SniffActivity not entered (title:Sniff TRF not found, ${DEDUP_COUNT} states)"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi

    # Navigate to correct sniff type
    for i in $(seq 1 "${down_count}"); do
        send_key "DOWN"
        sleep 0.5
    done
    sleep 0.5

    # Capture after navigation (if we moved)
    if [ "${down_count}" -gt 0 ]; then
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
    fi

    # ==========================================
    # PHASE 2: Select type → Instruction screen
    # ==========================================
    send_key "OK"
    sleep 2

    # Capture instruction screen
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    # Gate: verify INSTRUCTION state
    # Ground truth: sniff_14a_instruction_step1.png — M1=Start active, M2=Finish inactive
    if ! wait_for_ui_trigger "M1:Start" 10 "${raw_dir}" frame_idx; then
        dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
        report_fail "Instruction screen not reached (M1:Start not found, ${DEDUP_COUNT} states)"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi

    # Gate: M1 active, M2 inactive in INSTRUCTION
    if ! wait_for_ui_trigger "M1_active:true" 5 "${raw_dir}" frame_idx; then
        dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
        report_fail "M1 not active in INSTRUCTION (${DEDUP_COUNT} states)"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi
    if ! wait_for_ui_trigger "M2_active:false" 5 "${raw_dir}" frame_idx; then
        dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
        report_fail "M2 not inactive in INSTRUCTION (${DEDUP_COUNT} states)"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi

    # ==========================================
    # PHASE 3: Start sniff (M1 = "Start")
    # ==========================================
    send_key "M1"

    # Gate: sniffing toast appeared
    if ! wait_for_ui_trigger "${sniff_trigger}" "${SNIFF_WAIT}" "${raw_dir}" frame_idx; then
        dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
        report_fail "sniff trigger '${sniff_trigger}' not reached (${DEDUP_COUNT} states)"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi

    # Gate: M1 inactive, M2 active during SNIFFING
    # Ground truth: FB captures — M1=Start dimmed, M2=Finish bold
    if ! wait_for_ui_trigger "M1_active:false" 5 "${raw_dir}" frame_idx; then
        dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
        report_fail "M1 not inactive during SNIFFING (${DEDUP_COUNT} states)"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi
    if ! wait_for_ui_trigger "M2_active:true" 5 "${raw_dir}" frame_idx; then
        dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
        report_fail "M2 not active during SNIFFING (${DEDUP_COUNT} states)"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi

    # Capture sniffing state
    sleep 2
    for i in $(seq 1 3); do
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
        sleep 0.5
    done

    # ==========================================
    # PHASE 4: Finish sniff → show result
    # ==========================================
    # manual (default): press M2="Finish" to stop sniff (HF types)
    # auto_finish: skip M2 — T5577 auto-finishes when PM3 completes
    # Ground truth: trace_sniff_t5577_enhanced_20260404.txt — lf t55xx sniff
    #   blocks with timeout=-1 until PM3 hardware finishes, then returns data.
    if [ "${finish_mode}" != "auto_finish" ]; then
        send_key "M2"
        sleep 1
    fi

    # Gate (opt-in): verify Decoding screen for HF trace-result scenarios.
    # Decoding items are created on main thread (via startBGTask), visible
    # until the BG parse thread cleans them up in _finishHfResult.
    if [ "${check_decoding}" = "decoding" ]; then
        if ! wait_for_ui_trigger "content:Decoding" 30 "${raw_dir}" frame_idx; then
            dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
            report_fail "Decoding screen not reached (content:Decoding not found, ${DEDUP_COUNT} states)"
            cleanup_qemu
            rm -rf "${raw_dir}"
            return 1
        fi
    fi

    # Gate: result displayed — M2 changes to "Save"
    if ! wait_for_ui_trigger "${result_trigger}" "${SNIFF_WAIT}" "${raw_dir}" frame_idx; then
        dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
        report_fail "result trigger '${result_trigger}' not reached (${DEDUP_COUNT} states)"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi

    # Gate: verify TraceLen content in result
    # Ground truth: sniff_14a_result_tracelen_9945.png
    if ! wait_for_ui_trigger "content:TraceLen" 10 "${raw_dir}" frame_idx; then
        dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
        report_fail "TraceLen not found in result (${DEDUP_COUNT} states)"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi

    # Gate: M1 active in RESULT
    if ! wait_for_ui_trigger "M1_active:true" 5 "${raw_dir}" frame_idx; then
        dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
        report_fail "M1 not active in RESULT (${DEDUP_COUNT} states)"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi

    # Gate: M2 (Save) active state matches expectation
    # Ground truth (FB captures 20260403):
    #   trace > 0: M2=Save ACTIVE  (state_030 — both buttons bold)
    #   trace = 0: M2=Save INACTIVE (state_059 — Save dimmed)
    if [ "${do_save}" = "save" ]; then
        if ! wait_for_ui_trigger "M2_active:true" 5 "${raw_dir}" frame_idx; then
            dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
            report_fail "M2 (Save) not active in RESULT — expected active for save (${DEDUP_COUNT} states)"
            cleanup_qemu
            rm -rf "${raw_dir}"
            return 1
        fi
    else
        if ! wait_for_ui_trigger "M2_active:false" 5 "${raw_dir}" frame_idx; then
            dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
            report_fail "M2 (Save) not inactive in RESULT — expected inactive for empty trace (${DEDUP_COUNT} states)"
            cleanup_qemu
            rm -rf "${raw_dir}"
            return 1
        fi
    fi

    # Dismiss any toast, capture result
    send_key "TOAST_CANCEL"
    sleep 1
    for i in $(seq 1 3); do
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
        sleep 0.5
    done

    # ==========================================
    # PHASE 5: Save trace
    # ==========================================
    if [ "${do_save}" = "save" ]; then
        # Record trace file count BEFORE save
        # Ground truth: original .so saves to /mnt/upan/trace/{type}_{N}.txt
        local trace_types=("14a" "14b" "iclass" "topaz" "t5577")
        local trace_prefix="${trace_types[${down_count}]}"
        local trace_dir="/mnt/upan/trace"
        local pre_save_count=0
        if [ -d "${trace_dir}" ]; then
            pre_save_count=$(ls "${trace_dir}/${trace_prefix}_"*.txt 2>/dev/null | wc -l)
        fi

        send_key "M2"

        # Gate: save toast — MANDATORY
        # Ground truth: sniff_14a_trace_file_saved.png
        if ! wait_for_ui_trigger "toast:Trace file" 15 "${raw_dir}" frame_idx; then
            dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
            report_fail "Save toast 'toast:Trace file' not reached (${DEDUP_COUNT} states)"
            cleanup_qemu
            rm -rf "${raw_dir}"
            return 1
        fi

        # Gate: verify trace file was created
        # Ground truth: /mnt/upan/trace/{type}_{N}.txt
        sleep 0.5
        local post_save_count=0
        if [ -d "${trace_dir}" ]; then
            post_save_count=$(ls "${trace_dir}/${trace_prefix}_"*.txt 2>/dev/null | wc -l)
        fi
        if [ "${post_save_count}" -le "${pre_save_count}" ]; then
            dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
            report_fail "Trace file not created in ${trace_dir}/${trace_prefix}_*.txt (before=${pre_save_count} after=${post_save_count})"
            cleanup_qemu
            rm -rf "${raw_dir}"
            return 1
        fi

        # Record saved file path for result metadata
        local saved_file
        saved_file=$(ls -t "${trace_dir}/${trace_prefix}_"*.txt 2>/dev/null | head -1)
        if [ -n "${saved_file}" ]; then
            echo "[SAVE] ${saved_file} ($(wc -c < "${saved_file}") bytes)"
        fi

        # Capture save result
        for i in $(seq 1 3); do
            frame_idx=$((frame_idx + 1))
            capture_frame_with_state "${raw_dir}" "${frame_idx}"
            sleep 0.3
        done
    fi

    # ==========================================
    # Final: dismiss, dedup, evaluate
    # ==========================================
    send_key "TOAST_CANCEL"
    sleep 1
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    # Deduplicate
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"

    # Negative assertions for empty-trace scenarios (no_save)
    # Ground truth: FB state_059 — empty traces have NO Decoding screen, NO ProgressBar
    if [ "${do_save}" != "save" ]; then
        local states_json="${SCENARIO_DIR}/scenario_states.json"
        if [ -f "${states_json}" ]; then
            if python3 -c "
import json, sys
with open('${states_json}') as f:
    data = json.load(f)
# Only check RESULT state (M2=Save) for stale Decoding/ProgressBar
# Ground truth: FB state_059 — result has NO Decoding, NO ProgressBar
for s in data['states']:
    if s.get('M2') != 'Save':
        continue
    for item in s.get('content_text', []):
        if 'Decoding' in item.get('text', ''):
            print('FAIL: Decoding text in RESULT state %d' % s['state'])
            sys.exit(1)
    for ci in s.get('canvas_items', []):
        tags = ' '.join(ci.get('tags', []))
        if 'sniff_decode' in tags or 'ProgressBar' in tags:
            print('FAIL: Decoding/ProgressBar in RESULT state %d' % s['state'])
            sys.exit(1)
" 2>/dev/null; then
                : # negative assertions passed
            else
                report_fail "empty trace has Decoding or ProgressBar (must not)"
                cleanup_qemu
                rm -rf "${raw_dir}"
                return 1
            fi
        fi
    fi

    # Evaluate
    if [ "${DEDUP_COUNT}" -lt "${min_unique}" ]; then
        report_fail "${DEDUP_COUNT} unique states (expected >= ${min_unique})"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi

    # Validate against expected.json
    local expected_path="${SNIFF_SCENARIO_DIR}/expected.json"
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
