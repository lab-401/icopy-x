#!/bin/bash
# Run ALL volume scenarios sequentially.
# Each scenario gets its own QEMU boot.
# Output: _results/volume/scenarios/<name>/{screenshots/,logs/,result.txt}
# Summary: _results/volume/scenario_summary.txt

set +e
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
RESULTS_DIR="${RESULTS_DIR:-${PROJECT}/tests/flows/_results/${TEST_TARGET:-original}}"
VOLUME_RESULTS="${RESULTS_DIR}/volume"
SUMMARY="${VOLUME_RESULTS}/scenario_summary.txt"

mkdir -p "${VOLUME_RESULTS}"
> "${SUMMARY}"

PASS=0; FAIL=0; TOTAL=0
START_TIME=$(date +%s)

echo "========================================"
echo "  VOLUME FLOW — ALL SCENARIOS"
echo "  Output: ${VOLUME_RESULTS}/"
echo "========================================"

for script in "${PROJECT}/tests/flows/volume/scenarios"/*/volume_*.sh; do
    [ -f "$script" ] || continue
    TOTAL=$((TOTAL + 1))
    scenario_name=$(basename "$(dirname "$script")")

    echo ""
    echo "--- [${TOTAL}] ${scenario_name} ---"

    # Run the scenario
    PROJECT="${PROJECT}" RESULTS_DIR="${RESULTS_DIR}" TEST_TARGET="${TEST_TARGET:-original}" bash "$script"

    # Check result
    result_file="${VOLUME_RESULTS}/scenarios/${scenario_name}/result.txt"
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
