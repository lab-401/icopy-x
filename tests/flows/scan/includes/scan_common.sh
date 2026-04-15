#!/bin/bash
# Scan-flow specific test logic.
# Shared by all scan scenario scripts.
#
# Expects: PROJECT, FLOW="scan", SCENARIO set before sourcing.
# Sources common.sh, then provides run_scan_scenario().

FLOW="scan"
source "${PROJECT}/tests/includes/common.sh"

# Scenario directory containing fixture.py
SCAN_SCENARIO_DIR="${PROJECT}/tests/flows/scan/scenarios/${SCENARIO}"

# === Run a single scan scenario ===
# Args: $1=min_unique_states (default 3)
run_scan_scenario() {
    local min_unique="${1:-3}"
    local raw_dir="/tmp/raw_scan_${SCENARIO}"
    local fixture_path="${SCAN_SCENARIO_DIR}/fixture.py"

    # Validate fixture exists
    if [ ! -f "${fixture_path}" ]; then
        echo "[FAIL] ${SCENARIO}: fixture.py not found at ${fixture_path}"
        return 1
    fi

    # Setup
    check_env
    clean_scenario
    mkdir -p "${raw_dir}"

    # Boot with per-scenario fixture.py directly
    boot_qemu "${fixture_path}"

    # Wait for HMI
    if ! wait_for_hmi 30; then
        report_fail "HMI not ready"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi
    sleep 1

    # Navigate to Scan Tag (position 2)
    send_key "GOTO:2"

    # Capture scanning phase (20s at 0.1s intervals = 200 frames)
    capture_frames "${raw_dir}" 200 1 0.1

    # Dismiss toast
    send_key "TOAST_CANCEL"
    sleep 2

    # Capture clean result (5s more)
    capture_frames "${raw_dir}" 50 201 0.1

    # Deduplicate
    dedup_screenshots "${raw_dir}" "${SCREENSHOTS_DIR}"

    # Evaluate: state count (smoke test)
    if [ "${DEDUP_COUNT}" -lt "${min_unique}" ]; then
        report_fail "${DEDUP_COUNT} unique states (expected >= ${min_unique})"
        cleanup_qemu
        rm -rf "${raw_dir}"
        return 1
    fi

    # Validate: content, titles, buttons, toasts, scan_cache (quality gate)
    local expected_path="${SCAN_SCENARIO_DIR}/expected.json"
    local states_path="${SCENARIO_DIR}/scenario_states.json"
    local validator="${PROJECT}/tests/flows/scan/includes/validate_states.py"

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
        report_pass "${DEDUP_COUNT} unique states (no expected.json)"
    fi

    # Cleanup
    cleanup_qemu
    rm -rf "${raw_dir}"
}
