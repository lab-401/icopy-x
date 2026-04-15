#!/bin/bash
# Full test suite runner for remote QEMU server.
# Syncs code, runs each flow (parallel where available), pulls results.
#
# Usage: bash tests/run_full_suite_remote.sh USER@HOST [JOBS]

set +e

PROJECT="${PROJECT:-$(cd "$(dirname "$0")/.." && pwd)}"
REMOTE="${1:?Usage: $0 USER@HOST [JOBS]}"
JOBS="${2:-9}"
RESULTS_DIR="${PROJECT}/tests/flows/_results/${TEST_TARGET:-original}"

SSH_CMD="sshpass -p proxmark ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -o ServerAliveInterval=30"
RSYNC_SSH="sshpass -p proxmark ssh -o StrictHostKeyChecking=no"
RSYNC_CMD="rsync -az -e '${RSYNC_SSH}'"

echo "========================================"
echo "  FULL SUITE — REMOTE QEMU"
echo "  Host:    ${REMOTE}"
echo "  Target:  ${TEST_TARGET:-original}"
echo "  Workers: ${JOBS}"
echo "========================================"

# === Step 1: Sync project ===
echo ""
echo "[SYNC] Pushing project to ${REMOTE}..."
eval rsync -az -e \"${RSYNC_SSH}\" \
    --exclude='_results' --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
    "${PROJECT}/" "${REMOTE}:~/icopy-x-reimpl/"
echo "[SYNC] Done."

# === Step 2: Init remote (ensure deps + rootfs) ===
echo ""
echo "[INIT] Checking remote environment..."
$SSH_CMD "$REMOTE" "which qemu-arm-static >/dev/null 2>&1 && which Xvfb >/dev/null 2>&1 && echo 'DEPS OK' || echo 'DEPS MISSING'"

# === Step 3: Run each flow ===
# Flows are dispatched sequentially (one at a time).
# Within each flow, scenarios run in parallel (JOBS workers) where a parallel runner exists.
# Backlight/Volume MUST run sequentially (shared conf.ini).

OVERALL_START=$(date +%s)
OVERALL_PASS=0
OVERALL_FAIL=0
OVERALL_TOTAL=0

# Build the remote runner script
$SSH_CMD "$REMOTE" "cat > ~/icopy-x-reimpl/_run_suite.sh" << 'REMOTESCRIPT'
#!/bin/bash
set +e
cd ~/icopy-x-reimpl
PROJECT="$(pwd)"
RESULTS_DIR="${PROJECT}/tests/flows/_results/${TEST_TARGET:-original}"
JOBS="${1:-9}"

# Clean previous results for THIS target only
rm -rf "${RESULTS_DIR}"
mkdir -p "${RESULTS_DIR}"

# Start global Xvfb on :99 for sequential runners
pkill -f "Xvfb :99" 2>/dev/null
Xvfb :99 -screen 0 240x240x24 -ac +extension GLX +render -noreset &>/dev/null &
XVFB_PID=$!
sleep 0.5
export DISPLAY=:99

OVERALL_PASS=0; OVERALL_FAIL=0; OVERALL_TOTAL=0
SUITE_START=$(date +%s)

run_flow() {
    local flow="$1"
    local runner="$2"
    local jobs="$3"
    local flow_start=$(date +%s)

    echo ""
    echo "========================================"
    echo "  FLOW: ${flow} ($(basename ${runner}), ${jobs} workers)"
    echo "========================================"

    PROJECT="${PROJECT}" RESULTS_DIR="${RESULTS_DIR}" TEST_TARGET="${TEST_TARGET}" bash "${runner}" --clean-flow-only ${jobs} 2>&1 \
        | grep -E "^\[|PASS|FAIL|MISSING|COMPLETE|===|TOTAL|Duration|Workers|Scenarios" \
        | tail -30

    # Find summary
    local summary=""
    for candidate in "${RESULTS_DIR}/${flow}/scenario_summary.txt" "${RESULTS_DIR}/${flow}/${flow}_summary.txt"; do
        [ -f "$candidate" ] && summary="$candidate" && break
    done

    local flow_end=$(date +%s)
    local flow_elapsed=$((flow_end - flow_start))

    if [ -n "$summary" ]; then
        local line=$(grep "^TOTAL:" "$summary" 2>/dev/null || true)
        if [ -n "$line" ]; then
            local fp=$(echo "$line" | grep -oP 'PASS:\s*\K\d+' || echo 0)
            local ff=$(echo "$line" | grep -oP 'FAIL:\s*\K\d+' || echo 0)
            local ft=$(echo "$line" | grep -oP 'TOTAL:\s*\K\d+' || echo 0)
            OVERALL_PASS=$((OVERALL_PASS + fp))
            OVERALL_FAIL=$((OVERALL_FAIL + ff))
            OVERALL_TOTAL=$((OVERALL_TOTAL + ft))
            echo "  >> ${flow}: ${fp} PASS, ${ff} FAIL / ${ft} total (${flow_elapsed}s)"
        else
            echo "  >> ${flow}: summary exists but no TOTAL line (${flow_elapsed}s)"
        fi
    else
        echo "  >> ${flow}: NO SUMMARY (${flow_elapsed}s)"
    fi
}

# --- Flows with parallel runners (use $JOBS workers) ---
for flow_runner in \
    "scan:tests/flows/scan/test_scans_parallel.sh:${JOBS}" \
    "read:tests/flows/read/test_reads_parallel.sh:${JOBS}" \
    "write:tests/flows/write/test_writes_parallel.sh:${JOBS}" \
    "auto-copy:tests/flows/auto-copy/test_auto_copy_parallel.sh:${JOBS}" \
    "erase:tests/flows/erase/test_erase_parallel.sh:${JOBS}" \
    "simulate:tests/flows/simulate/test_simulate_parallel.sh:${JOBS}" \
    "sniff:tests/flows/sniff/test_sniffs.sh:${JOBS}" \
    "lua-script:tests/flows/lua-script/test_lua_parallel.sh:${JOBS}" \
    "time_settings:tests/flows/time_settings/test_time_settings_parallel.sh:${JOBS}" \
    "about:tests/flows/about/test_about_parallel.sh:${JOBS}" \
    "install:tests/flows/install/test_install_parallel.sh:${JOBS}" \
    "pc_mode:tests/flows/pc_mode/test_pc_mode_parallel.sh:${JOBS}" \
    "dump_files:tests/flows/dump_files/test_dump_files.sh:1" \
    "backlight:tests/flows/backlight/test_backlight.sh:1" \
    "volume:tests/flows/volume/test_volume.sh:1" \
    "diagnosis:tests/flows/diagnosis/test_diagnosis.sh:1" \
; do
    flow="${flow_runner%%:*}"
    rest="${flow_runner#*:}"
    runner="${rest%%:*}"
    jobs="${rest#*:}"

    if [ -f "${PROJECT}/${runner}" ]; then
        run_flow "$flow" "${PROJECT}/${runner}" "$jobs"
    else
        echo ""
        echo "  >> ${flow}: SKIPPED (runner not found: ${runner})"
    fi
done

SUITE_END=$(date +%s)
SUITE_ELAPSED=$((SUITE_END - SUITE_START))

echo ""
echo "========================================"
echo "  FULL SUITE COMPLETE"
echo "========================================"
echo "  PASS:    ${OVERALL_PASS}"
echo "  FAIL:    ${OVERALL_FAIL}"
echo "  TOTAL:   ${OVERALL_TOTAL}"
echo "  Time:    ${SUITE_ELAPSED}s"

# Cleanup Xvfb
kill ${XVFB_PID} 2>/dev/null
echo "========================================"
REMOTESCRIPT

echo ""
echo "[RUN] Executing full suite on ${REMOTE} with ${JOBS} workers..."
echo ""

$SSH_CMD "$REMOTE" "TEST_TARGET=${TEST_TARGET:-original} bash ~/icopy-x-reimpl/_run_suite.sh ${JOBS}" 2>&1

# === Step 4: Pull results ===
echo ""
echo "[PULL] Fetching results..."
LOCAL_RESULTS_BASE="${PROJECT}/tests/flows/_results"
mkdir -p "${LOCAL_RESULTS_BASE}"
eval rsync -az -e \"${RSYNC_SSH}\" \
    "${REMOTE}:~/icopy-x-reimpl/tests/flows/_results/" "${LOCAL_RESULTS_BASE}/"
echo "[PULL] Done. Results in ${LOCAL_RESULTS_BASE}/${TEST_TARGET:-original}/"
