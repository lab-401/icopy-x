#!/bin/bash
# Run console-related read test scenarios in parallel using Xvfb.
# Usage: bash test_reads_console_parallel.sh [MAX_JOBS]
# Default: 12 parallel workers

PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
RESULTS_DIR="${RESULTS_DIR:-${PROJECT}/tests/flows/_results/${TEST_TARGET:-original}}"
MAX_JOBS="${1:-12}"
BASE_DISPLAY=200

# All console scenarios (read + scan + auto-copy)
ALL_SCENARIOS=(
    # Read console scenarios
    "read:read_mf1k_console_during_read"
    "read:read_ultralight_console_during_read"
    "read:read_iclass_console_during_read"
    "read:read_em410x_console_during_read"
    "read:read_t5577_console_during_read"
    "read:read_mf1k_console_on_success"
    "read:read_mf1k_console_on_failure"
    "read:read_mf1k_console_on_partial"
    "read:read_ultralight_console_on_success"
    "read:read_mf1k_no_console_in_list"
    # Scan negative
    "scan:scan_no_console_on_right"
    # Auto-copy console
    "auto-copy:autocopy_mf1k_console_during_read"
    "auto-copy:autocopy_mf1k_no_console_during_scan"
    "auto-copy:autocopy_mf1k_no_console_during_write"
)

TOTAL=${#ALL_SCENARIOS[@]}
echo "=== Console Tests: ${TOTAL} scenarios, max ${MAX_JOBS} parallel ==="

# Launch workers
PIDS=()
SCENARIO_NAMES=()
WORKER=0

for entry in "${ALL_SCENARIOS[@]}"; do
    flow="${entry%%:*}"
    scenario="${entry##*:}"
    WORKER=$((WORKER+1))
    DISPLAY_NUM=$((BASE_DISPLAY + WORKER))

    # Start Xvfb for this worker
    Xvfb ":${DISPLAY_NUM}" -screen 0 320x280x24 -ac -nolisten tcp &>/dev/null &
    XVFB_PID=$!
    sleep 0.3

    # Determine script path
    SCRIPT="${PROJECT}/tests/flows/${flow}/scenarios/${scenario}/${scenario}.sh"

    # Run scenario with isolated display
    (
        export TEST_DISPLAY=":${DISPLAY_NUM}"
        export PROJECT
        bash "${SCRIPT}" 2>&1
        kill ${XVFB_PID} 2>/dev/null
        wait ${XVFB_PID} 2>/dev/null
    ) &
    PIDS+=($!)
    SCENARIO_NAMES+=("${scenario}")

    # Throttle: wait if at max capacity
    if [ "${#PIDS[@]}" -ge "${MAX_JOBS}" ]; then
        wait "${PIDS[0]}" 2>/dev/null
        PIDS=("${PIDS[@]:1}")
        SCENARIO_NAMES=("${SCENARIO_NAMES[@]:1}")
    fi
done

# Wait for remaining
for pid in "${PIDS[@]}"; do
    wait "$pid" 2>/dev/null
done

# Collect results
PASS=0; FAIL=0
for entry in "${ALL_SCENARIOS[@]}"; do
    flow="${entry%%:*}"
    scenario="${entry##*:}"
    result_file="${RESULTS_DIR}/${flow}/scenarios/${scenario}/result.txt"
    if [ -f "${result_file}" ] && grep -q "^PASS" "${result_file}"; then
        echo "[PASS] ${scenario}"
        PASS=$((PASS+1))
    else
        msg="(no result file)"
        [ -f "${result_file}" ] && msg="$(cat "${result_file}")"
        echo "[FAIL] ${scenario}: ${msg}"
        FAIL=$((FAIL+1))
    fi
done

echo ""
echo "=== CONSOLE TEST SUMMARY ==="
echo "TOTAL: ${TOTAL}  PASS: ${PASS}  FAIL: ${FAIL}"
[ "${FAIL}" -eq 0 ] && exit 0 || exit 1
