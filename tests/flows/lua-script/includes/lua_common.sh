#!/bin/bash
# LUA Script flow specific test logic.
# Shared by all lua-script scenario scripts.
#
# Expects: PROJECT, SCENARIO set before sourcing.
# Provides: run_lua_scenario(), run_lua_exit_scenario()
#
# The LUA Script flow (verified by real device traces 20260330):
#   Main menu pos 13 → LUAScriptCMDActivity (paginated file list)
#     → 5 items per page, sorted alphabetically from /mnt/upan/luascripts/
#     → 47 .lua files total = 10 pages
#     → RIGHT = next page, LEFT = prev page, DOWN/UP = select item
#     → M2/OK = run selected script
#     → ConsolePrinterActivity opens with PM3 output
#
# hf_read.lua navigation (verified against /mnt/upan/luascripts/ listing):
#   Index 15 (0-indexed), page 4 (1-indexed), position 0 on page
#   Page 1 (0-4):   14araw, brutesim, calc_di, calc_ev1_it, calc_mizip
#   Page 2 (5-9):   calypso, cmdline, didump, dumptoemul-mfu, dumptoemul
#   Page 3 (10-14): e, emul2dump, emul2html, formatMifare, hf_bruteforce
#   Page 4 (15-19): hf_read, htmldump, init_rdv4, iso15_magic, legic
#   Navigation: RIGHT×3 → cursor on hf_read (first item on page 4)
#
# Console interaction (verified by real device trace):
#   executor.startPM3Task("script run <name>", timeout=-1)
#   Output fed to ConsolePrinterActivity via add_task_call() callbacks
#   Console keys: UP/M2 = font size up, DOWN/M1 = font size down
#   PWR in console → launcher destroys console Frame, returns to FILE_LIST
#   PWR in FILE_LIST → finish() → exits to Main Menu
#
# PM3 commands (from traces):
#   PM3-TASK> script run hf_read
#   PM3-TASK< ret=1 (success with card) or ret=-1 (PM3 error)

FLOW="lua-script"
source "${PROJECT}/tests/includes/common.sh"

# Re-derive paths with FLOW="lua-script"
SCENARIO_DIR="${RESULTS_DIR}/${FLOW}/scenarios/${SCENARIO}"
SCREENSHOTS_DIR="${SCENARIO_DIR}/screenshots"
LOG_FILE="${SCENARIO_DIR}/logs/scenario_log.txt"

# Scenario fixture directory
LUA_SCENARIO_DIR="${PROJECT}/tests/flows/lua-script/scenarios/${SCENARIO}"

# Timing
PM3_DELAY="${PM3_DELAY:-0.5}"
BOOT_TIMEOUT="${BOOT_TIMEOUT:-120}"
LUA_CONSOLE_WAIT="${LUA_CONSOLE_WAIT:-60}"

# === wait_for_ui_trigger (same pattern as erase/sniff/write common) ===
# Polls state dumps for a specific UI field:value match.
# Supports: M1, M2, toast, title, content, page_indicator, highlight_y
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
elif field == 'page_indicator':
    # Page indicator is a canvas item with tag '*:top'
    for item in d.get('canvas_items', []):
        tags = item.get('tags', [])
        if any(':top' in str(t) for t in tags) and 'text' in item:
            if value in item['text']: sys.exit(0)
elif field == 'highlight_y':
    # Highlight rect (selection) with fill=#EEEEEE — check y1 coord
    target_y = float(value)
    for item in d.get('canvas_items', []):
        if item.get('type') == 'rectangle' and item.get('fill') == '#EEEEEE':
            coords = item.get('coords', [])
            if len(coords) >= 2 and abs(coords[1] - target_y) < 5:
                sys.exit(0)
elif field == 'stack_depth':
    stack = d.get('activity_stack', [])
    if len(stack) >= int(value): sys.exit(0)
sys.exit(1)
" 2>/dev/null; then
                return 0
            fi
        fi
    done
    return 1
}

# === check_gate: one-shot state dump field check (no polling) ===
# Reads the LATEST state dump and checks a single gate.
# Args: $1=trigger (field:value), $2=frame_idx (to find dump file)
# Returns: 0 if gate passes, 1 if fails
check_gate() {
    local trigger="$1"
    local idx="$2"
    local field="${trigger%%:*}"
    local value="${trigger#*:}"
    local dump_file="${STATE_DUMP_TMP}/state_$(printf '%03d' ${idx}).json"

    if [ ! -f "$dump_file" ]; then
        echo "[GATE] FAIL: no state dump at index ${idx}"
        return 1
    fi

    if python3 -c "
import json, sys
with open('${dump_file}') as f: d = json.load(f)
field, value = '${field}', '${value}'
if field == 'title':
    actual = d.get('title') or ''
    if value in actual: sys.exit(0)
elif field == 'content_count_gte':
    items = d.get('content_text', [])
    if len(items) >= int(value): sys.exit(0)
elif field == 'content':
    for item in d.get('content_text', []):
        if value in item.get('text', ''): sys.exit(0)
elif field == 'page_indicator':
    for item in d.get('canvas_items', []):
        tags = item.get('tags', [])
        if any(':top' in str(t) for t in tags) and 'text' in item:
            if value in item['text']: sys.exit(0)
elif field == 'highlight_y':
    target_y = float(value)
    for item in d.get('canvas_items', []):
        if item.get('type') == 'rectangle' and item.get('fill') == '#EEEEEE':
            coords = item.get('coords', [])
            if len(coords) >= 2 and abs(coords[1] - target_y) < 5:
                sys.exit(0)
elif field == 'stack_depth':
    stack = d.get('activity_stack', [])
    if len(stack) >= int(value): sys.exit(0)
elif field in ('M1','M2','toast'):
    actual = d.get(field) or ''
    if value in actual: sys.exit(0)
sys.exit(1)
" 2>/dev/null; then
        return 0
    else
        echo "[GATE] FAIL: ${trigger} at frame ${idx}"
        return 1
    fi
}

# === Validate scenario states against expected.json ===
# Call after dedup_screenshots, before final report_pass.
# Args:
#   $1 = scenario_dir (flow scenario dir with expected.json)
#   $2 = results_scenario_dir (SCENARIO_DIR with scenario_states.json)
# Returns: 0 if valid/no expected.json, 1 if validation failed
validate_scenario_states() {
    local scenario_src_dir="$1"
    local scenario_results_dir="$2"
    local expected_path="${scenario_src_dir}/expected.json"
    local states_path="${scenario_results_dir}/scenario_states.json"
    local validator="${PROJECT}/tests/includes/validate_common.py"
    if [ -f "${expected_path}" ] && [ -f "${states_path}" ]; then
        local validate_output
        validate_output=$(python3 "${validator}" "${states_path}" "${expected_path}" 2>&1)
        local validate_rc=$?
        echo "${validate_output}"
        if [ "${validate_rc}" -ne 0 ]; then
            return 1
        fi
        return 0
    fi
    return 0
}

# === wait_for_console_output ===
# Polls for visual change after script execution.
# ConsolePrinterActivity uses a tkinter.Text widget (not canvas items),
# so state dumps may not capture its content reliably.
# We detect console presence by screenshot pixel change vs. the file list.
#
# Args: $1=raw_dir, $2=frame_idx_nameref, $3=baseline_png, $4=max_wait
# Returns: 0 if screen changed (console showing output), 1 if no change
wait_for_console_output() {
    local raw_dir="$1"
    local -n _cidx=$2
    local baseline_png="$3"
    local max_wait="${4:-30}"

    local baseline_hash
    baseline_hash=$(convert "${baseline_png}" -fill black -draw "rectangle 200,0 240,40" rgba:- 2>/dev/null | md5sum | awk '{print $1}')

    for attempt in $(seq 1 $((max_wait * 2))); do
        sleep 0.5
        _cidx=$((_cidx + 1))
        capture_frame_with_state "${raw_dir}" "${_cidx}"
        sleep 0.2

        local cur_png="${raw_dir}/$(printf '%05d' ${_cidx}).png"
        local cur_hash
        cur_hash=$(convert "${cur_png}" -fill black -draw "rectangle 200,0 240,40" rgba:- 2>/dev/null | md5sum | awk '{print $1}')

        if [ "${cur_hash}" != "${baseline_hash}" ]; then
            return 0
        fi
    done
    return 1
}

# === Run a single LUA Script scenario ===
# Args:
#   $1 = min_unique: minimum unique states to PASS (default 3)
#   $2 = expect_output: "yes" to wait for console output, "no" for timeout/error (default "yes")
#   $3 = nav_right_count: RIGHT presses to reach target page (default 3 for hf_read)
#   $4 = nav_down_count: DOWN presses on target page (default 0 for first item)
run_lua_scenario() {
    local min_unique="${1:-3}"
    local expect_output="${2:-yes}"
    local nav_right="${3:-3}"
    local nav_down="${4:-0}"
    local raw_dir="/tmp/raw_lua_${SCENARIO}"
    local fixture_path="${LUA_SCENARIO_DIR}/fixture.py"

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
    if ! wait_for_hmi 30; then
        report_fail "HMI not ready"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi
    sleep 1

    local frame_idx=0

    # ==========================================
    # PHASE 1: Navigate to LUA Script (menu pos 13)
    # ==========================================
    send_key "GOTO:13"
    sleep 2

    # Capture LUA Script file list screen
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    # Wait for LUAScriptCMDActivity to be visible
    if ! wait_for_ui_trigger "title:LUA Script" 15 "${raw_dir}" frame_idx; then
        report_fail "Could not reach LUA Script screen"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi

    # ==========================================
    # PHASE 2: Navigate to target script
    # ==========================================
    # RIGHT to advance pages
    for i in $(seq 1 "${nav_right}"); do
        send_key "RIGHT"
        sleep 0.8
    done

    # Capture after page navigation
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"
    sleep 0.5

    # DOWN to select item on page
    for i in $(seq 1 "${nav_down}"); do
        send_key "DOWN"
        sleep 0.5
    done

    if [ "${nav_down}" -gt 0 ]; then
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
        sleep 0.3
    fi

    # Save pre-run screenshot for console detection
    local pre_run_png="${raw_dir}/$(printf '%05d' ${frame_idx}).png"

    # ==========================================
    # PHASE 3: Run script (M2/OK)
    # ==========================================
    send_key "OK"
    sleep 1

    # ==========================================
    # PHASE 4: Wait for console output
    # ==========================================
    if [ "${expect_output}" = "yes" ]; then
        # Wait for ConsolePrinterActivity to show output
        # The console is a tkinter.Text widget overlay — detect via pixel change
        if ! wait_for_console_output "${raw_dir}" frame_idx "${pre_run_png}" "${LUA_CONSOLE_WAIT}"; then
            frame_idx=$((frame_idx + 1))
            capture_frame_with_state "${raw_dir}" "${frame_idx}"
            dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
            report_fail "console output not detected (${DEDUP_COUNT} states)"
            cleanup_qemu
            rm -rf "${raw_dir}"
            return 1
        fi

        # Capture a few more frames of console output
        sleep 2
        for i in $(seq 1 3); do
            frame_idx=$((frame_idx + 1))
            capture_frame_with_state "${raw_dir}" "${frame_idx}"
            sleep 0.5
        done
    else
        # For error scenarios (PM3 returns -1), the script may fail silently
        # or show a brief error. Wait a short time and capture whatever appears.
        sleep 3
        for i in $(seq 1 3); do
            frame_idx=$((frame_idx + 1))
            capture_frame_with_state "${raw_dir}" "${frame_idx}"
            sleep 0.5
        done
    fi

    # ==========================================
    # PHASE 5: Exit console via PWR
    # ==========================================
    # PWR → launcher detects console Frame and destroys it → returns to FILE_LIST
    send_key "PWR"
    sleep 2

    # Capture after console dismiss
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"
    sleep 0.5

    # ==========================================
    # PHASE 6: Exit FILE_LIST via PWR → back to main menu
    # ==========================================
    send_key "PWR"
    sleep 2

    # Capture final state (should be back at main menu or LUA Script list)
    for i in $(seq 1 3); do
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
        sleep 0.3
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
    if validate_scenario_states "${LUA_SCENARIO_DIR}" "${SCENARIO_DIR}"; then
        report_pass "${DEDUP_COUNT} unique states, validated"
    else
        report_fail "validation failed"
        cleanup_qemu; rm -rf "${raw_dir}"; return 1
    fi

    # Cleanup
    cleanup_qemu
    rm -rf "${raw_dir}"
}

# === Run LUA Script list display scenario ===
# Enter file list, validate title + content + page indicator, then exit.
run_lua_list_display_scenario() {
    local raw_dir="/tmp/raw_lua_${SCENARIO}"
    local fixture_path="${LUA_SCENARIO_DIR}/fixture.py"

    if [ ! -f "${fixture_path}" ]; then
        echo "[FAIL] ${SCENARIO}: fixture.py not found at ${fixture_path}"
        return 1
    fi

    check_env
    clean_scenario
    mkdir -p "${raw_dir}"
    boot_qemu "${fixture_path}"

    if ! wait_for_hmi 30; then
        report_fail "HMI not ready"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi
    sleep 1

    local frame_idx=0

    # Navigate to LUA Script (main menu pos 13)
    send_key "GOTO:13"
    sleep 2

    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    # Wait for LUAScriptCMDActivity
    if ! wait_for_ui_trigger "title:LUA Script" 15 "${raw_dir}" frame_idx; then
        report_fail "Could not reach LUA Script screen"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi

    # Extra captures for stable state
    sleep 0.5
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"
    sleep 0.3

    # === VALIDATION GATES ===
    local gate_fail=0

    # Gate 1: Title = "LUA Script"
    check_gate "title:LUA Script" "${frame_idx}" || gate_fail=1

    # Gate 2: Content has multiple script names (>=3 items in content_text)
    check_gate "content_count_gte:3" "${frame_idx}" || gate_fail=1

    # Gate 3: Page indicator present (canvas item *:top shows "1/10" for 47 scripts)
    check_gate "page_indicator:1/" "${frame_idx}" || gate_fail=1

    # Gate 4: Activity stack depth 2 (MainActivity + LUAScriptCMDActivity)
    check_gate "stack_depth:2" "${frame_idx}" || gate_fail=1

    # Exit
    send_key "PWR"
    sleep 2
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"

    if [ "${gate_fail}" -eq 0 ]; then
        if validate_scenario_states "${LUA_SCENARIO_DIR}" "${SCENARIO_DIR}"; then
            report_pass "${DEDUP_COUNT} states, all gates passed, validated"
        else
            report_fail "validation failed"
            cleanup_qemu; rm -rf "${raw_dir}"; return 1
        fi
    else
        report_fail "validation gate(s) failed"
    fi

    cleanup_qemu
    rm -rf "${raw_dir}"
}

# === Run LUA Script pagination scenario ===
# Navigate pages with RIGHT/LEFT, verify page indicator updates in canvas items.
run_lua_pagination_scenario() {
    local raw_dir="/tmp/raw_lua_${SCENARIO}"
    local fixture_path="${LUA_SCENARIO_DIR}/fixture.py"

    if [ ! -f "${fixture_path}" ]; then
        echo "[FAIL] ${SCENARIO}: fixture.py not found at ${fixture_path}"
        return 1
    fi

    check_env
    clean_scenario
    mkdir -p "${raw_dir}"
    boot_qemu "${fixture_path}"

    if ! wait_for_hmi 30; then
        report_fail "HMI not ready"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi
    sleep 1

    local frame_idx=0
    local gate_fail=0

    send_key "GOTO:13"
    sleep 2

    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    if ! wait_for_ui_trigger "title:LUA Script" 15 "${raw_dir}" frame_idx; then
        report_fail "Could not reach LUA Script screen"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi

    # Gate 1: Initial page indicator shows "1/"
    # (page indicator is canvas item with :top tag, NOT in title field)
    if ! wait_for_ui_trigger "page_indicator:1/" 5 "${raw_dir}" frame_idx; then
        echo "[GATE] FAIL: page indicator does not show '1/' initially"
        gate_fail=1
    fi

    # RIGHT → page 2
    send_key "RIGHT"
    sleep 1
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"
    sleep 0.3

    # Gate 2: Page indicator = "2/"
    if ! wait_for_ui_trigger "page_indicator:2/" 10 "${raw_dir}" frame_idx; then
        echo "[GATE] FAIL: page indicator not '2/' after RIGHT"
        gate_fail=1
    fi

    # RIGHT → page 3
    send_key "RIGHT"
    sleep 1

    # Gate 3: Page indicator = "3/"
    if ! wait_for_ui_trigger "page_indicator:3/" 10 "${raw_dir}" frame_idx; then
        echo "[GATE] FAIL: page indicator not '3/' after second RIGHT"
        gate_fail=1
    fi

    # LEFT → back to page 2
    send_key "LEFT"
    sleep 1

    # Gate 4: Page indicator back to "2/"
    if ! wait_for_ui_trigger "page_indicator:2/" 10 "${raw_dir}" frame_idx; then
        echo "[GATE] FAIL: page indicator not '2/' after LEFT"
        gate_fail=1
    fi

    # Exit
    send_key "PWR"
    sleep 2
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"

    if [ "${gate_fail}" -eq 0 ]; then
        if validate_scenario_states "${LUA_SCENARIO_DIR}" "${SCENARIO_DIR}"; then
            report_pass "${DEDUP_COUNT} states, pagination verified, validated"
        else
            report_fail "validation failed"
            cleanup_qemu; rm -rf "${raw_dir}"; return 1
        fi
    else
        report_fail "pagination gate(s) failed"
    fi

    cleanup_qemu
    rm -rf "${raw_dir}"
}

# === wait_for_screen_change ===
# Polls for visual change from a baseline screenshot.
# Args: $1=raw_dir, $2=frame_idx_nameref, $3=baseline_png, $4=max_wait
# Returns: 0 if screen changed, 1 if no change
wait_for_screen_change() {
    local raw_dir="$1"
    local -n _scidx=$2
    local baseline_png="$3"
    local max_wait="${4:-10}"

    local baseline_hash
    baseline_hash=$(convert "${baseline_png}" -fill black -draw "rectangle 200,0 240,40" rgba:- 2>/dev/null | md5sum | awk '{print $1}')

    for attempt in $(seq 1 $((max_wait * 2))); do
        sleep 0.5
        _scidx=$((_scidx + 1))
        capture_frame_with_state "${raw_dir}" "${_scidx}"
        sleep 0.2
        local cur_png="${raw_dir}/$(printf '%05d' ${_scidx}).png"
        local cur_hash
        cur_hash=$(convert "${cur_png}" -fill black -draw "rectangle 200,0 240,40" rgba:- 2>/dev/null | md5sum | awk '{print $1}')
        if [ "${cur_hash}" != "${baseline_hash}" ]; then
            return 0
        fi
    done
    return 1
}

# === Run LUA Script scroll scenario ===
# Scroll within page with UP/DOWN, verify screen changes via pixel diff.
# Canvas highlight positions may not be captured reliably in state dumps
# across different environments (local vs remote), so we use pixel comparison.
run_lua_scroll_scenario() {
    local raw_dir="/tmp/raw_lua_${SCENARIO}"
    local fixture_path="${LUA_SCENARIO_DIR}/fixture.py"

    if [ ! -f "${fixture_path}" ]; then
        echo "[FAIL] ${SCENARIO}: fixture.py not found at ${fixture_path}"
        return 1
    fi

    check_env
    clean_scenario
    mkdir -p "${raw_dir}"
    boot_qemu "${fixture_path}"

    if ! wait_for_hmi 30; then
        report_fail "HMI not ready"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi
    sleep 1

    local frame_idx=0
    local gate_fail=0

    send_key "GOTO:13"
    sleep 2
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    if ! wait_for_ui_trigger "title:LUA Script" 15 "${raw_dir}" frame_idx; then
        report_fail "Could not reach LUA Script screen"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi

    # Gate 1: Title = "LUA Script" (on file list)
    check_gate "title:LUA Script" "${frame_idx}" || gate_fail=1

    # Capture stable baseline
    sleep 1
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"
    sleep 0.5
    local baseline_png="${raw_dir}/$(printf '%05d' ${frame_idx}).png"

    # DOWN → screen should change (highlight moves)
    send_key "DOWN"
    sleep 0.5

    # Gate 2: Screen changes after DOWN (pixel diff)
    if ! wait_for_screen_change "${raw_dir}" frame_idx "${baseline_png}" 10; then
        echo "[GATE] FAIL: screen unchanged after DOWN key"
        gate_fail=1
    fi

    # Save this state as new baseline for next DOWN
    local after_down1_png="${raw_dir}/$(printf '%05d' ${frame_idx}).png"

    # DOWN again → screen should change again
    send_key "DOWN"
    sleep 0.5

    # Gate 3: Screen changes after second DOWN
    if ! wait_for_screen_change "${raw_dir}" frame_idx "${after_down1_png}" 10; then
        echo "[GATE] FAIL: screen unchanged after second DOWN key"
        gate_fail=1
    fi

    local after_down2_png="${raw_dir}/$(printf '%05d' ${frame_idx}).png"

    # UP → screen should change (back toward previous position)
    send_key "UP"
    sleep 0.5

    # Gate 4: Screen changes after UP
    if ! wait_for_screen_change "${raw_dir}" frame_idx "${after_down2_png}" 10; then
        echo "[GATE] FAIL: screen unchanged after UP key"
        gate_fail=1
    fi

    # Exit
    send_key "PWR"
    sleep 2
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"

    if [ "${gate_fail}" -eq 0 ]; then
        if validate_scenario_states "${LUA_SCENARIO_DIR}" "${SCENARIO_DIR}"; then
            report_pass "${DEDUP_COUNT} states, scroll verified, validated"
        else
            report_fail "validation failed"
            cleanup_qemu; rm -rf "${raw_dir}"; return 1
        fi
    else
        report_fail "scroll gate(s) failed"
    fi

    cleanup_qemu
    rm -rf "${raw_dir}"
}

# === Run LUA Script no-scripts scenario ===
# Empty the scripts directory, verify toast and title still present.
run_lua_no_scripts_scenario() {
    local raw_dir="/tmp/raw_lua_${SCENARIO}"
    local fixture_path="${LUA_SCENARIO_DIR}/fixture.py"
    local script_dir="/mnt/upan/luascripts"
    local backup_dir="/tmp/luascripts_backup_${SCENARIO}"

    if [ ! -f "${fixture_path}" ]; then
        echo "[FAIL] ${SCENARIO}: fixture.py not found at ${fixture_path}"
        return 1
    fi

    check_env
    clean_scenario
    mkdir -p "${raw_dir}"

    # Backup and empty the scripts directory
    rm -rf "${backup_dir}"
    mkdir -p "${backup_dir}"
    if [ -d "${script_dir}" ]; then
        mv "${script_dir}"/*.lua "${backup_dir}/" 2>/dev/null || true
    fi

    boot_qemu "${fixture_path}"

    if ! wait_for_hmi 30; then
        mv "${backup_dir}"/*.lua "${script_dir}/" 2>/dev/null || true
        rm -rf "${backup_dir}"
        report_fail "HMI not ready"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi
    sleep 1

    local frame_idx=0
    local gate_fail=0

    send_key "GOTO:13"
    sleep 2

    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    # Wait for the activity to load
    if ! wait_for_ui_trigger "title:LUA Script" 15 "${raw_dir}" frame_idx; then
        # May not get title if activity errors — still capture
        sleep 2
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
    fi

    # Capture several frames to catch transient toast
    for i in 1 2 3 4 5; do
        sleep 0.5
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
    done

    # Gate 1: Title = "LUA Script" (activity loaded even with no scripts)
    # Use wait_for_ui_trigger to poll for title
    if ! wait_for_ui_trigger "title:LUA Script" 10 "${raw_dir}" frame_idx; then
        echo "[GATE] FAIL: title not 'LUA Script'"
        gate_fail=1
    fi

    # Gate 2: Content must be EMPTY (no script names in content_text)
    # This is the ground truth signal: with 0 scripts, content_text = []
    local latest_dump="${STATE_DUMP_TMP}/state_$(printf '%03d' ${frame_idx}).json"
    if [ -f "$latest_dump" ]; then
        if python3 -c "
import json, sys
with open('${latest_dump}') as f: d = json.load(f)
items = d.get('content_text', [])
# With no scripts, content should be empty
if len(items) > 0: sys.exit(1)
sys.exit(0)
" 2>/dev/null; then
            : # Empty content — correct for no-scripts
        else
            echo "[GATE] FAIL: content_text not empty (expected no scripts)"
            gate_fail=1
        fi
    else
        echo "[GATE] FAIL: no state dump available"
        gate_fail=1
    fi

    # Gate 3: Check for toast (bonus — may be transient)
    local found_toast=0
    for idx in $(seq 1 ${frame_idx}); do
        local dump_file="${STATE_DUMP_TMP}/state_$(printf '%03d' ${idx}).json"
        if [ -f "$dump_file" ]; then
            if python3 -c "
import json, sys
with open('${dump_file}') as f: d = json.load(f)
toast = d.get('toast') or ''
if 'No scripts' in toast or 'no script' in toast.lower(): sys.exit(0)
sys.exit(1)
" 2>/dev/null; then
                found_toast=1
                break
            fi
        fi
    done
    if [ "${found_toast}" -eq 0 ]; then
        echo "[GATE] INFO: toast 'No scripts found' not captured (may be transient)"
    fi

    # Exit
    send_key "PWR"
    sleep 2
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    # Restore scripts
    mv "${backup_dir}"/*.lua "${script_dir}/" 2>/dev/null || true
    rm -rf "${backup_dir}"

    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"

    if [ "${gate_fail}" -eq 0 ]; then
        if validate_scenario_states "${LUA_SCENARIO_DIR}" "${SCENARIO_DIR}"; then
            report_pass "${DEDUP_COUNT} states, no-scripts verified, validated"
        else
            report_fail "validation failed"
            cleanup_qemu; rm -rf "${raw_dir}"; return 1
        fi
    else
        report_fail "no-scripts gate(s) failed"
    fi

    cleanup_qemu
    rm -rf "${raw_dir}"
}

# === Run LUA Script PWR cancel scenario ===
# Run script, send PWR during execution to cancel, verify return to list.
# Uses PM3_DELAY=10 to keep the task "running" long enough for PWR to cancel it.
run_lua_pwr_cancel_scenario() {
    local raw_dir="/tmp/raw_lua_${SCENARIO}"
    local fixture_path="${LUA_SCENARIO_DIR}/fixture.py"

    if [ ! -f "${fixture_path}" ]; then
        echo "[FAIL] ${SCENARIO}: fixture.py not found at ${fixture_path}"
        return 1
    fi

    check_env
    clean_scenario
    mkdir -p "${raw_dir}"

    # Long delay so task is still "running" when we send PWR
    PM3_DELAY=10
    boot_qemu "${fixture_path}"

    if ! wait_for_hmi 30; then
        report_fail "HMI not ready"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi
    sleep 1

    local frame_idx=0
    local gate_fail=0

    # Navigate to LUA Script
    send_key "GOTO:13"
    sleep 2
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    if ! wait_for_ui_trigger "title:LUA Script" 15 "${raw_dir}" frame_idx; then
        report_fail "Could not reach LUA Script screen"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi

    # Gate 1: File list loaded with content
    check_gate "title:LUA Script" "${frame_idx}" || gate_fail=1
    check_gate "content_count_gte:3" "${frame_idx}" || gate_fail=1

    # Navigate to hf_read (page 4, first item)
    for i in 1 2 3; do
        send_key "RIGHT"
        sleep 0.8
    done
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"
    sleep 0.5

    local pre_run_png="${raw_dir}/$(printf '%05d' ${frame_idx}).png"

    # Execute script
    send_key "OK"
    sleep 2

    # Capture during execution (console may or may not be visible)
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    # Send PWR to cancel the running task
    send_key "PWR"
    sleep 3

    # Capture after cancel
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    # Gate 2: Back at file list (title = "LUA Script")
    if ! wait_for_ui_trigger "title:LUA Script" 15 "${raw_dir}" frame_idx; then
        echo "[GATE] FAIL: not back at LUA Script list after PWR cancel"
        gate_fail=1
    fi

    # Gate 3: Content still present (script list restored)
    check_gate "content_count_gte:3" "${frame_idx}" || gate_fail=1

    # Exit file list
    send_key "PWR"
    sleep 2
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"

    if [ "${gate_fail}" -eq 0 ]; then
        if validate_scenario_states "${LUA_SCENARIO_DIR}" "${SCENARIO_DIR}"; then
            report_pass "${DEDUP_COUNT} states, PWR cancel verified, validated"
        else
            report_fail "validation failed"
            cleanup_qemu; rm -rf "${raw_dir}"; return 1
        fi
    else
        report_fail "PWR cancel gate(s) failed"
    fi

    cleanup_qemu
    rm -rf "${raw_dir}"
}

# === Run LUA Script console-no-title scenario ===
# Run a script, verify the console has no title bar and screen changed from file list.
run_lua_console_no_title_scenario() {
    local raw_dir="/tmp/raw_lua_${SCENARIO}"
    local fixture_path="${LUA_SCENARIO_DIR}/fixture.py"

    if [ ! -f "${fixture_path}" ]; then
        echo "[FAIL] ${SCENARIO}: fixture.py not found at ${fixture_path}"
        return 1
    fi

    check_env
    clean_scenario
    mkdir -p "${raw_dir}"
    boot_qemu "${fixture_path}"

    if ! wait_for_hmi 30; then
        report_fail "HMI not ready"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi
    sleep 1

    local frame_idx=0
    local gate_fail=0

    # Navigate to LUA Script
    send_key "GOTO:13"
    sleep 2
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    if ! wait_for_ui_trigger "title:LUA Script" 15 "${raw_dir}" frame_idx; then
        report_fail "Could not reach LUA Script screen"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi

    # Gate 1: Confirm we're on the file list
    check_gate "title:LUA Script" "${frame_idx}" || gate_fail=1

    # Navigate to hf_read
    for i in 1 2 3; do
        send_key "RIGHT"
        sleep 0.8
    done
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"
    sleep 0.5

    local pre_run_png="${raw_dir}/$(printf '%05d' ${frame_idx}).png"

    # Execute script
    send_key "OK"
    sleep 1

    # Wait for console output (pixel change = console appeared)
    if ! wait_for_console_output "${raw_dir}" frame_idx "${pre_run_png}" "${LUA_CONSOLE_WAIT}"; then
        dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
        report_fail "console output not detected"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi

    # Capture console state
    sleep 2
    for i in 1 2; do
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
        sleep 0.5
    done

    # Gate 2: Console appeared (visual change from file list)
    # The original .so renders ConsolePrinterActivity as a Frame overlay on the same
    # canvas — state dump title stays "LUA Script" and stack stays at depth 2.
    # Console presence is proven by the pixel diff (wait_for_console_output passed above).
    # Verify the screen now looks different from the pre-run file list screenshot.
    local console_png="${raw_dir}/$(printf '%05d' ${frame_idx}).png"
    if [ -f "${pre_run_png}" ] && [ -f "${console_png}" ]; then
        local h_pre h_con
        h_pre=$(convert "${pre_run_png}" -fill black -draw "rectangle 200,0 240,40" rgba:- 2>/dev/null | md5sum | awk '{print $1}')
        h_con=$(convert "${console_png}" -fill black -draw "rectangle 200,0 240,40" rgba:- 2>/dev/null | md5sum | awk '{print $1}')
        if [ "${h_pre}" = "${h_con}" ]; then
            echo "[GATE] FAIL: console screen identical to file list (console not visible)"
            gate_fail=1
        fi
    fi

    # Exit console + file list
    send_key "PWR"
    sleep 2
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    send_key "PWR"
    sleep 2
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"

    if [ "${gate_fail}" -eq 0 ]; then
        if validate_scenario_states "${LUA_SCENARIO_DIR}" "${SCENARIO_DIR}"; then
            report_pass "${DEDUP_COUNT} states, console no-title verified, validated"
        else
            report_fail "validation failed"
            cleanup_qemu; rm -rf "${raw_dir}"; return 1
        fi
    else
        report_fail "console no-title gate(s) failed"
    fi

    cleanup_qemu
    rm -rf "${raw_dir}"
}

# === Run LUA Script console zoom + navigation scenario ===
# Run a script, then exercise zoom (M1/M2) and scroll (arrow keys).
# Each action is validated via pixel diff — screen must change.
run_lua_console_zoom_nav_scenario() {
    local raw_dir="/tmp/raw_lua_${SCENARIO}"
    local fixture_path="${LUA_SCENARIO_DIR}/fixture.py"

    if [ ! -f "${fixture_path}" ]; then
        echo "[FAIL] ${SCENARIO}: fixture.py not found at ${fixture_path}"
        return 1
    fi

    check_env
    clean_scenario
    mkdir -p "${raw_dir}"
    boot_qemu "${fixture_path}"

    if ! wait_for_hmi 30; then
        report_fail "HMI not ready"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi
    sleep 1

    local frame_idx=0
    local gate_fail=0

    # Navigate to LUA Script, then to hf_read (page 4, first item)
    send_key "GOTO:13"
    sleep 2
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    if ! wait_for_ui_trigger "title:LUA Script" 15 "${raw_dir}" frame_idx; then
        report_fail "Could not reach LUA Script screen"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi

    for i in 1 2 3; do
        send_key "RIGHT"
        sleep 0.8
    done
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"
    sleep 0.5

    local pre_run_png="${raw_dir}/$(printf '%05d' ${frame_idx}).png"

    # Execute script
    send_key "OK"
    sleep 1

    # Wait for console output
    if ! wait_for_console_output "${raw_dir}" frame_idx "${pre_run_png}" "${LUA_CONSOLE_WAIT}"; then
        dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
        report_fail "console output not detected"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi

    # Let console content fully render
    sleep 3
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"
    sleep 0.5

    # === ZOOM IN: M2 x3 ===
    for z in 1 2 3; do
        local before_png="${raw_dir}/$(printf '%05d' ${frame_idx}).png"
        send_key "M2"
        sleep 1
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
        sleep 0.3

        if ! wait_for_screen_change "${raw_dir}" frame_idx "${before_png}" 5; then
            echo "[GATE] FAIL: zoom in #${z} (M2) did not change screen"
            gate_fail=1
        fi
    done

    # === SCROLL RIGHT: RIGHT x2 ===
    for r in 1 2; do
        local before_png="${raw_dir}/$(printf '%05d' ${frame_idx}).png"
        send_key "RIGHT"
        sleep 1
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
        sleep 0.3

        if ! wait_for_screen_change "${raw_dir}" frame_idx "${before_png}" 5; then
            echo "[GATE] FAIL: scroll right #${r} did not change screen"
            gate_fail=1
        fi
    done

    # === SCROLL LEFT: LEFT x2 ===
    for l in 1 2; do
        local before_png="${raw_dir}/$(printf '%05d' ${frame_idx}).png"
        send_key "LEFT"
        sleep 1
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
        sleep 0.3

        if ! wait_for_screen_change "${raw_dir}" frame_idx "${before_png}" 5; then
            echo "[GATE] FAIL: scroll left #${l} did not change screen"
            gate_fail=1
        fi
    done

    # === SCROLL UP: UP x2 ===
    for u in 1 2; do
        local before_png="${raw_dir}/$(printf '%05d' ${frame_idx}).png"
        send_key "UP"
        sleep 1
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
        sleep 0.3

        if ! wait_for_screen_change "${raw_dir}" frame_idx "${before_png}" 5; then
            echo "[GATE] FAIL: scroll up #${u} did not change screen"
            gate_fail=1
        fi
    done

    # === SCROLL DOWN: DOWN x2 ===
    for d in 1 2; do
        local before_png="${raw_dir}/$(printf '%05d' ${frame_idx}).png"
        send_key "DOWN"
        sleep 1
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
        sleep 0.3

        if ! wait_for_screen_change "${raw_dir}" frame_idx "${before_png}" 5; then
            echo "[GATE] FAIL: scroll down #${d} did not change screen"
            gate_fail=1
        fi
    done

    # === ZOOM OUT: M1 x2 ===
    for z in 1 2; do
        local before_png="${raw_dir}/$(printf '%05d' ${frame_idx}).png"
        send_key "M1"
        sleep 1
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
        sleep 0.3

        if ! wait_for_screen_change "${raw_dir}" frame_idx "${before_png}" 5; then
            echo "[GATE] FAIL: zoom out #${z} (M1) did not change screen"
            gate_fail=1
        fi
    done

    # Exit console + file list
    send_key "PWR"
    sleep 2
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    send_key "PWR"
    sleep 2
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"

    if [ "${gate_fail}" -eq 0 ]; then
        if validate_scenario_states "${LUA_SCENARIO_DIR}" "${SCENARIO_DIR}"; then
            report_pass "${DEDUP_COUNT} states, zoom+nav verified, validated"
        else
            report_fail "validation failed"
            cleanup_qemu; rm -rf "${raw_dir}"; return 1
        fi
    else
        report_fail "zoom/nav gate(s) failed"
    fi

    cleanup_qemu
    rm -rf "${raw_dir}"
}

# === Run LUA Script exit-without-running scenario ===
# Enter LUA Script list, PWR exit immediately — no script execution.
# Args:
#   $1 = min_unique: minimum unique states to PASS (default 2)
run_lua_exit_scenario() {
    local min_unique="${1:-2}"
    local raw_dir="/tmp/raw_lua_${SCENARIO}"
    local fixture_path="${LUA_SCENARIO_DIR}/fixture.py"

    if [ ! -f "${fixture_path}" ]; then
        echo "[FAIL] ${SCENARIO}: fixture.py not found at ${fixture_path}"
        return 1
    fi

    # Setup
    check_env
    clean_scenario
    mkdir -p "${raw_dir}"

    boot_qemu "${fixture_path}"

    if ! wait_for_hmi 30; then
        report_fail "HMI not ready"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi
    sleep 1

    local frame_idx=0

    # Navigate to LUA Script
    send_key "GOTO:13"
    sleep 2

    # Capture LUA Script file list
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    # Wait for activity to load
    if ! wait_for_ui_trigger "title:LUA Script" 15 "${raw_dir}" frame_idx; then
        report_fail "Could not reach LUA Script screen"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi

    # Capture the list screen (multiple frames for stability)
    for i in 1 2 3; do
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
        sleep 0.5
    done

    # PWR to exit back to main menu
    send_key "PWR"
    sleep 3

    # Capture main menu state
    for i in 1 2 3; do
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
        sleep 0.5
    done

    # Deduplicate
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"

    # Expect at least min_unique unique states
    if [ "${DEDUP_COUNT}" -lt "${min_unique}" ]; then
        report_fail "${DEDUP_COUNT} unique states (expected >= ${min_unique})"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi

    # Validate against expected.json
    if validate_scenario_states "${LUA_SCENARIO_DIR}" "${SCENARIO_DIR}"; then
        report_pass "${DEDUP_COUNT} unique states, validated"
    else
        report_fail "validation failed"
        cleanup_qemu; rm -rf "${raw_dir}"; return 1
    fi

    cleanup_qemu
    rm -rf "${raw_dir}"
}
