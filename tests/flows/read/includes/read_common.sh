#!/bin/bash
# Read-flow specific test logic.
# Shared by all read scenario scripts.
#
# Expects: PROJECT, FLOW="read", SCENARIO set before sourcing.
# Sources common.sh, then provides run_read_scenario().

FLOW="read"

# Save per-scenario overrides BEFORE common.sh clobbers them
_SCENARIO_BOOT_TIMEOUT="${BOOT_TIMEOUT}"
_SCENARIO_TRIGGER_WAIT="${TRIGGER_WAIT}"

source "${PROJECT}/tests/includes/common.sh"

# Read flow defaults — override common.sh's 80s, but respect per-scenario values
# Errors and toasts typically appear within ~30s. 45s default covers QEMU overhead.
# Force-read tests set their own TRIGGER_WAIT=300 per-scenario (darkside+nested).
PM3_DELAY="${PM3_DELAY:-0.1}"
BOOT_TIMEOUT="${_SCENARIO_BOOT_TIMEOUT:-144}"
TRIGGER_WAIT="${_SCENARIO_TRIGGER_WAIT:-54}"

# Scenario directory containing fixture.py
READ_SCENARIO_DIR="${PROJECT}/tests/flows/read/scenarios/${SCENARIO}"

# === Wait for a UI state transition ===
# Polls STATE_DUMP JSON for a specific string in a specific field.
# Format: "field:value" where field is M1, M2, toast, or content.
#
# Examples from the .so's showButton() / showScanToast() / showReadToast():
#   "M2:Read"      — scan complete, M2 button shows "Read"
#   "M2:Rescan"    — scan failed, M2 shows "Rescan"
#   "M1:Reread"    — read complete, M1 shows "Reread"
#   "M1:Rescan"    — scan complete (any outcome), M1 shows "Rescan"
#   "toast:Tag Found"     — scan found a tag
#   "toast:Read Failed"   — read failed
#   "content:ChkDIC"      — key checking in progress
#
# Args: $1=field:value trigger, $2=max_seconds, $3=raw_dir, $4=frame_idx_var_name
# Returns: 0 if found, 1 if timeout
wait_for_ui_trigger() {
    local trigger="$1"
    local max_wait="${2:-60}"
    local raw_dir="$3"
    local -n _fidx=$4  # nameref to caller's frame index

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
elif field == 'content':
    for item in d.get('content_text', []):
        if value in item.get('text', ''): sys.exit(0)
elif field == 'activity_state':
    if d.get('activity_state', '') == value: sys.exit(0)
sys.exit(1)
" 2>/dev/null; then
                return 0
            fi
        fi
    done
    return 1
}

# === Resolve tag type navigation from fixture.py + read_list_map.json ===
# Reads TAG_TYPE from the scenario's fixture.py, looks up page/down in read_list_map.json.
# Returns "page down" (e.g., "4 2" for page 4, 2 DOWNs).
resolve_tag_nav() {
    local fixture_path="$1"
    python3 -c "
import sys, json
ns = {}
exec(open('${fixture_path}').read(), ns)
tag_type = ns.get('TAG_TYPE', 1)
with open('${PROJECT}/tools/read_list_map.json') as f:
    rlm = json.load(f)
for item in rlm['items']:
    if item['type'] == tag_type:
        print('%d %d' % (item['page'], item['down']))
        sys.exit(0)
# Fallback: type 1 = page 1, down 0
print('1 0')
" 2>/dev/null
}

# === Navigate to a specific item in ReadListActivity ===
# The list has 5 items per page. DOWN×5 scrolls to the next page.
# Args: $1=page (1-based), $2=down (0-based within page)
navigate_to_tag() {
    local page="$1"
    local down="$2"

    # Page advances: each page = 5 DOWNs from page top
    local page_downs=$(( (page - 1) * 5 ))
    local total_downs=$(( page_downs + down ))

    for ((i=0; i<total_downs; i++)); do
        send_key "DOWN"
        sleep 0.3
    done
}

# === Wait for UI trigger with negative (contradictory) toast detection ===
# Like wait_for_ui_trigger but also checks for contradictory toasts.
# Returns: 0=trigger matched, 1=timeout, 2=contradictory toast (prints the bad toast to stdout)
#
# Contradiction rules:
#   Expecting success (File saved / Partial data) → "Read Failed" is contradictory
#   Expecting failure (Read Failed) → "File saved" or "Partial data" is contradictory
#   Expecting scan-fail (Wrong type / No tag found) → "File saved" is contradictory
#   Expecting M1:Sniff → "File saved" is contradictory
wait_for_ui_trigger_with_negative() {
    local trigger="$1"
    local max_wait="${2:-60}"
    local raw_dir="$3"
    local -n _fidx2=$4

    local field="${trigger%%:*}"
    local value="${trigger#*:}"

    # Build negative patterns based on the expected trigger
    local neg_patterns=""
    if [[ "$trigger" == *"File saved"* ]] || [[ "$trigger" == *"Partial data"* ]]; then
        neg_patterns="Read Failed"
    elif [[ "$trigger" == *"Read Failed"* ]]; then
        neg_patterns="File saved"
    elif [[ "$trigger" == "M1:Sniff" ]]; then
        neg_patterns="File saved"
    fi

    for attempt in $(seq 1 $((max_wait * 2))); do
        sleep 0.5
        _fidx2=$((_fidx2 + 1))
        capture_frame_with_state "${raw_dir}" "${_fidx2}"
        sleep 0.2
        local dump_file="${STATE_DUMP_TMP}/state_$(printf '%03d' ${_fidx2}).json"
        if [ -f "$dump_file" ]; then
            local check_result
            check_result=$(python3 -c "
import json, sys
with open('${dump_file}') as f: d = json.load(f)
field, value = '${field}', '${value}'
neg = '${neg_patterns}'
toast = d.get('toast') or ''

# Check negative (contradictory) toast FIRST
if neg and toast and neg in toast:
    print(toast.replace(chr(10), ' '))
    sys.exit(2)

# Check positive trigger
if field in ('M1','M2','toast'):
    actual = d.get(field) or ''
    if value in actual: sys.exit(0)
elif field == 'content':
    for item in d.get('content_text', []):
        if value in item.get('text', ''): sys.exit(0)
elif field == 'activity_state':
    if d.get('activity_state', '') == value: sys.exit(0)
sys.exit(1)
" 2>/dev/null)
            local rc=$?
            if [ "$rc" -eq 0 ]; then
                return 0
            elif [ "$rc" -eq 2 ]; then
                echo "$check_result"
                return 2
            fi
        fi
    done
    return 1
}

# === Run a single read scenario ===
# Args: $1=min_unique (default 3), $2=result_trigger (REQUIRED field:value)
#
# The Read flow is a SINGLE operation triggered by OK on the tag list:
#   OK → scan → read → result toast → M1="Reread", M2="Write"
# There is NO intermediate button press between scan and read.
# The .so handles the full scan+read pipeline automatically.
#
# The result_trigger MUST be the expected toast from resources.so:
#   "toast:File saved"     — read_ok_1 (full success)
#   "toast:Partial data"   — read_ok_2 (partial success)
#   "toast:Read Failed"    — read_failed
#   "toast:No tag found"   — no_tag_found (scan found nothing)
#   "toast:Wrong type"     — no_tag_found2 (scan found wrong type)
#   "toast:Multiple tags"  — tag_multi
#
# The trigger gates pass/fail: if the expected toast never appears, the test FAILS.
# After the trigger, button state is validated (M2="Write" for success, absent for fail).
run_read_scenario() {
    local min_unique="${1:-3}"
    local result_trigger="${2}"
    local raw_dir="/tmp/raw_read_${SCENARIO}"
    local fixture_path="${READ_SCENARIO_DIR}/fixture.py"

    # result_trigger is REQUIRED — no default. Every scenario must specify its expected outcome.
    if [ -z "${result_trigger}" ]; then
        echo "[FAIL] ${SCENARIO}: result_trigger not specified. Every read scenario must declare its expected toast."
        return 1
    fi

    # Validate fixture exists
    if [ ! -f "${fixture_path}" ]; then
        echo "[FAIL] ${SCENARIO}: fixture.py not found at ${fixture_path}"
        return 1
    fi

    # Setup
    check_env
    clean_scenario
    mkdir -p "${raw_dir}"

    # Resolve navigation from fixture.py's TAG_TYPE
    local nav
    nav=$(resolve_tag_nav "${fixture_path}")
    local nav_page="${nav%% *}"
    local nav_down="${nav##* }"

    # Boot with per-scenario fixture.py directly (no runtime merge needed)
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

    # Navigate to Read Tag — position differs by target (see common.sh)
    navigate_to_read_tag
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    # Navigate to the correct tag type in the list
    navigate_to_tag "${nav_page}" "${nav_down}"
    sleep 0.5

    # OK starts the scan+read as one automatic flow. No further presses needed.
    send_key "OK"

    # Wait for the final result toast — scan+read complete automatically.
    # The result_trigger is the EXPECTED toast from the .so (not a button label).
    #
    # NEGATIVE MATCHING: If we expect success ("File saved" / "Partial data") but
    # see "Read Failed!" first, that's an immediate FAIL — the fixture data is wrong.
    # Similarly, if we expect "Read Failed" but see "File saved", that's wrong too.
    # This prevents false positives where the wrong outcome is silently accepted.
    local _neg_result=""
    _neg_result=$(wait_for_ui_trigger_with_negative "${result_trigger}" "${TRIGGER_WAIT}" "${raw_dir}" frame_idx)
    local _wait_rc=$?

    if [ "${_wait_rc}" -eq 2 ]; then
        # Contradictory toast detected
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
        sleep 0.5
        dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
        report_fail "contradictory toast: expected '${result_trigger}' but saw '${_neg_result}' (${DEDUP_COUNT} states)"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    elif [ "${_wait_rc}" -ne 0 ]; then
        # Expected toast never appeared
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
        sleep 0.5
        dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
        report_fail "trigger '${result_trigger}' not reached (${DEDUP_COUNT} states captured)"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi

    # Toast appeared — capture it, then validate button state
    for i in $(seq 1 3); do
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
        sleep 0.3
    done

    # Dismiss result toast, capture clean result
    send_key "TOAST_CANCEL"
    sleep 2
    for i in $(seq 1 3); do
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
        sleep 0.3
    done

    # Deduplicate
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"

    # Sanity check: minimum unique states (smoke test)
    if [ "${DEDUP_COUNT}" -lt "${min_unique}" ]; then
        report_fail "${DEDUP_COUNT} unique states (expected >= ${min_unique}, trigger: ${result_trigger})"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi

    # Validate: content, titles, buttons, toasts, scan_cache (quality gate)
    local expected_path="${READ_SCENARIO_DIR}/expected.json"
    local states_path="${SCENARIO_DIR}/scenario_states.json"
    local validator="${PROJECT}/tests/flows/read/includes/validate_states.py"

    if [ "${SKIP_VALIDATION}" = "1" ]; then
        report_pass "${DEDUP_COUNT} unique states (trigger: ${result_trigger}, validation skipped)"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 0
    fi

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
        report_pass "${DEDUP_COUNT} unique states, validated (trigger: ${result_trigger})"
    else
        report_pass "${DEDUP_COUNT} unique states (trigger: ${result_trigger})"
    fi

    # Cleanup
    cleanup_qemu
    rm -rf "${raw_dir}"
}

# === Run a Force Read scenario (multi-phase) ===
# Phase 1: Navigate to tag, press OK → scan+read starts
# Phase 2: Wait for Warning screen (M1:Sniff)
# Phase 3: Navigate to Force Read (DOWN → M1 on page 2/2 where M1="Force")
# Phase 4: Wait for result toast (Partial data or Read Failed)
#
# Args: $1=min_unique (default 3), $2=result_trigger (REQUIRED), $3=warning_trigger (default M1:Sniff)
run_read_force_scenario() {
    local min_unique="${1:-3}"
    local result_trigger="${2}"
    local warning_trigger="${3:-M1:Sniff}"
    local raw_dir="/tmp/raw_read_${SCENARIO}"
    local fixture_path="${READ_SCENARIO_DIR}/fixture.py"

    if [ -z "${result_trigger}" ]; then
        echo "[FAIL] ${SCENARIO}: result_trigger not specified."
        return 1
    fi
    if [ ! -f "${fixture_path}" ]; then
        echo "[FAIL] ${SCENARIO}: fixture.py not found at ${fixture_path}"
        return 1
    fi

    check_env
    clean_scenario
    mkdir -p "${raw_dir}"

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

    local frame_idx=0

    # Phase 1: Navigate to Read Tag → select tag type → OK
    navigate_to_read_tag
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    navigate_to_tag "${nav_page}" "${nav_down}"
    sleep 0.5
    send_key "OK"

    # Phase 2: Wait for Warning screen
    if ! wait_for_ui_trigger "${warning_trigger}" "${TRIGGER_WAIT}" "${raw_dir}" frame_idx; then
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
        dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
        report_fail "Warning screen '${warning_trigger}' not reached (${DEDUP_COUNT} states)"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi

    # Capture Warning screen state
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"
    sleep 1

    # Phase 3: Navigate to Force Read — DOWN to page 2, then M1 ("Force")
    send_key "DOWN"
    sleep 1
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"
    sleep 0.5

    send_key "M1"
    sleep 2

    # Phase 4: Wait for result toast (Force Read completes)
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
        report_fail "trigger '${result_trigger}' not reached after Force Read (${DEDUP_COUNT} states)"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi

    # Capture result
    for i in $(seq 1 3); do
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
        sleep 0.3
    done
    send_key "TOAST_CANCEL"
    sleep 2
    for i in $(seq 1 3); do
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
        sleep 0.3
    done

    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"

    if [ "${DEDUP_COUNT}" -lt "${min_unique}" ]; then
        report_fail "${DEDUP_COUNT} unique states (expected >= ${min_unique}, trigger: ${result_trigger})"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi

    local expected_path="${READ_SCENARIO_DIR}/expected.json"
    local states_path="${SCENARIO_DIR}/scenario_states.json"
    local validator="${PROJECT}/tests/flows/read/includes/validate_states.py"

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
        report_pass "${DEDUP_COUNT} unique states, validated (trigger: ${result_trigger})"
    else
        report_pass "${DEDUP_COUNT} unique states (trigger: ${result_trigger})"
    fi

    cleanup_qemu
    rm -rf "${raw_dir}"
}
