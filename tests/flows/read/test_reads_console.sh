#!/bin/bash
# Run all console-related read test scenarios.
# Usage: bash test_reads_console.sh
#        bash test_reads_console.sh [scenario_name]  — run single scenario

PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
RESULTS_DIR="${RESULTS_DIR:-${PROJECT}/tests/flows/_results/${TEST_TARGET:-original}}"

PASS=0
FAIL=0
TOTAL=0

run_one() {
    local scenario="$1"
    local script_path="${PROJECT}/tests/flows/read/scenarios/${scenario}/${scenario}.sh"
    if [ ! -f "${script_path}" ]; then
        echo "[SKIP] ${scenario}: script not found"
        return
    fi
    TOTAL=$((TOTAL+1))
    echo "=== Running: ${scenario} ==="
    bash "${script_path}" 2>&1
    local result_file="${RESULTS_DIR}/read/scenarios/${scenario}/result.txt"
    if [ -f "${result_file}" ] && grep -q "^PASS" "${result_file}"; then
        PASS=$((PASS+1))
    else
        FAIL=$((FAIL+1))
    fi
}

# Console scenarios
CONSOLE_SCENARIOS=(
    # Phase 1: During read
    read_mf1k_console_during_read
    read_ultralight_console_during_read
    read_iclass_console_during_read
    read_em410x_console_during_read
    read_t5577_console_during_read
    # Phase 2: On result screen
    read_mf1k_console_on_success
    read_mf1k_console_on_failure
    read_ultralight_console_on_success
    # Phase 3: Negative
    read_mf1k_no_console_in_list
)

if [ -n "$1" ]; then
    run_one "$1"
else
    for s in "${CONSOLE_SCENARIOS[@]}"; do
        run_one "$s"
    done
fi

echo ""
echo "=== CONSOLE TEST SUMMARY ==="
echo "TOTAL: ${TOTAL}  PASS: ${PASS}  FAIL: ${FAIL}"
