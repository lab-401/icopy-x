#!/bin/bash
# Auto-Copy flow test infrastructure.
# Shared by all auto-copy scenario scripts.
#
# Expects: PROJECT, SCENARIO set before sourcing.
# Optionally set before sourcing:
#   BOOT_TIMEOUT, AUTOCOPY_TRIGGER_WAIT, WRITE_TRIGGER_WAIT, VERIFY_TRIGGER_WAIT
#
# Provides: run_auto_copy_scenario()
#
# The Auto-Copy flow is a multi-phase pipeline that auto-starts on entry:
#   GOTO:0 → Scan (auto) → Read (auto) → Place Card Prompt → WarningWriteActivity → WriteActivity → [Verify]
#
# Ground truth: docs/UI_Mapping/01_auto_copy/V1090_AUTOCOPY_FLOW_COMPLETE.md
#               docs/traces/trace_autocopy_mf1k_standard.txt

FLOW="auto-copy"

# Save per-scenario overrides BEFORE common.sh sets defaults
_SCENARIO_BOOT_TIMEOUT="${BOOT_TIMEOUT}"
_SCENARIO_AUTOCOPY_TRIGGER_WAIT="${AUTOCOPY_TRIGGER_WAIT}"
_SCENARIO_WRITE_TRIGGER_WAIT="${WRITE_TRIGGER_WAIT}"
_SCENARIO_VERIFY_TRIGGER_WAIT="${VERIFY_TRIGGER_WAIT}"

# Source shared infrastructure: QEMU boot, capture, dedup, cleanup
source "${PROJECT}/tests/includes/common.sh"

# Apply flow-level defaults (override common.sh values)
FLOW="auto-copy"
PM3_DELAY="${PM3_DELAY:-0.5}"
BOOT_TIMEOUT="${_SCENARIO_BOOT_TIMEOUT:-600}"
AUTOCOPY_TRIGGER_WAIT="${_SCENARIO_AUTOCOPY_TRIGGER_WAIT:-240}"
WRITE_TRIGGER_WAIT="${_SCENARIO_WRITE_TRIGGER_WAIT:-300}"
VERIFY_TRIGGER_WAIT="${_SCENARIO_VERIFY_TRIGGER_WAIT:-60}"
WARNING_TRIGGER_WAIT=30

# Re-derive paths with FLOW="auto-copy"
SCENARIO_DIR="${RESULTS_DIR}/${FLOW}/scenarios/${SCENARIO}"
SCREENSHOTS_DIR="${SCENARIO_DIR}/screenshots"
LOG_FILE="${SCENARIO_DIR}/logs/scenario_log.txt"

# Scenario fixture directory
AUTOCOPY_SCENARIO_DIR="${PROJECT}/tests/flows/auto-copy/scenarios/${SCENARIO}"

# === wait_for_ui_trigger ===
# Polls state dumps for a specific UI field:value match.
# Supports: M1, M2, toast, title, content
#
# Args:
#   $1 = trigger string "field:value"
#   $2 = max wait seconds (default 60)
#   $3 = raw screenshot directory
#   $4 = frame index variable name (nameref)
#
# Returns: 0 if found, 1 if timeout
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

# === Run a single auto-copy scenario ===
# Args:
#   $1 = min_unique states (default 5)
#   $2 = expected final trigger (default "toast:Write successful")
#   $3 = mode: "early_exit" for scan/read fail, "no_verify" to skip verify, "" for full pipeline
#
# Modes:
#   early_exit — Wait for failure trigger (scan fail, read fail), capture result, done.
#                No write phase. Used for: no_tag, multi_tag, wrong_type, darkside_fail, no_valid_key.
#
#   no_verify  — Full pipeline through write, but skip verify phase.
#                Used for: write_fail, HF write success (no LF verify).
#
#   "" (default) — Full pipeline: scan → read → place card → WarningWrite → Write → Verify.
#                  Used for: LF tag happy paths with verify.
#
# Phase triggers (from V1090_AUTOCOPY_FLOW_COMPLETE.md + resources.so):
#   M2:Write              — Read success, place card prompt visible
#   title:Data ready      — WarningWriteActivity entered
#   M2:Rewrite            — Write phase complete (success or fail), buttons re-enabled
#   toast:Write successful — write success
#   toast:Write failed     — write failure
#   toast:Verification successful — verify success
#   toast:Verification failed     — verify failure
#   toast:No tag found     — scan fail: no tag
#   toast:Multiple tags    — scan fail: multiple tags
#   toast:Read Failed      — read fail
#   content:No valid key   — key recovery fail (content_text, not toast)
run_auto_copy_scenario() {
    local min_unique="${1:-5}"
    local final_trigger="${2:-toast:Write successful}"
    local mode="${3:-}"
    local write_toast_trigger="${4:-}"  # optional: validate write toast after M2:Rewrite
    local raw_dir="/tmp/raw_autocopy_${SCENARIO}"
    local fixture_path="${AUTOCOPY_SCENARIO_DIR}/fixture.py"

    # Validate fixture exists
    if [ ! -f "${fixture_path}" ]; then
        echo "[FAIL] ${SCENARIO}: fixture.py not found at ${fixture_path}"
        return 1
    fi

    # Setup
    check_env
    clean_scenario
    mkdir -p "${raw_dir}"

    # Ensure dump directories are world-writable so QEMU can create files.
    # The directories may be owned by root from prior runs under a different user.
    sudo chmod -R a+w /mnt/upan/dump/ 2>/dev/null || true

    # Ensure key file exists (needed by hfmfkeys.so for fchk)
    [ ! -f /tmp/.keys/mf_tmp_keys ] && mkdir -p /tmp/.keys && python3 -c "
with open('/tmp/.keys/mf_tmp_keys','wb') as f: f.write(b'\xff\xff\xff\xff\xff\xff'*104)
" 2>/dev/null

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
    # PHASE 1: Enter AutoCopyActivity
    # ==========================================
    # AutoCopy is menu item 0 (first item). GOTO:0 enters it directly.
    # onCreate() calls startScan() — scan begins immediately, no user input.
    send_key "GOTO:0"

    # Capture initial state
    sleep 2
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    # ==========================================
    # EARLY EXIT MODE — scan/read failures
    # ==========================================
    if [ "${mode}" == "early_exit" ]; then
        # Wait for the failure trigger (toast or button state)
        if ! wait_for_ui_trigger "${final_trigger}" "${AUTOCOPY_TRIGGER_WAIT}" "${raw_dir}" frame_idx; then
            frame_idx=$((frame_idx + 1))
            capture_frame_with_state "${raw_dir}" "${frame_idx}"
            sleep 0.5
            dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
            report_fail "early exit trigger '${final_trigger}' not reached (${DEDUP_COUNT} states)"
            cleanup_qemu
            rm -rf "${raw_dir}"
            return 1
        fi

        # Capture failure state
        for i in $(seq 1 3); do
            frame_idx=$((frame_idx + 1))
            capture_frame_with_state "${raw_dir}" "${frame_idx}"
            sleep 0.3
        done

        # Dismiss toast if any
        send_key "TOAST_CANCEL"
        sleep 1
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"

        # Deduplicate and evaluate
        dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
        if [ "${DEDUP_COUNT}" -lt "${min_unique}" ]; then
            report_fail "${DEDUP_COUNT} unique states (expected >= ${min_unique})"
            cleanup_qemu
            rm -rf "${raw_dir}"
            return 1
        fi

        # Validate against expected.json
        local expected_path="${AUTOCOPY_SCENARIO_DIR}/expected.json"
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
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 0
    fi

    # ==========================================
    # PHASE 2: Wait for scan+read to complete
    # ==========================================
    # AutoCopy scan+read runs automatically. On success, the UI shows:
    #   Toast: "Data ready for copy!\nPlease place new tag for copy."
    #   M2: "Write"
    # Source: V1090_AUTOCOPY_FLOW_COMPLETE.md Phase 3 (PLACE_CARD_PROMPT)
    if ! wait_for_ui_trigger "M2:Write" "${AUTOCOPY_TRIGGER_WAIT}" "${raw_dir}" frame_idx; then
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
        sleep 0.5
        dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
        report_fail "scan+read trigger 'M2:Write' not reached (${DEDUP_COUNT} states)"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi

    # Capture place card prompt state
    send_key "TOAST_CANCEL"
    sleep 1
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    # Fix dump file: mock's identical rdsc responses create an invalid dump.
    # Overwrite with structurally valid data (correct UID, proper trailers).
    python3 "${PROJECT}/tools/generate_write_dump.py" "${fixture_path}" 2>/dev/null

    # ==========================================
    # PHASE 3: WarningWriteActivity
    # ==========================================
    # Press M2 to confirm → pushes WarningWriteActivity
    # Source: trace_autocopy_mf1k_standard.txt line 111-114
    send_key "M2"

    # Wait for WarningWriteActivity — title shows "Data ready!"
    # Some tag types (T55xx, EM4305, partial reads) skip WarningWriteActivity
    # and go directly to write. If not found, proceed anyway.
    if wait_for_ui_trigger "title:Data ready" "${WARNING_TRIGGER_WAIT}" "${raw_dir}" frame_idx; then
        # Capture warning screen
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"

        # ==========================================
        # PHASE 4: WriteActivity — start write
        # ==========================================
        # Press M2 to confirm write → pushes WriteActivity
        # Source: trace_autocopy_mf1k_standard.txt line 115-119
        send_key "M2"
        sleep 2

        # Send M1 to trigger startWrite() — no-op if write auto-started
        send_key "M1"
    else
        # WarningWriteActivity title not detected — but the activity may still
        # have appeared briefly. Send M2 to confirm write, but skip M1 since
        # it would trigger a rescan for tag types that skip the warning screen.
        sleep 2
        send_key "M2"
        sleep 2
    fi

    # Wait for write to complete — M2 shows "Rewrite" when done
    if ! wait_for_ui_trigger "M2:Rewrite" "${WRITE_TRIGGER_WAIT}" "${raw_dir}" frame_idx; then
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
        sleep 0.5
        dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
        report_fail "write trigger 'M2:Rewrite' not reached (${DEDUP_COUNT} states)"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi

    # Capture write result (toast visible)
    for i in $(seq 1 3); do
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
        sleep 0.3
    done

    # === Write toast validation ===
    # For no_verify: final_trigger IS the write toast — validate it now.
    # For full verify: use write_toast_trigger (arg 4) if provided.
    local _wt_trigger=""
    if [ "${mode}" == "no_verify" ]; then
        _wt_trigger="${final_trigger}"
    elif [ -n "${write_toast_trigger}" ]; then
        _wt_trigger="${write_toast_trigger}"
    fi
    if [ -n "${_wt_trigger}" ]; then
        if ! wait_for_ui_trigger "${_wt_trigger}" 10 "${raw_dir}" frame_idx; then
            dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
            report_fail "write toast '${_wt_trigger}' not found after write completed (${DEDUP_COUNT} states)"
            cleanup_qemu
            rm -rf "${raw_dir}"
            return 1
        fi
    fi

    # ==========================================
    # PHASE 5: Verify (full pipeline mode only)
    # ==========================================
    if [ "${mode}" != "no_verify" ]; then
        # Dismiss write toast, then press M1 to start verify
        # WriteActivity buttons: M1=Verify (left), M2=Rewrite (right)
        local verify_ok=0
        for verify_attempt in 1 2; do
            send_key "TOAST_CANCEL"
            sleep 1
            send_key "M1"

            # Wait for verify result
            if wait_for_ui_trigger "${final_trigger}" "${VERIFY_TRIGGER_WAIT}" "${raw_dir}" frame_idx; then
                verify_ok=1
                break
            fi
            # Retry: toast may have appeared and auto-dismissed too fast
            [ "${verify_attempt}" -eq 1 ] && sleep 1
        done

        if [ "${verify_ok}" -eq 0 ]; then
            frame_idx=$((frame_idx + 1))
            capture_frame_with_state "${raw_dir}" "${frame_idx}"
            sleep 0.5
            dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
            report_fail "verify trigger '${final_trigger}' not reached (${DEDUP_COUNT} states)"
            cleanup_qemu
            rm -rf "${raw_dir}"
            return 1
        fi

        # Capture verify result
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
    for i in $(seq 1 3); do
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
        sleep 0.3
    done

    # Deduplicate
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"

    # Smoke test: minimum unique states
    if [ "${DEDUP_COUNT}" -lt "${min_unique}" ]; then
        report_fail "${DEDUP_COUNT} unique states (expected >= ${min_unique})"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi

    # Validate against expected.json
    local expected_path="${AUTOCOPY_SCENARIO_DIR}/expected.json"
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
