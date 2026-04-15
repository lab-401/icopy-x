#!/bin/bash
# Simulate flow test infrastructure.
# Shared by all simulate scenario scripts.
#
# Expects: PROJECT, SCENARIO set before sourcing.
# Optionally set before sourcing:
#   BOOT_TIMEOUT, SIM_TRIGGER_WAIT
#
# Provides: run_sim_scenario()
#
# The Simulate flow:
#   GOTO:5 → LIST_VIEW (16 types, 4 pages) → select type → SIM_UI → edit fields
#   → M2 "Simulate" → SIM_RUNNING → M1 "Stop" → HF: TRACE_VIEW / LF: back to SIM_UI
#   → PWR exit
#
# Ground truth: docs/UI_Mapping/06_simulation/README.md
#               docs/UI_Mapping/06_simulation/V1090_SIMULATION_FLOW_COMPLETE.md

FLOW="simulate"

# Save per-scenario overrides BEFORE common.sh sets defaults
_SCENARIO_BOOT_TIMEOUT="${BOOT_TIMEOUT}"
_SCENARIO_SIM_TRIGGER_WAIT="${SIM_TRIGGER_WAIT}"

# Source shared infrastructure
source "${PROJECT}/tests/includes/common.sh"

# Apply flow-level defaults
FLOW="simulate"
PM3_DELAY="${PM3_DELAY:-0.3}"
BOOT_TIMEOUT="${_SCENARIO_BOOT_TIMEOUT:-300}"
SIM_TRIGGER_WAIT="${_SCENARIO_SIM_TRIGGER_WAIT:-60}"

# Re-derive paths with FLOW="simulate"
SCENARIO_DIR="${RESULTS_DIR}/${FLOW}/scenarios/${SCENARIO}"
SCREENSHOTS_DIR="${SCENARIO_DIR}/screenshots"
LOG_FILE="${SCENARIO_DIR}/logs/scenario_log.txt"

# Scenario fixture directory
SIM_SCENARIO_DIR="${PROJECT}/tests/flows/simulate/scenarios/${SCENARIO}"

# === SIM_MAP navigation ===
# 16 types across 4 pages (5 items per page, last page has 1).
# Page navigation: RIGHT from page 1. Item navigation: DOWN from top.
# List position 0 = page 1, item 0 (M1 S50 1k)
# List position 5 = page 2, item 0 (Em410x ID)
# List position 10 = page 3, item 0 (Viking ID)
# List position 15 = page 4, item 0 (FDX-B Data)
navigate_to_sim_type() {
    local idx="$1"  # 0-15 in SIM_MAP
    local page=$((idx / 5))       # 0-3
    local pos_in_page=$((idx % 5)) # 0-4

    # Navigate to correct page (RIGHT from page 1)
    for ((p=0; p<page; p++)); do
        send_key "RIGHT"
        sleep 0.5
    done

    # Navigate to correct item (DOWN from top of page)
    for ((d=0; d<pos_in_page; d++)); do
        send_key "DOWN"
        sleep 0.5
    done

    # Select type
    send_key "OK"
    sleep 1
}

# === Field editing ===
# Edits a hex field by cycling through each position.
# Pattern: position 0 UP, position 1 DOWN, position 2 UP, ...
# This ensures every position is visited and modified.
#
# Args:
#   $1 = number of hex characters in the field
edit_hex_field() {
    local num_chars="$1"

    # OK enters edit mode on the focused field
    send_key "OK"
    sleep 0.5

    for ((c=0; c<num_chars; c++)); do
        if (( c % 2 == 0 )); then
            send_key "UP"
        else
            send_key "DOWN"
        fi
        sleep 0.3

        # Move to next position (don't move after last char)
        if (( c < num_chars - 1 )); then
            send_key "RIGHT"
            sleep 0.3
        fi
    done

    # OK confirms the edit
    send_key "OK"
    sleep 0.5
}

# Edits a decimal field. Same pattern as hex but digits cycle 0-9.
# Args:
#   $1 = number of digits in the field
edit_decimal_field() {
    local num_digits="$1"

    # OK enters edit mode
    send_key "OK"
    sleep 0.5

    for ((c=0; c<num_digits; c++)); do
        if (( c % 2 == 0 )); then
            send_key "UP"
        else
            send_key "DOWN"
        fi
        sleep 0.3

        if (( c < num_digits - 1 )); then
            send_key "RIGHT"
            sleep 0.3
        fi
    done

    # OK confirms edit
    send_key "OK"
    sleep 0.5
}

# Toggles a selection field (e.g., FDX-B Animal Bit: 0/1).
# Just presses UP once to toggle the value.
edit_selection_field() {
    send_key "OK"
    sleep 0.3
    send_key "UP"
    sleep 0.3
    send_key "OK"
    sleep 0.5
}

# Move focus to the next field (multi-field types).
# When unfocused, DOWN moves to next field.
move_to_next_field() {
    send_key "DOWN"
    sleep 0.5
}

# Sets a decimal field to a specific small value by rolling digits.
# Used for multi-field happy paths where defaults exceed validation max.
# Strategy: roll each digit to target value.
# Args:
#   $1 = number of digits
#   $2 = target string (e.g., "00002" for value 2)
#   $3 = current string (e.g., "222222")
edit_decimal_field_to_value() {
    local num_digits="$1"
    local target="$2"
    local current="$3"

    # OK enters edit mode
    send_key "OK"
    sleep 0.5

    for ((c=0; c<num_digits; c++)); do
        local cur_digit="${current:$c:1}"
        local tgt_digit="${target:$c:1}"
        if [ "$cur_digit" != "$tgt_digit" ]; then
            # Calculate shortest path (UP or DOWN)
            local diff=$(( (tgt_digit - cur_digit + 10) % 10 ))
            if (( diff <= 5 )); then
                for ((d=0; d<diff; d++)); do
                    send_key "UP"
                    sleep 0.2
                done
            else
                for ((d=0; d<(10-diff); d++)); do
                    send_key "DOWN"
                    sleep 0.2
                done
            fi
        fi
        if (( c < num_digits - 1 )); then
            send_key "RIGHT"
            sleep 0.2
        fi
    done

    # OK confirms edit
    send_key "OK"
    sleep 0.5
}

# === Per-type editing dispatch ===
# Edits all fields for a given SIM_MAP type index.
# QEMU-verified field order and defaults (see debug probe results).
# Single-field types: OK to edit, arrows to modify, OK to confirm.
# Multi-field types: DOWN to move between fields, OK to edit each.
#
# ACTUAL DEFAULTS (QEMU-verified, NOT from docs):
#   AWID:       Format=50(2d) / FC=2001(4d) / CN=13371337(8d)
#   IO Prox:    Format=01(2h) / FC=FF(2h) / CN=65535(5d)
#   G-Prox:     Format=26(2d) / FC=255(3d) / CN=65535(5d)
#   Pyramid:    FC=255(3d) / CN=65536(5d)
#   FDX-B Anim: Country=999(3d) / NC=112233445566(12d)
#   FDX-B Data: Country=999(3d) / NC=112233445566(12d) / AnimalBit=16A(3?)
#   Nedap:      Subtype=15(2h) / Code=999(3d) / ID=99999(5d)
#
# Args:
#   $1 = SIM_MAP index (0-15)
#   $2 = mode: "valid" (ensure values pass validation) or "overflow" (exceed max)
edit_sim_fields() {
    local idx="$1"
    local mode="${2:-valid}"

    case "$idx" in
        0|1)    # M1 S50 1k, M1 S70 4k — 8 hex chars, single field
            edit_hex_field 8
            ;;
        2|3)    # Ultralight, Ntag215 — 14 hex chars, single field
            edit_hex_field 14
            ;;
        4)      # FM11RF005SH — 8 hex chars, single field
            edit_hex_field 8
            ;;
        5)      # Em410x ID — 10 hex chars, single field
            edit_hex_field 10
            ;;
        6)      # HID Prox ID — 12 hex chars, single field
            edit_hex_field 12
            ;;
        7)      # AWID — Field order: Format(2d) / FC(4d) / CN(8d)
                # Defaults: 50 / 2001 / 13371337. Max: 255/65535/65535
            if [ "$mode" == "overflow" ]; then
                # Edit Format to valid, skip to FC, set FC=99999 > 65535
                edit_decimal_field 2                    # Format (touch all)
                move_to_next_field
                edit_decimal_field_to_value 4 "9999" "2001"  # FC → 9999... wait FC max=65535, 4 digits max=9999 < 65535
                # FC=9999 < 65535 → valid! Need to overflow CN instead.
                # CN=13371337 (8 digits). CN max=65535.
                # CN is ALREADY > 65535 but doesn't trigger validation with defaults.
                # Edit CN to ensure it's been touched, then press M2.
                move_to_next_field
                edit_decimal_field 8                    # CN (touch all 8 digits)
            else
                edit_decimal_field 2                    # Format
                move_to_next_field
                edit_decimal_field 4                    # FC
                move_to_next_field
                edit_decimal_field 8                    # CN
            fi
            ;;
        8)      # IO Prox — Field order: Format(2h) / FC(2h) / CN(5d)
                # Defaults: 01 / FF / 65535. Max: 255/255/999
            if [ "$mode" == "overflow" ]; then
                # CN=65535 > 999. Edit CN to touch it, validation should catch.
                edit_hex_field 2                        # Format (touch)
                move_to_next_field
                edit_hex_field 2                        # FC (touch)
                move_to_next_field
                edit_decimal_field 5                    # CN: edit all 5 digits (65535→touched)
            else
                edit_hex_field 2                        # Format
                move_to_next_field
                edit_hex_field 2                        # FC
                move_to_next_field
                # CN=65535 > 999 by default — set to valid value
                edit_decimal_field_to_value 5 "00100" "65535"  # CN → 100
            fi
            ;;
        9)      # G-Prox II — Field order: Format(2d) / FC(3d) / CN(5d)
                # Defaults: 26 / 255 / 65535. Max: 255/255/65535
            if [ "$mode" == "overflow" ]; then
                # FC=255 at boundary. Edit FC to 999 (>255)
                edit_decimal_field 2                    # Format (touch)
                move_to_next_field
                edit_decimal_field_to_value 3 "999" "255"  # FC → 999 > 255
                move_to_next_field
                edit_decimal_field 5                    # CN (touch)
            else
                edit_decimal_field 2                    # Format
                move_to_next_field
                edit_decimal_field 3                    # FC (255 is valid)
                move_to_next_field
                # CN default=65535 — standard edit would produce 74626 (>65535).
                # Set to safe value under chipset max 0xFFFF.
                edit_decimal_field_to_value 5 "12345" "65535"  # CN → 12345
            fi
            ;;
        10)     # Viking ID — 8 hex chars, single field
            edit_hex_field 8
            ;;
        11)     # Pyramid — Field order: FC(3d) / CN(5d)
                # Defaults: 255 / 65536. Max: 255/99999
            if [ "$mode" == "overflow" ]; then
                # FC=255 at boundary. Edit FC to 999 (>255)
                edit_decimal_field_to_value 3 "999" "255"  # FC → 999 > 255
                move_to_next_field
                edit_decimal_field 5                    # CN (touch)
            else
                edit_decimal_field 3                    # FC (255 is valid)
                move_to_next_field
                edit_decimal_field 5                    # CN
            fi
            ;;
        12)     # Jablotron ID — single hex field (SIM_MAP index 12)
            edit_hex_field 6
            ;;
        13)     # Nedap — Field order: Subtype(2d) / Code(3d) / ID(5d)
                # Defaults: 15 / 999 / 99999. Max: 15/999/65535
                # Subtype=15 is at max. Don't edit in valid mode.
            if [ "$mode" == "overflow" ]; then
                # Edit Subtype above 15 to trigger validation
                edit_decimal_field_to_value 2 "16" "15"   # Subtype → 16 > 15
                move_to_next_field
                edit_decimal_field 3                    # Code (touch)
                move_to_next_field
                edit_decimal_field 5                    # ID (touch)
            else
                # Subtype=15 is at max. Skip it.
                move_to_next_field
                edit_decimal_field 3                    # Code
                move_to_next_field
                edit_decimal_field 5                    # ID
            fi
            ;;
        14)     # FDX-B Animal — Field order: Country(3d) / NC(12d)
                # FB: only 2 fields, no "Animal" selector
                # NC max=274877906943 (38-bit). Default=112233445566.
                # Overflow: set NC to 999999999999 (> 274877906943)
            if [ "$mode" == "overflow" ]; then
                edit_decimal_field 3                    # Country (touch)
                move_to_next_field
                edit_decimal_field_to_value 12 "999999999999" "112233445566"  # NC → overflow
            else
                edit_decimal_field 3                    # Country
                move_to_next_field
                edit_decimal_field 12                   # NC
            fi
            ;;
        15)     # FDX-B Data — Field order: Country(3d) / NC(12d) / Animal Bit(1d)
                # FB: "Animal Bit:" not "Ext:"
                # NC max=274877906943 (38-bit). Default=112233445566.
                # Overflow: set NC to 999999999999 (> 274877906943)
            if [ "$mode" == "overflow" ]; then
                edit_decimal_field 3                    # Country (touch)
                move_to_next_field
                edit_decimal_field_to_value 12 "999999999999" "112233445566"  # NC → overflow
                move_to_next_field
                edit_decimal_field 1                    # Animal Bit (touch)
            else
                edit_decimal_field 3                    # Country
                move_to_next_field
                edit_decimal_field 12                   # NC
                move_to_next_field
                edit_decimal_field 1                    # Animal Bit
            fi
            ;;
    esac
}

# === wait_for_ui_trigger ===
# Polls state dumps for a specific UI field:value match.
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

# === Run a single simulate scenario ===
# Args:
#   $1 = SIM_MAP index (0-15)
#   $2 = min unique states (default 3)
#   $3 = mode: "trace_data" | "trace_empty" | "trace_save" | "lf_sim" | "validation_fail" | "pwr_during_sim"
#   $4 = expected trigger (for verification)
run_sim_scenario() {
    local sim_idx="$1"
    local min_unique="${2:-3}"
    local mode="${3:-lf_sim}"
    local expected_trigger="${4:-}"
    local raw_dir="/tmp/raw_sim_${SCENARIO}"
    local fixture_path="${SIM_SCENARIO_DIR}/fixture.py"

    # Validate fixture exists
    if [ ! -f "${fixture_path}" ]; then
        echo "[FAIL] ${SCENARIO}: fixture.py not found at ${fixture_path}"
        return 1
    fi

    # Determine if HF type (indices 0-4)
    local is_hf=0
    if (( sim_idx < 5 )); then
        is_hf=1
    fi

    # Setup
    check_env
    clean_scenario
    mkdir -p "${raw_dir}"

    # Boot QEMU with fixture
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
    # PHASE 1: Enter SimulationActivity
    # ==========================================
    send_key "GOTO:5"
    sleep 2
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    # Verify we're in Simulation list view
    if ! wait_for_ui_trigger "title:Simulation" 15 "${raw_dir}" frame_idx; then
        report_fail "SimulationActivity not entered (title not 'Simulation')"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi

    # Capture list view state
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    # ==========================================
    # PHASE 2: Navigate to tag type and select
    # ==========================================
    navigate_to_sim_type "${sim_idx}"
    sleep 1

    # Capture sim UI
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    # Verify we're in sim UI (M1=Stop, M2=Start — confirmed via QEMU)
    if ! wait_for_ui_trigger "M2:Start" 10 "${raw_dir}" frame_idx; then
        report_fail "Sim UI not entered (M2 not 'Start')"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi

    # Verify correct tag type name appears in content
    # SIM_MAP type names (0-indexed)
    local -a SIM_NAMES=(
        "M1 S50 1k" "M1 S70 4k" "Ultralight" "Ntag215" "FM11RF005SH"
        "Em410x ID" "HID Prox ID" "AWID ID" "IO Prox ID" "G-Prox II ID"
        "Viking ID" "Pyramid ID" "Jablotron ID" "Nedap ID"
        "FDX-B Animal" "FDX-B Data"
    )
    local expected_name="${SIM_NAMES[$sim_idx]}"
    if [ -n "$expected_name" ]; then
        if ! wait_for_ui_trigger "content:${expected_name}" 5 "${raw_dir}" frame_idx; then
            report_fail "Wrong tag type (expected '${expected_name}' in content)"
            cleanup_qemu
            rm -rf "${raw_dir}"
            return 1
        fi
    fi

    # ==========================================
    # PHASE 3: Edit fields
    # ==========================================
    local edit_mode="valid"
    if [ "$mode" == "validation_fail" ]; then
        edit_mode="overflow"
    fi
    edit_sim_fields "${sim_idx}" "${edit_mode}"

    # Capture after editing
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    # ==========================================
    # PHASE 4: Start simulation
    # ==========================================
    send_key "M2"
    sleep 2

    # Capture post-M2 state
    for i in $(seq 1 3); do
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
        sleep 0.5
    done

    # Verify simulation started — check that no validation error toast appeared.
    # The "Simulation in progress" toast is transient (PM3 mock returns instantly).
    # Instead, verify we did NOT get a validation error by checking that the
    # sim progressed past the sim UI (no "Input invalid" toast visible).
    if [ "$mode" != "validation_fail" ]; then
        # Brief wait then check for validation error toast
        sleep 1
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
        local _dump="${STATE_DUMP_TMP}/state_$(printf '%03d' ${frame_idx}).json"
        if [ -f "$_dump" ]; then
            if python3 -c "
import json, sys
with open('${_dump}') as f: d = json.load(f)
toast = d.get('toast') or ''
if 'Input invalid' in toast or 'Invalid' in toast: sys.exit(0)
sys.exit(1)
" 2>/dev/null; then
                dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
                report_fail "Simulation did not start (validation error toast, ${DEDUP_COUNT} states)"
                cleanup_qemu
                rm -rf "${raw_dir}"
                return 1
            fi
        fi
    fi

    # ==========================================
    # VALIDATION_FAIL mode: expect toast
    # ==========================================
    if [ "$mode" == "validation_fail" ]; then
        if [ -n "$expected_trigger" ]; then
            if ! wait_for_ui_trigger "${expected_trigger}" 15 "${raw_dir}" frame_idx; then
                dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
                report_fail "Validation toast '${expected_trigger}' not found (${DEDUP_COUNT} states)"
                cleanup_qemu
                rm -rf "${raw_dir}"
                return 1
            fi
        fi
        # Capture validation toast
        for i in $(seq 1 3); do
            frame_idx=$((frame_idx + 1))
            capture_frame_with_state "${raw_dir}" "${frame_idx}"
            sleep 0.3
        done
        send_key "TOAST_CANCEL"
        sleep 1
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"

        dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
        if [ "${DEDUP_COUNT}" -lt "${min_unique}" ]; then
            report_fail "${DEDUP_COUNT} unique states (expected >= ${min_unique})"
            cleanup_qemu; rm -rf "${raw_dir}"; return 1
        fi
        local expected_path="${SIM_SCENARIO_DIR}/expected.json"
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
    # PHASE 5: Simulation running — wait then stop
    # ==========================================
    # The mock returns immediately, so sim may auto-complete.
    # Try to detect SIM_RUNNING state (M1=Stop), then press M1 to stop.
    # If sim already completed, proceed to result verification.

    # Check for sim running (toast "Simulation in progress...") or already transitioned
    # NOTE: M1=Stop and M2=Start are the same in sim UI and during sim,
    # so we use the toast to distinguish running state.
    local sim_was_running=0
    if wait_for_ui_trigger "toast:Simulation in progress" 10 "${raw_dir}" frame_idx; then
        sim_was_running=1
        # Capture running state
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
    fi

    # ==========================================
    # PWR_DURING_SIM mode: press PWR instead of M1
    # ==========================================
    if [ "$mode" == "pwr_during_sim" ]; then
        if [ "$sim_was_running" -eq 1 ]; then
            send_key "PWR"
            sleep 2
        fi
        for i in $(seq 1 3); do
            frame_idx=$((frame_idx + 1))
            capture_frame_with_state "${raw_dir}" "${frame_idx}"
            sleep 0.5
        done
        # PWR exits — may return to list or main menu
        send_key "PWR"
        sleep 1
        send_key "PWR"
        sleep 1
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"

        dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
        if [ "${DEDUP_COUNT}" -lt "${min_unique}" ]; then
            report_fail "${DEDUP_COUNT} unique states (expected >= ${min_unique})"
            cleanup_qemu; rm -rf "${raw_dir}"; return 1
        fi
        local expected_path="${SIM_SCENARIO_DIR}/expected.json"
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
    # PHASE 6: Stop simulation
    # ==========================================
    if [ "$sim_was_running" -eq 1 ]; then
        send_key "M1"
        sleep 2
    fi

    # Capture post-stop frames
    for i in $(seq 1 4); do
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
        sleep 0.5
    done

    # ==========================================
    # PHASE 7: Verify result state
    # ==========================================
    if [ "$is_hf" -eq 1 ]; then
        # HF types: expect Trace view (SimulationTraceActivity)
        # Wait for title:Trace
        if ! wait_for_ui_trigger "title:Trace" "${SIM_TRIGGER_WAIT}" "${raw_dir}" frame_idx; then
            # Sim might not have transitioned to trace — try pressing M1 stop again
            send_key "M1"
            sleep 2
            if ! wait_for_ui_trigger "title:Trace" 15 "${raw_dir}" frame_idx; then
                dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
                report_fail "Trace view not reached (title not 'Trace', ${DEDUP_COUNT} states)"
                cleanup_qemu
                rm -rf "${raw_dir}"
                return 1
            fi
        fi

        # Capture trace view
        for i in $(seq 1 3); do
            frame_idx=$((frame_idx + 1))
            capture_frame_with_state "${raw_dir}" "${frame_idx}"
            sleep 0.5
        done

        # Verify TraceLen in content
        if [ -n "$expected_trigger" ]; then
            if ! wait_for_ui_trigger "${expected_trigger}" 10 "${raw_dir}" frame_idx; then
                dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
                report_fail "Expected trigger '${expected_trigger}' not found in trace view (${DEDUP_COUNT} states)"
                cleanup_qemu
                rm -rf "${raw_dir}"
                return 1
            fi
        fi

        # === TRACE_SAVE mode: press M2 to save ===
        if [ "$mode" == "trace_save" ]; then
            send_key "M2"
            sleep 2
            if ! wait_for_ui_trigger "toast:Trace file" 15 "${raw_dir}" frame_idx; then
                dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
                report_fail "Trace save toast not found (${DEDUP_COUNT} states)"
                cleanup_qemu
                rm -rf "${raw_dir}"
                return 1
            fi
            for i in $(seq 1 3); do
                frame_idx=$((frame_idx + 1))
                capture_frame_with_state "${raw_dir}" "${frame_idx}"
                sleep 0.3
            done
            send_key "TOAST_CANCEL"
            sleep 1
        fi

        # PWR back from trace → sim UI → list → main
        send_key "PWR"
        sleep 1
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
    else
        # LF types: should be back in SIM_UI after stop
        # Verify M2=Start (sim UI state — confirmed via QEMU)
        if ! wait_for_ui_trigger "M2:Start" 15 "${raw_dir}" frame_idx; then
            dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
            report_fail "Sim UI not restored after LF stop (M2 not 'Start', ${DEDUP_COUNT} states)"
            cleanup_qemu
            rm -rf "${raw_dir}"
            return 1
        fi
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
    fi

    # ==========================================
    # PHASE 8: PWR back to main menu
    # ==========================================
    send_key "PWR"
    sleep 1
    send_key "PWR"
    sleep 1
    for i in $(seq 1 3); do
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
        sleep 0.5
    done

    # ==========================================
    # Final: dismiss, dedup, evaluate
    # ==========================================
    send_key "TOAST_CANCEL"
    sleep 0.5
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"

    if [ "${DEDUP_COUNT}" -lt "${min_unique}" ]; then
        report_fail "${DEDUP_COUNT} unique states (expected >= ${min_unique})"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi

    # Validate against expected.json
    local expected_path="${SIM_SCENARIO_DIR}/expected.json"
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
}
