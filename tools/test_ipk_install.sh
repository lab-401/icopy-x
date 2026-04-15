#!/bin/bash
# Test IPK installation via the ORIGINAL firmware install flow in QEMU.
#
# Usage:
#   bash tools/test_ipk_install.sh /path/to/file.ipk
#   bash tools/test_ipk_install.sh test-install.ipk
#
# This script:
#   1. Restores QEMU rootfs from backup
#   2. Places the IPK in the QEMU upan path
#   3. Boots QEMU with --target=original
#   4. Navigates: About → page 2 → OK (launch update) → M2 (start install)
#   5. Waits for and captures the install result
#   6. Verifies files were actually installed
#   7. Reports PASS/FAIL

set +e

IPK_FILE="${1:?Usage: $0 <ipk-file>}"
PROJECT="${PROJECT:-$(cd "$(dirname "$0")/.." && pwd)}"

ROOTFS="/mnt/sdcard/root2/root"
APP_DIR="${ROOTFS}/home/pi/ipk_app_main"
BACKUP_DIR="${ROOTFS}/home/pi/ipk_app_main.bak"
UPAN_DIR="${ROOTFS}/mnt/upan"

if [ ! -f "${IPK_FILE}" ]; then
    echo "[FAIL] IPK file not found: ${IPK_FILE}"
    exit 1
fi

echo "=== IPK Install Test ==="
echo "  IPK: ${IPK_FILE} ($(stat -c%s "${IPK_FILE}" 2>/dev/null | numfmt --to=iec 2>/dev/null || stat -c%s "${IPK_FILE}") bytes)"
echo ""

# -----------------------------------------------------------------------
# Step 1: Restore rootfs from backup
# -----------------------------------------------------------------------
echo "[1/6] Restoring QEMU rootfs from backup..."
if [ ! -d "${BACKUP_DIR}" ]; then
    echo "  Creating backup first..."
    cp -a "${APP_DIR}" "${BACKUP_DIR}"
fi
rm -rf "${APP_DIR}"
cp -a "${BACKUP_DIR}" "${APP_DIR}"
echo "  Restored."

# -----------------------------------------------------------------------
# Step 2: Place IPK in upan
# -----------------------------------------------------------------------
echo "[2/6] Placing IPK in QEMU upan..."
mkdir -p "${UPAN_DIR}"
rm -f "${UPAN_DIR}"/*.ipk "${UPAN_DIR}"/*.zip 2>/dev/null
cp "${IPK_FILE}" "${UPAN_DIR}/$(basename "${IPK_FILE}")"
# Also place at HOST /mnt/upan/ (shutil.move uses host paths, not QEMU LD_PREFIX)
mkdir -p /mnt/upan/ipk_old 2>/dev/null
rm -f /mnt/upan/*.ipk /mnt/upan/*.zip 2>/dev/null
cp "${IPK_FILE}" "/mnt/upan/$(basename "${IPK_FILE}")"
# Clean old backups
rm -f /mnt/upan/ipk_old/* 2>/dev/null
ls -la "${UPAN_DIR}/"*.ipk "${UPAN_DIR}/"*.zip 2>/dev/null
ls -la /mnt/upan/*.ipk /mnt/upan/*.zip 2>/dev/null
echo "  Placed at both QEMU and host paths."

# -----------------------------------------------------------------------
# Step 3: Ensure temp directories are writable
# -----------------------------------------------------------------------
echo "[3/6] Preparing temp directories..."
mkdir -p "${ROOTFS}/tmp"
chmod 777 "${ROOTFS}/tmp" 2>/dev/null || true
# Host-side temp dirs (install.so operates on host paths)
mkdir -p /tmp/.ipk/unpkg 2>/dev/null
mkdir -p /home/pi/ipk_app_main 2>/dev/null || true

# -----------------------------------------------------------------------
# Step 4: Boot QEMU and run install flow
# -----------------------------------------------------------------------
echo "[4/6] Booting QEMU..."

pkill -f "Xvfb :50" 2>/dev/null; sleep 0.3
Xvfb :50 -screen 0 240x240x24 -ac +render -noreset &>/dev/null &
sleep 1

export DISPLAY=:50 TEST_DISPLAY=:50 TEST_TARGET=original
export SCENARIO=ipk_install FLOW=ipk_test BOOT_TIMEOUT=180
export QEMU_TRACE=1

source "${PROJECT}/tests/includes/common.sh"

# Override launcher AFTER sourcing common.sh — use install-test launcher
LAUNCHER="${PROJECT}/tools/launcher_install_test.py"
mkdir -p "${SCENARIO_DIR}/screenshots" "${SCENARIO_DIR}/logs"

boot_qemu "${PROJECT}/tests/flows/about/scenarios/about_page1/fixture.py"

echo "  Waiting for HMI (PID: ${QEMU_PID})..."
if ! wait_for_hmi 40; then
    echo "[FAIL] HMI not ready"
    tail -10 "${LOG_FILE}"
    kill ${QEMU_PID} 2>/dev/null
    exit 1
fi
echo "  HMI ready."
sleep 2

# -----------------------------------------------------------------------
# Step 5: Navigate to update and trigger install
# -----------------------------------------------------------------------
echo "[5/6] Navigating to install..."

# About screen
send_key "GOTO:10"
sleep 4

# Page 2 (update instructions)
send_key "DOWN"
sleep 2

# Launch UpdateActivity (OK from page 2)
send_key "OK"
sleep 5

# Start install (M2 = Start)
send_key "M2"
echo "  Install triggered. Waiting 60s..."

# Poll for result every 5s
for i in $(seq 1 12); do
    sleep 5
    # Capture state
    frame_idx=$((i))
    capture_frame_with_state "/tmp/ipk_install_raw" "${frame_idx}"

    # Check for result toast in latest dump
    dump_file="${STATE_DUMP_TMP}/state_$(printf '%03d' ${frame_idx}).json"
    if [ -f "${dump_file}" ]; then
        result=$(python3 -c "
import json, sys
with open('${dump_file}') as f: d = json.load(f)
toast = str(d.get('toast') or '')
title = str(d.get('title') or '')
if 'Update finish' in toast:
    print('SUCCESS')
elif 'Install failed' in toast:
    print(f'FAILED: {toast}')
elif 'No update' in toast:
    print('NO_UPDATE_FOUND')
elif title == 'Update':
    print(f'IN_PROGRESS: title={title} toast={toast}')
" 2>/dev/null)

        if [ -n "${result}" ]; then
            echo "  [${i}0s] ${result}"
            if [[ "${result}" == SUCCESS* ]] || [[ "${result}" == FAILED* ]] || [[ "${result}" == NO_UPDATE* ]]; then
                break
            fi
        fi
    fi
done

kill ${QEMU_PID} 2>/dev/null
wait ${QEMU_PID} 2>/dev/null

# -----------------------------------------------------------------------
# Step 6: Verify installation
# -----------------------------------------------------------------------
echo ""
echo "[6/6] Verifying installation..."
echo ""

# Check for our Python UI files (only present if install succeeded)
echo "=== Key files ==="
for f in lib/activity_main.py lib/actbase.py lib/erase.py lib/version.py screens/about.json; do
    full="${APP_DIR}/${f}"
    if [ -f "${full}" ]; then
        echo "  ✓ ${f} ($(stat -c%s "${full}") bytes)"
    else
        echo "  ✗ ${f} NOT FOUND"
    fi
done

echo ""
echo "=== Middleware .so files ==="
for f in lib/scan.so lib/read.so lib/write.so lib/executor.so lib/tagtypes.so; do
    full="${APP_DIR}/${f}"
    if [ -f "${full}" ]; then
        echo "  ✓ ${f} ($(stat -c%s "${full}") bytes)"
    else
        echo "  ✗ ${f} NOT FOUND"
    fi
done

echo ""
echo "=== Replaced .so check (should NOT exist) ==="
leaked=0
for mod in actbase activity_main actstack hmi_driver keymap resources widget images; do
    if [ -f "${APP_DIR}/lib/${mod}.so" ]; then
        echo "  ⚠ ${mod}.so EXISTS (will shadow .py!)"
        leaked=1
    fi
done
[ "${leaked}" -eq 0 ] && echo "  ✓ No replaced .so files"

echo ""
echo "=== QEMU trace (last 15 lines) ==="
cat /tmp/qemu_trace.log 2>/dev/null | tail -15

echo ""
echo "=== Install trace log ==="
cat /tmp/install_trace.log 2>/dev/null | tail -40

echo ""
echo "=== Main log (filtered) ==="
grep -iE "install|update|error|fail|success|finish|0x0|font|search|checkPkg|checkVer|copy|shutil|chmod|INSTALL_TRACE" "${LOG_FILE}" 2>/dev/null | grep -v Fontconfig | tail -20

echo ""
echo "=== RESULT ==="
if [ -n "${result}" ]; then
    echo "${result}"
else
    echo "UNKNOWN — no result toast captured"
fi

# Cleanup
rm -rf "/tmp/ipk_install_raw"
pkill -f "Xvfb :50" 2>/dev/null
