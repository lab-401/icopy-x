#!/bin/bash
# Run ALL erase scenarios sequentially.
# Each scenario gets its own QEMU boot.
# Output: _results/erase/scenarios/<name>/{screenshots/,logs/,result.txt}
# Summary: _results/erase/scenario_summary.txt

set +e
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
RESULTS_DIR="${RESULTS_DIR:-${PROJECT}/tests/flows/_results/${TEST_TARGET:-original}}"
ERASE_RESULTS="${RESULTS_DIR}/erase"
SUMMARY="${ERASE_RESULTS}/scenario_summary.txt"

mkdir -p "${ERASE_RESULTS}"
> "${SUMMARY}"

PASS=0; FAIL=0; TOTAL=0
START_TIME=$(date +%s)

echo "========================================"
echo "  ERASE TAG FLOW — ALL SCENARIOS"
echo "  Output: ${ERASE_RESULTS}/"
echo "========================================"

for script in "${PROJECT}/tests/flows/erase/scenarios"/*/erase_*.sh; do
    [ -f "$script" ] || continue
    TOTAL=$((TOTAL + 1))
    scenario_name=$(basename "$(dirname "$script")")

    echo ""
    echo "--- [${TOTAL}] ${scenario_name} ---"

    # Run the scenario
    PROJECT="${PROJECT}" RESULTS_DIR="${RESULTS_DIR}" TEST_TARGET="${TEST_TARGET:-original}" bash "$script"

    # Check result
    result_file="${ERASE_RESULTS}/scenarios/${scenario_name}/result.txt"
    if [ -f "$result_file" ] && grep -q "^PASS" "$result_file"; then
        PASS=$((PASS + 1))
        echo "${scenario_name}: PASS ($(cat "$result_file" | head -1))" >> "${SUMMARY}"
    else
        FAIL=$((FAIL + 1))
        msg="unknown"
        [ -f "$result_file" ] && msg=$(head -1 "$result_file")
        echo "${scenario_name}: FAIL (${msg})" >> "${SUMMARY}"
    fi
done

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

# Write summary footer
echo "" >> "${SUMMARY}"
echo "========================================" >> "${SUMMARY}"
echo "TOTAL: ${TOTAL}  PASS: ${PASS}  FAIL: ${FAIL}" >> "${SUMMARY}"
echo "Duration: ${ELAPSED}s" >> "${SUMMARY}"
echo "========================================" >> "${SUMMARY}"

echo ""
echo "========================================"
echo "  COMPLETE: ${PASS} PASS, ${FAIL} FAIL / ${TOTAL} total (${ELAPSED}s)"
echo "  Summary: ${SUMMARY}"
echo "========================================"
