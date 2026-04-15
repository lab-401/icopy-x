#!/bin/bash
# Run ALL auto-copy scenarios sequentially.
# Usage: bash tests/flows/auto-copy/test_auto_copy.sh

set +e

PROJECT="${PROJECT:-$(cd "$(dirname "$0")/../../.." && pwd)}"
RESULTS_DIR="${RESULTS_DIR:-${PROJECT}/tests/flows/_results/${TEST_TARGET:-original}}"
AUTOCOPY_RESULTS="${RESULTS_DIR}/auto-copy"
SUMMARY="${AUTOCOPY_RESULTS}/scenario_summary.txt"

mkdir -p "${AUTOCOPY_RESULTS}"

# Verify dump directories exist
if [ ! -d /mnt/upan/dump ]; then
    echo "[WARN] /mnt/upan/dump missing — run --init-remote or setup_qemu_env.sh first"
fi
# Ensure key file exists (needed by hfmfkeys.so for fchk)
[ ! -f /tmp/.keys/mf_tmp_keys ] && mkdir -p /tmp/.keys && python3 -c "
with open('/tmp/.keys/mf_tmp_keys','wb') as f: f.write(b'\xff\xff\xff\xff\xff\xff'*104)
" 2>/dev/null

# Collect all scenario scripts
SCRIPTS=()
for script in "${PROJECT}/tests/flows/auto-copy/scenarios"/*/autocopy_*.sh; do
    [ -f "$script" ] && SCRIPTS+=("$script")
done
TOTAL=${#SCRIPTS[@]}

echo "========================================"
echo "  AUTO-COPY FLOW — SEQUENTIAL"
echo "  Scenarios: ${TOTAL}"
echo "  Output: ${AUTOCOPY_RESULTS}/"
echo "========================================"

# Kill any leftover QEMU
killall -9 qemu-arm-static 2>/dev/null
sleep 1

# Start a shared Xvfb if one isn't already running on :99
if ! xdpyinfo -display :99 >/dev/null 2>&1; then
    Xvfb :99 -screen 0 240x240x24 -ac 2>/dev/null &
    XVFB_PID=$!
    sleep 1
fi

START_TIME=$(date +%s)

PASS=0; FAIL=0
> "${SUMMARY}"

idx=0
for script in "${SCRIPTS[@]}"; do
    idx=$((idx + 1))
    scenario_name=$(basename "$(dirname "$script")")

    PROJECT="${PROJECT}" RESULTS_DIR="${RESULTS_DIR}" TEST_DISPLAY=":99" \
        bash "$script" 2>/dev/null

    result_file="${AUTOCOPY_RESULTS}/scenarios/${scenario_name}/result.txt"
    if [ -f "$result_file" ] && grep -q "^PASS" "$result_file"; then
        PASS=$((PASS + 1))
        echo "  [${idx}/${TOTAL}] PASS  ${scenario_name}"
        echo "${scenario_name}: PASS ($(head -1 "$result_file"))" >> "${SUMMARY}"
    else
        FAIL=$((FAIL + 1))
        msg="unknown"
        [ -f "$result_file" ] && msg=$(head -1 "$result_file")
        echo "  [${idx}/${TOTAL}] FAIL  ${scenario_name}: ${msg}"
        echo "${scenario_name}: FAIL (${msg})" >> "${SUMMARY}"
    fi
done

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

echo "" >> "${SUMMARY}"
echo "========================================" >> "${SUMMARY}"
echo "TOTAL: ${TOTAL}  PASS: ${PASS}  FAIL: ${FAIL}" >> "${SUMMARY}"
echo "Duration: ${ELAPSED}s (sequential)" >> "${SUMMARY}"
echo "========================================" >> "${SUMMARY}"

echo ""
echo "========================================"
echo "  COMPLETE: ${PASS} PASS, ${FAIL} FAIL / ${TOTAL} total"
echo "  Duration: ${ELAPSED}s (sequential)"
echo "  Summary: ${SUMMARY}"
echo "========================================"

# Cleanup shared Xvfb if we started it
[ -n "${XVFB_PID}" ] && kill "${XVFB_PID}" 2>/dev/null

exit "${FAIL}"
