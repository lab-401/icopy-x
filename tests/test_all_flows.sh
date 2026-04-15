#!/bin/bash
# Top-level runner: execute all flow tests.
# Runs scan, read, write, auto-copy in order.
# Output: flow_results/results_summary.txt

set +e
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
RESULTS_DIR="${RESULTS_DIR:-${PROJECT}/tests/flows/_results/${TEST_TARGET:-original}}"
OVERALL_SUMMARY="${RESULTS_DIR}/results_summary.txt"

mkdir -p "${RESULTS_DIR}"
> "${OVERALL_SUMMARY}"
START_TIME=$(date +%s)

echo "========================================"
echo "  ALL FLOWS — FULL TEST SUITE"
echo "  Output: ${RESULTS_DIR}/"
echo "========================================"

TOTAL_PASS=0; TOTAL_FAIL=0; TOTAL_RUN=0

# === Run each flow that has a runner ===
# Note: backlight and volume MUST run sequentially (shared conf.ini on rootfs).
# Their runners (test_backlight.sh, test_volume.sh) are sequential by design.
for flow in scan read write auto-copy erase simulate sniff backlight volume console lua-script diagnosis; do
    runner="${PROJECT}/tests/flows/${flow}/test_${flow//-/_}s.sh"
    # Handle naming: auto-copy → test_auto_copys.sh won't exist, check alternatives
    if [ ! -f "$runner" ]; then
        runner="${PROJECT}/tests/flows/${flow}/test_${flow//-/_}.sh"
    fi
    if [ ! -f "$runner" ]; then
        echo ""
        echo "--- ${flow}: no runner found, skipping ---"
        echo "${flow}: SKIPPED (no runner)" >> "${OVERALL_SUMMARY}"
        continue
    fi

    echo ""
    echo "========================================"
    echo "  FLOW: ${flow}"
    echo "========================================"

    PROJECT="${PROJECT}" RESULTS_DIR="${RESULTS_DIR}" bash "$runner"

    # Read flow summary — try ${flow}_summary.txt first, then scenario_summary.txt
    flow_summary="${RESULTS_DIR}/${flow}/${flow}_summary.txt"
    if [ ! -f "$flow_summary" ]; then
        flow_summary="${RESULTS_DIR}/${flow}/scenario_summary.txt"
    fi
    if [ -f "$flow_summary" ]; then
        # Extract PASS/FAIL counts from summary
        line=$(grep "^TOTAL:" "$flow_summary" 2>/dev/null || true)
        if [ -n "$line" ]; then
            fp=$(echo "$line" | grep -oP 'PASS:\s*\K\d+' || echo 0)
            ff=$(echo "$line" | grep -oP 'FAIL:\s*\K\d+' || echo 0)
            ft=$(echo "$line" | grep -oP 'TOTAL:\s*\K\d+' || echo 0)
            TOTAL_PASS=$((TOTAL_PASS + fp))
            TOTAL_FAIL=$((TOTAL_FAIL + ff))
            TOTAL_RUN=$((TOTAL_RUN + ft))
            echo "${flow}: ${fp} PASS, ${ff} FAIL / ${ft} total" >> "${OVERALL_SUMMARY}"
        fi
    else
        echo "${flow}: NO SUMMARY" >> "${OVERALL_SUMMARY}"
    fi
done

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

echo "" >> "${OVERALL_SUMMARY}"
echo "========================================" >> "${OVERALL_SUMMARY}"
echo "ALL FLOWS: ${TOTAL_PASS} PASS, ${TOTAL_FAIL} FAIL / ${TOTAL_RUN} total" >> "${OVERALL_SUMMARY}"
echo "Duration: ${ELAPSED}s" >> "${OVERALL_SUMMARY}"
echo "========================================" >> "${OVERALL_SUMMARY}"

echo ""
echo "========================================"
echo "  ALL FLOWS COMPLETE"
echo "  ${TOTAL_PASS} PASS, ${TOTAL_FAIL} FAIL / ${TOTAL_RUN} total (${ELAPSED}s)"
echo "  Summary: ${OVERALL_SUMMARY}"
echo "========================================"
