#!/bin/bash
# Run ALL auto-copy scenarios in parallel using worker pools.
# Each scenario gets its own Xvfb display — fully isolated.
#
# Usage:
#   bash tests/flows/auto-copy/test_auto_copy_parallel.sh [JOBS]
#   bash tests/flows/auto-copy/test_auto_copy_parallel.sh --no-clean [JOBS]
#   bash tests/flows/auto-copy/test_auto_copy_parallel.sh --clean-flow-only [JOBS]
#   JOBS defaults to 50% of cores, min 2, max 12.
#
# Cleanup modes:
#   (default)          Clean ALL _results before run
#   --no-clean         Keep all previous results; only overwrite scenarios that re-run
#   --clean-flow-only  Clean only _results/auto-copy/ before run (preserve read, write, etc.)
#
# Remote usage:
#   bash tests/flows/auto-copy/test_auto_copy_parallel.sh --init-remote USER@HOST
#   bash tests/flows/auto-copy/test_auto_copy_parallel.sh --remote USER@HOST [JOBS]

set +e

PROJECT="${PROJECT:-$(cd "$(dirname "$0")/../../.." && pwd)}"
RESULTS_DIR="${RESULTS_DIR:-${PROJECT}/tests/flows/_results/${TEST_TARGET:-original}}"
AUTOCOPY_RESULTS="${RESULTS_DIR}/auto-copy"
SUMMARY="${AUTOCOPY_RESULTS}/scenario_summary.txt"

# -----------------------------------------------------------------------
# Parse --no-clean / --clean-flow-only flags
# -----------------------------------------------------------------------
CLEAN_MODE="full"
NO_CLEAN=0
for arg in "$@"; do
    case "$arg" in
        --no-clean)       CLEAN_MODE="none"; NO_CLEAN=1; shift ;;
        --clean-flow-only) CLEAN_MODE="flow"; shift ;;
    esac
done
export NO_CLEAN

# -----------------------------------------------------------------------
# --init-remote: reuse the read flow's init (same environment needed)
# -----------------------------------------------------------------------
if [ "$1" = "--init-remote" ]; then
    REMOTE="$2"
    [ -z "$REMOTE" ] && { echo "Usage: $0 --init-remote USER@HOST"; exit 1; }
    # Delegate to the read parallel runner's init (same setup)
    bash "${PROJECT}/tests/flows/read/test_reads_parallel.sh" --init-remote "$REMOTE"
    exit $?
fi

# -----------------------------------------------------------------------
# --remote: sync + run + pull results
# -----------------------------------------------------------------------
if [ "$1" = "--remote" ]; then
    REMOTE="$2"
    RJOBS="${3:-8}"
    [ -z "$REMOTE" ] && { echo "Usage: $0 --remote USER@HOST [JOBS]"; exit 1; }

    SSH_CMD="ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -o ServerAliveInterval=30"
    RSYNC_CMD="rsync -az -e 'ssh -o StrictHostKeyChecking=no'"
    # Try key-based auth first; fall back to sshpass with REMOTE_PASS or interactive prompt
    if ! $SSH_CMD "$REMOTE" 'echo OK' 2>/dev/null | grep -q OK; then
        if [ -n "${REMOTE_PASS}" ]; then
            PASS="${REMOTE_PASS}"
        else
            read -rsp "Password for ${REMOTE}: " PASS; echo
        fi
        SSH_CMD="sshpass -p '${PASS}' $SSH_CMD"
        RSYNC_CMD="sshpass -p '${PASS}' $RSYNC_CMD"
    fi

    echo "=== Syncing project to ${REMOTE} ==="
    eval $RSYNC_CMD \
        --exclude='.git' --exclude='tests/flows/_results' \
        --exclude='__pycache__' --exclude='*.pyc' \
        "${PROJECT}/" "${REMOTE}:icopy-x-reimpl/" 2>&1 | tail -3

    echo "=== Ensuring remote environment is ready ==="
    eval $SSH_CMD "$REMOTE" "'cd ~/icopy-x-reimpl && bash tests/flows/read/test_reads_parallel.sh --init-remote-local'"

    if [ "${CLEAN_MODE}" != "none" ]; then
        echo "=== Cleaning remote results ==="
        eval $SSH_CMD "$REMOTE" "'rm -rf ~/icopy-x-reimpl/tests/flows/_results/auto-copy/scenarios ~/icopy-x-reimpl/tests/flows/_results/auto-copy/scenario_summary.txt'"
    fi

    # Forward clean flags to remote
    local remote_flags=""
    [ "${CLEAN_MODE}" = "none" ] && remote_flags="--no-clean"
    [ "${CLEAN_MODE}" = "flow" ] && remote_flags="--clean-flow-only"

    echo "=== Running ${RJOBS} workers on ${REMOTE} ==="
    eval $SSH_CMD "$REMOTE" "'cd ~/icopy-x-reimpl && bash tests/flows/auto-copy/test_auto_copy_parallel.sh ${remote_flags} ${RJOBS}'"
    RC=$?

    echo "=== Pulling results ==="
    if [ "${CLEAN_MODE}" != "none" ]; then
        rm -rf "${AUTOCOPY_RESULTS}/scenarios" "${AUTOCOPY_RESULTS}/scenario_summary.txt"
    fi
    mkdir -p "${AUTOCOPY_RESULTS}"
    eval $RSYNC_CMD "${REMOTE}:icopy-x-reimpl/tests/flows/_results/auto-copy/" "${AUTOCOPY_RESULTS}/" 2>&1 | tail -3

    echo "=== Results at: ${AUTOCOPY_RESULTS}/ ==="
    [ -f "${AUTOCOPY_RESULTS}/scenario_summary.txt" ] && cat "${AUTOCOPY_RESULTS}/scenario_summary.txt"
    exit $RC
fi

# -----------------------------------------------------------------------
# Local execution
# -----------------------------------------------------------------------

# Auto-scale: 50% of cores. Auto-copy scenarios are multi-phase (scan+read+write+verify)
# and I/O heavy. Cap at 12 workers to avoid Xvfb resource exhaustion.
CORES=$(nproc 2>/dev/null || echo 4)
DEFAULT_JOBS=$(( CORES / 2 ))
[ "$DEFAULT_JOBS" -lt 2 ] && DEFAULT_JOBS=2
[ "$DEFAULT_JOBS" -gt 12 ] && DEFAULT_JOBS=12
JOBS="${1:-${DEFAULT_JOBS}}"

mkdir -p "${AUTOCOPY_RESULTS}"

# Verify dump directories exist (created by --init-remote-local or --init-remote).
if [ ! -d /mnt/upan/dump ]; then
    echo "[WARN] /mnt/upan/dump missing — run --init-remote or setup_qemu_env.sh first"
fi
# Ensure key file exists (needed by hfmfkeys.so for fchk)
[ ! -f /tmp/.keys/mf_tmp_keys ] && mkdir -p /tmp/.keys && python3 -c "
with open('/tmp/.keys/mf_tmp_keys','wb') as f: f.write(b'\xff\xff\xff\xff\xff\xff'*104)
" 2>/dev/null
echo "[SETUP] Dump dirs: $(ls /mnt/upan/dump/ 2>/dev/null | wc -l) types"
echo "[SETUP] Key file: $(ls -la /tmp/.keys/mf_tmp_keys 2>/dev/null | awk '{print $5}') bytes"

# Collect all scenario scripts
SCRIPTS=()
for script in "${PROJECT}/tests/flows/auto-copy/scenarios"/*/autocopy_*.sh; do
    [ -f "$script" ] && SCRIPTS+=("$script")
done
TOTAL=${#SCRIPTS[@]}

echo "========================================"
echo "  AUTO-COPY FLOW — PARALLEL (${JOBS} workers)"
echo "  Scenarios: ${TOTAL}"
echo "  Output: ${AUTOCOPY_RESULTS}/"
echo "========================================"

# Kill any leftover QEMU from previous runs
killall -9 qemu-arm-static 2>/dev/null
sleep 1

# Clean previous results (respects CLEAN_MODE)
if [ "${CLEAN_MODE}" = "full" ] || [ "${CLEAN_MODE}" = "flow" ]; then
    rm -rf "${AUTOCOPY_RESULTS}/scenarios"
fi

START_TIME=$(date +%s)

# --- Worker function ---
run_one() {
    local script="$1"
    local uid="$2"
    local idx="$3"
    local display_num=$((100 + uid))
    local scenario_name
    scenario_name=$(basename "$(dirname "$script")")

    # Start a private Xvfb
    Xvfb ":${display_num}" -screen 0 240x240x24 -ac 2>/dev/null &
    local xvfb_pid=$!

    # Wait for Xvfb ready
    local ready=0
    for i in $(seq 1 20); do
        if xdpyinfo -display ":${display_num}" >/dev/null 2>&1; then
            ready=1; break
        fi
        sleep 0.2
    done
    if [ "$ready" -eq 0 ]; then
        echo "  [${idx}/${TOTAL}] FAIL  ${scenario_name}: Xvfb :${display_num} not ready"
        kill "$xvfb_pid" 2>/dev/null; wait "$xvfb_pid" 2>/dev/null
        mkdir -p "${AUTOCOPY_RESULTS}/scenarios/${scenario_name}"
        echo "FAIL: Xvfb startup failed" > "${AUTOCOPY_RESULTS}/scenarios/${scenario_name}/result.txt"
        return
    fi

    # Run scenario with isolated display
    TEST_DISPLAY=":${display_num}" \
    TEST_TARGET="${TEST_TARGET:-original}" \
    PROJECT="${PROJECT}" \
    RESULTS_DIR="${RESULTS_DIR}" \
    bash "$script" >/dev/null 2>&1

    # Tear down Xvfb
    kill "$xvfb_pid" 2>/dev/null
    wait "$xvfb_pid" 2>/dev/null

    # Check result
    local result_file="${AUTOCOPY_RESULTS}/scenarios/${scenario_name}/result.txt"
    if [ -f "$result_file" ] && grep -q "^PASS" "$result_file"; then
        echo "  [${idx}/${TOTAL}] PASS  ${scenario_name}"
    else
        local msg="unknown"
        [ -f "$result_file" ] && msg=$(head -1 "$result_file")
        echo "  [${idx}/${TOTAL}] FAIL  ${scenario_name}: ${msg}"
    fi
}

export -f run_one
export PROJECT RESULTS_DIR AUTOCOPY_RESULTS TOTAL NO_CLEAN

# --- Dispatch with FIFO semaphore ---
FIFO="/tmp/_par_autocopy_fifo_$$"
mkfifo "$FIFO"
exec 3<>"$FIFO"
rm -f "$FIFO"

for ((i=0; i<JOBS; i++)); do echo >&3; done

idx=0
PIDS=()
for script in "${SCRIPTS[@]}"; do
    read -u 3
    idx=$((idx + 1))
    (
        run_one "$script" "$idx" "$idx"
        echo >&3
    ) &
    PIDS+=($!)
done

for pid in "${PIDS[@]}"; do
    wait "$pid" 2>/dev/null
done
exec 3>&-

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

# --- Assemble summary ---
PASS=0; FAIL=0
> "${SUMMARY}"
for script in "${SCRIPTS[@]}"; do
    scenario_name=$(basename "$(dirname "$script")")
    result_file="${AUTOCOPY_RESULTS}/scenarios/${scenario_name}/result.txt"
    if [ -f "$result_file" ] && grep -q "^PASS" "$result_file"; then
        PASS=$((PASS + 1))
        echo "${scenario_name}: PASS ($(head -1 "$result_file"))" >> "${SUMMARY}"
    else
        FAIL=$((FAIL + 1))
        msg="unknown"
        [ -f "$result_file" ] && msg=$(head -1 "$result_file")
        echo "${scenario_name}: FAIL (${msg})" >> "${SUMMARY}"
    fi
done

echo "" >> "${SUMMARY}"
echo "========================================" >> "${SUMMARY}"
echo "TOTAL: ${TOTAL}  PASS: ${PASS}  FAIL: ${FAIL}" >> "${SUMMARY}"
echo "Duration: ${ELAPSED}s (${JOBS} workers)" >> "${SUMMARY}"
echo "========================================" >> "${SUMMARY}"

cp "${SUMMARY}" "${AUTOCOPY_RESULTS}/autocopy_summary.txt" 2>/dev/null

echo ""
echo "========================================"
echo "  COMPLETE: ${PASS} PASS, ${FAIL} FAIL / ${TOTAL} total"
echo "  Duration: ${ELAPSED}s (${JOBS} parallel workers)"
echo "  Summary: ${SUMMARY}"
echo "========================================"

exit "${FAIL}"
