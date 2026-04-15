#!/bin/bash
# Run ALL backlight + volume scenarios in parallel using worker pools.
# Each scenario gets its own Xvfb display — fully isolated.
#
# Usage:
#   bash tests/flows/test_settings_parallel.sh [JOBS]
#   bash tests/flows/test_settings_parallel.sh --clean-flow-only [JOBS]
#
# Remote usage:
#   bash tests/flows/test_settings_parallel.sh --init-remote USER@HOST
#   bash tests/flows/test_settings_parallel.sh --remote USER@HOST [JOBS]

set +e

PROJECT="${PROJECT:-$(cd "$(dirname "$0")/../.." && pwd)}"
RESULTS_DIR="${RESULTS_DIR:-${PROJECT}/tests/flows/_results/${TEST_TARGET:-original}}"
BL_RESULTS="${RESULTS_DIR}/backlight"
VOL_RESULTS="${RESULTS_DIR}/volume"

# -----------------------------------------------------------------------
# Parse flags
# -----------------------------------------------------------------------
CLEAN_MODE="full"
NO_CLEAN=0
for arg in "$@"; do
    case "$arg" in
        --no-clean)        CLEAN_MODE="none"; NO_CLEAN=1; shift ;;
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
    RJOBS="${3:-12}"
    [ -z "$REMOTE" ] && { echo "Usage: $0 --remote USER@HOST [JOBS]"; exit 1; }

    SSH_CMD="ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -o ServerAliveInterval=30"
    RSYNC_CMD="rsync -az -e 'ssh -o StrictHostKeyChecking=no'"

    echo "=== Syncing project to ${REMOTE} ==="
    eval $RSYNC_CMD \
        --exclude='_results' --exclude='.git' --exclude='__pycache__' \
        "${PROJECT}/" "${REMOTE}:~/icopy-x-reimpl/"

    echo "=== Running ${RJOBS} parallel settings tests on ${REMOTE} ==="
    $SSH_CMD "$REMOTE" "cd ~/icopy-x-reimpl && bash tests/flows/test_settings_parallel.sh --clean-flow-only ${RJOBS}" 2>&1 | tee /tmp/remote_settings_log.txt

    echo "=== Pulling results ==="
    mkdir -p "${BL_RESULTS}" "${VOL_RESULTS}"
    eval $RSYNC_CMD "${REMOTE}:~/icopy-x-reimpl/tests/flows/_results/backlight/" "${BL_RESULTS}/"
    eval $RSYNC_CMD "${REMOTE}:~/icopy-x-reimpl/tests/flows/_results/volume/" "${VOL_RESULTS}/"

    # Show summary
    for sum in "${BL_RESULTS}/scenario_summary.txt" "${VOL_RESULTS}/scenario_summary.txt"; do
        [ -f "$sum" ] && cat "$sum"
    done
    exit 0
fi

# -----------------------------------------------------------------------
# Local parallel execution
# -----------------------------------------------------------------------

# Clean results based on mode
case "$CLEAN_MODE" in
    full) rm -rf "${BL_RESULTS}" "${VOL_RESULTS}" ;;
    flow) rm -rf "${BL_RESULTS}" "${VOL_RESULTS}" ;;
    none) ;; # keep everything
esac
mkdir -p "${BL_RESULTS}" "${VOL_RESULTS}"

# Collect scenario scripts from BOTH flows
SCRIPTS=()

for scenario_dir in "${PROJECT}/tests/flows/backlight/scenarios"/backlight_*/; do
    name="$(basename "$scenario_dir")"
    script="${scenario_dir}/${name}.sh"
    [ -f "$script" ] && SCRIPTS+=("$script")
done

for scenario_dir in "${PROJECT}/tests/flows/volume/scenarios"/volume_*/; do
    name="$(basename "$scenario_dir")"
    script="${scenario_dir}/${name}.sh"
    [ -f "$script" ] && SCRIPTS+=("$script")
done

echo "========================================"
echo "  SETTINGS FLOW (Backlight + Volume)"
echo "  Scenarios: ${#SCRIPTS[@]}"
echo "========================================"

# Settings scenarios MUST run sequentially (JOBS=1) because they share
# a persistent conf.ini file. Parallel execution causes race conditions
# where one worker's config write is overwritten by another before boot.
JOBS=1
echo "  Workers: ${JOBS}"
echo "========================================"

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
FIFO="/tmp/_par_settings_fifo_$$"
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
# Summary — Backlight
# -----------------------------------------------------------------------
BL_PASS=0; BL_FAIL=0; BL_MISSING=0
BL_SUMMARY="${BL_RESULTS}/scenario_summary.txt"
> "${BL_SUMMARY}"

for scenario_dir in "${PROJECT}/tests/flows/backlight/scenarios"/backlight_*/; do
    scenario_name="$(basename "$scenario_dir")"
    result_file="${BL_RESULTS}/scenarios/${scenario_name}/result.txt"
    if [ -f "$result_file" ]; then
        result="$(cat "$result_file")"
        if echo "$result" | grep -q "^PASS"; then
            BL_PASS=$((BL_PASS + 1))
            echo "${scenario_name}: ${result}" >> "${BL_SUMMARY}"
        else
            BL_FAIL=$((BL_FAIL + 1))
            echo "${scenario_name}: ${result}" >> "${BL_SUMMARY}"
        fi
    else
        BL_MISSING=$((BL_MISSING + 1))
        echo "${scenario_name}: MISSING" >> "${BL_SUMMARY}"
    fi
done

# -----------------------------------------------------------------------
# Summary — Volume
# -----------------------------------------------------------------------
VOL_PASS=0; VOL_FAIL=0; VOL_MISSING=0
VOL_SUMMARY="${VOL_RESULTS}/scenario_summary.txt"
> "${VOL_SUMMARY}"

for scenario_dir in "${PROJECT}/tests/flows/volume/scenarios"/volume_*/; do
    scenario_name="$(basename "$scenario_dir")"
    result_file="${VOL_RESULTS}/scenarios/${scenario_name}/result.txt"
    if [ -f "$result_file" ]; then
        result="$(cat "$result_file")"
        if echo "$result" | grep -q "^PASS"; then
            VOL_PASS=$((VOL_PASS + 1))
            echo "${scenario_name}: ${result}" >> "${VOL_SUMMARY}"
        else
            VOL_FAIL=$((VOL_FAIL + 1))
            echo "${scenario_name}: ${result}" >> "${VOL_SUMMARY}"
        fi
    else
        VOL_MISSING=$((VOL_MISSING + 1))
        echo "${scenario_name}: MISSING" >> "${VOL_SUMMARY}"
    fi
done

TOTAL_PASS=$((BL_PASS + VOL_PASS))
TOTAL_FAIL=$((BL_FAIL + VOL_FAIL))
TOTAL_MISSING=$((BL_MISSING + VOL_MISSING))
TOTAL=$((TOTAL_PASS + TOTAL_FAIL + TOTAL_MISSING))

echo ""
echo "========================================"
echo "  BACKLIGHT: ${BL_PASS} PASS / $((BL_PASS + BL_FAIL + BL_MISSING)) total"
echo "  VOLUME:    ${VOL_PASS} PASS / $((VOL_PASS + VOL_FAIL + VOL_MISSING)) total"
echo "========================================"
echo "  Total:   ${TOTAL}"
echo "  PASS:    ${TOTAL_PASS}"
echo "  FAIL:    ${TOTAL_FAIL}"
echo "  MISSING: ${TOTAL_MISSING}"
echo "  Time:    ${ELAPSED}s (${JOBS} workers)"
echo "========================================"

if [ "$TOTAL_FAIL" -gt 0 ] || [ "$TOTAL_MISSING" -gt 0 ]; then
    echo ""
    echo "Failed/missing:"
    grep -v "^PASS" "${BL_SUMMARY}" "${VOL_SUMMARY}" 2>/dev/null | grep -E "FAIL|MISSING" | head -20
fi
