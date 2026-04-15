#!/bin/bash
# Run ALL read scenarios in parallel using worker pools.
# Each scenario gets its own Xvfb display — fully isolated.
#
# Usage:
#   bash tests/flows/read/test_reads_parallel.sh [JOBS]
#   bash tests/flows/read/test_reads_parallel.sh --no-clean [JOBS]
#   bash tests/flows/read/test_reads_parallel.sh --clean-flow-only [JOBS]
#   JOBS defaults to 75% of cores, min 2, max 24.
#
# Cleanup modes:
#   (default)          Clean ALL _results before run
#   --no-clean         Keep all previous results; only overwrite scenarios that re-run
#   --clean-flow-only  Clean only _results/read/ before run (preserve write, auto-copy, etc.)
#
# Remote usage:
#   bash tests/flows/read/test_reads_parallel.sh --init-remote USER@HOST
#     → Installs dependencies on a fresh Ubuntu server and mounts the SD image.
#
#   bash tests/flows/read/test_reads_parallel.sh --remote USER@HOST [JOBS]
#     → Syncs the project, runs tests on remote, pulls results back.

set +e

PROJECT="${PROJECT:-$(cd "$(dirname "$0")/../../.." && pwd)}"
RESULTS_DIR="${RESULTS_DIR:-${PROJECT}/tests/flows/_results/${TEST_TARGET:-original}}"
READ_RESULTS="${RESULTS_DIR}/read"
SUMMARY="${READ_RESULTS}/scenario_summary.txt"

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
# --init-remote: bootstrap a fresh server
# -----------------------------------------------------------------------
if [ "$1" = "--init-remote" ]; then
    REMOTE="$2"
    [ -z "$REMOTE" ] && { echo "Usage: $0 --init-remote USER@HOST"; exit 1; }
    echo "=== Initialising remote: ${REMOTE} ==="

    # Detect if password is needed (try key-based first)
    SSH_CMD="ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10"
    SCP_CMD="scp -o StrictHostKeyChecking=no"
    RSYNC_CMD="rsync -az"
    if ! $SSH_CMD "$REMOTE" 'echo OK' 2>/dev/null | grep -q OK; then
        read -rsp "Password for ${REMOTE}: " PASS; echo
        SSH_CMD="sshpass -p '$PASS' $SSH_CMD"
        SCP_CMD="sshpass -p '$PASS' $SCP_CMD"
        RSYNC_CMD="sshpass -p '$PASS' $RSYNC_CMD"
    fi

    eval $SSH_CMD "$REMOTE" 'bash -s' << 'INIT_EOF'
set -e
echo "[1/5] Installing packages..."
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    qemu-user-static xvfb imagemagick python3 rsync 2>&1 | tail -3

echo "[2/5] Checking SD card image..."
if [ ! -d /mnt/sdcard ]; then
    echo "  /mnt/sdcard not found — looking for SD image..."
    IMG=$(ls /home/*/icopy*.img /root/*.img /tmp/*.img 2>/dev/null | head -1)
    if [ -z "$IMG" ]; then
        echo "  ERROR: No SD card image found. Please copy it to the server and mount:"
        echo "    sudo mkdir -p /mnt/sdcard"
        echo "    sudo losetup -Pf <image.img>"
        echo "    sudo mount /dev/loopXp1 /mnt/sdcard/root1 && sudo mount /dev/loopXp2 /mnt/sdcard/root2"
        exit 1
    fi
    echo "  Found: $IMG"
    sudo mkdir -p /mnt/sdcard/root1 /mnt/sdcard/root2
    LOOP=$(sudo losetup -Pf --show "$IMG")
    sudo mount "${LOOP}p1" /mnt/sdcard/root1
    sudo mount "${LOOP}p2" /mnt/sdcard/root2
    echo "  Mounted on $LOOP"
fi

echo "[3/5] Verifying rootfs..."
if [ -f /mnt/sdcard/root2/root/home/pi/ipk_app_main/lib/actmain.so ]; then
    echo "  rootfs OK"
else
    echo "  ERROR: rootfs not found at /mnt/sdcard/root2/root/home/pi/ipk_app_main/"
    exit 1
fi

echo "[4/5] Verifying QEMU..."
qemu-arm-static --version | head -1

echo "[5/5] Setting up runtime directories..."
mkdir -p ~/icopy-x-reimpl/tools/qemu_img_overlay

# Create dump directories the .so needs for file saves
# The .so writes to /mnt/upan/dump/<type>/ — these must exist and be writable
DUMP_TYPES="mf1 mfu em410x hid indala awid ioprox gproxii securakey viking pyramid iclass icode legic felica hf14a t55xx em4x05 fdx gallagher jablotron keri nedap noralsy pac paradox presco visa2000 nexwatch id"
sudo mkdir -p /mnt/upan/dump /mnt/upan/keys /mnt/upan/keys/mf1 /mnt/upan/key /mnt/upan/trace
for t in $DUMP_TYPES; do sudo mkdir -p "/mnt/upan/dump/$t"; done
sudo chmod -R 777 /mnt/upan
# Create default MFC key file (fchk loads this)
mkdir -p /tmp/.keys
python3 -c "
with open('/tmp/.keys/mf_tmp_keys','wb') as f: f.write(b'\\xff\\xff\\xff\\xff\\xff\\xff'*104)
" 2>/dev/null
echo "  /mnt/upan/dump: $(ls /mnt/upan/dump/ | wc -l) type directories"

echo "=== Remote ready ==="
INIT_EOF
    echo "=== Init complete ==="
    exit 0
fi

# -----------------------------------------------------------------------
# --init-remote-local: run ON the remote to ensure dirs/perms are correct
# Called automatically by --remote before each test run.
# -----------------------------------------------------------------------
if [ "$1" = "--init-remote-local" ]; then
    echo "[init] Ensuring dump directories and permissions..."
    DUMP_DIRS="mf1 mfu em410x hid indala awid ioprox gproxii securakey viking pyramid iclass icode legic felica hf14a t55xx em4x05 fdx gallagher jablotron keri nedap noralsy pac paradox presco visa2000 nexwatch id"
    echo proxmark | sudo -S mkdir -p /mnt/upan/dump /mnt/upan/keys /mnt/upan/keys/mf1 /mnt/upan/key /mnt/upan/trace 2>/dev/null
    for _d in $DUMP_DIRS; do echo proxmark | sudo -S mkdir -p "/mnt/upan/dump/$_d" 2>/dev/null; done
    echo proxmark | sudo -S chmod -R 777 /mnt/upan 2>/dev/null
    mkdir -p /tmp/.keys
    python3 -c "
with open('/tmp/.keys/mf_tmp_keys','wb') as f: f.write(b'\xff\xff\xff\xff\xff\xff'*104)
" 2>/dev/null
    echo "[init] Dump dirs: $(ls /mnt/upan/dump/ 2>/dev/null | wc -l) types, perms: $(stat -c '%a' /mnt/upan/dump 2>/dev/null)"
    exit 0
fi

# -----------------------------------------------------------------------
# --remote: sync + run + pull results
# -----------------------------------------------------------------------
if [ "$1" = "--remote" ]; then
    REMOTE="$2"
    RJOBS="${3:-12}"
    [ -z "$REMOTE" ] && { echo "Usage: $0 --remote USER@HOST [JOBS]"; exit 1; }

    # Detect auth method
    SSH_CMD="ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -o ServerAliveInterval=30"
    RSYNC_CMD="rsync -az"
    if ! $SSH_CMD "$REMOTE" 'echo OK' 2>/dev/null | grep -q OK; then
        read -rsp "Password for ${REMOTE}: " PASS; echo
        SSH_CMD="sshpass -p '$PASS' $SSH_CMD"
        RSYNC_CMD="sshpass -p '$PASS' $RSYNC_CMD"
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
        eval $SSH_CMD "$REMOTE" "'rm -rf ~/icopy-x-reimpl/tests/flows/_results/read/scenarios ~/icopy-x-reimpl/tests/flows/_results/read/scenario_summary.txt'"
    fi

    # Forward clean flags to remote
    local remote_flags=""
    [ "${CLEAN_MODE}" = "none" ] && remote_flags="--no-clean"
    [ "${CLEAN_MODE}" = "flow" ] && remote_flags="--clean-flow-only"

    echo "=== Running ${RJOBS} workers on ${REMOTE} ==="
    eval $SSH_CMD "$REMOTE" "'cd ~/icopy-x-reimpl && bash tests/flows/read/test_reads_parallel.sh ${remote_flags} ${RJOBS}'"
    RC=$?

    echo "=== Pulling results ==="
    if [ "${CLEAN_MODE}" != "none" ]; then
        rm -rf "${READ_RESULTS}/scenarios" "${READ_RESULTS}/scenario_summary.txt"
    fi
    mkdir -p "${READ_RESULTS}"
    eval $RSYNC_CMD "${REMOTE}:icopy-x-reimpl/tests/flows/_results/read/" "${READ_RESULTS}/" 2>&1 | tail -3

    echo "=== Results at: ${READ_RESULTS}/ ==="
    [ -f "${READ_RESULTS}/scenario_summary.txt" ] && cat "${READ_RESULTS}/scenario_summary.txt"
    exit $RC
fi

# -----------------------------------------------------------------------
# Local execution
# -----------------------------------------------------------------------

# Auto-scale: 50% of cores for read tests (I/O heavy — SD card image + Xvfb + state dumps).
# Each worker runs QEMU + Xvfb + ImageMagick captures. Under parallel load, shared I/O
# (rootfs reads, state dump writes) becomes the bottleneck, not CPU. 16 workers on a
# 48-core server is the practical maximum before Xvfb resource exhaustion / timeouts.
CORES=$(nproc 2>/dev/null || echo 4)
DEFAULT_JOBS=$(( CORES / 2 ))
[ "$DEFAULT_JOBS" -lt 2 ] && DEFAULT_JOBS=2
[ "$DEFAULT_JOBS" -gt 16 ] && DEFAULT_JOBS=16
JOBS="${1:-${DEFAULT_JOBS}}"

mkdir -p "${READ_RESULTS}"

# Verify dump directories exist (created by --init-remote-local or --init-remote).
# On local dev machines these already exist from setup_qemu_env.sh.
if [ ! -d /mnt/upan/dump ]; then
    echo "[WARN] /mnt/upan/dump missing — run --init-remote or setup_qemu_env.sh first"
fi
# Ensure key file exists
[ ! -f /tmp/.keys/mf_tmp_keys ] && mkdir -p /tmp/.keys && python3 -c "
with open('/tmp/.keys/mf_tmp_keys','wb') as f: f.write(b'\xff\xff\xff\xff\xff\xff'*104)
" 2>/dev/null
echo "[SETUP] Dump dirs: $(ls /mnt/upan/dump/ 2>/dev/null | wc -l) types"

# Collect all scenario scripts
SCRIPTS=()
for script in "${PROJECT}/tests/flows/read/scenarios"/*/read_*.sh; do
    [ -f "$script" ] && SCRIPTS+=("$script")
done
TOTAL=${#SCRIPTS[@]}

echo "========================================"
echo "  READ FLOW — PARALLEL (${JOBS} workers)"
echo "  Scenarios: ${TOTAL}"
echo "  Output: ${READ_RESULTS}/"
echo "========================================"

# Kill any leftover QEMU from previous runs (safe — we haven't started ours yet)
killall -9 qemu-arm-static 2>/dev/null
sleep 1

# Clean previous results (respects CLEAN_MODE)
if [ "${CLEAN_MODE}" = "full" ] || [ "${CLEAN_MODE}" = "flow" ]; then
    rm -rf "${READ_RESULTS}/scenarios"
fi
# CLEAN_MODE="none" (--no-clean): skip deletion entirely

START_TIME=$(date +%s)

# --- Worker function ---
# Runs a single scenario with its own Xvfb display.
# Args: $1=script_path, $2=unique_id (for display number), $3=scenario_index (1-based)
run_one() {
    local script="$1"
    local uid="$2"
    local idx="$3"
    local display_num=$((100 + uid))
    local scenario_name
    scenario_name=$(basename "$(dirname "$script")")

    # Start a private Xvfb for this scenario (unique display = no conflicts)
    Xvfb ":${display_num}" -screen 0 240x240x24 -ac 2>/dev/null &
    local xvfb_pid=$!

    # Wait for Xvfb to be ready (check the socket)
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
        mkdir -p "${READ_RESULTS}/scenarios/${scenario_name}"
        echo "FAIL: Xvfb startup failed" > "${READ_RESULTS}/scenarios/${scenario_name}/result.txt"
        return
    fi

    # Run the scenario with isolated display
    TEST_DISPLAY=":${display_num}" \
    TEST_TARGET="${TEST_TARGET:-original}" \
    PROJECT="${PROJECT}" \
    RESULTS_DIR="${RESULTS_DIR}" \
    bash "$script" >/dev/null 2>&1

    # Tear down Xvfb
    kill "$xvfb_pid" 2>/dev/null
    wait "$xvfb_pid" 2>/dev/null

    # Check result
    local result_file="${READ_RESULTS}/scenarios/${scenario_name}/result.txt"
    if [ -f "$result_file" ] && grep -q "^PASS" "$result_file"; then
        echo "  [${idx}/${TOTAL}] PASS  ${scenario_name}"
    else
        local msg="unknown"
        [ -f "$result_file" ] && msg=$(head -1 "$result_file")
        echo "  [${idx}/${TOTAL}] FAIL  ${scenario_name}: ${msg}"
    fi
}

export -f run_one
export PROJECT RESULTS_DIR READ_RESULTS TOTAL NO_CLEAN

# --- Dispatch with job control ---
# Uses a FIFO-based semaphore to limit concurrency.
FIFO="/tmp/_par_fifo_$$"
mkfifo "$FIFO"
exec 3<>"$FIFO"
rm -f "$FIFO"

# Pre-fill the semaphore with $JOBS tokens
for ((i=0; i<JOBS; i++)); do echo >&3; done

idx=0
PIDS=()
for script in "${SCRIPTS[@]}"; do
    read -u 3  # Wait for a token (blocks if all workers busy)
    idx=$((idx + 1))
    (
        run_one "$script" "$idx" "$idx"
        echo >&3  # Release token
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

# --- Assemble summary ---
PASS=0; FAIL=0
> "${SUMMARY}"
for script in "${SCRIPTS[@]}"; do
    scenario_name=$(basename "$(dirname "$script")")
    result_file="${READ_RESULTS}/scenarios/${scenario_name}/result.txt"
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

cp "${SUMMARY}" "${READ_RESULTS}/read_summary.txt" 2>/dev/null

echo ""
echo "========================================"
echo "  COMPLETE: ${PASS} PASS, ${FAIL} FAIL / ${TOTAL} total"
echo "  Duration: ${ELAPSED}s (${JOBS} parallel workers)"
echo "  Summary: ${SUMMARY}"
echo "========================================"

# Exit with failure count
exit "${FAIL}"
