#!/bin/bash
# Erase-flow specific test logic.
# Shared by all erase scenario scripts.
#
# Expects: PROJECT, SCENARIO set before sourcing.
# Provides: run_erase_scenario()
#
# The Erase Tag flow (verified by real device traces 20260330):
#   Main menu pos 11 → WipeTagActivity (selection: 2 items)
#     → item 0: "Erase MF1/L1/L2/L3" → scan + key check + wrbl
#     → item 1: "Erase T5577" → WarningT5XActivity → wipe
#
# MF1 erase path (trace-verified):
#   1. hf 14a info — detect card
#   2. hf mf cgetblk 0 — check Gen1a (wupC1 error = not Gen1a)
#      Gen1a path: hf mf cwipe → success/fail
#      Standard path: hf mf fchk → check keys → hf mf wrbl (all blocks)
#   3. Post-erase: hf 14a info + hf mf cgetblk 0 verification
#
# T5577 erase path (trace-verified):
#   1. lf t55xx wipe p 20206666 — try DRM password first
#   2. lf t55xx detect — verify wipe
#   3. If detect fails: lf t55xx detect p 20206666 → lf t55xx chk f key3
#
# UI triggers (from resources.py / UI Mapping):
#   toast:Erase successful — wipe success
#   toast:Erase failed     — wipe failure
#   toast:No valid keys    — no keys for MF1 erase
#   title:Erase Tag        — WipeTagActivity visible
#   title:Warning          — WarningT5XActivity visible

FLOW="erase"
source "${PROJECT}/tests/includes/common.sh"

# Re-derive paths with FLOW="erase"
SCENARIO_DIR="${RESULTS_DIR}/${FLOW}/scenarios/${SCENARIO}"
SCREENSHOTS_DIR="${SCENARIO_DIR}/screenshots"
LOG_FILE="${SCENARIO_DIR}/logs/scenario_log.txt"

# Scenario fixture directory
ERASE_SCENARIO_DIR="${PROJECT}/tests/flows/erase/scenarios/${SCENARIO}"

# Timing
PM3_DELAY=0.5
BOOT_TIMEOUT="${BOOT_TIMEOUT:-300}"
ERASE_TRIGGER_WAIT="${ERASE_TRIGGER_WAIT:-300}"

# === wait_for_ui_trigger ===
# Polls state dumps for a specific UI field:value match.
# Supports:
#   M1, M2, toast, title  — substring match on string fields
#   content               — substring match on content_text items
#   M1_active, M2_active, M1_visible, M2_visible — boolean match (true/false)
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
elif field in ('M1_active', 'M2_active', 'M1_visible', 'M2_visible'):
    expected = value.lower() == 'true'
    if d.get(field) == expected: sys.exit(0)
sys.exit(1)
" 2>/dev/null; then
                return 0
            fi
        fi
    done
    return 1
}

# === Run a single erase scenario ===
# Args:
#   $1 = item_index: 0 = "Erase MF1/L1/L2/L3", 1 = "Erase T5577"
#   $2 = min_unique: minimum unique states to PASS (default 3)
#   $3 = final_trigger: trigger to detect erase result (default "toast:Erase successful")
#   $4 = mode: "" (default), "no_keys" (expect no-keys warning), "t5577" (T5577 with confirmation)
#
# Per-gate validation (modelled on sniff_common.sh):
#   Gate 1: title:Erase Tag — activity reached
#   Gate 2: M1:Back, M2:Erase — TYPE_SELECT buttons correct
#   Gate 3: M1_active:false — buttons hidden during scan/erase
#   Gate 4: final_trigger — result toast appeared
#   Gate 5: M1:Erase, M2:Erase — result buttons restored
run_erase_scenario() {
    local item_index="${1:-0}"
    local min_unique="${2:-3}"
    local final_trigger="${3:-toast:Erase successful}"
    local mode="${4:-}"
    local raw_dir="/tmp/raw_erase_${SCENARIO}"
    local fixture_path="${ERASE_SCENARIO_DIR}/fixture.py"

    # Validate fixture exists
    if [ ! -f "${fixture_path}" ]; then
        echo "[FAIL] ${SCENARIO}: fixture.py not found at ${fixture_path}"
        return 1
    fi

    # Setup
    check_env
    clean_scenario
    mkdir -p "${raw_dir}"

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
    # GATE 1: Navigate to Erase Tag (menu pos 11)
    # ==========================================
    send_key "GOTO:11"
    sleep 2
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    if ! wait_for_ui_trigger "title:Erase Tag" 15 "${raw_dir}" frame_idx; then
        # Fallback: manual navigation
        send_key "PWR"; sleep 1
        for i in $(seq 1 10); do send_key "DOWN"; sleep 0.3; done
        send_key "OK"; sleep 2
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
        if ! wait_for_ui_trigger "title:Erase Tag" 10 "${raw_dir}" frame_idx; then
            report_fail "Could not reach Erase Tag screen"
            cleanup_qemu
            rm -rf "${raw_dir}"
            return 1
        fi
    fi

    # ==========================================
    # GATE 2: TYPE_SELECT buttons correct
    # Ground truth: screenshot erase_tag_menu_1.png
    # ==========================================
    if ! wait_for_ui_trigger "M2:Erase" 5 "${raw_dir}" frame_idx; then
        dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
        report_fail "M2 not 'Erase' in TYPE_SELECT (${DEDUP_COUNT} states)"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi

    # ==========================================
    # Select erase type and press OK
    # ==========================================
    if [ "${item_index}" -eq 1 ]; then
        send_key "DOWN"
        sleep 0.5
    fi
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    send_key "OK"

    # ==========================================
    # T5577 — handle optional WarningT5XActivity
    # ==========================================
    if [ "${mode}" == "t5577" ]; then
        if wait_for_ui_trigger "title:Warning" 15 "${raw_dir}" frame_idx; then
            frame_idx=$((frame_idx + 1))
            capture_frame_with_state "${raw_dir}" "${frame_idx}"
            send_key "M2"
            sleep 1
        fi
    fi

    # ==========================================
    # GATE 3: Verify transition past TYPE_SELECT
    # Ground truth: screenshots menu_2..5 show no button bar
    # For fast operations (no_tag, T5577), the buttons-hidden state
    # may be too brief to catch. Accept either:
    #   - M1_active:false (buttons hidden during operation), OR
    #   - final_trigger already visible (operation completed fast)
    # ==========================================
    if ! wait_for_ui_trigger "M1_active:false" 5 "${raw_dir}" frame_idx; then
        # Operation may have completed already — check for result toast
        if ! wait_for_ui_trigger "${final_trigger}" 3 "${raw_dir}" frame_idx; then
            dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
            report_fail "No transition from TYPE_SELECT (no hidden buttons, no result toast) (${DEDUP_COUNT} states)"
            cleanup_qemu
            rm -rf "${raw_dir}"
            return 1
        fi
        # Fast path: result already visible, skip Gate 4 wait
        _gate4_done=1
    fi

    # ==========================================
    # GATE 4: Wait for erase result toast
    # (skipped if fast path already found it in Gate 3)
    # ==========================================
    if [ "${_gate4_done:-0}" -eq 0 ] && ! wait_for_ui_trigger "${final_trigger}" "${ERASE_TRIGGER_WAIT}" "${raw_dir}" frame_idx; then
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
        sleep 0.5
        dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
        report_fail "Toast '${final_trigger}' not reached (${DEDUP_COUNT} states)"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi

    # Capture result frames
    for i in $(seq 1 3); do
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
        sleep 0.3
    done

    # ==========================================
    # GATE 5: Result buttons restored to "Erase"/"Erase"
    # Ground truth: screenshots menu_6, unknown_error
    # ==========================================
    if ! wait_for_ui_trigger "M1:Erase" 5 "${raw_dir}" frame_idx; then
        dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
        report_fail "M1 not 'Erase' on result screen (${DEDUP_COUNT} states)"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi

    if ! wait_for_ui_trigger "M2:Erase" 5 "${raw_dir}" frame_idx; then
        dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
        report_fail "M2 not 'Erase' on result screen (${DEDUP_COUNT} states)"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
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

    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"

    if [ "${DEDUP_COUNT}" -lt "${min_unique}" ]; then
        report_fail "${DEDUP_COUNT} unique states (expected >= ${min_unique})"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi

    # Validate against expected.json
    local expected_path="${ERASE_SCENARIO_DIR}/expected.json"
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
        report_pass "${DEDUP_COUNT} unique states, 5/5 gates passed, validated"
    else
        report_pass "${DEDUP_COUNT} unique states, 5/5 gates passed"
    fi

    cleanup_qemu
    rm -rf "${raw_dir}"
}
