#!/bin/bash
# About-flow specific test logic.
# Shared by all about scenario scripts.
#
# Expects: PROJECT, SCENARIO set before sourcing.
# Provides: run_about_scenario()
#
# The About flow (verified by QEMU STATE_DUMP captures 20260405):
#   GOTO:10 → AboutActivity
#     → Entry: title "About", toast "Processing..." (brief), buttons HIDDEN
#     → Page 1: version info (iCopy-XS, HW, HMI, OS, PM, SN), page indicator "1/2"
#     → Page 2: firmware update instructions, page indicator "2/2"
#     → DOWN: page 1→2    M1: page 2→1    UP: NO NAVIGATION (verified)
#     → OK/M2: triggers UpdateActivity → "Install failed, code = 0x03" under QEMU
#     → PWR: finish() from either page
#
# UI triggers (from QEMU ground truth):
#   toast:Processing           — entry loading screen
#   content:1/2                — page 1 indicator
#   content:2/2                — page 2 indicator
#   content:iCopy-XS           — version info page 1
#   content:Firmware update    — update instructions page 2
#   toast:Install failed       — UpdateActivity failure under QEMU
#   title:About                — AboutActivity visible (title never changes)
#
# Button state (QEMU ground truth):
#   M1=None, M2=None, M1_visible=False, M2_visible=False (buttons HIDDEN on all pages)

FLOW="about"
source "${PROJECT}/tests/includes/common.sh"

# Re-derive paths with FLOW="about"
SCENARIO_DIR="${RESULTS_DIR}/${FLOW}/scenarios/${SCENARIO}"
SCREENSHOTS_DIR="${SCENARIO_DIR}/screenshots"
LOG_FILE="${SCENARIO_DIR}/logs/scenario_log.txt"

# Scenario fixture directory
ABOUT_SCENARIO_DIR="${PROJECT}/tests/flows/about/scenarios/${SCENARIO}"

# Timing
PM3_DELAY="${PM3_DELAY:-0.5}"
BOOT_TIMEOUT="${BOOT_TIMEOUT:-120}"
ABOUT_TRIGGER_WAIT="${ABOUT_TRIGGER_WAIT:-30}"

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
    if value in str(actual): sys.exit(0)
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

# === Run a single about scenario ===
# Args:
#   $1 = key_sequence: space-separated keys to send after reaching About
#   $2 = min_unique: minimum unique states to PASS (default 2)
#   $3 = gates: pipe-separated gate triggers (e.g., "title:About|content:1/2|content:iCopy-XS")
#
# Per-gate validation:
#   Gate 0: title:About — activity reached
#   Gates 1..N: caller-specified triggers validated in order
run_about_scenario() {
    local key_sequence="$1"
    local min_unique="${2:-2}"
    local gates="$3"
    local raw_dir="/tmp/raw_about_${SCENARIO}"
    local fixture_path="${ABOUT_SCENARIO_DIR}/fixture.py"

    # Validate fixture exists
    if [ ! -f "${fixture_path}" ]; then
        echo "[FAIL] ${SCENARIO}: fixture.py not found at ${fixture_path}"
        return 1
    fi

    # Setup
    check_env
    clean_scenario
    mkdir -p "${raw_dir}"

    # Boot QEMU with per-scenario fixture
    boot_qemu "${fixture_path}"

    # Wait for HMI
    if ! wait_for_hmi 40; then
        report_fail "HMI not ready"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi
    sleep 1

    local frame_idx=0

    # ==========================================
    # GATE 0: Navigate to About (menu pos 10)
    # ==========================================
    send_key "GOTO:10"
    sleep 3
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    if ! wait_for_ui_trigger "title:About" 15 "${raw_dir}" frame_idx; then
        report_fail "Could not reach About screen"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi

    # ==========================================
    # GATES 1..N: Validate caller-specified triggers in order
    # ==========================================
    IFS='|' read -ra gate_list <<< "${gates}"
    for gate in "${gate_list[@]}"; do
        gate="$(echo "$gate" | xargs)"  # trim whitespace
        [ -z "$gate" ] && continue

        # Check if this gate starts with KEY: — means send a key first
        if [[ "$gate" == KEY:* ]]; then
            local key_to_send="${gate#KEY:}"
            send_key "${key_to_send}"
            sleep 1
            frame_idx=$((frame_idx + 1))
            capture_frame_with_state "${raw_dir}" "${frame_idx}"
            continue
        fi

        if ! wait_for_ui_trigger "${gate}" "${ABOUT_TRIGGER_WAIT}" "${raw_dir}" frame_idx; then
            dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
            report_fail "Gate '${gate}' not reached (${DEDUP_COUNT} states)"
            cleanup_qemu
            rm -rf "${raw_dir}"
            return 1
        fi
    done

    # ==========================================
    # Send key sequence (if any)
    # ==========================================
    if [ -n "${key_sequence}" ]; then
        for key in ${key_sequence}; do
            send_key "${key}"
            sleep 1
            frame_idx=$((frame_idx + 1))
            capture_frame_with_state "${raw_dir}" "${frame_idx}"
        done
    fi

    # Capture a few final frames
    for i in $(seq 1 3); do
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
        sleep 0.5
    done

    # ==========================================
    # Final: dedup, evaluate
    # ==========================================
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"

    if [ "${DEDUP_COUNT}" -lt "${min_unique}" ]; then
        report_fail "${DEDUP_COUNT} unique states (expected >= ${min_unique})"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi

    # Validate against expected.json
    local expected_path="${ABOUT_SCENARIO_DIR}/expected.json"
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
        report_pass "${DEDUP_COUNT} unique states, all gates passed, validated"
    else
        report_pass "${DEDUP_COUNT} unique states, all gates passed"
    fi

    cleanup_qemu
    rm -rf "${raw_dir}"
}
