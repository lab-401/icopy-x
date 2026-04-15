#!/bin/bash
# Master runner: execute ALL 11 flow test suites sequentially.
# Each parallel script uses --clean-flow-only so it only wipes its own results.
#
# Usage:
#   TEST_TARGET=current bash tests/flows/run_all_flows.sh [JOBS]
#
# Results land in: tests/flows/_results/${TEST_TARGET}/*/scenario_summary.txt

set +e

PROJECT="${PROJECT:-$(cd "$(dirname "$0")/../.." && pwd)}"
export PROJECT
export TEST_TARGET="${TEST_TARGET:-original}"
RESULTS_DIR="${PROJECT}/tests/flows/_results/${TEST_TARGET}"
export RESULTS_DIR

JOBS="${1:-$(( $(nproc 2>/dev/null || echo 4) / 2 ))}"
[ "$JOBS" -lt 2 ] && JOBS=2
[ "$JOBS" -gt 16 ] && JOBS=16

echo "========================================"
echo "  FULL SUITE — TEST_TARGET=${TEST_TARGET}"
echo "  Workers: ${JOBS}"
echo "  Results: ${RESULTS_DIR}/"
echo "========================================"

# Clean the target results directory once at the start
rm -rf "${RESULTS_DIR}"
mkdir -p "${RESULTS_DIR}"

SUITE_START=$(date +%s)
SUITE_PASS=0
SUITE_FAIL=0
SUITE_TOTAL=0

cleanup_between_flows() {
    # Kill any stale QEMU or Xvfb processes from previous flow
    pkill -f "qemu-arm-static.*launcher" 2>/dev/null
    pkill -f "Xvfb :1[0-9][0-9]" 2>/dev/null
    pkill -f "Xvfb :2[0-9][0-9]" 2>/dev/null
    pkill -f "Xvfb :3[0-9][0-9]" 2>/dev/null
    sleep 1
}

run_flow() {
    local label="$1"
    local script="$2"
    shift 2
    local args=("$@")

    echo ""
    echo "========================================"
    echo "  FLOW: ${label}"
    echo "========================================"

    if [ ! -f "$script" ]; then
        echo "  SKIP: script not found: $script"
        return
    fi

    cleanup_between_flows
    bash "$script" "${args[@]}" 2>&1

    # Parse results from summary file
    local summary_dir="${RESULTS_DIR}/${label}"
    local summary_file="${summary_dir}/scenario_summary.txt"
    if [ -f "$summary_file" ]; then
        local pass fail total
        # Extract from "TOTAL: N  PASS: N  FAIL: N" line
        total=$(grep -oP 'TOTAL:\s*\K\d+' "$summary_file" | tail -1)
        pass=$(grep -oP 'PASS:\s*\K\d+' "$summary_file" | tail -1)
        fail=$(grep -oP 'FAIL:\s*\K\d+' "$summary_file" | tail -1)
        SUITE_TOTAL=$((SUITE_TOTAL + ${total:-0}))
        SUITE_PASS=$((SUITE_PASS + ${pass:-0}))
        SUITE_FAIL=$((SUITE_FAIL + ${fail:-0}))
        echo "  => ${label}: ${pass:-?}/${total:-?} passed"
    else
        echo "  => ${label}: NO SUMMARY FOUND"
    fi
}

# === Parallel flows (use --no-clean since we cleaned above) ===
run_flow "scan"      "${PROJECT}/tests/flows/scan/test_scans_parallel.sh"      --no-clean "$JOBS"
run_flow "read"      "${PROJECT}/tests/flows/read/test_reads_parallel.sh"      --no-clean "$JOBS"
run_flow "write"     "${PROJECT}/tests/flows/write/test_writes_parallel.sh"    --no-clean "$JOBS"
run_flow "auto-copy" "${PROJECT}/tests/flows/auto-copy/test_auto_copy_parallel.sh" --no-clean "$JOBS"
run_flow "erase"     "${PROJECT}/tests/flows/erase/test_erase_parallel.sh"    --no-clean "$JOBS"
run_flow "simulate"  "${PROJECT}/tests/flows/simulate/test_simulate_parallel.sh" --no-clean "$JOBS"

# === Settings (backlight + volume in one script) ===
run_flow "backlight" "${PROJECT}/tests/flows/test_settings_parallel.sh"       --no-clean "$JOBS"
# Settings script writes both backlight and volume — parse volume too
if [ -f "${RESULTS_DIR}/volume/scenario_summary.txt" ]; then
    total=$(grep -oP 'TOTAL:\s*\K\d+' "${RESULTS_DIR}/volume/scenario_summary.txt" | tail -1)
    pass=$(grep -oP 'PASS:\s*\K\d+' "${RESULTS_DIR}/volume/scenario_summary.txt" | tail -1)
    fail=$(grep -oP 'FAIL:\s*\K\d+' "${RESULTS_DIR}/volume/scenario_summary.txt" | tail -1)
    SUITE_TOTAL=$((SUITE_TOTAL + ${total:-0}))
    SUITE_PASS=$((SUITE_PASS + ${pass:-0}))
    SUITE_FAIL=$((SUITE_FAIL + ${fail:-0}))
    echo "  => volume: ${pass:-?}/${total:-?} passed"
fi

# === Sequential flows (filesystem-exclusive — cannot run in parallel) ===
run_flow "dump_files" "${PROJECT}/tests/flows/dump_files/test_dump_files.sh"
run_flow "diagnosis"  "${PROJECT}/tests/flows/diagnosis/test_diagnosis.sh"
run_flow "sniff"      "${PROJECT}/tests/flows/sniff/test_sniffs.sh"
run_flow "lua-script" "${PROJECT}/tests/flows/lua-script/test_lua.sh"

# === Read console (separate from main read) ===
run_flow "read"       "${PROJECT}/tests/flows/read/test_reads_console_parallel.sh" --no-clean "$JOBS"

# === Minor flows (About, Time Settings, PC Mode) ===
run_flow "about"          "${PROJECT}/tests/flows/about/test_about_parallel.sh"              --no-clean "$JOBS"
run_flow "time_settings"  "${PROJECT}/tests/flows/time_settings/test_time_settings_parallel.sh" --no-clean "$JOBS"
run_flow "pc_mode"        "${PROJECT}/tests/flows/pc_mode/test_pc_mode_parallel.sh"          --no-clean "$JOBS"

# Final cleanup
cleanup_between_flows

SUITE_END=$(date +%s)
SUITE_ELAPSED=$((SUITE_END - SUITE_START))

echo ""
echo "========================================"
echo "  FULL SUITE SUMMARY"
echo "========================================"
echo "  TEST_TARGET: ${TEST_TARGET}"
echo "  TOTAL: ${SUITE_TOTAL}  PASS: ${SUITE_PASS}  FAIL: ${SUITE_FAIL}"
echo "  Duration: ${SUITE_ELAPSED}s"
echo "========================================"

# Write master summary
cat > "${RESULTS_DIR}/master_summary.txt" <<EOFSUM
FULL SUITE — TEST_TARGET=${TEST_TARGET}
TOTAL: ${SUITE_TOTAL}  PASS: ${SUITE_PASS}  FAIL: ${SUITE_FAIL}
Duration: ${SUITE_ELAPSED}s
EOFSUM

[ "$SUITE_FAIL" -gt 0 ] && exit 1
exit 0
