#!/bin/bash
# Dump Files flow test infrastructure.
# Shared by all dump_files scenario scripts.
#
# Expects: PROJECT, SCENARIO set before sourcing.
# Optionally set before sourcing:
#   BOOT_TIMEOUT, DUMP_TRIGGER_WAIT, WRITE_TRIGGER_WAIT, VERIFY_TRIGGER_WAIT
#
# Provides: run_dump_scenario()
#
# The Dump Files flow:
#   GOTO:1 → Type List (categories with files, 4/page) → select type →
#   File List (files sorted by ctime, 4/page, M1=Details M2=Delete) →
#   M1/OK → Tag Info (parsed metadata, M1=Simulate M2=Write) →
#   M2 → Data Ready ("Data ready!" M1=Watch M2=Write) →
#   M2 → WarningWriteActivity → WriteActivity
#
# Ground truth: docs/UI_Mapping/03_dump_files/README.md
#               docs/flows/dump_files/README.md

FLOW="dump_files"

# Save per-scenario overrides BEFORE common.sh sets defaults
_SCENARIO_BOOT_TIMEOUT="${BOOT_TIMEOUT}"
_SCENARIO_DUMP_TRIGGER_WAIT="${DUMP_TRIGGER_WAIT}"
_SCENARIO_WRITE_TRIGGER_WAIT="${WRITE_TRIGGER_WAIT}"
_SCENARIO_VERIFY_TRIGGER_WAIT="${VERIFY_TRIGGER_WAIT}"

# Source shared infrastructure
source "${PROJECT}/tests/includes/common.sh"

# Apply flow-level defaults
FLOW="dump_files"
PM3_DELAY="${PM3_DELAY:-0.3}"
BOOT_TIMEOUT="${_SCENARIO_BOOT_TIMEOUT:-300}"
DUMP_TRIGGER_WAIT="${_SCENARIO_DUMP_TRIGGER_WAIT:-30}"
WRITE_TRIGGER_WAIT="${_SCENARIO_WRITE_TRIGGER_WAIT:-300}"
VERIFY_TRIGGER_WAIT="${_SCENARIO_VERIFY_TRIGGER_WAIT:-60}"
WARNING_TRIGGER_WAIT=30

# Re-derive paths with FLOW="dump_files"
SCENARIO_DIR="${RESULTS_DIR}/${FLOW}/scenarios/${SCENARIO}"
SCREENSHOTS_DIR="${SCENARIO_DIR}/screenshots"
LOG_FILE="${SCENARIO_DIR}/logs/scenario_log.txt"

# Scenario fixture directory
DUMP_SCENARIO_DIR="${PROJECT}/tests/flows/dump_files/scenarios/${SCENARIO}"

# === Seed dump files ===
# Args:
#   $1 = types to seed: "all", "none", or comma-separated (e.g., "mf1,em410x,hid")
#   $2 = (optional) extra files: "multi:<type>:<count>" to seed multiple files per type
seed_dump_files() {
    local types="$1"
    local extra="${2:-}"

    # Ensure dump root exists and is writable
    sudo mkdir -p /mnt/upan/dump 2>/dev/null || true
    sudo chmod -R a+w /mnt/upan/dump/ 2>/dev/null || true
    sudo mkdir -p /mnt/upan/keys/mf1 2>/dev/null || true
    sudo chmod -R a+w /mnt/upan/keys/ 2>/dev/null || true

    if [ "$types" = "none" ]; then
        python3 "${PROJECT}/tools/seed_dump_files.py" --clean 2>/dev/null
        # Remove all files AND subdirectories — prevents stale type dirs
        # from inflating the type list during parallel execution
        find /mnt/upan/dump/ -mindepth 1 -delete 2>/dev/null || true
        return
    fi

    # Clean first to ensure deterministic state
    python3 "${PROJECT}/tools/seed_dump_files.py" --clean 2>/dev/null
    find /mnt/upan/dump/ -mindepth 1 -delete 2>/dev/null || true

    if [ "$types" = "all" ]; then
        python3 "${PROJECT}/tools/seed_dump_files.py" 2>/dev/null
    else
        IFS=',' read -ra TYPE_ARRAY <<< "$types"
        for t in "${TYPE_ARRAY[@]}"; do
            python3 "${PROJECT}/tools/seed_dump_files.py" --type "$t" 2>/dev/null
        done
    fi

    # Handle extra files (e.g., multi:mf1:5 creates 5 additional MF1 dumps)
    if [[ "$extra" == multi:* ]]; then
        local parts
        IFS=':' read -ra parts <<< "$extra"
        local etype="${parts[1]}"
        local ecount="${parts[2]}"
        python3 -c "
from pathlib import Path
from tools.seed_dump_files import DUMP_TYPES, BASE
cfg = DUMP_TYPES.get('${etype}', {})
d = BASE / cfg.get('path', '${etype}')
d.mkdir(parents=True, exist_ok=True)
for i in range(2, ${ecount} + 2):
    fname = cfg['files'][0][0].replace('_1.', '_%d.' % i)
    content = cfg['files'][0][1]
    (d / fname).write_bytes(content)
    print(f'  [SEED-EXTRA] {d / fname}')
" 2>/dev/null
    fi
}

# === wait_for_ui_trigger ===
# Polls state dumps for a specific UI field:value match.
# Supported fields: M1, M2, toast, title, content, not_content, activity
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
elif field == 'not_content':
    found = False
    for item in d.get('content_text', []):
        if value in item.get('text', ''): found = True; break
    if not found: sys.exit(0)
elif field == 'activity':
    actual = d.get('current_activity') or ''
    if value in actual: sys.exit(0)
sys.exit(1)
" 2>/dev/null; then
                return 0
            fi
        fi
    done
    return 1
}

# === verify_file_exists ===
# Check if a dump file exists under /mnt/upan/dump/
verify_file_exists() {
    local relpath="$1"
    [ -f "/mnt/upan/dump/${relpath}" ]
}

# === verify_file_deleted ===
# Check if a dump file was removed
verify_file_deleted() {
    local relpath="$1"
    [ ! -f "/mnt/upan/dump/${relpath}" ]
}

# === count_dump_files ===
# Count files in a dump directory
count_dump_files() {
    local type_dir="$1"
    find "/mnt/upan/dump/${type_dir}" -type f 2>/dev/null | wc -l
}

# === Run a single dump files scenario ===
# This is the main test driver. Handles the full Dump Files pipeline.
#
# Args:
#   $1 = mode (see below)
#   $2 = min_unique states (default 3)
#   $3 = seed types: "all", "none", "mf1", "mf1,em410x" etc.
#   $4 = type_index: 0-based position in Type List (default 0)
#   $5 = expected trigger for validation (optional)
#   $6 = extra seed config (optional, e.g., "multi:mf1:5")
#
# Modes:
#   pwr_type_list       — Enter Dump Files, PWR exit immediately
#   pwr_file_list       — Enter type, PWR back to types
#   pwr_tag_info        — Enter detail, PWR back to files
#   pwr_data_ready      — Enter data ready, PWR back to tag info
#   pwr_warning_write   — Enter WarningWrite, PWR cancel
#   types_empty         — No dumps, verify empty state
#   types_single        — One type, verify it shows
#   types_multi         — Multiple types, verify list
#   types_scroll        — Scroll through type list
#   files_browse        — Browse file list
#   files_empty         — Type with no valid files
#   files_scroll        — Scroll through file list
#   detail              — View tag info detail
#   delete_yes          — Delete with Yes confirmation
#   delete_no           — Delete with No cancel
#   delete_pwr          — Delete with PWR cancel
#   delete_last         — Delete last file in category
#   simulate            — Launch SimulationActivity from tag info
#   write_success       — Full write path, expect success
#   write_fail          — Full write path, expect failure
#   write_verify_ok     — Write + verify success
#   write_verify_fail   — Write success + verify failure
#   write_cancel        — Cancel at WarningWriteActivity
run_dump_scenario() {
    local mode="$1"
    local min_unique="${2:-3}"
    local seed_types="${3:-all}"
    local type_index="${4:-0}"
    local expected_trigger="${5:-}"
    local extra_seed="${6:-}"
    local raw_dir="/tmp/raw_dump_${SCENARIO}"
    local fixture_path="${DUMP_SCENARIO_DIR}/fixture.py"

    # Validate fixture exists
    if [ ! -f "${fixture_path}" ]; then
        echo "[FAIL] ${SCENARIO}: fixture.py not found at ${fixture_path}"
        return 1
    fi

    # Setup
    check_env
    clean_scenario
    mkdir -p "${raw_dir}"

    # Seed dump files BEFORE booting QEMU
    seed_dump_files "${seed_types}" "${extra_seed}"

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
    # PHASE 1: Enter CardWalletActivity
    # ==========================================
    # Dump Files is menu item #2 (index 1): GOTO:1
    send_key "GOTO:1"
    sleep 2
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    # Verify we're in Dump Files
    if ! wait_for_ui_trigger "title:Dump Files" "${DUMP_TRIGGER_WAIT}" "${raw_dir}" frame_idx; then
        # Also check for empty state which might not show "Dump Files" title
        if [ "$mode" != "types_empty" ]; then
            report_fail "CardWalletActivity not entered (title not 'Dump Files')"
            cleanup_qemu
            rm -rf "${raw_dir}"
            return 1
        fi
    fi

    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    # ==========================================
    # MODE: types_empty — verify empty state, exit
    # ==========================================
    if [ "$mode" = "types_empty" ]; then
        # Should show empty message
        if ! wait_for_ui_trigger "content:No dump" 10 "${raw_dir}" frame_idx; then
            # Try alternate: the title might still say "Dump Files"
            frame_idx=$((frame_idx + 1))
            capture_frame_with_state "${raw_dir}" "${frame_idx}"
        fi
        # PWR to exit
        send_key "PWR"
        sleep 1
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"

        dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
        if [ "${DEDUP_COUNT}" -ge "${min_unique}" ]; then
            report_pass "${DEDUP_COUNT} unique states"
        else
            report_fail "${DEDUP_COUNT} unique states (expected >= ${min_unique})"
        fi
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 0
    fi

    # ==========================================
    # MODE: pwr_type_list — PWR from type list
    # ==========================================
    if [ "$mode" = "pwr_type_list" ]; then
        send_key "PWR"
        sleep 1
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"

        dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
        if [ "${DEDUP_COUNT}" -ge "${min_unique}" ]; then
            report_pass "${DEDUP_COUNT} unique states"
        else
            report_fail "${DEDUP_COUNT} unique states (expected >= ${min_unique})"
        fi
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 0
    fi

    # ==========================================
    # PHASE 2: Type List navigation
    # ==========================================
    # types_single, types_multi, types_scroll just verify the type list
    if [ "$mode" = "types_single" ] || [ "$mode" = "types_multi" ] || [ "$mode" = "types_scroll" ]; then
        # Capture type list state
        for i in $(seq 1 3); do
            frame_idx=$((frame_idx + 1))
            capture_frame_with_state "${raw_dir}" "${frame_idx}"
            sleep 0.5
        done

        if [ "$mode" = "types_scroll" ]; then
            # Scroll through type list
            for i in $(seq 1 5); do
                send_key "DOWN"
                sleep 0.5
                frame_idx=$((frame_idx + 1))
                capture_frame_with_state "${raw_dir}" "${frame_idx}"
            done
            for i in $(seq 1 3); do
                send_key "UP"
                sleep 0.5
                frame_idx=$((frame_idx + 1))
                capture_frame_with_state "${raw_dir}" "${frame_idx}"
            done
        fi

        # Verify expected trigger if set
        if [ -n "$expected_trigger" ]; then
            if ! wait_for_ui_trigger "${expected_trigger}" 10 "${raw_dir}" frame_idx; then
                dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
                report_fail "Expected trigger '${expected_trigger}' not found (${DEDUP_COUNT} states)"
                cleanup_qemu
                rm -rf "${raw_dir}"
                return 1
            fi
        fi

        # PWR to exit
        send_key "PWR"
        sleep 1
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"

        dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
        if [ "${DEDUP_COUNT}" -ge "${min_unique}" ]; then
            report_pass "${DEDUP_COUNT} unique states"
        else
            report_fail "${DEDUP_COUNT} unique states (expected >= ${min_unique})"
        fi
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 0
    fi

    # ==========================================
    # Select type from Type List
    # ==========================================
    # Navigate to type_index (DOWN presses) then OK
    # 1.0s between presses: page transitions need time to render
    for ((d=0; d<type_index; d++)); do
        send_key "DOWN"
        sleep 1.0
    done
    send_key "OK"
    sleep 1

    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    # Verify we're in File List (M1=Details visible)
    if ! wait_for_ui_trigger "M1:Details" "${DUMP_TRIGGER_WAIT}" "${raw_dir}" frame_idx; then
        dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
        report_fail "File List not entered (M1:Details not found, ${DEDUP_COUNT} states)"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi

    # ==========================================
    # MODE: pwr_file_list — PWR from file list
    # ==========================================
    if [ "$mode" = "pwr_file_list" ]; then
        send_key "PWR"
        sleep 1
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"

        # Verify we're back in type list (title should show "Dump Files")
        wait_for_ui_trigger "title:Dump Files" 5 "${raw_dir}" frame_idx

        dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
        if [ "${DEDUP_COUNT}" -ge "${min_unique}" ]; then
            report_pass "${DEDUP_COUNT} unique states"
        else
            report_fail "${DEDUP_COUNT} unique states (expected >= ${min_unique})"
        fi
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 0
    fi

    # ==========================================
    # MODE: files_browse / files_scroll / files_empty / files_show_date
    # ==========================================
    if [ "$mode" = "files_browse" ] || [ "$mode" = "files_scroll" ] || [ "$mode" = "files_empty" ] || [ "$mode" = "files_show_date" ]; then
        for i in $(seq 1 3); do
            frame_idx=$((frame_idx + 1))
            capture_frame_with_state "${raw_dir}" "${frame_idx}"
            sleep 0.5
        done

        if [ "$mode" = "files_scroll" ]; then
            for i in $(seq 1 5); do
                send_key "DOWN"
                sleep 0.5
                frame_idx=$((frame_idx + 1))
                capture_frame_with_state "${raw_dir}" "${frame_idx}"
            done
        fi

        if [ "$mode" = "files_show_date" ]; then
            # M1 ("Details") toggles is_dump_show_date — file list re-renders with dates
            # Ground truth: is_dump_show_date (L21389), get_ctime (L22076), date_format (L21842)
            send_key "M1"
            sleep 1
            for i in $(seq 1 3); do
                frame_idx=$((frame_idx + 1))
                capture_frame_with_state "${raw_dir}" "${frame_idx}"
                sleep 0.5
            done
        fi

        if [ -n "$expected_trigger" ]; then
            if ! wait_for_ui_trigger "${expected_trigger}" 10 "${raw_dir}" frame_idx; then
                dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
                report_fail "Expected '${expected_trigger}' not found (${DEDUP_COUNT} states)"
                cleanup_qemu
                rm -rf "${raw_dir}"
                return 1
            fi
        fi

        send_key "PWR"
        sleep 1
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"

        dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
        if [ "${DEDUP_COUNT}" -ge "${min_unique}" ]; then
            report_pass "${DEDUP_COUNT} unique states"
        else
            report_fail "${DEDUP_COUNT} unique states (expected >= ${min_unique})"
        fi
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 0
    fi

    # ==========================================
    # DELETE MODES: delete_yes, delete_no, delete_pwr, delete_last
    # ==========================================
    if [[ "$mode" == delete_* ]]; then
        # M2 to enter Delete confirmation
        send_key "M2"
        sleep 1

        # Wait for "Delete?" toast
        if ! wait_for_ui_trigger "toast:Delete" "${DUMP_TRIGGER_WAIT}" "${raw_dir}" frame_idx; then
            dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
            report_fail "Delete confirmation toast not found (${DEDUP_COUNT} states)"
            cleanup_qemu
            rm -rf "${raw_dir}"
            return 1
        fi

        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"

        # Verify softkeys: M1=No, M2=Yes
        if ! wait_for_ui_trigger "M1:No" 5 "${raw_dir}" frame_idx; then
            frame_idx=$((frame_idx + 1))
            capture_frame_with_state "${raw_dir}" "${frame_idx}"
        fi

        case "$mode" in
            delete_no)
                # Press M1 (No) to cancel
                send_key "M1"
                sleep 1
                ;;
            delete_pwr)
                # Press PWR to cancel
                send_key "PWR"
                sleep 1
                ;;
            delete_yes|delete_last)
                # Press M2 (Yes) to confirm delete
                send_key "M2"
                sleep 1
                ;;
        esac

        # Capture post-delete state
        for i in $(seq 1 3); do
            frame_idx=$((frame_idx + 1))
            capture_frame_with_state "${raw_dir}" "${frame_idx}"
            sleep 0.5
        done

        # Validate expected trigger
        if [ -n "$expected_trigger" ]; then
            if ! wait_for_ui_trigger "${expected_trigger}" 10 "${raw_dir}" frame_idx; then
                dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
                report_fail "Expected '${expected_trigger}' not found after delete (${DEDUP_COUNT} states)"
                cleanup_qemu
                rm -rf "${raw_dir}"
                return 1
            fi
        fi

        # PWR to exit
        send_key "PWR"
        sleep 1
        send_key "PWR"
        sleep 1
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"

        dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
        if [ "${DEDUP_COUNT}" -ge "${min_unique}" ]; then
            report_pass "${DEDUP_COUNT} unique states"
        else
            report_fail "${DEDUP_COUNT} unique states (expected >= ${min_unique})"
        fi
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 0
    fi

    # ==========================================
    # Enter Tag Info (OK from File List → push ReadFromHistoryActivity)
    # ==========================================
    # OK pushes ReadFromHistoryActivity; M1 toggles date display (is_dump_show_date)
    # Ground truth: trace L5-6, is_dump_show_date (L21389)
    send_key "OK"
    sleep 1

    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    # Verify Tag Info view — title should be "Tag Info", softkeys "Simulate"/"Write"
    if ! wait_for_ui_trigger "title:Tag Info" "${DUMP_TRIGGER_WAIT}" "${raw_dir}" frame_idx; then
        # Fallback: check for Simulate button
        if ! wait_for_ui_trigger "M1:Simulate" 5 "${raw_dir}" frame_idx; then
            dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
            report_fail "Tag Info not entered (${DEDUP_COUNT} states)"
            cleanup_qemu
            rm -rf "${raw_dir}"
            return 1
        fi
    fi

    # ==========================================
    # MODE: pwr_tag_info — PWR from tag info
    # ==========================================
    if [ "$mode" = "pwr_tag_info" ]; then
        send_key "PWR"
        sleep 1
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"

        dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
        if [ "${DEDUP_COUNT}" -ge "${min_unique}" ]; then
            report_pass "${DEDUP_COUNT} unique states"
        else
            report_fail "${DEDUP_COUNT} unique states (expected >= ${min_unique})"
        fi
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 0
    fi

    # ==========================================
    # MODE: detail — view tag info and verify content
    # ==========================================
    if [ "$mode" = "detail" ]; then
        # Capture tag info content
        for i in $(seq 1 3); do
            frame_idx=$((frame_idx + 1))
            capture_frame_with_state "${raw_dir}" "${frame_idx}"
            sleep 0.5
        done

        # Validate expected trigger (e.g., content with tag type info)
        if [ -n "$expected_trigger" ]; then
            if ! wait_for_ui_trigger "${expected_trigger}" 10 "${raw_dir}" frame_idx; then
                dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
                report_fail "Tag info '${expected_trigger}' not found (${DEDUP_COUNT} states)"
                cleanup_qemu
                rm -rf "${raw_dir}"
                return 1
            fi
        fi

        # PWR back through to exit
        send_key "PWR"
        sleep 1
        send_key "PWR"
        sleep 1
        send_key "PWR"
        sleep 1
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"

        dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
        if [ "${DEDUP_COUNT}" -ge "${min_unique}" ]; then
            report_pass "${DEDUP_COUNT} unique states"
        else
            report_fail "${DEDUP_COUNT} unique states (expected >= ${min_unique})"
        fi
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 0
    fi

    # ==========================================
    # MODE: simulate — launch SimulationActivity
    # ==========================================
    if [ "$mode" = "simulate" ]; then
        # M1 = Simulate
        send_key "M1"
        sleep 2

        # Check if SimulationActivity entered
        for i in $(seq 1 5); do
            frame_idx=$((frame_idx + 1))
            capture_frame_with_state "${raw_dir}" "${frame_idx}"
            sleep 0.5
        done

        if [ -n "$expected_trigger" ]; then
            if ! wait_for_ui_trigger "${expected_trigger}" "${DUMP_TRIGGER_WAIT}" "${raw_dir}" frame_idx; then
                dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
                report_fail "Simulate trigger '${expected_trigger}' not found (${DEDUP_COUNT} states)"
                cleanup_qemu
                rm -rf "${raw_dir}"
                return 1
            fi
        fi

        # PWR back to exit
        send_key "PWR"
        sleep 1
        send_key "PWR"
        sleep 1
        send_key "PWR"
        sleep 1
        send_key "PWR"
        sleep 1
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"

        dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
        if [ "${DEDUP_COUNT}" -ge "${min_unique}" ]; then
            report_pass "${DEDUP_COUNT} unique states"
        else
            report_fail "${DEDUP_COUNT} unique states (expected >= ${min_unique})"
        fi
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 0
    fi

    # ==========================================
    # Enter Data Ready (M2 from Tag Info)
    # ==========================================
    send_key "M2"
    sleep 1

    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    # Verify Data Ready — title "Data ready!"
    if ! wait_for_ui_trigger "title:Data ready" "${DUMP_TRIGGER_WAIT}" "${raw_dir}" frame_idx; then
        if ! wait_for_ui_trigger "M2:Write" 5 "${raw_dir}" frame_idx; then
            dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
            report_fail "Data Ready not entered (${DEDUP_COUNT} states)"
            cleanup_qemu
            rm -rf "${raw_dir}"
            return 1
        fi
    fi

    # ==========================================
    # MODE: pwr_data_ready — PWR from Data Ready
    # ==========================================
    if [ "$mode" = "pwr_data_ready" ]; then
        send_key "PWR"
        sleep 1
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"

        dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
        if [ "${DEDUP_COUNT}" -ge "${min_unique}" ]; then
            report_pass "${DEDUP_COUNT} unique states"
        else
            report_fail "${DEDUP_COUNT} unique states (expected >= ${min_unique})"
        fi
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 0
    fi

    # ==========================================
    # Enter Write flow (M2 from Data Ready)
    # ==========================================
    # M2 pushes WarningWriteActivity
    send_key "M2"
    sleep 1

    # ==========================================
    # MODE: write_cancel — cancel at WarningWrite
    # ==========================================
    if [ "$mode" = "write_cancel" ]; then
        # Wait for WarningWriteActivity
        wait_for_ui_trigger "title:Data ready" 10 "${raw_dir}" frame_idx
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"

        # M1 to cancel (or PWR)
        send_key "M1"
        sleep 1
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"

        # PWR to exit
        send_key "PWR"
        sleep 1
        send_key "PWR"
        sleep 1
        send_key "PWR"
        sleep 1
        send_key "PWR"
        sleep 1
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"

        dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
        if [ "${DEDUP_COUNT}" -ge "${min_unique}" ]; then
            report_pass "${DEDUP_COUNT} unique states"
        else
            report_fail "${DEDUP_COUNT} unique states (expected >= ${min_unique})"
        fi
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 0
    fi

    # ==========================================
    # MODE: pwr_warning_write — PWR from WarningWrite
    # ==========================================
    if [ "$mode" = "pwr_warning_write" ]; then
        wait_for_ui_trigger "title:Data ready" 10 "${raw_dir}" frame_idx
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"

        send_key "PWR"
        sleep 1
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"

        dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
        if [ "${DEDUP_COUNT}" -ge "${min_unique}" ]; then
            report_pass "${DEDUP_COUNT} unique states"
        else
            report_fail "${DEDUP_COUNT} unique states (expected >= ${min_unique})"
        fi
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 0
    fi

    # ==========================================
    # WRITE MODES: WriteActivity (already started by M2 at line 738)
    # ==========================================
    # M2 at line 738 confirmed write in WarningWriteActivity → WriteActivity is now active.
    # WarningWriteActivity was already verified at line 704. No need to check again.
    # Ground truth: trace lines 10-12 — FINISH(WarningWrite d=4) → START(WriteActivity)
    sleep 2

    # Send M1 to trigger startWrite (no-op if auto-started)
    send_key "M1"

    # Wait for write to complete — M2 shows "Rewrite"
    if ! wait_for_ui_trigger "M2:Rewrite" "${WRITE_TRIGGER_WAIT}" "${raw_dir}" frame_idx; then
        dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
        report_fail "Write trigger 'M2:Rewrite' not reached (${DEDUP_COUNT} states)"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi

    # Capture write result
    for i in $(seq 1 3); do
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
        sleep 0.3
    done

    # Validate write toast if expected_trigger is set and mode is write_success/write_fail
    if [ "$mode" = "write_success" ] || [ "$mode" = "write_fail" ]; then
        if [ -n "$expected_trigger" ]; then
            if ! wait_for_ui_trigger "${expected_trigger}" 10 "${raw_dir}" frame_idx; then
                dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
                report_fail "Write toast '${expected_trigger}' not found (${DEDUP_COUNT} states)"
                cleanup_qemu
                rm -rf "${raw_dir}"
                return 1
            fi
        fi

        # Done — exit
        send_key "TOAST_CANCEL"
        sleep 1
        send_key "PWR"
        sleep 1
        send_key "PWR"
        sleep 1
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"

        dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
        if [ "${DEDUP_COUNT}" -ge "${min_unique}" ]; then
            report_pass "${DEDUP_COUNT} unique states"
        else
            report_fail "${DEDUP_COUNT} unique states (expected >= ${min_unique})"
        fi
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 0
    fi

    # ==========================================
    # VERIFY MODES: write_verify_ok, write_verify_fail
    # ==========================================
    # Dismiss write toast, press M1 to start verify
    send_key "TOAST_CANCEL"
    sleep 1
    send_key "M1"

    local verify_trigger="${expected_trigger:-toast:Verification successful}"

    # Wait for verify result
    local verify_ok=0
    for verify_attempt in 1 2; do
        if wait_for_ui_trigger "${verify_trigger}" "${VERIFY_TRIGGER_WAIT}" "${raw_dir}" frame_idx; then
            verify_ok=1
            break
        fi
        [ "${verify_attempt}" -eq 1 ] && sleep 1
        send_key "TOAST_CANCEL"
        sleep 1
        send_key "M1"
    done

    if [ "${verify_ok}" -eq 0 ]; then
        dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
        report_fail "Verify trigger '${verify_trigger}' not reached (${DEDUP_COUNT} states)"
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

    # Exit
    send_key "TOAST_CANCEL"
    sleep 1
    send_key "PWR"
    sleep 1
    send_key "PWR"
    sleep 1
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
    if [ "${DEDUP_COUNT}" -ge "${min_unique}" ]; then
        report_pass "${DEDUP_COUNT} unique states"
    else
        report_fail "${DEDUP_COUNT} unique states (expected >= ${min_unique})"
    fi
    cleanup_qemu
    rm -rf "${raw_dir}"
}
