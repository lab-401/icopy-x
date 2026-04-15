#!/bin/bash
# Run ALL simulate scenarios in parallel using worker pools.
# Each scenario gets its own Xvfb display — fully isolated.
#
# Usage:
#   bash tests/flows/simulate/test_simulate_parallel.sh [JOBS]
#   bash tests/flows/simulate/test_simulate_parallel.sh --no-clean [JOBS]
#   bash tests/flows/simulate/test_simulate_parallel.sh --clean-flow-only [JOBS]
#   JOBS defaults to 50% of cores, min 2, max 12.
#
# Remote usage:
#   bash tests/flows/simulate/test_simulate_parallel.sh --init-remote USER@HOST
#   bash tests/flows/simulate/test_simulate_parallel.sh --remote USER@HOST [JOBS]

set +e

PROJECT="${PROJECT:-$(cd "$(dirname "$0")/../../.." && pwd)}"
RESULTS_DIR="${RESULTS_DIR:-${PROJECT}/tests/flows/_results/${TEST_TARGET:-original}}"
SIM_RESULTS="${RESULTS_DIR}/simulate"
SUMMARY="${SIM_RESULTS}/scenario_summary.txt"

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

    echo "=== Syncing project to ${REMOTE} ==="
    eval $RSYNC_CMD \
        --exclude='_results' --exclude='.git' --exclude='__pycache__' \
        "${PROJECT}/" "${REMOTE}:~/icopy-x-reimpl/"

    echo "=== Running ${RJOBS} parallel simulate tests on ${REMOTE} ==="
    $SSH_CMD "$REMOTE" "cd ~/icopy-x-reimpl && bash tests/flows/simulate/test_simulate_parallel.sh --clean-flow-only ${RJOBS}" 2>&1 | tee /tmp/remote_sim_log.txt

    echo "=== Pulling results ==="
    mkdir -p "${SIM_RESULTS}"
    eval $RSYNC_CMD "${REMOTE}:~/icopy-x-reimpl/tests/flows/_results/simulate/" "${SIM_RESULTS}/"

    # Show summary
    if [ -f "${SUMMARY}" ]; then
        echo ""
        cat "${SUMMARY}"
    fi
    exit 0
fi

# -----------------------------------------------------------------------
# Local parallel execution
# -----------------------------------------------------------------------

# Clean results based on mode
case "$CLEAN_MODE" in
    full) rm -rf "${RESULTS_DIR}" ;;
    flow) rm -rf "${SIM_RESULTS}" ;;
    none) ;; # keep everything
esac
mkdir -p "${SIM_RESULTS}"

# Collect scenario scripts
SCENARIO_BASE="${PROJECT}/tests/flows/simulate/scenarios"
SCRIPTS=()
for scenario_dir in "${SCENARIO_BASE}"/sim_*/; do
    name="$(basename "$scenario_dir")"
    script="${scenario_dir}/${name}.sh"
    [ -f "$script" ] && SCRIPTS+=("$script")
done

echo "=== Simulate Flow: ${#SCRIPTS[@]} scenarios ==="

# Determine worker count
CORES=$(nproc 2>/dev/null || echo 4)
DEFAULT_JOBS=$(( CORES / 2 ))
[ "$DEFAULT_JOBS" -lt 2 ] && DEFAULT_JOBS=2
[ "$DEFAULT_JOBS" -gt 12 ] && DEFAULT_JOBS=12
JOBS="${1:-${DEFAULT_JOBS}}"
echo "=== Workers: ${JOBS} ==="

START_TIME=$(date +%s)

# === Worker function ===
run_one() {
    local script="$1"
    local uid="$2"
    local display_num=$((100 + uid))
    local scenario_name
    scenario_name="$(basename "$(dirname "$script")")"

    # Start Xvfb for this worker
    Xvfb ":${display_num}" -screen 0 240x240x24 -ac +extension GLX +render -noreset &>/dev/null &
    local xvfb_pid=$!
    sleep 0.5

    # Run scenario with isolated display
    TEST_DISPLAY=":${display_num}" \
    TEST_TARGET="${TEST_TARGET:-original}" \
    PROJECT="${PROJECT}" \
    RESULTS_DIR="${RESULTS_DIR}" \
    NO_CLEAN="${NO_CLEAN}" \
    bash "$script" 2>&1 | while IFS= read -r line; do echo "[${scenario_name}] $line"; done

    # Cleanup Xvfb
    kill "$xvfb_pid" 2>/dev/null
    wait "$xvfb_pid" 2>/dev/null
}

# === FIFO semaphore for worker pool ===
FIFO="/tmp/_par_sim_fifo_$$"
mkfifo "$FIFO"
exec 3<>"$FIFO"
rm -f "$FIFO"

# Fill semaphore with tokens
for ((i=0; i<JOBS; i++)); do echo >&3; done

idx=0
PIDS=()
for script in "${SCRIPTS[@]}"; do
    read -u 3  # Block until token available
    idx=$((idx + 1))
    (
        run_one "$script" "$idx"
        echo >&3  # Return token
    ) &
    PIDS+=($!)
done

# Wait for all workers
for pid in "${PIDS[@]}"; do
    wait "$pid" 2>/dev/null
done
exec 3>&-

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

# -----------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------
PASS=0
FAIL=0
MISSING=0
echo "" > "${SUMMARY}"

for script in "${SCRIPTS[@]}"; do
    scenario_name="$(basename "$(dirname "$script")")"
    result_file="${SIM_RESULTS}/scenarios/${scenario_name}/result.txt"
    if [ -f "$result_file" ]; then
        result="$(cat "$result_file")"
        if echo "$result" | grep -q "^PASS"; then
            PASS=$((PASS + 1))
        else
            FAIL=$((FAIL + 1))
            echo "  FAIL: ${scenario_name}: ${result}" >> "${SUMMARY}"
        fi
    else
        MISSING=$((MISSING + 1))
        echo "  MISSING: ${scenario_name}" >> "${SUMMARY}"
    fi
done

TOTAL=$((PASS + FAIL + MISSING))
{
    echo "========================================"
    echo "  SIMULATE FLOW TEST SUMMARY"
    echo "========================================"
    echo "  Total:   ${TOTAL}"
    echo "  PASS:    ${PASS}"
    echo "  FAIL:    ${FAIL}"
    echo "  MISSING: ${MISSING}"
    echo "  Time:    ${ELAPSED}s (${JOBS} workers)"
    echo "========================================"
} | tee -a "${SUMMARY}"

if [ "$FAIL" -gt 0 ] || [ "$MISSING" -gt 0 ]; then
    echo ""
    echo "Failed/missing scenarios:"
    grep -E "FAIL|MISSING" "${SUMMARY}" | head -20
fi
