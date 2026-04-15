#!/bin/bash
# Run ALL simulate scenarios sequentially (for debugging).
# Use test_simulate_parallel.sh for normal execution.
set +e

PROJECT="${PROJECT:-$(cd "$(dirname "$0")/../../.." && pwd)}"
RESULTS_DIR="${RESULTS_DIR:-${PROJECT}/tests/flows/_results/${TEST_TARGET:-original}}"
SIM_RESULTS="${RESULTS_DIR}/simulate"

mkdir -p "${SIM_RESULTS}"

SCENARIO_BASE="${PROJECT}/tests/flows/simulate/scenarios"
PASS=0; FAIL=0; TOTAL=0

for scenario_dir in "${SCENARIO_BASE}"/sim_*/; do
    name="$(basename "$scenario_dir")"
    script="${scenario_dir}/${name}.sh"
    [ -f "$script" ] || continue
    TOTAL=$((TOTAL + 1))
    echo "=== [${TOTAL}] ${name} ==="
    bash "$script"
    result_file="${SIM_RESULTS}/scenarios/${name}/result.txt"
    if [ -f "$result_file" ] && grep -q "^PASS" "$result_file"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
    fi
done

echo ""
echo "========================================"
echo "  SIMULATE: ${PASS}/${TOTAL} PASS, ${FAIL} FAIL"
echo "========================================"
