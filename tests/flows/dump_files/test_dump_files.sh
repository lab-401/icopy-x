#!/bin/bash
# Run ALL dump_files scenarios sequentially (for debugging).
# Usage: TEST_TARGET=current bash tests/flows/dump_files/test_dump_files.sh

set +e
PROJECT="${PROJECT:-$(cd "$(dirname "$0")/../../.." && pwd)}"

TOTAL=0
PASS=0
FAIL=0

for script in "${PROJECT}/tests/flows/dump_files/scenarios"/dump_*/dump_*.sh; do
    [ -f "$script" ] || continue
    TOTAL=$((TOTAL + 1))
    scenario_name="$(basename "$(dirname "$script")")"
    echo "=== Running: ${scenario_name} ==="

    PROJECT="${PROJECT}" TEST_TARGET="${TEST_TARGET:-current}" bash "$script" 2>&1

    result_file="${PROJECT}/tests/flows/_results/${TEST_TARGET:-current}/dump_files/scenarios/${scenario_name}/result.txt"
    if [ -f "$result_file" ] && grep -q "^PASS" "$result_file"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
    fi
done

echo ""
echo "========================================"
echo "  DUMP FILES: ${PASS}/${TOTAL} PASS, ${FAIL} FAIL"
echo "========================================"
