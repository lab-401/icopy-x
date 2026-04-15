#!/bin/bash
# Backlight-flow specific test logic.
# Shared by all backlight scenario scripts.
#
# Expects: PROJECT, SCENARIO set before sourcing.
# Provides: run_backlight_scenario()
#
# The Backlight flow (verified by real device trace 20260330):
#   Main menu pos 8 → BacklightActivity (3 items)
#     → item 0: "Low"    (setbaklight 10)
#     → item 1: "Middle" (setbaklight 50)
#     → item 2: "High"   (setbaklight 100)
#
# Navigation: UP/DOWN moves selection, instant preview via hmi_driver.setbaklight()
# M2/OK: saves — settings.setBacklight(level) + hmi_driver.setbaklight(level)
# PWR: cancels — recovery_backlight() restores original level, then finish()
#
# conf.ini at /mnt/sdcard/root2/root/home/pi/ipk_app_main/data/conf.ini
# Section [DEFAULT], key "backlight", values 0/1/2
#
# NO PM3 commands — fixture is empty SCENARIO_RESPONSES.

FLOW="backlight"
source "${PROJECT}/tests/includes/common.sh"

# Re-derive paths with FLOW="backlight"
SCENARIO_DIR="${RESULTS_DIR}/${FLOW}/scenarios/${SCENARIO}"
SCREENSHOTS_DIR="${SCENARIO_DIR}/screenshots"
LOG_FILE="${SCENARIO_DIR}/logs/scenario_log.txt"

# Scenario fixture directory
BACKLIGHT_SCENARIO_DIR="${PROJECT}/tests/flows/backlight/scenarios/${SCENARIO}"

# Timing
PM3_DELAY="${PM3_DELAY:-0.5}"
BOOT_TIMEOUT="${BOOT_TIMEOUT:-300}"

# conf.ini path inside rootfs
CONF_INI="/mnt/sdcard/root2/root/home/pi/ipk_app_main/data/conf.ini"

# Ground-truth constants (from resources.so / V1090_SETTINGS_FLOWS_COMPLETE.md)
BACKLIGHT_MENU_POS=8

# === wait_for_ui_trigger ===
# Polls state dumps for a specific UI field:value match.
# Supports: M1, M2, toast, title, content
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

# === Write conf.ini with the specified backlight level ===
# Args: $1 = backlight level (0, 1, or 2)
write_conf_ini() {
    local level="$1"
    python3 -c "
import configparser, os
path = '${CONF_INI}'
cfg = configparser.ConfigParser()
if os.path.exists(path):
    cfg.read(path)
if not cfg.has_section('DEFAULT'):
    pass  # DEFAULT section always exists implicitly in configparser
cfg['DEFAULT']['backlight'] = '${level}'
# Preserve volume if it exists, otherwise default to 0
if 'volume' not in cfg['DEFAULT']:
    cfg['DEFAULT']['volume'] = '0'
with open(path, 'w') as f:
    cfg.write(f)
print('[CONF] Wrote backlight=${level} to ${CONF_INI}')
"
}

# === Wait for a state dump file to appear ===
# STATE_DUMP is processed asynchronously by the Tk main loop.
# Args: $1 = dump file path, $2 = max wait seconds (default 5)
wait_for_dump() {
    local dump_file="$1"
    local max_wait="${2:-5}"
    for i in $(seq 1 $((max_wait * 10))); do
        [ -f "${dump_file}" ] && return 0
        sleep 0.1
    done
    return 1
}

# === Verify BacklightActivity state from a state dump ===
# Checks against ground truth (V1090_SETTINGS_FLOWS_COMPLETE.md):
#   1. title == "Backlight"
#   2. content_text contains all 3 items: Low, Middle, High
#   3. #EEEEEE highlight rectangle at correct Y for expected level
# Args:
#   $1 = state dump JSON file path
#   $2 = expected highlighted level (0=Low, 1=Middle, 2=High)
#   $3 = context label for log messages
# Returns 0 if all checks pass, 1 if any fail.
verify_backlight_state() {
    local dump_file="$1"
    local expected_level="$2"
    local context="${3:-check}"

    if [ ! -f "${dump_file}" ]; then
        echo "[VERIFY FAIL] ${context}: state dump not found at ${dump_file}"
        return 1
    fi

    DUMP_FILE="${dump_file}" EXPECTED_LEVEL="${expected_level}" CONTEXT="${context}" \
    python3 << 'PYEOF'
import json, sys, os

dump_file = os.environ["DUMP_FILE"]
expected_level = int(os.environ["EXPECTED_LEVEL"])
context = os.environ["CONTEXT"]

with open(dump_file) as f:
    d = json.load(f)

# Ground truth: resources.so blline1/2/3
level_names = ["Low", "Middle", "High"]
errors = []

# 1. Title must be "Backlight" (resources.so key: backlight)
title = d.get("title", "")
if "Backlight" not in title:
    errors.append(f'title="{title}", expected "Backlight"')

# 2. All 3 items must be present in content_text
actual_texts = [item.get("text", "") for item in d.get("content_text", [])]
for name in level_names:
    if name not in actual_texts:
        errors.append(f'missing list item "{name}"')

# 3. Selection highlight: #EEEEEE rectangle in item area (y >= 40)
#    Item layout: each item is 40px tall, starting at y=40
#    Level 0 (Low):    y=40..80
#    Level 1 (Middle): y=80..120
#    Level 2 (High):   y=120..160
expected_y = 40 + (expected_level * 40)
hl_found = False
actual_level = -1
for item in d.get("canvas_items", []):
    if item.get("type") == "rectangle" and item.get("fill") == "#EEEEEE":
        coords = item.get("coords", [])
        if len(coords) >= 4 and coords[1] >= 40:
            hl_found = True
            actual_level = int((coords[1] - 40) / 40)
            break

if not hl_found:
    errors.append("no selection highlight (#EEEEEE) found in canvas")
elif actual_level != expected_level:
    errors.append(
        f"highlight at level {actual_level} ({level_names[actual_level]}), "
        f"expected level {expected_level} ({level_names[expected_level]})"
    )

if errors:
    for e in errors:
        print(f"[VERIFY FAIL] {context}: {e}")
    sys.exit(1)
else:
    print(f"[VERIFY OK] {context}: level={expected_level} ({level_names[expected_level]}), "
          f"title=Backlight, items={len(actual_texts)}")
    sys.exit(0)
PYEOF
}

# === Run a single backlight scenario ===
# Args:
#   $1 = starting_level: 0=Low, 1=Middle, 2=High (written to conf.ini)
#   $2 = nav_keys: space-separated UP/DOWN keys (e.g. "DOWN DOWN" or "" for none)
#   $3 = action: "OK" to save, "PWR" to cancel/exit
#   $4 = min_unique: minimum unique states to PASS (default 3)
#   $5 = expected_final_level: level that MUST be highlighted on re-entry (0/1/2)
#        For OK save: the target level after navigation
#        For PWR cancel: the starting_level (recovery_backlight restores original)
run_backlight_scenario() {
    local starting_level="${1:-0}"
    local nav_keys="${2:-}"
    local action="${3:-OK}"
    local min_unique="${4:-3}"
    local expected_final_level="${5:-${starting_level}}"
    local raw_dir="/tmp/raw_backlight_${SCENARIO}"
    local fixture_path="${BACKLIGHT_SCENARIO_DIR}/fixture.py"

    # Validate fixture exists
    if [ ! -f "${fixture_path}" ]; then
        echo "[FAIL] ${SCENARIO}: fixture.py not found at ${fixture_path}"
        return 1
    fi

    # Read CONF_BACKLIGHT from fixture.py
    local conf_level
    conf_level=$(python3 -c "
import sys
sys.path.insert(0, '$(dirname "${fixture_path}")')
with open('${fixture_path}') as f:
    for line in f:
        if line.strip().startswith('CONF_BACKLIGHT'):
            print(line.split('=')[1].strip())
            break
    else:
        print('${starting_level}')
" 2>/dev/null)
    conf_level="${conf_level:-${starting_level}}"

    # Setup
    check_env
    clean_scenario
    mkdir -p "${raw_dir}"

    # Write conf.ini with starting backlight level BEFORE boot
    write_conf_ini "${conf_level}"

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
    local verify_errors=0

    # ==========================================
    # PHASE 1: Navigate to Backlight (menu pos 8)
    # ==========================================
    send_key "GOTO:${BACKLIGHT_MENU_POS}"
    sleep 2

    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    # Wait for BacklightActivity to be visible
    if ! wait_for_ui_trigger "title:Backlight" 15 "${raw_dir}" frame_idx; then
        # Fallback: try manual navigation (DOWN 7x + OK) if GOTO fails
        send_key "PWR"; sleep 1
        for i in $(seq 1 7); do send_key "DOWN"; sleep 0.3; done
        send_key "OK"; sleep 2
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
        if ! wait_for_ui_trigger "title:Backlight" 10 "${raw_dir}" frame_idx; then
            report_fail "Could not reach Backlight screen"
            cleanup_qemu
            rm -rf "${raw_dir}"
            return 1
        fi
    fi

    # Capture initial state (Backlight screen with starting selection)
    sleep 0.5
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    # CHECKPOINT 1: Verify initial selection matches starting_level
    local init_dump="${STATE_DUMP_TMP}/state_$(printf '%03d' ${frame_idx}).json"
    wait_for_dump "${init_dump}" 5
    if verify_backlight_state "${init_dump}" "${starting_level}" "initial"; then
        echo "[CHECK 1/2] Initial selection verified: level ${starting_level}"
    else
        echo "[CHECK 1/2] Initial selection MISMATCH (expected level ${starting_level})"
        verify_errors=$((verify_errors + 1))
    fi

    # ==========================================
    # PHASE 2: Send navigation keys (UP/DOWN for instant preview)
    # ==========================================
    if [ -n "${nav_keys}" ]; then
        for key in ${nav_keys}; do
            send_key "${key}"
            sleep 0.8
            frame_idx=$((frame_idx + 1))
            capture_frame_with_state "${raw_dir}" "${frame_idx}"
        done
    fi

    # ==========================================
    # PHASE 3: Send action key (OK to save, PWR to cancel)
    # ==========================================
    send_key "${action}"
    sleep 1

    # Capture post-action state
    for i in $(seq 1 3); do
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
        sleep 0.3
    done

    # ==========================================
    # PHASE 4: RE-ENTRY VERIFICATION
    # Re-enter BacklightActivity to prove persistence/recovery
    # ==========================================
    sleep 0.5
    send_key "GOTO:${BACKLIGHT_MENU_POS}"
    sleep 2

    if wait_for_ui_trigger "title:Backlight" 15 "${raw_dir}" frame_idx; then
        # Capture the re-entry state
        sleep 0.5
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"

        # CHECKPOINT 2: Verify final selection matches expected_final_level
        local reentry_dump="${STATE_DUMP_TMP}/state_$(printf '%03d' ${frame_idx}).json"
        wait_for_dump "${reentry_dump}" 5
        if verify_backlight_state "${reentry_dump}" "${expected_final_level}" "re-entry"; then
            echo "[CHECK 2/2] Re-entry verification PASSED: level ${expected_final_level}"
        else
            echo "[CHECK 2/2] Re-entry verification FAILED: expected level ${expected_final_level}"
            verify_errors=$((verify_errors + 1))
        fi
    else
        echo "[CHECK 2/2] Re-entry verification FAILED: could not re-enter Backlight screen"
        verify_errors=$((verify_errors + 1))
    fi

    # Exit after re-entry verification
    send_key "PWR"
    sleep 0.5

    # ==========================================
    # PHASE 5: Dedup and evaluate
    # ==========================================
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"

    # Evaluate: BOTH min_unique AND all verify checkpoints must pass
    if [ "${verify_errors}" -gt 0 ]; then
        report_fail "${DEDUP_COUNT} unique states, ${verify_errors} verification error(s)"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    elif [ "${DEDUP_COUNT}" -lt "${min_unique}" ]; then
        report_fail "${DEDUP_COUNT} unique states (expected >= ${min_unique})"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi

    # Validate against expected.json
    local expected_path="${BACKLIGHT_SCENARIO_DIR}/expected.json"
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
        report_pass "${DEDUP_COUNT} unique states, all checkpoints verified, validated"
    else
        report_pass "${DEDUP_COUNT} unique states, all checkpoints verified"
    fi

    # Cleanup
    cleanup_qemu
    rm -rf "${raw_dir}"
}
