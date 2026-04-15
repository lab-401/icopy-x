#!/bin/bash
# Run ALL install scenarios sequentially.
# Each scenario gets its own QEMU boot + isolated /mnt/upan/ state.
# Output: _results/{target}/install/scenarios/<name>/{screenshots/,logs/,result.txt}
# Summary: _results/{target}/install/scenario_summary.txt
#
# IMPORTANT: Install scenarios share the QEMU-mapped /mnt/upan/ (rootfs overlay).
# They MUST run sequentially — parallel execution causes IPK contamination.
# Ordering: install_no_ipk first (most sensitive to stale state),
# error scenarios middle, success scenarios last (restart_app kills QEMU).

set +e
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
TEST_TARGET="${TEST_TARGET:-original}"
RESULTS_DIR="${RESULTS_DIR:-${PROJECT}/tests/flows/_results/${TEST_TARGET}}"
INSTALL_RESULTS="${RESULTS_DIR}/install"
SUMMARY="${INSTALL_RESULTS}/scenario_summary.txt"

mkdir -p "${INSTALL_RESULTS}"
> "${SUMMARY}"

# Build fixture IPKs if not present
FIXTURE_DIR="${PROJECT}/tests/flows/install/fixtures"
if [ ! -f "${FIXTURE_DIR}/valid_minimal.ipk" ]; then
    echo "=== Building fixture IPKs ==="
    python3 "${FIXTURE_DIR}/build_fixtures.py"
fi

# Nuke ALL .ipk files from BOTH rootfs and host /mnt/upan/ before starting.
# QEMU reads from rootfs, but rename/unlink go to host — clean both.
ROOT_FS="/mnt/sdcard/root2/root"
QEMU_UPAN="${ROOT_FS}/mnt/upan"
HOST_UPAN="/mnt/upan"
mkdir -p "${QEMU_UPAN}/ipk_old" "${HOST_UPAN}/ipk_old"
find "${QEMU_UPAN}" -name "*.ipk" -delete 2>/dev/null
find "${HOST_UPAN}" -name "*.ipk" -delete 2>/dev/null
rm -rf /tmp/.ipk /tmp/ipk_extract 2>/dev/null

# Ordered scenario list — install_no_ipk FIRST, success scenarios LAST.
SCENARIO_ORDER=(
    # 1. No-IPK scenario first (most sensitive to stale /mnt/upan/ state)
    install_no_ipk

    # 2. READY state navigation (non-destructive, don't start install)
    install_ready_cancel
    install_ready_pwr

    # 3. checkPkg error scenarios (IPK validation fails)
    install_checkpkg_invalid_zip
    install_checkpkg_no_app
    install_checkpkg_no_install
    install_checkpkg_no_version

    # 4. checkVer error (DRM serial mismatch)
    install_checkver_fail

    # 5. Install module load failure
    install_install_exception

    # 6. Error dismiss scenarios
    install_error_dismiss_ok
    install_error_dismiss_pwr

    # 7. Success scenarios last (restart_app kills QEMU, may leave state)
    install_success_minimal
    install_success_with_fonts
)

SCENARIO_BASE="${PROJECT}/tests/flows/install/scenarios"

PASS=0; FAIL=0; TOTAL=0
START_TIME=$(date +%s)

echo "========================================"
echo "  INSTALL FLOW — SEQUENTIAL (${TEST_TARGET})"
echo "  Output: ${INSTALL_RESULTS}/"
echo "========================================"

for scenario_name in "${SCENARIO_ORDER[@]}"; do
    script="${SCENARIO_BASE}/${scenario_name}/${scenario_name}.sh"
    [ -f "$script" ] || { echo "SKIP: ${scenario_name} (script not found)"; continue; }

    TOTAL=$((TOTAL + 1))

    echo ""
    echo "--- [${TOTAL}] ${scenario_name} ---"

    # Pre-test cleanup: both rootfs and host paths
    find "${QEMU_UPAN}" -name "*.ipk" -delete 2>/dev/null
    find "${HOST_UPAN}" -name "*.ipk" -delete 2>/dev/null
    rm -rf /tmp/.ipk /tmp/ipk_extract 2>/dev/null

    # Run the scenario
    PROJECT="${PROJECT}" \
    RESULTS_DIR="${RESULTS_DIR}" \
    TEST_TARGET="${TEST_TARGET}" \
    bash "$script"

    # Check result
    result_file="${INSTALL_RESULTS}/scenarios/${scenario_name}/result.txt"
    if [ -f "$result_file" ] && grep -q "^PASS" "$result_file"; then
        PASS=$((PASS + 1))
        echo "${scenario_name}: PASS ($(head -1 "$result_file"))" >> "${SUMMARY}"
    else
        FAIL=$((FAIL + 1))
        msg="unknown"
        [ -f "$result_file" ] && msg=$(head -1 "$result_file")
        echo "${scenario_name}: FAIL (${msg})" >> "${SUMMARY}"
    fi

    # Post-test cleanup: both rootfs and host paths
    find "${QEMU_UPAN}" -name "*.ipk" -delete 2>/dev/null
    find "${HOST_UPAN}" -name "*.ipk" -delete 2>/dev/null
    rm -rf /tmp/.ipk /tmp/ipk_extract 2>/dev/null
done

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

# Write summary footer
echo "" >> "${SUMMARY}"
echo "========================================" >> "${SUMMARY}"
echo "TOTAL: ${TOTAL}  PASS: ${PASS}  FAIL: ${FAIL}" >> "${SUMMARY}"
echo "Duration: ${ELAPSED}s" >> "${SUMMARY}"
echo "========================================" >> "${SUMMARY}"

echo ""
echo "========================================"
echo "  COMPLETE: ${PASS} PASS, ${FAIL} FAIL / ${TOTAL} total (${ELAPSED}s)"
echo "========================================"

if [ "$FAIL" -gt 0 ]; then
    echo ""
    echo "Failed scenarios:"
    grep "FAIL" "${SUMMARY}" | head -20
fi
