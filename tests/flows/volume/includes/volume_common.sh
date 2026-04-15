#!/bin/bash
# Volume flow test infrastructure.
# Shared by all volume scenario scripts.
#
# Expects: PROJECT, SCENARIO set before sourcing.
# Provides: run_volume_scenario()
#
# The Volume flow (verified by real device trace Session 1):
#   Main menu pos 9 → VolumeActivity (4 items: Off=0, Low=1, Middle=2, High=3)
#   Navigation: UP/DOWN cycles through levels, instant preview each step
#     audio.playVolumeExam() + setKeyAudioEnable on each nav
#   M2/OK saves: settings.setVolume(level) + audio.setVolume + playVolumeExam
#     level==0 → setKeyAudioEnable(false)
#     level>0  → setKeyAudioEnable(true)
#   PWR exits: finish() with NO recovery (unlike Backlight)
#
# No PM3 commands involved.
#
# conf.ini at /mnt/sdcard/root2/root/home/pi/ipk_app_main/data/conf.ini:
#   [DEFAULT]
#   volume = 0|1|2|3
#   backlight = <preserved>

FLOW="volume"

# Save per-scenario overrides BEFORE common.sh sets defaults
_SCENARIO_BOOT_TIMEOUT="${BOOT_TIMEOUT}"

# Source shared infrastructure
source "${PROJECT}/tests/includes/common.sh"

# Apply flow-level defaults
FLOW="volume"
PM3_DELAY="${PM3_DELAY:-0.3}"
BOOT_TIMEOUT="${_SCENARIO_BOOT_TIMEOUT:-120}"

# Re-derive paths with FLOW="volume"
SCENARIO_DIR="${RESULTS_DIR}/${FLOW}/scenarios/${SCENARIO}"
SCREENSHOTS_DIR="${SCENARIO_DIR}/screenshots"
LOG_FILE="${SCENARIO_DIR}/logs/scenario_log.txt"

# Scenario fixture directory
VOLUME_SCENARIO_DIR="${PROJECT}/tests/flows/volume/scenarios/${SCENARIO}"

# conf.ini paths
CONF_INI="/mnt/sdcard/root2/root/home/pi/ipk_app_main/data/conf.ini"

# Ground-truth constants (from resources.so / V1090_SETTINGS_FLOWS_COMPLETE.md)
VOLUME_MENU_POS=9

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

# === Write conf.ini with specified volume level ===
# Args:
#   $1 = volume level (0-3)
# Preserves backlight setting (reads current value, defaults to 2).
write_conf_ini() {
    local vol_level="$1"

    # Read current backlight value (default 2 if not set)
    local bl_level=2
    if [ -f "${CONF_INI}" ]; then
        local existing_bl
        existing_bl=$(python3 -c "
import configparser
c = configparser.ConfigParser()
c.read('${CONF_INI}')
print(c.get('DEFAULT', 'backlight', fallback='2'))
" 2>/dev/null)
        if [ -n "${existing_bl}" ]; then
            bl_level="${existing_bl}"
        fi
    fi

    # Ensure directory exists
    mkdir -p "$(dirname "${CONF_INI}")"

    # Write conf.ini with both keys
    python3 -c "
import configparser
c = configparser.ConfigParser()
c['DEFAULT'] = {
    'backlight': '${bl_level}',
    'volume': '${vol_level}'
}
with open('${CONF_INI}', 'w') as f:
    c.write(f)
" 2>/dev/null
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

# === Verify VolumeActivity state from a state dump ===
# Checks against ground truth (V1090_SETTINGS_FLOWS_COMPLETE.md):
#   1. title == "Volume"
#   2. content_text contains all 4 items: Off, Low, Middle, High
#   3. #EEEEEE highlight rectangle at correct Y for expected level
# Args:
#   $1 = state dump JSON file path
#   $2 = expected highlighted level (0=Off, 1=Low, 2=Middle, 3=High)
#   $3 = context label for log messages
# Returns 0 if all checks pass, 1 if any fail.
verify_volume_state() {
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

# Ground truth: resources.so valueline1/2/3/4
level_names = ["Off", "Low", "Middle", "High"]
errors = []

# 1. Title must be "Volume" (resources.so key: volume)
title = d.get("title", "")
if "Volume" not in title:
    errors.append(f'title="{title}", expected "Volume"')

# 2. All 4 items must be present in content_text
actual_texts = [item.get("text", "") for item in d.get("content_text", [])]
for name in level_names:
    if name not in actual_texts:
        errors.append(f'missing list item "{name}"')

# 3. Selection highlight: #EEEEEE rectangle in item area (y >= 40)
#    Item layout: each item is 40px tall, starting at y=40
#    Level 0 (Off):    y=40..80
#    Level 1 (Low):    y=80..120
#    Level 2 (Middle): y=120..160
#    Level 3 (High):   y=160..200
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
          f"title=Volume, items={len(actual_texts)}")
    sys.exit(0)
PYEOF
}

# === Run a single volume scenario ===
# Args:
#   $1 = starting volume level (0-3, written to conf.ini)
#   $2 = navigation keys (space-separated, e.g. "DOWN DOWN DOWN")
#   $3 = action key: "OK" (save) or "PWR" (exit without recovery)
#   $4 = min unique states (default 2)
#   $5 = expected_final_level: level that MUST be highlighted on re-entry (0-3)
#        For OK save: the target level after navigation
#        For PWR exit: the starting_level (no recovery, conf.ini unchanged)
run_volume_scenario() {
    local start_level="$1"
    local nav_keys="$2"
    local action_key="$3"
    local min_unique="${4:-2}"
    local expected_final_level="${5:-${start_level}}"
    local raw_dir="/tmp/raw_volume_${SCENARIO}"
    local fixture_path="${VOLUME_SCENARIO_DIR}/fixture.py"

    # Validate fixture exists
    if [ ! -f "${fixture_path}" ]; then
        echo "[FAIL] ${SCENARIO}: fixture.py not found at ${fixture_path}"
        return 1
    fi

    # Read CONF_VOLUME from fixture
    local conf_vol
    conf_vol=$(python3 -c "
import sys
sys.path.insert(0, '$(dirname "${fixture_path}")')
import fixture
print(getattr(fixture, 'CONF_VOLUME', ${start_level}))
" 2>/dev/null)
    conf_vol="${conf_vol:-${start_level}}"

    # Setup
    check_env
    clean_scenario
    mkdir -p "${raw_dir}"

    # Write conf.ini with starting volume level BEFORE boot
    write_conf_ini "${conf_vol}"

    # Boot QEMU with fixture (no PM3 commands needed, but fixture still required)
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
    # PHASE 1: Navigate to Volume (menu pos 9)
    # ==========================================
    send_key "GOTO:${VOLUME_MENU_POS}"
    sleep 2

    # Capture initial Volume screen
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    # Wait for VolumeActivity to be visible
    if ! wait_for_ui_trigger "title:Volume" 15 "${raw_dir}" frame_idx; then
        report_fail "VolumeActivity not entered (title not 'Volume')"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi

    # Capture Volume screen state
    sleep 0.5
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    # CHECKPOINT 1: Verify initial selection matches start_level
    local init_dump="${STATE_DUMP_TMP}/state_$(printf '%03d' ${frame_idx}).json"
    wait_for_dump "${init_dump}" 5
    if verify_volume_state "${init_dump}" "${start_level}" "initial"; then
        echo "[CHECK 1/2] Initial selection verified: level ${start_level}"
    else
        echo "[CHECK 1/2] Initial selection MISMATCH (expected level ${start_level})"
        verify_errors=$((verify_errors + 1))
    fi

    # ==========================================
    # PHASE 2: Navigate (preview on each step)
    # ==========================================
    if [ -n "${nav_keys}" ]; then
        for key in ${nav_keys}; do
            send_key "${key}"
            sleep 0.5
            frame_idx=$((frame_idx + 1))
            capture_frame_with_state "${raw_dir}" "${frame_idx}"
        done
    fi

    # Extra capture after navigation settles
    sleep 0.5
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    # ==========================================
    # PHASE 3: Send action key (OK to save, PWR to exit)
    # ==========================================
    send_key "${action_key}"
    sleep 1

    # Capture post-action state
    for i in $(seq 1 3); do
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
        sleep 0.3
    done

    # ==========================================
    # PHASE 4: RE-ENTRY VERIFICATION
    # Re-enter VolumeActivity to prove persistence (M2) or no-save (PWR)
    # ==========================================
    sleep 0.5
    send_key "GOTO:${VOLUME_MENU_POS}"
    sleep 2

    if wait_for_ui_trigger "title:Volume" 15 "${raw_dir}" frame_idx; then
        # Capture the re-entry state
        sleep 0.5
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"

        # CHECKPOINT 2: Verify final selection matches expected_final_level
        local reentry_dump="${STATE_DUMP_TMP}/state_$(printf '%03d' ${frame_idx}).json"
        wait_for_dump "${reentry_dump}" 5
        if verify_volume_state "${reentry_dump}" "${expected_final_level}" "re-entry"; then
            echo "[CHECK 2/2] Re-entry verification PASSED: level ${expected_final_level}"
        else
            echo "[CHECK 2/2] Re-entry verification FAILED: expected level ${expected_final_level}"
            verify_errors=$((verify_errors + 1))
        fi
    else
        echo "[CHECK 2/2] Re-entry verification FAILED: could not re-enter Volume screen"
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
    local expected_path="${VOLUME_SCENARIO_DIR}/expected.json"
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
