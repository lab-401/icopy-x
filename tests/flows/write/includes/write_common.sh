#!/bin/bash
# Write-flow specific test logic.
# Shared by all write scenario scripts.
#
# Expects: PROJECT, SCENARIO set before sourcing.
# Optionally set before sourcing:
#   BOOT_TIMEOUT, READ_TRIGGER_WAIT, WRITE_TRIGGER_WAIT, VERIFY_TRIGGER_WAIT
#
# Provides: run_write_scenario()
#
# The Write flow is a 5-phase pipeline accessed via Read happy-path:
#   Navigate → Read → WarningWriteActivity → WriteActivity → Verify
#
# Phase 1: Navigate to Read Tag, select type, OK → scan+read auto-runs
# Phase 2: Read complete (M2="Write") → press M2 → WarningWriteActivity
# Phase 3: WarningWrite shows (M1="Cancel") → press M2 → WriteActivity
# Phase 4: Write auto-starts → wait for M1="Rewrite" → capture result
# Phase 5: (success paths) Press M2 → verify → capture result

FLOW="write"

# Save per-scenario overrides BEFORE common.sh clobbers them
_SCENARIO_BOOT_TIMEOUT="${BOOT_TIMEOUT}"
_SCENARIO_READ_TRIGGER_WAIT="${READ_TRIGGER_WAIT}"
_SCENARIO_WRITE_TRIGGER_WAIT="${WRITE_TRIGGER_WAIT}"
_SCENARIO_VERIFY_TRIGGER_WAIT="${VERIFY_TRIGGER_WAIT}"

# Source read_common.sh to get: wait_for_ui_trigger, resolve_tag_nav, navigate_to_tag
# This also sources common.sh for: boot_qemu, wait_for_hmi, send_key, capture_*, dedup_*
source "${PROJECT}/tests/flows/read/includes/read_common.sh"

# Override read defaults with write defaults
FLOW="write"
PM3_DELAY=0.5  # Force 0.5s PM3 mock — common.sh default 3.0 is too slow for write verify, 0.1 can race
BOOT_TIMEOUT="${_SCENARIO_BOOT_TIMEOUT:-600}"
READ_TRIGGER_WAIT="${_SCENARIO_READ_TRIGGER_WAIT:-200}"
WRITE_TRIGGER_WAIT="${_SCENARIO_WRITE_TRIGGER_WAIT:-300}"
VERIFY_TRIGGER_WAIT="${_SCENARIO_VERIFY_TRIGGER_WAIT:-60}"
WARNING_TRIGGER_WAIT=30

# Re-derive paths with FLOW="write"
SCENARIO_DIR="${RESULTS_DIR}/${FLOW}/scenarios/${SCENARIO}"
SCREENSHOTS_DIR="${SCENARIO_DIR}/screenshots"
LOG_FILE="${SCENARIO_DIR}/logs/scenario_log.txt"

# Scenario fixture directory
WRITE_SCENARIO_DIR="${PROJECT}/tests/flows/write/scenarios/${SCENARIO}"

# === Override wait_for_ui_trigger to add 'title' field support ===
# The base version in read_common.sh only supports M1, M2, toast, content.
# WriteActivity states need to trigger on title="Data ready!" for WarningWriteActivity.
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
elif field == 'scan_type':
    sc = d.get('scan_cache') or {}
    if str(sc.get('type', '')) == value: sys.exit(0)
elif field == 'activity_state':
    if d.get('activity_state', '') == value: sys.exit(0)
elif field == 'not_content':
    found = False
    for item in d.get('content_text', []):
        if value in item.get('text', ''): found = True; break
    if not found: sys.exit(0)
sys.exit(1)
" 2>/dev/null; then
                return 0
            fi
        fi
    done
    return 1
}

# === Run a single write scenario ===
# Args:
#   $1 = min_unique states (default 5)
#   $2 = expected final trigger (default "toast:Verification successful")
#   $3 = "no_verify" to skip verify phase (for fail scenarios)
#
# The function drives the FULL pipeline:
#   Read happy-path → WarningWrite → Write → (optional) Verify
#
# Triggers used (from resources.py / UI Mapping / real device traces):
#   M2:Write         — Read succeeded, M2 button shows "Write"
#   M1:Cancel        — WarningWriteActivity is visible
#   M2:Rewrite       — Write complete (success or fail), buttons re-enabled
#   toast:Write successful    — write success
#   toast:Write failed        — write failure
#   toast:Verification successful — verify success
#   toast:Verification failed     — verify failure
run_write_scenario() {
    local min_unique="${1:-5}"
    local final_trigger="${2:-toast:Verification successful}"
    local skip_verify="${3:-}"
    local write_toast_trigger="${4:-}"   # optional: verify write toast (e.g. "toast:Write successful")
    local raw_dir="/tmp/raw_write_${SCENARIO}"
    local fixture_path="${WRITE_SCENARIO_DIR}/fixture.py"

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

    # Resolve navigation from fixture.py's TAG_TYPE
    local nav
    nav=$(resolve_tag_nav "${fixture_path}")
    local nav_page="${nav%% *}"
    local nav_down="${nav##* }"

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
    # PHASE 1: Navigate to Read Tag + start read
    # ==========================================
    # Navigate to Read Tag — position differs by target (see common.sh)
    navigate_to_read_tag
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    # Navigate to the correct tag type in the list
    navigate_to_tag "${nav_page}" "${nav_down}"
    sleep 0.5

    # OK starts scan+read as one automatic flow
    send_key "OK"

    # ==========================================
    # PHASE 2: Wait for read to complete
    # ==========================================
    # Happy-path read: M2 shows "Write" when read succeeds
    if ! wait_for_ui_trigger "M2:Write" "${READ_TRIGGER_WAIT}" "${raw_dir}" frame_idx; then
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
        sleep 0.5
        dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
        report_fail "read trigger 'M2:Write' not reached (${DEDUP_COUNT} states captured)"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi

    # Capture read result
    send_key "TOAST_CANCEL"
    sleep 1
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    # Fix dump file: the mock's identical rdsc responses create an invalid dump.
    # Overwrite with structurally valid data (correct UID placement, proper trailers).
    python3 "${PROJECT}/tools/generate_write_dump.py" "${fixture_path}" 2>/dev/null

    # ==========================================
    # PHASE 3: WarningWriteActivity
    # ==========================================
    # Press M2 to enter WarningWriteActivity
    send_key "M2"

    # Wait for WarningWriteActivity — title shows "Data ready!"
    if ! wait_for_ui_trigger "title:Data ready" "${WARNING_TRIGGER_WAIT}" "${raw_dir}" frame_idx; then
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
        sleep 0.5
        dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
        report_fail "WarningWriteActivity trigger 'title:Data ready' not reached (${DEDUP_COUNT} states)"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi

    # Capture warning screen
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    # ==========================================
    # PHASE 4: WriteActivity — start write
    # ==========================================
    # Press M2 to confirm write → transitions to WriteActivity
    send_key "M2"
    sleep 2

    # Send M1 to trigger startWrite() — no-op if write auto-started (buttons disabled)
    send_key "M1"

    # Wait for write to complete — M1 shows "Rewrite" when done
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

    # Validate write toast if write_toast_trigger is set.
    # Prevents false positives where write fails but dedup count is still >= min_unique.
    if [ -n "${write_toast_trigger}" ]; then
        if ! wait_for_ui_trigger "${write_toast_trigger}" 10 "${raw_dir}" frame_idx; then
            dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
            report_fail "write toast '${write_toast_trigger}' not found after write completed (${DEDUP_COUNT} states)"
            cleanup_qemu
            rm -rf "${raw_dir}"
            return 1
        fi
    fi

    # ==========================================
    # PHASE 5: Verify (success paths only)
    # ==========================================
    if [ "${skip_verify}" != "no_verify" ]; then
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
            # Retry: toast may have appeared and auto-dismissed too fast for capture.
            # Dismiss any lingering toast, sleep, try M1 again.
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

    # Validate: titles, toasts, buttons, content (quality gate)
    local expected_path="${WRITE_SCENARIO_DIR}/expected.json"
    local states_path="${SCENARIO_DIR}/scenario_states.json"
    local validator="${PROJECT}/tests/flows/write/includes/validate_states.py"

    if [ -f "${expected_path}" ] && [ -f "${states_path}" ]; then
        local validate_output
        validate_output=$(python3 "${validator}" "${states_path}" "${expected_path}" 2>&1)
        local validate_rc=$?
        echo "${validate_output}"
        if [ "${validate_rc}" -ne 0 ]; then
            report_fail "validation: ${validate_output}"
            cleanup_qemu
            rm -rf "${raw_dir}"
            return 1
        fi
        report_pass "${DEDUP_COUNT} unique states, validated"
    else
        report_pass "${DEDUP_COUNT} unique states"
    fi

    # Cleanup
    cleanup_qemu
    rm -rf "${raw_dir}"
}
