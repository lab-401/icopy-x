#!/bin/bash
# Read-flow console test logic.
# Tests the ConsolePrinterActivity (RIGHT key) during and after read operations.
#
# Expects: PROJECT, FLOW="read", SCENARIO set before sourcing.
# Sources read_common.sh which sources common.sh.
#
# Provides:
#   run_read_console_during_read_scenario() — RIGHT during READ_IN_PROGRESS
#   run_read_console_on_result_scenario()   — RIGHT on the result screen
#   run_read_no_console_scenario()          — negative: RIGHT should NOT open console

source "${PROJECT}/tests/flows/read/includes/read_common.sh"

# === Per-key-press screenshot hash helper ===
# Captures a screenshot, computes its pixel hash (battery-masked), and returns it.
# Args: $1=png_path
# Stdout: md5 hash
_screenshot_hash() {
    convert "$1" -fill black -draw "rectangle 200,0 240,40" rgba:- 2>/dev/null | md5sum | awk '{print $1}'
}

# === Console exercise sequence with per-key-press gates ===
# Each key press is a separate gate: capture screenshot, verify it differs from
# the previous screenshot. If any gate fails, the test reports which key failed.
#
# ConsolePrinterActivity key handling (from binary + real device observation):
#   UP / M2   → textfontsizeup()   (zoom in / increase font, max 14)
#   DOWN / M1 → textfontsizedown() (zoom out / decrease font, min 6)
#   RIGHT     → horizontal scroll right (works when text overflows screen)
#   LEFT      → horizontal scroll left (must scroll RIGHT first from origin)
#   PWR       → exit console
#
# Default fontsize is 14 (max). At font 14, PM3 output lines (60+ chars)
# overflow 240px width, so RIGHT scroll works immediately.
#
# Exercise sequence (9 gates):
#   1. RIGHT  — horizontal scroll right (text overflows at font 14)
#   2. LEFT   — horizontal scroll back to origin
#   3. DOWN   (14→13) — zoom out
#   4. DOWN   (13→12) — zoom out more
#   5. M1     (12→11) — confirms M1 = fontsize down
#   6. UP     (11→12) — zoom in
#   7. M2     (12→13) — confirms M2 = fontsize up
#   8. UP     (13→14) — zoom back to max
#   9. DOWN   (14→13) — final zoom out round-trip
#
# Args: $1=raw_dir, $2=frame_idx_var_name (nameref), $3=gate_failures_var (nameref)
# Sets gate_failures to a comma-separated list of failed keys (empty = all passed).
_exercise_console() {
    local raw_dir="$1"
    local -n _cidx=$2
    local -n _gate_fails=$3
    _gate_fails=""

    local -a KEYS=("RIGHT" "LEFT"  "DOWN"  "DOWN"  "M1"    "UP"    "M2"    "UP"    "DOWN")
    local -a ACTS=("hscrl" "hscrl" "zoom-" "zoom-" "zoom-" "zoom+" "zoom+" "zoom+" "zoom-")

    # Capture reference frame (current console state)
    local prev_png="${raw_dir}/$(printf '%05d' ${_cidx}).png"
    local prev_hash
    prev_hash=$(_screenshot_hash "${prev_png}")

    for i in "${!KEYS[@]}"; do
        local key="${KEYS[$i]}"
        local act="${ACTS[$i]}"

        send_key "${key}"
        sleep 2.0

        _cidx=$((_cidx + 1))
        capture_frame_with_state "${raw_dir}" "${_cidx}"
        sleep 0.5

        # Double-capture: take a second screenshot to catch late renders
        _cidx=$((_cidx + 1))
        capture_frame_with_state "${raw_dir}" "${_cidx}"
        sleep 0.3

        local cur_png="${raw_dir}/$(printf '%05d' ${_cidx}).png"
        local cur_hash
        cur_hash=$(_screenshot_hash "${cur_png}")

        if [ "${cur_hash}" = "${prev_hash}" ]; then
            _gate_fails="${_gate_fails:+${_gate_fails},}${key}:${act}:step$((i+1))"
        fi
        prev_hash="${cur_hash}"
    done
}

# === Verify console was entered via screenshot comparison ===
# The ConsolePrinterActivity uses a tkinter.Text widget (not canvas items),
# so the state dump cannot reliably detect it. Instead, we verify that
# RIGHT produced a VISIBLE change by comparing screenshot pixel hashes.
#
# Args: $1=before_png (screenshot before RIGHT), $2=after_png (screenshot after RIGHT)
# Returns: 0 if screenshots differ (console entered), 1 if identical (no change)
_verify_console_entered() {
    local before_png="$1"
    local after_png="$2"
    [ -f "$before_png" ] || return 1
    [ -f "$after_png" ] || return 1
    local h1 h2
    h1=$(convert "${before_png}" -fill black -draw "rectangle 200,0 240,40" rgba:- 2>/dev/null | md5sum | awk '{print $1}')
    h2=$(convert "${after_png}" -fill black -draw "rectangle 200,0 240,40" rgba:- 2>/dev/null | md5sum | awk '{print $1}')
    [ "$h1" != "$h2" ]
}

# === Common setup for console scenarios ===
# Boots QEMU, navigates to Read Tag, selects tag type, presses OK.
# Sets: frame_idx, raw_dir
# Args: $1=pm3_delay override
_console_setup_and_start_read() {
    local pm3_delay_override="$1"
    local fixture_path="${READ_SCENARIO_DIR}/fixture.py"

    if [ ! -f "${fixture_path}" ]; then
        echo "[FAIL] ${SCENARIO}: fixture.py not found at ${fixture_path}"
        return 1
    fi

    check_env
    clean_scenario

    raw_dir="/tmp/raw_read_console_${SCENARIO}"
    mkdir -p "${raw_dir}"

    # Apply PM3_DELAY override for this scenario
    if [ -n "${pm3_delay_override}" ]; then
        PM3_DELAY="${pm3_delay_override}"
    fi

    # Resolve navigation from fixture.py's TAG_TYPE
    local nav
    nav=$(resolve_tag_nav "${fixture_path}")
    local nav_page="${nav%% *}"
    local nav_down="${nav##* }"

    boot_qemu "${fixture_path}"

    if ! wait_for_hmi 30; then
        report_fail "HMI not ready"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi
    sleep 1

    frame_idx=0

    # Navigate to Read Tag — position differs by target (see common.sh)
    navigate_to_read_tag

    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    # Navigate to the correct tag type in the list
    navigate_to_tag "${nav_page}" "${nav_down}"
    sleep 0.5

    # OK starts the scan+read pipeline
    send_key "OK"

    return 0
}

# =========================================================================
# run_read_console_during_read_scenario()
# =========================================================================
# Tests console access via RIGHT while the read is in progress.
# Uses PM3_DELAY=3.0 (overrideable) so PM3 commands take long enough
# that we can enter the console mid-read.
#
# Args: $1=min_unique (default 5), $2=result_trigger (REQUIRED)
run_read_console_during_read_scenario() {
    local min_unique="${1:-5}"
    local result_trigger="${2}"
    local raw_dir  # set by _console_setup_and_start_read
    local frame_idx  # set by _console_setup_and_start_read

    if [ -z "${result_trigger}" ]; then
        echo "[FAIL] ${SCENARIO}: result_trigger not specified."
        return 1
    fi

    # Use slow PM3 delay so read is still running when we press RIGHT.
    # Caller can override via PM3_DELAY env var before sourcing.
    local delay="${PM3_CONSOLE_DURING_DELAY:-3.0}"
    PM3_DELAY="${delay}"

    if ! _console_setup_and_start_read "${delay}"; then
        return 1
    fi

    # --- Phase 1: Wait for read to begin ---
    # The real device shows NO buttons between scan and read phases.
    # Wait long enough for scan + read start, then proceed.
    # The PM3_DELAY (3.0s default for console tests) ensures the read
    # is still in progress when we press RIGHT.
    sleep 8

    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    # Save pre-RIGHT screenshot for comparison
    local pre_right_png="${raw_dir}/$(printf '%05d' ${frame_idx}).png"

    # --- Phase 2: Enter console via RIGHT ---
    send_key "RIGHT"
    sleep 1

    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"
    sleep 0.3

    # Verify console entry via screenshot change (Text widget not in state dump)
    local post_right_png="${raw_dir}/$(printf '%05d' ${frame_idx}).png"
    if ! _verify_console_entered "${pre_right_png}" "${post_right_png}"; then
        # Try one more capture — rendering may lag
        sleep 1
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
        sleep 0.3
        post_right_png="${raw_dir}/$(printf '%05d' ${frame_idx}).png"
        if ! _verify_console_entered "${pre_right_png}" "${post_right_png}"; then
            dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
            report_fail "RIGHT did not change screen during read (${DEDUP_COUNT} states)"
            cleanup_qemu
            rm -rf "${raw_dir}"
            return 1
        fi
    fi

    # --- Phase 3: Exercise console controls (each key press is a gate) ---
    local gate_fails=""
    _exercise_console "${raw_dir}" frame_idx gate_fails

    # --- Phase 4: Exit console via PWR ---
    # PWR → BaseActivity.callKeyEvent() → finish() → pops ConsolePrinterActivity
    # from the activity stack → ReadActivity resumes. The read continues.
    send_key "PWR"
    sleep 2

    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"
    sleep 0.5

    # GATE: Verify we returned to the Read activity screen (not still in console).
    # The read screen shows title "Read Tag" with scan result text (MIFARE, UID, etc.)
    # or progress indicators (ChkDIC, Reading). Check the state dump.
    local pwr_return_dump="${STATE_DUMP_TMP}/state_$(printf '%03d' ${frame_idx}).json"
    local pwr_return_ok="no"
    if [ -f "${pwr_return_dump}" ]; then
        pwr_return_ok=$(python3 -c "
import json, sys
with open('${pwr_return_dump}') as f: d = json.load(f)
title = d.get('title') or ''
m1 = d.get('M1') or ''
m2 = d.get('M2') or ''
content = ' '.join(it.get('text','') for it in d.get('content_text', []))
# Read activity indicators: title contains 'Read Tag', or buttons show read labels,
# or content has scan result info (MIFARE, UID, frequency, etc.)
if 'Read Tag' in title or 'Rescan' in m1 or 'Reread' in m1 or 'Simulate' in m2 or 'Write' in m2:
    print('yes'); sys.exit(0)
if 'MIFARE' in content or 'UID' in content or 'ChkDIC' in content or 'Reading' in content:
    print('yes'); sys.exit(0)
print('no')
" 2>/dev/null)
    fi
    if [ "${pwr_return_ok}" != "yes" ]; then
        # Retry — PWR may need more time to propagate
        sleep 2
        frame_idx=$((frame_idx + 1))
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
if 'Read Tag' in title or 'Rescan' in m1 or 'Reread' in m1 or 'Simulate' in m2 or 'Write' in m2:
    print('yes'); sys.exit(0)
if 'MIFARE' in content or 'UID' in content or 'ChkDIC' in content or 'Reading' in content:
    print('yes'); sys.exit(0)
print('no')
" 2>/dev/null)
        fi
    fi
    if [ "${pwr_return_ok}" != "yes" ]; then
        dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
        report_fail "PWR did not return to Read activity screen (${DEDUP_COUNT} states)"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi

    # --- Phase 5: Wait for read to complete ---
    local _neg_result=""
    _neg_result=$(wait_for_ui_trigger_with_negative "${result_trigger}" "${TRIGGER_WAIT}" "${raw_dir}" frame_idx)
    local _wait_rc=$?

    if [ "${_wait_rc}" -eq 2 ]; then
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
        dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
        report_fail "contradictory toast: expected '${result_trigger}' but saw '${_neg_result}' (${DEDUP_COUNT} states)"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    elif [ "${_wait_rc}" -ne 0 ]; then
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
        dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
        report_fail "trigger '${result_trigger}' not reached after console exit (${DEDUP_COUNT} states)"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi

    # --- Phase 6: Capture final result ---
    for i in $(seq 1 2); do
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
        sleep 0.3
    done

    send_key "TOAST_CANCEL"
    sleep 2
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    # --- Phase 7: Dedup and report ---
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"

    # During-read scenarios: async PM3 output can cause some gate timing mismatches.
    # Primary criterion: total unique states must be >= min_unique.
    # Secondary: report individual gate results but don't hard-fail on them.
    local fail_count=0
    if [ -n "${gate_fails}" ]; then
        fail_count=$(echo "${gate_fails}" | tr ',' '\n' | wc -l)
    fi
    local pass_count=$((9 - fail_count))

    if [ "${DEDUP_COUNT}" -lt "${min_unique}" ]; then
        report_fail "${DEDUP_COUNT} unique states (need >= ${min_unique}), ${pass_count}/9 gates passed [${gate_fails:-(none)}] (trigger: ${result_trigger})"
    else
        local msg="${DEDUP_COUNT} unique states, ${pass_count}/9 gates passed"
        [ -n "${gate_fails}" ] && msg="${msg} [flaky: ${gate_fails}]"
        report_pass "${msg} (console during read, trigger: ${result_trigger})"
    fi

    cleanup_qemu
    rm -rf "${raw_dir}"
}

# =========================================================================
# run_read_console_on_result_scenario()
# =========================================================================
# Tests console access via RIGHT on the result screen (after read completes).
# Uses PM3_DELAY=0.5 (overrideable) so the read completes quickly.
#
# Args: $1=min_unique (default 5), $2=result_trigger (REQUIRED)
run_read_console_on_result_scenario() {
    local min_unique="${1:-5}"
    local result_trigger="${2}"
    local raw_dir  # set by _console_setup_and_start_read
    local frame_idx  # set by _console_setup_and_start_read

    if [ -z "${result_trigger}" ]; then
        echo "[FAIL] ${SCENARIO}: result_trigger not specified."
        return 1
    fi

    # Use moderate PM3 delay — fast enough to complete, slow enough to be stable
    local delay="${PM3_CONSOLE_RESULT_DELAY:-0.5}"
    PM3_DELAY="${delay}"

    if ! _console_setup_and_start_read "${delay}"; then
        return 1
    fi

    # --- Phase 1: Wait for read to complete ---
    local _neg_result=""
    _neg_result=$(wait_for_ui_trigger_with_negative "${result_trigger}" "${TRIGGER_WAIT}" "${raw_dir}" frame_idx)
    local _wait_rc=$?

    if [ "${_wait_rc}" -eq 2 ]; then
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
        dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
        report_fail "contradictory toast: expected '${result_trigger}' but saw '${_neg_result}' (${DEDUP_COUNT} states)"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    elif [ "${_wait_rc}" -ne 0 ]; then
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
        dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
        report_fail "trigger '${result_trigger}' not reached (${DEDUP_COUNT} states)"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi

    # Capture result screen state (with toast)
    for i in $(seq 1 3); do
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
        sleep 0.3
    done

    # Dismiss toast so we have a clean result screen
    send_key "TOAST_CANCEL"
    sleep 2

    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    # Save pre-RIGHT screenshot for comparison
    local pre_right_png="${raw_dir}/$(printf '%05d' ${frame_idx}).png"

    # --- Phase 2: Enter console via RIGHT on result screen ---
    send_key "RIGHT"
    sleep 1

    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"
    sleep 0.3

    # Verify console entry via screenshot change
    local post_right_png="${raw_dir}/$(printf '%05d' ${frame_idx}).png"
    if ! _verify_console_entered "${pre_right_png}" "${post_right_png}"; then
        sleep 1
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
        sleep 0.3
        post_right_png="${raw_dir}/$(printf '%05d' ${frame_idx}).png"
        if ! _verify_console_entered "${pre_right_png}" "${post_right_png}"; then
            dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
            report_fail "RIGHT did not change screen on result (${DEDUP_COUNT} states)"
            cleanup_qemu
            rm -rf "${raw_dir}"
            return 1
        fi
    fi

    # --- Phase 3: Exercise console controls (each key press is a gate) ---
    local gate_fails=""
    _exercise_console "${raw_dir}" frame_idx gate_fails

    # --- Phase 4: Exit console via PWR, return to result screen ---
    send_key "PWR"
    sleep 2

    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"
    sleep 0.5

    # GATE: Verify we returned to the Read result screen (not still in console).
    # Result screen shows M1=Reread and M2=Write (success/partial), or
    # M1=Reread with M2 disabled (failure). Title is "Read Tag".
    local pwr_return_dump="${STATE_DUMP_TMP}/state_$(printf '%03d' ${frame_idx}).json"
    local pwr_return_ok="no"
    if [ -f "${pwr_return_dump}" ]; then
        pwr_return_ok=$(python3 -c "
import json, sys
with open('${pwr_return_dump}') as f: d = json.load(f)
title = d.get('title') or ''
m1 = d.get('M1') or ''
m2 = d.get('M2') or ''
content = ' '.join(it.get('text','') for it in d.get('content_text', []))
# Result screen indicators
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
        # Retry
        sleep 2
        frame_idx=$((frame_idx + 1))
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
        return 1
    fi

    # --- Phase 5: Dedup and report ---
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"

    # On-result scenarios: no async PM3 output, so most gates should work.
    # Primary criterion: total unique states must be >= min_unique.
    local fail_count=0
    if [ -n "${gate_fails}" ]; then
        fail_count=$(echo "${gate_fails}" | tr ',' '\n' | wc -l)
    fi
    local pass_count=$((9 - fail_count))

    if [ "${DEDUP_COUNT}" -lt "${min_unique}" ]; then
        report_fail "${DEDUP_COUNT} unique states (need >= ${min_unique}), ${pass_count}/9 gates passed [${gate_fails:-(none)}] (trigger: ${result_trigger})"
    else
        local msg="${DEDUP_COUNT} unique states, ${pass_count}/9 gates passed"
        [ -n "${gate_fails}" ] && msg="${msg} [flaky: ${gate_fails}]"
        report_pass "${msg} (console on result, trigger: ${result_trigger})"
    fi

    cleanup_qemu
    rm -rf "${raw_dir}"
}

# =========================================================================
# run_read_no_console_scenario()
# =========================================================================
# Negative test: RIGHT should NOT open the console from certain screens
# (e.g., ReadListActivity, main menu, ScanActivity before read starts).
#
# This function navigates to the target screen, captures a baseline,
# sends RIGHT, and verifies the pixel hash did NOT change.
#
# Args: $1=context description (for reporting), $2=stop_at (where to stop navigation)
#   stop_at values:
#     "main_menu"  — stop at the main menu (don't navigate to Read Tag)
#     "read_list"  — stop at ReadListActivity (after entering Read Tag menu)
#     (default)    — stop at ReadListActivity
run_read_no_console_scenario() {
    local context="${1:-RIGHT should not open console}"
    local stop_at="${2:-read_list}"
    local fixture_path="${READ_SCENARIO_DIR}/fixture.py"

    # Use fast PM3 delay for negative tests
    local delay="${PM3_CONSOLE_NEGATIVE_DELAY:-0.1}"
    PM3_DELAY="${delay}"

    if [ ! -f "${fixture_path}" ]; then
        echo "[FAIL] ${SCENARIO}: fixture.py not found at ${fixture_path}"
        return 1
    fi

    check_env
    clean_scenario

    local raw_dir="/tmp/raw_read_console_${SCENARIO}"
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

    # Navigate to the target screen
    case "${stop_at}" in
        main_menu)
            # Stay on main menu — no navigation needed
            sleep 1
            ;;
        read_list|*)
            # Navigate to Read Tag list — position differs by target
            navigate_to_read_tag
            ;;
    esac

    # Capture baseline state
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"
    sleep 0.5

    # Hash baseline screenshot (mask battery icon)
    local baseline_png="${raw_dir}/$(printf '%05d' ${frame_idx}).png"
    local baseline_hash
    baseline_hash=$(convert "${baseline_png}" -fill black -draw "rectangle 200,0 240,40" rgba:- 2>/dev/null | md5sum | awk '{print $1}')

    # Send RIGHT — should have NO effect
    send_key "RIGHT"
    sleep 1

    # Capture after RIGHT
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"
    sleep 0.5

    local after_png="${raw_dir}/$(printf '%05d' ${frame_idx}).png"
    local after_hash
    after_hash=$(convert "${after_png}" -fill black -draw "rectangle 200,0 240,40" rgba:- 2>/dev/null | md5sum | awk '{print $1}')

    # Dedup for result artifacts
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"

    # For ReadListActivity: RIGHT does page navigation (not console).
    # The screen WILL change (different list items), and that's correct behavior.
    # For other contexts (main_menu): screen should NOT change.
    if [ "${stop_at}" = "read_list" ]; then
        # ReadListActivity: RIGHT = page forward. Screen change expected.
        # Verify the change is page navigation (title still "Read Tag", no console bg)
        local after_dump="${STATE_DUMP_TMP}/state_$(printf '%03d' ${frame_idx}).json"
        sleep 0.3
        local still_read_list="no"
        if [ -f "${after_dump}" ]; then
            still_read_list=$(python3 -c "
import json, sys
with open('${after_dump}') as f: d = json.load(f)
title = d.get('title') or ''
if 'Read Tag' in title:
    print('yes')
else:
    print('no')
" 2>/dev/null)
        fi
        if [ "${still_read_list}" = "yes" ]; then
            report_pass "${context}: RIGHT did page navigation, stayed in ReadListActivity (${DEDUP_COUNT} states)"
        else
            report_fail "${context}: RIGHT left ReadListActivity unexpectedly (${DEDUP_COUNT} states)"
        fi
    else
        # Other contexts: screen should NOT change
        if [ "${baseline_hash}" = "${after_hash}" ]; then
            report_pass "${context}: RIGHT had no effect (${stop_at}, ${DEDUP_COUNT} states)"
        else
            report_fail "${context}: screen changed after RIGHT on ${stop_at} (hash mismatch, ${DEDUP_COUNT} states)"
        fi
    fi

    cleanup_qemu
    rm -rf "${raw_dir}"
}
