#!/bin/bash
# Install-flow specific test logic.
# Shared by all install scenario scripts.
#
# Expects: PROJECT, SCENARIO set before sourcing.
#
# The Install flow (verified by real device trace + framebuffer 20260410):
#   GOTO:10 → AboutActivity
#     → OK → search('/mnt/upan/') for .ipk files
#       → No IPK: toast "No update available", stay on About
#       → IPK found: actstack.start_activity(UpdateActivity, ipk_path)
#         → READY: title "Update", M1="Cancel", M2="Start"
#         → M2/OK: starts install pipeline in background
#         → Pipeline: checkPkg → unpkg → checkVer → install(callback)
#         → Progress: ProgressBar with step messages
#         → Success: "App restarting..." → restart
#         → Failure: "Install failed, code = 0x{NN}"
#         → M1/PWR from READY: finish() back to About
#
# Ground truth:
#   - docs/UI_Mapping/19_install/README.md
#   - docs/Real_Hardware_Intel/trace_update_flow_analysis_20260410.md
#   - decompiled/activity_update_ghidra_raw.txt
#   - decompiled/install_ghidra_raw.txt

FLOW="install"
source "${PROJECT}/tests/includes/common.sh"

# Re-derive paths with FLOW
SCENARIO_DIR="${RESULTS_DIR}/${FLOW}/scenarios/${SCENARIO}"
SCREENSHOTS_DIR="${SCENARIO_DIR}/screenshots"
LOG_FILE="${SCENARIO_DIR}/logs/scenario_log.txt"

INSTALL_SCENARIO_DIR="${PROJECT}/tests/flows/install/scenarios/${SCENARIO}"
FIXTURE_IPK_DIR="${PROJECT}/tests/flows/install/fixtures"

# Timing — MUST override common.sh's 80s default. Install scenarios need
# longer: boot (~30s) + navigation (~15s) + install trigger wait (~45s).
# common.sh already set BOOT_TIMEOUT=80, so we force-override here.
# Individual scenario scripts can override further (e.g. BOOT_TIMEOUT=240).
: "${INSTALL_BOOT_TIMEOUT:=180}"
BOOT_TIMEOUT="${INSTALL_BOOT_TIMEOUT}"
INSTALL_TRIGGER_WAIT="${INSTALL_TRIGGER_WAIT:-30}"

# === File system setup ===
# QEMU path mapping: Under qemu-arm-static with QEMU_LD_PREFIX, file
# READ syscalls (stat, open, opendir) check the rootfs prefix first,
# but MUTATION syscalls (rename, unlink) go to the HOST kernel directly.
# Therefore, fixture IPKs must exist at BOTH locations:
#   - QEMU_UPAN (rootfs) — firmware can read/list/stat the IPK
#   - HOST_UPAN (host)   — firmware can rename/move/delete the IPK

QEMU_UPAN="${ROOT_FS}/mnt/upan"
HOST_UPAN="/mnt/upan"

setup_upan() {
    local fixture_ipk="$1"  # path to fixture .ipk, or empty for no-ipk scenario

    # Ensure directory structure exists at BOTH locations
    mkdir -p "${QEMU_UPAN}/ipk_old" "${HOST_UPAN}/ipk_old"

    # NUKE all .ipk files from BOTH locations
    find "${QEMU_UPAN}" -name "*.ipk" -delete 2>/dev/null
    find "${HOST_UPAN}" -name "*.ipk" -delete 2>/dev/null

    # Clean temp state from any previous install attempt
    rm -rf /tmp/.ipk /tmp/ipk_extract 2>/dev/null

    # Place fixture IPK at BOTH locations
    if [ -n "${fixture_ipk}" ] && [ -f "${fixture_ipk}" ]; then
        cp "${fixture_ipk}" "${QEMU_UPAN}/02150004_1.0.90.ipk"
        cp "${fixture_ipk}" "${HOST_UPAN}/02150004_1.0.90.ipk"
        echo "[INSTALL_SETUP] Placed $(basename ${fixture_ipk}) at rootfs+host ($(stat -c%s "${QEMU_UPAN}/02150004_1.0.90.ipk" 2>/dev/null) bytes)"
    else
        echo "[INSTALL_SETUP] No fixture IPK (no-ipk scenario)"
    fi

    echo "[INSTALL_SETUP] IPKs (rootfs): $(find ${QEMU_UPAN} -name '*.ipk' 2>/dev/null || echo 'NONE')"
}

cleanup_upan() {
    # NUKE all .ipk files from BOTH locations
    find "${QEMU_UPAN}" -name "*.ipk" -delete 2>/dev/null
    find "${HOST_UPAN}" -name "*.ipk" -delete 2>/dev/null

    # Clean temp state
    rm -rf /tmp/.ipk /tmp/ipk_extract 2>/dev/null
    rm -rf "${ROOT_FS}/tmp/.ipk" 2>/dev/null
    rm -rf "${ROOT_FS}/home/pi/ipk_app_new" 2>/dev/null
    rm -rf "${ROOT_FS}/home/pi/unpkg" 2>/dev/null
}

# === wait_for_ui_trigger (reused from about_common.sh) ===
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

# === Run a single install scenario ===
# This is the common entry point. Individual scenario scripts call this
# with scenario-specific parameters.
#
# Args:
#   $1 = fixture_ipk_name: filename in fixtures/ dir (or "NONE" for no-ipk)
#   $2 = gates: pipe-separated gate triggers after reaching UpdateActivity
#              (e.g., "title:Update|M2:Start|KEY:OK|toast:Install failed")
#   $3 = min_unique: minimum unique states to PASS (default 3)
run_install_scenario() {
    local fixture_ipk_name="$1"
    local gates="$2"
    local min_unique="${3:-3}"
    local raw_dir="/tmp/raw_install_${SCENARIO}"
    local fixture_path="${INSTALL_SCENARIO_DIR}/fixture.py"

    # Validate fixture.py exists
    if [ ! -f "${fixture_path}" ]; then
        echo "[FAIL] ${SCENARIO}: fixture.py not found at ${fixture_path}"
        return 1
    fi

    # Setup
    check_env
    clean_scenario
    mkdir -p "${raw_dir}"

    # Place fixture IPK on /mnt/upan/
    if [ "${fixture_ipk_name}" = "NONE" ]; then
        setup_upan ""
    else
        local ipk_path="${FIXTURE_IPK_DIR}/${fixture_ipk_name}"
        if [ ! -f "${ipk_path}" ]; then
            echo "[FAIL] ${SCENARIO}: fixture IPK not found: ${ipk_path}"
            return 1
        fi
        setup_upan "${ipk_path}"
    fi

    # Boot QEMU
    boot_qemu "${fixture_path}"

    if ! wait_for_hmi 40; then
        report_fail "HMI not ready"
        cleanup_qemu; cleanup_upan; rm -rf "${raw_dir}"; return 1
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
        cleanup_qemu; cleanup_upan; rm -rf "${raw_dir}"; return 1
    fi

    # ==========================================
    # GATE 1: Wait for About page 1 to render
    # ==========================================
    if ! wait_for_ui_trigger "content:1/2" 20 "${raw_dir}" frame_idx; then
        sleep 5
    fi

    # ==========================================
    # GATE 2: Navigate to page 2, then press OK
    # Ground truth: about_update_install_fail shows OK only works from page 2.
    # The original firmware's onKeyEvent routes OK→checkUpdate only on page 2.
    # ==========================================
    send_key "DOWN"
    sleep 2
    if ! wait_for_ui_trigger "content:2/2" 15 "${raw_dir}" frame_idx; then
        sleep 3
    fi

    send_key "OK"
    sleep 3
    frame_idx=$((frame_idx + 1))
    capture_frame_with_state "${raw_dir}" "${frame_idx}"

    # ==========================================
    # GATES 2..N: Validate caller-specified triggers
    # ==========================================
    IFS='|' read -ra gate_list <<< "${gates}"
    for gate in "${gate_list[@]}"; do
        gate="$(echo "$gate" | xargs)"  # trim
        [ -z "$gate" ] && continue

        # KEY: prefix = send a key, don't validate
        if [[ "$gate" == KEY:* ]]; then
            local key_to_send="${gate#KEY:}"
            send_key "${key_to_send}"
            sleep 2
            frame_idx=$((frame_idx + 1))
            capture_frame_with_state "${raw_dir}" "${frame_idx}"
            continue
        fi

        # SLEEP: prefix = wait, but with log-monitoring capture.
        # Polls the launcher log for install pipeline progress markers
        # (Chinese strings from install.so) and captures screenshot + state dump
        # each time a new marker appears. This ensures every install step gets
        # a screenshot even though the pipeline runs faster than polling intervals.
        if [[ "$gate" == SLEEP:* ]]; then
            local sleep_secs="${gate#SLEEP:}"
            local sleep_end=$(($(date +%s) + sleep_secs))
            local last_log_pos=0
            [ -f "${LOG_FILE}" ] && last_log_pos=$(wc -c < "${LOG_FILE}")
            while [ "$(date +%s)" -lt "${sleep_end}" ]; do
                sleep 0.3
                # Check for new install progress lines since last check
                if [ -f "${LOG_FILE}" ]; then
                    local new_lines
                    new_lines=$(tail -c +$((last_log_pos + 1)) "${LOG_FILE}" 2>/dev/null | \
                        grep -E '检查字体|正在拷贝|正在更新所有的权限|目录已经存在|copy files|正在重启|App restarting|Font will install|Permission Updating|LUA dep|App install' 2>/dev/null)
                    if [ -n "$new_lines" ]; then
                        while IFS= read -r marker_line; do
                            [ -z "$marker_line" ] && continue
                            frame_idx=$((frame_idx + 1))
                            capture_frame_with_state "${raw_dir}" "${frame_idx}"
                            sleep 0.1
                        done <<< "$new_lines"
                    fi
                    last_log_pos=$(wc -c < "${LOG_FILE}")
                fi
            done
            frame_idx=$((frame_idx + 1))
            capture_frame_with_state "${raw_dir}" "${frame_idx}"
            continue
        fi

        if ! wait_for_ui_trigger "${gate}" "${INSTALL_TRIGGER_WAIT}" "${raw_dir}" frame_idx; then
            dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"
            report_fail "Gate '${gate}' not reached (${DEDUP_COUNT} states)"
            cleanup_qemu; cleanup_upan; rm -rf "${raw_dir}"; return 1
        fi
    done

    # Capture a few final frames
    for i in $(seq 1 3); do
        frame_idx=$((frame_idx + 1))
        capture_frame_with_state "${raw_dir}" "${frame_idx}"
        sleep 0.5
    done

    # ==========================================
    # Final: dedup, validate, report
    # ==========================================
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"

    if [ "${DEDUP_COUNT}" -lt "${min_unique}" ]; then
        report_fail "${DEDUP_COUNT} unique states (expected >= ${min_unique})"
        cleanup_qemu; cleanup_upan; rm -rf "${raw_dir}"; return 1
    fi

    # Validate against expected.json (UI state checks)
    local expected_path="${INSTALL_SCENARIO_DIR}/expected.json"
    local states_path="${SCENARIO_DIR}/scenario_states.json"
    local validator="${PROJECT}/tests/includes/validate_common.py"
    if [ -f "${expected_path}" ] && [ -f "${states_path}" ]; then
        local validate_output
        validate_output=$(python3 "${validator}" "${states_path}" "${expected_path}" 2>&1)
        local validate_rc=$?
        echo "${validate_output}"
        if [ "${validate_rc}" -ne 0 ]; then
            report_fail "validation: ${validate_output}"
            cleanup_qemu; cleanup_upan; rm -rf "${raw_dir}"; return 1
        fi

        # Validate log_markers: grep the launcher log for install pipeline evidence.
        # install.so prints hardcoded Chinese/English strings during each pipeline step.
        # These appear reliably in the launcher log even when UI captures miss them.
        local log_markers
        log_markers=$(python3 -c "
import json
with open('${expected_path}') as f: d = json.load(f)
for m in d.get('log_markers', []): print(m)
" 2>/dev/null)

        if [ -n "${log_markers}" ]; then
            local marker_fail=0
            while IFS= read -r marker; do
                [ -z "${marker}" ] && continue
                if ! grep -q "${marker}" "${LOG_FILE}" 2>/dev/null; then
                    echo "LOG_MARKER_FAIL: '${marker}' not found in launcher log"
                    marker_fail=1
                fi
            done <<< "${log_markers}"
            if [ "${marker_fail}" -ne 0 ]; then
                report_fail "install pipeline did not execute (missing log markers)"
                cleanup_qemu; cleanup_upan; rm -rf "${raw_dir}"; return 1
            fi
            echo "LOG_MARKERS_PASS: all pipeline steps confirmed in launcher log"
        fi

        report_pass "${DEDUP_COUNT} unique states, all gates passed, validated"
    else
        report_pass "${DEDUP_COUNT} unique states, all gates passed"
    fi

    cleanup_qemu
    cleanup_upan
    rm -rf "${raw_dir}"
}
