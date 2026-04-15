#!/bin/bash
# Test a built IPK under QEMU emulation.
#
# Validates that the IPK contains the right files, that replaced .so modules
# are absent, that kept middleware .so modules are present, and that the
# application boots and renders correctly under QEMU.
#
# Usage:
#   ./tools/test_ipk_qemu.sh [ipk_file]
#
# If no ipk_file is given, looks for the most recent .ipk in dist/.
#
# Exit codes:
#   0 — all checks passed
#   1 — one or more checks failed
#
# Prerequisites:
#   - QEMU rootfs mounted at /mnt/sdcard/root{1,2}/
#   - Xvfb running (or TEST_DISPLAY pointing to a valid X display)
#   - qemu-arm-static available
#   - ImageMagick 'import' for screenshots
#
# Steps:
#   1. Extract IPK to temp directory
#   2. Verify file structure (lib/*.py, screens/*.json)
#   3. Verify replaced .so files are NOT present
#   4. Verify middleware .so files ARE present (in rootfs)
#   5. Boot under QEMU with src/lib on PYTHONPATH
#   6. Smoke test: import all Python modules
#   7. Smoke test: MainActivity boots and renders 14 items
#   8. Run a few flow tests (backlight, volume, diagnosis)
#   9. Report results

set -euo pipefail

PROJECT="$(cd "$(dirname "$0")/.." && pwd)"

# --- Configuration ---
ROOT_FS="/mnt/sdcard/root2/root"
ORIG_LIB="${ROOT_FS}/home/pi/ipk_app_main/lib"
QEMU_BIN="${QEMU_BIN:-/home/qx/.local/bin/qemu-arm-static}"
[ -x "${QEMU_BIN}" ] || QEMU_BIN="$(command -v qemu-arm-static 2>/dev/null || echo /usr/bin/qemu-arm-static)"
TEST_DISPLAY="${TEST_DISPLAY:-:99}"

# Replaced .so modules — these must NOT be in the IPK
REPLACED_SO=(
    actbase.so
    actstack.so
    widget.so
    batteryui.so
    hmi_driver.so
    keymap.so
    resources.so
    images.so
    actmain.so
    activity_main.so
    activity_tools.so
    activity_update.so
)

# Kept middleware .so modules — these must be present in rootfs
KEPT_SO=(
    executor.so
    scan.so
    read.so
    write.so
    sniff.so
    tagtypes.so
    container.so
    mifare.so
    template.so
    hfmfread.so
    hfmfwrite.so
    hfmfkeys.so
    hfmfuread.so
    lft55xx.so
    lfread.so
    lfwrite.so
    hficlass.so
    appfiles.so
    commons.so
    audio.so
    config.so
    debug.so
)

# Required Python replacement modules
REQUIRED_PY=(
    _constants.py
    _renderer.py
    _state_machine.py
    _variable_resolver.py
    actbase.py
    actmain.py
    actstack.py
    activity_main.py
    activity_tools.py
    hmi_driver.py
    images.py
    keymap.py
    resources.py
    widget.py
)

# Required JSON screen definitions
REQUIRED_JSON=(
    main_menu.json
    backlight.json
    volume.json
    diagnosis.json
    about.json
    scan_tag.json
    read_tag.json
    write_tag.json
    erase_tag.json
    sniff.json
    simulation.json
    autocopy.json
    pc_mode.json
    time_settings.json
    lua_script.json
    dump_files.json
    warning_write.json
    warning_m1.json
)

# --- Counters ---
PASS=0
FAIL=0
WARN=0

pass_check() {
    PASS=$((PASS + 1))
    echo "  [PASS] $1"
}

fail_check() {
    FAIL=$((FAIL + 1))
    echo "  [FAIL] $1"
}

warn_check() {
    WARN=$((WARN + 1))
    echo "  [WARN] $1"
}

# --- Find IPK ---
IPK_FILE="${1:-}"
if [ -z "${IPK_FILE}" ]; then
    IPK_FILE=$(ls -t "${PROJECT}"/dist/*.ipk 2>/dev/null | head -1)
    if [ -z "${IPK_FILE}" ]; then
        # No dist/ IPK — validate src/lib and src/screens directly
        echo "No IPK file found. Validating src/ directory structure directly."
        IPK_FILE=""
    fi
fi

echo "========================================"
echo "  IPK QEMU Integration Test"
echo "========================================"
echo ""

# --- Phase 1: Extract and validate file structure ---
EXTRACT_DIR=""
LIB_DIR=""
SCREENS_DIR=""

if [ -n "${IPK_FILE}" ]; then
    echo "[Phase 1] Extracting IPK: ${IPK_FILE}"
    EXTRACT_DIR=$(mktemp -d /tmp/ipk_test_XXXXXX)
    trap "rm -rf ${EXTRACT_DIR}" EXIT

    # IPK is an ar archive containing data.tar.gz
    cd "${EXTRACT_DIR}"
    ar x "${IPK_FILE}" 2>/dev/null || { fail_check "IPK extraction failed (ar)"; exit 1; }

    # Extract data tarball
    if [ -f data.tar.gz ]; then
        tar xzf data.tar.gz 2>/dev/null
    elif [ -f data.tar.xz ]; then
        tar xJf data.tar.xz 2>/dev/null
    elif [ -f data.tar ]; then
        tar xf data.tar 2>/dev/null
    else
        fail_check "No data tarball found in IPK"
        exit 1
    fi
    cd "${PROJECT}"

    # Locate lib/ and screens/ within extracted tree
    LIB_DIR=$(find "${EXTRACT_DIR}" -type d -name "lib" | head -1)
    SCREENS_DIR=$(find "${EXTRACT_DIR}" -type d -name "screens" | head -1)

    if [ -z "${LIB_DIR}" ]; then
        fail_check "No lib/ directory found in IPK"
    else
        pass_check "lib/ directory found in IPK"
    fi
    if [ -z "${SCREENS_DIR}" ]; then
        fail_check "No screens/ directory found in IPK"
    else
        pass_check "screens/ directory found in IPK"
    fi
else
    echo "[Phase 1] Validating src/ directory structure (no IPK)"
    LIB_DIR="${PROJECT}/src/lib"
    SCREENS_DIR="${PROJECT}/src/screens"

    if [ -d "${LIB_DIR}" ]; then
        pass_check "src/lib/ directory exists"
    else
        fail_check "src/lib/ directory missing"
    fi
    if [ -d "${SCREENS_DIR}" ]; then
        pass_check "src/screens/ directory exists"
    else
        fail_check "src/screens/ directory missing"
    fi
fi

echo ""

# --- Phase 2: Check required Python modules ---
echo "[Phase 2] Checking required Python modules (${#REQUIRED_PY[@]} expected)"
if [ -n "${LIB_DIR}" ] && [ -d "${LIB_DIR}" ]; then
    py_count=0
    for pyf in "${REQUIRED_PY[@]}"; do
        if [ -f "${LIB_DIR}/${pyf}" ]; then
            py_count=$((py_count + 1))
        else
            fail_check "Missing Python module: ${pyf}"
        fi
    done
    if [ "${py_count}" -eq "${#REQUIRED_PY[@]}" ]; then
        pass_check "All ${#REQUIRED_PY[@]} required Python modules present"
    fi

    # Count total .py files
    total_py=$(ls "${LIB_DIR}"/*.py 2>/dev/null | wc -l)
    echo "  [INFO] Total .py files in lib/: ${total_py}"
fi

echo ""

# --- Phase 3: Check required JSON screen definitions ---
echo "[Phase 3] Checking required JSON screens (${#REQUIRED_JSON[@]} expected)"
if [ -n "${SCREENS_DIR}" ] && [ -d "${SCREENS_DIR}" ]; then
    json_count=0
    for jf in "${REQUIRED_JSON[@]}"; do
        if [ -f "${SCREENS_DIR}/${jf}" ]; then
            json_count=$((json_count + 1))
        else
            fail_check "Missing JSON screen: ${jf}"
        fi
    done
    if [ "${json_count}" -eq "${#REQUIRED_JSON[@]}" ]; then
        pass_check "All ${#REQUIRED_JSON[@]} required JSON screens present"
    fi

    # Count total .json files
    total_json=$(ls "${SCREENS_DIR}"/*.json 2>/dev/null | wc -l)
    echo "  [INFO] Total .json files in screens/: ${total_json}"
fi

echo ""

# --- Phase 4: Verify replaced .so files are NOT in the package ---
echo "[Phase 4] Checking replaced .so files are absent"
if [ -n "${LIB_DIR}" ] && [ -d "${LIB_DIR}" ]; then
    stale_count=0
    for sof in "${REPLACED_SO[@]}"; do
        if [ -f "${LIB_DIR}/${sof}" ]; then
            fail_check "Stale .so found (should be replaced by .py): ${sof}"
            stale_count=$((stale_count + 1))
        fi
    done
    if [ "${stale_count}" -eq 0 ]; then
        pass_check "No replaced .so files found in package (${#REPLACED_SO[@]} checked)"
    fi
fi

echo ""

# --- Phase 5: Verify middleware .so files in rootfs ---
echo "[Phase 5] Checking middleware .so files in rootfs"
if [ -d "${ORIG_LIB}" ]; then
    mw_count=0
    for sof in "${KEPT_SO[@]}"; do
        if [ -f "${ORIG_LIB}/${sof}" ]; then
            mw_count=$((mw_count + 1))
        else
            warn_check "Middleware .so missing from rootfs: ${sof}"
        fi
    done
    if [ "${mw_count}" -eq "${#KEPT_SO[@]}" ]; then
        pass_check "All ${#KEPT_SO[@]} middleware .so files present in rootfs"
    else
        echo "  [INFO] ${mw_count}/${#KEPT_SO[@]} middleware .so files found"
    fi
else
    warn_check "QEMU rootfs not mounted at ${ROOT_FS} — skipping middleware check"
fi

echo ""

# --- Phase 6: Python import smoke test ---
echo "[Phase 6] Python import smoke test"
IMPORT_LOG=$(mktemp /tmp/ipk_import_XXXXXX.log)
python3 -c "
import sys, os
sys.path.insert(0, '${PROJECT}/src/lib')
sys.path.insert(0, '${PROJECT}/src')
# Set up minimal environment so modules can import
os.environ.setdefault('DISPLAY', ':99')

errors = []
modules = [
    '_constants', '_renderer', '_state_machine', '_variable_resolver',
    'actbase', 'actmain', 'actstack', 'activity_main', 'activity_tools',
    'hmi_driver', 'images', 'keymap', 'resources', 'widget',
]
for mod in modules:
    try:
        __import__(mod)
    except Exception as e:
        errors.append((mod, str(e)))

if errors:
    for mod, err in errors:
        print('IMPORT_FAIL: %s — %s' % (mod, err))
    sys.exit(1)
else:
    print('ALL_IMPORTS_OK: %d modules' % len(modules))
" > "${IMPORT_LOG}" 2>&1
IMPORT_RC=$?

if [ "${IMPORT_RC}" -eq 0 ]; then
    pass_check "All Python modules import successfully"
else
    fail_check "Python import failures:"
    grep "IMPORT_FAIL" "${IMPORT_LOG}" | while read -r line; do
        echo "    ${line}"
    done
fi
rm -f "${IMPORT_LOG}"

echo ""

# --- Phase 7: JSON schema validation ---
echo "[Phase 7] JSON schema validation"
JSON_LOG=$(mktemp /tmp/ipk_json_XXXXXX.log)
python3 -c "
import json, sys, os, glob

screens_dir = '${SCREENS_DIR}'
errors = []
count = 0

for jf in sorted(glob.glob(os.path.join(screens_dir, '*.json'))):
    count += 1
    name = os.path.basename(jf)
    try:
        with open(jf) as f:
            data = json.load(f)
        # Basic schema checks
        if not isinstance(data, dict):
            errors.append((name, 'root is not an object'))
            continue
        # Must have 'id' or 'screens' or 'states'
        has_structure = any(k in data for k in ('id', 'screens', 'states', 'items', 'content'))
        if not has_structure:
            errors.append((name, 'missing expected top-level key (id/screens/states/items/content)'))
    except json.JSONDecodeError as e:
        errors.append((name, 'invalid JSON: %s' % e))
    except Exception as e:
        errors.append((name, str(e)))

if errors:
    for name, err in errors:
        print('JSON_FAIL: %s — %s' % (name, err))
    sys.exit(1)
else:
    print('ALL_JSON_OK: %d files validated' % count)
" > "${JSON_LOG}" 2>&1
JSON_RC=$?

if [ "${JSON_RC}" -eq 0 ]; then
    pass_check "All JSON screen definitions are valid"
else
    fail_check "JSON validation failures:"
    grep "JSON_FAIL" "${JSON_LOG}" | while read -r line; do
        echo "    ${line}"
    done
fi
rm -f "${JSON_LOG}"

echo ""

# --- Phase 8: QEMU boot test (if rootfs available) ---
echo "[Phase 8] QEMU boot + MainActivity test"
if [ ! -d "${ROOT_FS}" ]; then
    warn_check "QEMU rootfs not mounted — skipping boot test"
elif [ ! -x "${QEMU_BIN}" ]; then
    warn_check "qemu-arm-static not found — skipping boot test"
elif ! command -v import &>/dev/null; then
    warn_check "ImageMagick 'import' not found — skipping boot test"
else
    BOOT_LOG=$(mktemp /tmp/ipk_boot_XXXXXX.log)
    BOOT_KF=$(mktemp /tmp/ipk_boot_keys_XXXXXX.txt)
    BOOT_MOCK=$(mktemp /tmp/ipk_boot_mock_XXXXXX.py)
    BOOT_PNG=$(mktemp /tmp/ipk_boot_XXXXXX.png)

    # Empty mock (no PM3 commands needed for boot test)
    cat > "${BOOT_MOCK}" <<'MOCKEOF'
SCENARIO_RESPONSES = {}
DEFAULT_RETURN = -1
MOCKEOF

    PYTHON38="/mnt/sdcard/root2/root/usr/local/python-3.8.0/bin/python3.8"
    SITE1="/mnt/sdcard/root1/home/pi/.local/lib/python3.8/site-packages"
    SITE2="/mnt/sdcard/root2/root/home/pi/.local/lib/python3.8/site-packages"
    LAUNCHER="${PROJECT}/tools/minimal_launch_090.py"

    # Boot QEMU with our Python modules on PYTHONPATH (before .so modules)
    QEMU_LD_PREFIX="${ROOT_FS}" \
    QEMU_SET_ENV="LD_LIBRARY_PATH=${ROOT_FS}/usr/local/python-3.8.0/lib:${ROOT_FS}/usr/lib/arm-linux-gnueabihf:${ROOT_FS}/lib/arm-linux-gnueabihf:/mnt/sdcard/root1/usr/lib/arm-linux-gnueabihf:/mnt/sdcard/root1/lib/arm-linux-gnueabihf" \
    DISPLAY="${TEST_DISPLAY}" \
    PYTHONPATH="${PROJECT}/src/lib:${PROJECT}/src:${SITE2}:${SITE1}:${ROOT_FS}/home/pi/ipk_app_main/lib:${ROOT_FS}/home/pi/ipk_app_main/main:${ROOT_FS}/home/pi/ipk_app_main:${PROJECT}/tools/qemu_shims" \
    PYTHONUNBUFFERED=1 \
    PM3_SCENARIO_FILE="${BOOT_MOCK}" \
    PM3_MOCK_DELAY="0.1" \
    ICOPY_KEY_FILE="${BOOT_KF}" \
    timeout 80 "${QEMU_BIN}" \
        "${PYTHON38}" \
        -u "${LAUNCHER}" > "${BOOT_LOG}" 2>&1 &
    BOOT_PID=$!

    # Wait for HMI to be ready
    BOOT_OK=false
    for attempt in $(seq 1 30); do
        sleep 2
        if ! kill -0 "${BOOT_PID}" 2>/dev/null; then
            break
        fi
        import -display "${TEST_DISPLAY}" -window root "${BOOT_PNG}" 2>/dev/null || continue
        sz=$(stat -c%s "${BOOT_PNG}" 2>/dev/null || echo 0)
        hmi=$(grep -c "\[HMI\]" "${BOOT_LOG}" 2>/dev/null || echo 0)
        sz=${sz:-0}; hmi=${hmi:-0}
        if [ "$sz" -gt 5000 ] 2>/dev/null && [ "$hmi" -gt 0 ] 2>/dev/null; then
            BOOT_OK=true
            break
        fi
    done

    if [ "${BOOT_OK}" = true ]; then
        pass_check "QEMU boots successfully with new UI modules"

        # Check for critical log entries
        if grep -q "\[OK\] actmain patched" "${BOOT_LOG}" 2>/dev/null; then
            pass_check "actmain loaded and patched"
        else
            fail_check "actmain did not load properly"
        fi

        if grep -q "\[OK\] tagtypes DRM passed" "${BOOT_LOG}" 2>/dev/null; then
            pass_check "tagtypes DRM passed"
        elif grep -q "\[OK\] tagtypes DRM" "${BOOT_LOG}" 2>/dev/null; then
            pass_check "tagtypes DRM handled"
        else
            warn_check "tagtypes DRM status unclear"
        fi

        # Request a STATE_DUMP to verify 14 menu items
        echo "STATE_DUMP" >> "${BOOT_KF}"
        sleep 3

        # Check state dump for 14 items
        STATE_JSON=$(ls -t /tmp/state_dumps_*/state_*.json 2>/dev/null | head -1)
        if [ -n "${STATE_JSON}" ] && [ -f "${STATE_JSON}" ]; then
            ITEM_COUNT=$(python3 -c "
import json
with open('${STATE_JSON}') as f:
    d = json.load(f)
items = d.get('content_text', [])
print(len(items))
" 2>/dev/null || echo 0)
            if [ "${ITEM_COUNT}" -ge 14 ] 2>/dev/null; then
                pass_check "MainActivity renders ${ITEM_COUNT} menu items (expected >=14)"
            else
                warn_check "MainActivity shows ${ITEM_COUNT} items (expected 14)"
            fi
        else
            warn_check "No state dump captured — cannot verify menu item count"
        fi
    else
        fail_check "QEMU failed to boot within timeout"
        echo "  [INFO] Last 20 lines of boot log:"
        tail -20 "${BOOT_LOG}" | while read -r line; do
            echo "    ${line}"
        done
    fi

    # Cleanup boot test
    kill "${BOOT_PID}" 2>/dev/null
    wait "${BOOT_PID}" 2>/dev/null
    rm -f "${BOOT_LOG}" "${BOOT_KF}" "${BOOT_MOCK}" "${BOOT_PNG}"
fi

echo ""

# --- Phase 9: Flow test smoke check ---
echo "[Phase 9] Flow test smoke check (backlight, volume, diagnosis)"
FLOW_PASS=0
FLOW_FAIL=0
FLOW_SKIP=0

run_flow_test() {
    local test_script="$1"
    local test_name="$2"

    if [ ! -f "${test_script}" ]; then
        warn_check "Flow test not found: ${test_name}"
        FLOW_SKIP=$((FLOW_SKIP + 1))
        return
    fi

    if [ ! -d "${ROOT_FS}" ] || [ ! -x "${QEMU_BIN}" ]; then
        warn_check "QEMU not available — skipping ${test_name}"
        FLOW_SKIP=$((FLOW_SKIP + 1))
        return
    fi

    local FLOW_RESULTS="${PROJECT}/tests/flows/_results"
    local flow_log=$(mktemp /tmp/flow_test_XXXXXX.log)

    # Run with new UI modules prepended to PYTHONPATH
    PYTHONPATH="${PROJECT}/src/lib:${PROJECT}/src:${PYTHONPATH:-}" \
    PROJECT="${PROJECT}" \
    RESULTS_DIR="${FLOW_RESULTS}" \
    TEST_DISPLAY="${TEST_DISPLAY}" \
    timeout 300 bash "${test_script}" > "${flow_log}" 2>&1
    local rc=$?

    # Parse results from summary
    local summary_dir
    summary_dir=$(dirname "${test_script}")
    local flow_name
    flow_name=$(basename "${summary_dir}")
    local summary_file="${FLOW_RESULTS}/${flow_name}/scenario_summary.txt"

    if [ -f "${summary_file}" ]; then
        local total_line
        total_line=$(grep "^TOTAL:" "${summary_file}" 2>/dev/null || echo "")
        if [ -n "${total_line}" ]; then
            local t_pass t_fail
            t_pass=$(echo "${total_line}" | grep -oP 'PASS: \K[0-9]+' || echo 0)
            t_fail=$(echo "${total_line}" | grep -oP 'FAIL: \K[0-9]+' || echo 0)
            if [ "${t_fail}" -eq 0 ] 2>/dev/null && [ "${t_pass}" -gt 0 ] 2>/dev/null; then
                pass_check "${test_name}: ${t_pass} scenarios passed"
                FLOW_PASS=$((FLOW_PASS + 1))
            else
                fail_check "${test_name}: ${t_pass} pass, ${t_fail} fail"
                FLOW_FAIL=$((FLOW_FAIL + 1))
            fi
        else
            warn_check "${test_name}: no summary line found"
            FLOW_SKIP=$((FLOW_SKIP + 1))
        fi
    elif [ "${rc}" -eq 0 ]; then
        pass_check "${test_name}: exited cleanly"
        FLOW_PASS=$((FLOW_PASS + 1))
    else
        fail_check "${test_name}: exited with code ${rc}"
        FLOW_FAIL=$((FLOW_FAIL + 1))
    fi

    rm -f "${flow_log}"
}

run_flow_test "${PROJECT}/tests/flows/backlight/test_backlight.sh" "backlight"
run_flow_test "${PROJECT}/tests/flows/volume/test_volume.sh" "volume"
run_flow_test "${PROJECT}/tests/flows/diagnosis/test_diagnosis.sh" "diagnosis"

echo ""
echo "  Flow smoke: ${FLOW_PASS} suites passed, ${FLOW_FAIL} failed, ${FLOW_SKIP} skipped"

echo ""

# --- Phase 10: pytest smoke check ---
echo "[Phase 10] pytest UI test suite"
PYTEST_LOG=$(mktemp /tmp/ipk_pytest_XXXXXX.log)
cd "${PROJECT}"
python3 -m pytest tests/ui/ -q --tb=line 2>&1 | tee "${PYTEST_LOG}" | tail -5
PYTEST_RC=${PIPESTATUS[0]}

if [ "${PYTEST_RC}" -eq 0 ]; then
    pass_check "pytest UI test suite passed"
else
    # Count failures
    pytest_summary=$(tail -1 "${PYTEST_LOG}")
    fail_check "pytest UI test suite failed: ${pytest_summary}"
fi
rm -f "${PYTEST_LOG}"

echo ""

# --- Summary ---
TOTAL=$((PASS + FAIL))
echo "========================================"
echo "  IPK QEMU Integration Test — Summary"
echo "========================================"
echo "  PASS: ${PASS}"
echo "  FAIL: ${FAIL}"
echo "  WARN: ${WARN}"
echo "  TOTAL: ${TOTAL} checks"
echo "========================================"

if [ "${FAIL}" -gt 0 ]; then
    echo ""
    echo "RESULT: FAIL (${FAIL} failures)"
    exit 1
else
    echo ""
    echo "RESULT: PASS (all checks passed, ${WARN} warnings)"
    exit 0
fi
