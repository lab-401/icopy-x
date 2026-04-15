#!/bin/bash
# Shared test infrastructure for all flow tests.
# Sources: walk_scan_scenarios.sh + minimal_launch_090.py patterns.
#
# Usage: source this from any test script AFTER setting PROJECT, FLOW, SCENARIO.
# Parallel-safe: set TEST_DISPLAY to assign a unique X display per worker.

set +e

# === Paths ===
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
# Select launcher based on TEST_TARGET:
#   original             → launcher_original.py (boots via application.so, all .so)
#   current              → launcher_current.py  (boots OSS Python UI directly, src/ shadows .so)
#   original_current_ui  → launcher_current.py  (boots OSS Python UI, but from installed IPK dir)
case "${TEST_TARGET:-original}" in
    current|original_current_ui)
        LAUNCHER="${PROJECT}/tools/launcher_current.py"
        ;;
    *)
        LAUNCHER="${PROJECT}/tools/launcher_original.py"
        ;;
esac
FIXTURES="${PROJECT}/tools/pm3_fixtures.py"
KF="/tmp/icopy_keys_${SCENARIO}.txt"

# QEMU environment
QEMU_BIN="${QEMU_BIN:-/home/qx/.local/bin/qemu-arm-static}"
[ -x "${QEMU_BIN}" ] || QEMU_BIN="$(command -v qemu-arm-static 2>/dev/null || echo /usr/bin/qemu-arm-static)"
PYTHON38="/mnt/sdcard/root2/root/usr/local/python-3.8.0/bin/python3.8"
ROOT_FS="/mnt/sdcard/root2/root"
SITE1="/mnt/sdcard/root1/home/pi/.local/lib/python3.8/site-packages"
SITE2="/mnt/sdcard/root2/root/home/pi/.local/lib/python3.8/site-packages"

# Display — override with TEST_DISPLAY for parallel execution
TEST_DISPLAY="${TEST_DISPLAY:-:99}"

# Output paths
# TEST_TARGET controls both module loading (in boot_qemu) and result isolation.
# Results always land in _results/{target}/{flow}/... so original and current
# results NEVER overlap. This is not optional — the target is baked into the path.
TEST_TARGET="${TEST_TARGET:-original}"

# Strip any trailing target name that a caller may have already appended.
_BASE_RESULTS="${RESULTS_DIR:-${PROJECT}/tests/flows/_results}"
_BASE_RESULTS="${_BASE_RESULTS%/original}"
_BASE_RESULTS="${_BASE_RESULTS%/current}"
_BASE_RESULTS="${_BASE_RESULTS%/original_current_ui}"

RESULTS_DIR="${_BASE_RESULTS}/${TEST_TARGET}"
FLOW="${FLOW:-unknown}"
SCENARIO="${SCENARIO:-unknown}"
SCENARIO_DIR="${RESULTS_DIR}/${FLOW}/scenarios/${SCENARIO}"
SCREENSHOTS_DIR="${SCENARIO_DIR}/screenshots"
LOG_FILE="${SCENARIO_DIR}/logs/scenario_log.txt"

# State dump directory (inside QEMU process, collected after)
STATE_DUMP_TMP="/tmp/state_dumps_${SCENARIO}"

# Timing
BOOT_TIMEOUT="${BOOT_TIMEOUT:-80}"
PM3_DELAY="${PM3_DELAY:-3.0}"
CAPTURE_INTERVAL="${CAPTURE_INTERVAL:-0.1}"

# === Environment check ===
check_env() {
    if [ ! -f "${ROOT_FS}/home/pi/ipk_app_main/lib/actmain.so" ]; then
        echo "ERROR: rootfs not mounted. Run tools/setup_qemu_env.sh first."
        exit 1
    fi
    if ! command -v import &>/dev/null; then
        echo "ERROR: ImageMagick 'import' not found."
        exit 1
    fi
}

# === Cleanup from previous run ===
# Respects NO_CLEAN=1 env var: skip result deletion, only ensure dirs exist.
clean_scenario() {
    # In parallel mode, only kill our own QEMU (QEMU_PID set by boot_qemu).
    # In sequential mode (no QEMU_PID yet), skip — the runner handles global cleanup.
    if [ -n "${QEMU_PID}" ] && kill -0 "${QEMU_PID}" 2>/dev/null; then
        kill -9 "${QEMU_PID}" 2>/dev/null
        wait "${QEMU_PID}" 2>/dev/null
    fi
    if [ "${NO_CLEAN}" != "1" ]; then
        rm -rf "${SCENARIO_DIR}" "${STATE_DUMP_TMP}"
    fi
    mkdir -p "${SCREENSHOTS_DIR}" "${SCENARIO_DIR}/logs" "${STATE_DUMP_TMP}"
    > "${KF}"
}

# === Generate PM3 mock file from fixture dict ===
# Args: $1=fixture_dict_name (key in ALL_SCAN_SCENARIOS etc), $2=output_mock_path, $3=source_dict
generate_mock() {
    local fixture_key="$1"
    local mock_path="$2"
    local source_dict="${3:-ALL_SCAN_SCENARIOS}"

    python3 -c "
import sys; sys.path.insert(0, '${PROJECT}/tools')
from pm3_fixtures import ${source_dict}
f = ${source_dict}.get('${fixture_key}', {'_default_return': -1})
default_ret = f.get('_default_return', -1)
lines = ['SCENARIO_RESPONSES = {']
for k, v in f.items():
    if k.startswith('_'): continue
    if isinstance(v, tuple): lines.append(\"    '%s': (%d, '''%s'''),\" % (k, v[0], v[1].replace(\"'''\", \"\\\\'''\")))
    else: lines.append(\"    '%s': %r,\" % (k, v))
lines.append('}'); lines.append('DEFAULT_RETURN = %d' % default_ret)
print('\n'.join(lines))
" > "${mock_path}" 2>/dev/null
}

# === Boot QEMU ===
# Args: $1=mock_file_path
# Sets: QEMU_PID
#
# TEST_TARGET controls which UI modules are loaded:
#   original             — all .so from QEMU rootfs (real v1.0.90 firmware)
#   current              — src/lib + src/middleware shadow .so (full OSS dev)
#   original_current_ui  — installed IPK: our .py UI + original middleware .so
boot_qemu() {
    local mock_path="$1"

    # Base PYTHONPATH: site-packages + original .so module dirs + shims
    local base_pypath="${SITE2}:${SITE1}:${ROOT_FS}/home/pi/ipk_app_main/lib:${ROOT_FS}/home/pi/ipk_app_main/main:${ROOT_FS}/home/pi/ipk_app_main:${PROJECT}/tools/qemu_shims"

    local test_target="${TEST_TARGET:-original}"
    local pypath
    case "${test_target}" in
        current)
            # Dev mode: src/lib + src/middleware + src/main shadow .so from rootfs
            pypath="${PROJECT}/src/lib:${PROJECT}/src/middleware:${PROJECT}/src/main:${PROJECT}/src:${base_pypath}"
            ;;
        original_current_ui)
            # Installed IPK: boot from /home/pi/ipk_app_new/ (post-install location)
            # install.so moves unpkg → ipk_app_new. On real device, next boot
            # swaps ipk_app_new → ipk_app_main. In QEMU we use ipk_app_new directly.
            # The installed lib/ has our .py files + original middleware .so
            # (replaced .so excluded by build script, so .py wins)
            local installed="${ROOT_FS}/home/pi/ipk_app_new"
            pypath="${installed}/lib:${installed}/main:${installed}:${SITE2}:${SITE1}:${PROJECT}/tools/qemu_shims"
            ;;
        *)
            # Original: all .so from rootfs
            pypath="${base_pypath}"
            ;;
    esac

    QEMU_LD_PREFIX="${ROOT_FS}" \
    QEMU_SET_ENV="LD_LIBRARY_PATH=${ROOT_FS}/usr/local/python-3.8.0/lib:${ROOT_FS}/usr/lib/arm-linux-gnueabihf:${ROOT_FS}/lib/arm-linux-gnueabihf:/mnt/sdcard/root1/usr/lib/arm-linux-gnueabihf:/mnt/sdcard/root1/lib/arm-linux-gnueabihf" \
    DISPLAY="${TEST_DISPLAY}" \
    PYTHONPATH="${pypath}" \
    PYTHONUNBUFFERED=1 \
    PM3_SCENARIO_FILE="${mock_path}" \
    PM3_MOCK_DELAY="${PM3_DELAY}" \
    ICOPY_KEY_FILE="${KF}" \
    STATE_DUMP_DIR="${STATE_DUMP_TMP}" \
    QEMU_TRACE="${QEMU_TRACE:-}" \
    timeout "${BOOT_TIMEOUT}" "${QEMU_BIN}" \
        "${PYTHON38}" \
        -u "${LAUNCHER}" > "${LOG_FILE}" 2>&1 &
    QEMU_PID=$!
}

# === Wait for HMI to be ready (Tk window + key bindings) ===
wait_for_hmi() {
    local max_attempts="${1:-30}"
    local poll_png="/tmp/poll_check_${SCENARIO}.png"
    for attempt in $(seq 1 "${max_attempts}"); do
        sleep 2
        # Check: screenshot exists and has content, HMI bindings done
        import -display "${TEST_DISPLAY}" -window root "${poll_png}" 2>/dev/null
        local sz=$(stat -c%s "${poll_png}" 2>/dev/null | head -1 || echo 0)
        local hmi=$(grep -c "\[HMI\]" "${LOG_FILE}" 2>/dev/null | head -1 || echo 0)
        sz=${sz:-0}; hmi=${hmi:-0}
        if [ "$sz" -gt 5000 ] 2>/dev/null && [ "$sz" -lt 17000 ] 2>/dev/null && [ "$hmi" -gt 0 ] 2>/dev/null; then
            rm -f "${poll_png}"
            return 0
        fi
    done
    rm -f "${poll_png}"
    return 1
}

# === Send key command ===
send_key() {
    echo "$1" >> "${KF}"
}

# === Navigate from main menu to Read Tag ===
# v1.0.90 original menu: Auto Copy, Scan Tag, Read Tag (pos 2 → DOWN×2)
# Current reimplemented: Auto Copy, Dump Files, Scan Tag, Read Tag (pos 3 → DOWN×3)
navigate_to_read_tag() {
    if [ "${TEST_TARGET:-original}" = "current" ]; then
        send_key "DOWN"; sleep 0.5
        send_key "DOWN"; sleep 0.5
        send_key "DOWN"; sleep 0.5
    else
        send_key "DOWN"; sleep 0.5
        send_key "DOWN"; sleep 0.5
    fi
    send_key "OK"; sleep 3
}

# === Capture a single frame + trigger state dump ===
# Passes the raw frame index through the STATE_DUMP command so the
# dump file records which frame it belongs to. This survives async
# batching in the key reader / Tk event loop.
# Args: $1=raw_dir, $2=frame_index
capture_frame_with_state() {
    local raw_dir="$1"
    local idx="$2"
    import -display "${TEST_DISPLAY}" -window root "${raw_dir}/$(printf '%05d' $idx).png" 2>/dev/null
    send_key "STATE_DUMP:${idx}"
}

# === Capture screenshots at interval (with state dumps) ===
# Args: $1=raw_dir, $2=count, $3=start_index (default 1), $4=interval (default CAPTURE_INTERVAL)
capture_frames() {
    local raw_dir="$1"
    local count="$2"
    local start="${3:-1}"
    local interval="${4:-${CAPTURE_INTERVAL}}"

    for i in $(seq "${start}" $((start + count - 1))); do
        capture_frame_with_state "${raw_dir}" "$i"
        sleep "${interval}"
    done
}

# === Deduplicate screenshots and assemble scenario_states.json ===
# Args: $1=raw_dir, $2=output_dir
# Outputs: DEDUP_COUNT (number of unique states)
dedup_screenshots() {
    local raw_dir="$1"
    local out_dir="$2"

    DEDUP_COUNT=0
    local prev=""
    # Track which raw frame indices map to unique states
    local -a kept_raw_indices=()

    for f in $(ls "${raw_dir}"/*.png 2>/dev/null | sort); do
        # Hash raw pixel data (strips PNG metadata/compression variance)
        # Mask battery icon (top-right 200,0 to 240,40) before hashing
        local h=$(convert "$f" -fill black -draw "rectangle 200,0 240,40" rgba:- 2>/dev/null | md5sum | awk '{print $1}')
        if [ "$h" != "$prev" ]; then
            DEDUP_COUNT=$((DEDUP_COUNT + 1))
            cp "$f" "${out_dir}/state_$(printf '%03d' ${DEDUP_COUNT}).png"
            prev="$h"
            # Extract raw frame index from filename (e.g., 00042.png → 42)
            local base=$(basename "$f" .png)
            local raw_idx=$((10#$base))
            kept_raw_indices+=("${raw_idx}")
        fi
    done

    # Assemble scenario_states.json from matching state dumps
    _assemble_states_json "${kept_raw_indices[@]}"
}

# === Assemble scenario_states.json from state dumps ===
# Maps raw frame indices to state_NNN.json dumps, picks the best match for each.
_assemble_states_json() {
    local out_json="${SCENARIO_DIR}/scenario_states.json"
    local indices=("$@")

    # Wait briefly for any pending STATE_DUMP writes
    sleep 1

    python3 -c "
import json, glob, os, sys

dump_dir = '${STATE_DUMP_TMP}'
indices = [${indices:+$(IFS=,; echo "${indices[*]}")}]

# Load all state dumps, keyed by raw_frame (explicit mapping from
# STATE_DUMP:N command). Falls back to seq for legacy compatibility.
dumps_by_frame = {}
dumps_by_seq = {}
for f in sorted(glob.glob(os.path.join(dump_dir, 'state_*.json'))):
    try:
        with open(f) as fh:
            d = json.load(fh)
            rf = d.get('raw_frame')
            if rf is not None:
                dumps_by_frame[rf] = d
            dumps_by_seq[d['seq']] = d
    except: pass

# Build output: one entry per unique screenshot state
states = []
for state_idx, raw_frame in enumerate(indices, 1):
    # Prefer explicit raw_frame mapping, fall back to seq-based
    dump = dumps_by_frame.get(raw_frame) or dumps_by_seq.get(raw_frame)
    entry = {
        'state': state_idx,
        'screenshot': 'state_%03d.png' % state_idx,
        'raw_frame': raw_frame,
    }
    if dump:
        entry['activity'] = dump.get('current_activity')
        entry['activity_stack'] = [a['class'] for a in dump.get('activity_stack', [])]
        entry['title'] = dump.get('title')
        entry['M1'] = dump.get('M1')
        entry['M2'] = dump.get('M2')
        entry['M1_active'] = dump.get('M1_active')
        entry['M2_active'] = dump.get('M2_active')
        entry['toast'] = dump.get('toast')
        entry['content_text'] = dump.get('content_text', [])
        entry['scan_cache'] = dump.get('scan_cache')
        entry['executor'] = dump.get('executor', {})
        entry['canvas_items'] = dump.get('canvas_items', [])
    else:
        entry['_note'] = 'no state dump for this frame'
    states.append(entry)

with open('${out_json}', 'w') as f:
    json.dump({'scenario': '${SCENARIO}', 'states': states}, f, indent=2, default=str)
print('[STATES] Assembled %d states → ${out_json}' % len(states))
" 2>&1
}

# === Kill QEMU ===
cleanup_qemu() {
    kill ${QEMU_PID} 2>/dev/null
    wait ${QEMU_PID} 2>/dev/null
    rm -rf "${STATE_DUMP_TMP}"
}

# === Result reporting ===
report_pass() {
    echo "[PASS] ${SCENARIO}: $1"
    echo "PASS: $1" > "${SCENARIO_DIR}/result.txt"
}

report_fail() {
    echo "[FAIL] ${SCENARIO}: $1"
    echo "FAIL: $1" > "${SCENARIO_DIR}/result.txt"
}
