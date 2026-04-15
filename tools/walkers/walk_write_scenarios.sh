#!/bin/bash
# Run write scenarios under QEMU.
# One fresh QEMU boot per scenario. Uses teleport to skip scan+read navigation.
# The .so handles ALL logic — scan, read, activity transitions, write, toasts.
# The mock provides PM3 fixture responses. No middleware.
#
# Output: docs/screenshots/Write/walker_v1/<scenario_name>/

set +e
PROJECT="/home/qx/icopy-x-reimpl"
SDIR="$PROJECT/docs/screenshots/Write/walker_v1"
LAUNCHER="$PROJECT/tools/minimal_launch_090.py"
KF="/tmp/icopy_keys_090.txt"

# Verify environment
if [ ! -f "/mnt/sdcard/root2/root/home/pi/ipk_app_main/lib/actmain.so" ]; then
    echo "ERROR: rootfs not mounted. Run tools/setup_qemu_env.sh first."
    exit 1
fi

PASS=0; FAIL=0; TOTAL=0

run_write() {
    local name="$1"           # scenario name
    local scenario_key="$2"   # key in ALL_WRITE_SCENARIO_RESPONSES
    local tag_type="$3"       # numeric tag type ID
    local dump_path="$4"      # path to dump file
    local min_unique="${5:-2}"
    TOTAL=$((TOTAL + 1))

    local outdir="$SDIR/${name}"
    local raw="/tmp/raw_write_${name}"
    local mock="/tmp/mock_write_${name}.py"
    local logfile="/tmp/log_write_${name}.log"

    killall -9 qemu-arm-static 2>/dev/null; sleep 1
    rm -rf "$outdir" "$raw"; mkdir -p "$outdir" "$raw"; > "$KF"

    # Create dump file if needed
    mkdir -p "$(dirname "$dump_path")"
    if [ ! -f "$dump_path" ]; then
        dd if=/dev/zero of="$dump_path" bs=1024 count=1 2>/dev/null
    fi

    # Generate PM3 mock from pre-built SCENARIO_RESPONSES
    python3 -c "
import sys; sys.path.insert(0, '$PROJECT/tools')
from pm3_fixtures import ALL_WRITE_SCENARIO_RESPONSES

scenario = ALL_WRITE_SCENARIO_RESPONSES.get('$scenario_key', {})

lines = ['SCENARIO_RESPONSES = {']
for k, v in scenario.items():
    if isinstance(v, tuple):
        lines.append(\"    '%s': (%d, '''%s'''),\" % (k, v[0], v[1].replace(\"'''\", \"\\\\'''\")))
lines.append('}')
lines.append('DEFAULT_RETURN = -1')
print('\n'.join(lines))
" > "$mock" 2>/dev/null

    # Boot QEMU with teleport
    QEMU_LD_PREFIX=/mnt/sdcard/root2/root \
    QEMU_SET_ENV="LD_LIBRARY_PATH=/mnt/sdcard/root2/root/usr/local/python-3.8.0/lib:/mnt/sdcard/root2/root/usr/lib/arm-linux-gnueabihf:/mnt/sdcard/root2/root/lib/arm-linux-gnueabihf:/mnt/sdcard/root1/usr/lib/arm-linux-gnueabihf:/mnt/sdcard/root1/lib/arm-linux-gnueabihf" \
    DISPLAY=:99 \
    PYTHONPATH="/mnt/sdcard/root2/root/home/pi/.local/lib/python3.8/site-packages:/mnt/sdcard/root2/root/home/pi/ipk_app_main/lib:/mnt/sdcard/root2/root/home/pi/ipk_app_main/main:/mnt/sdcard/root2/root/home/pi/ipk_app_main:$PROJECT/tools/qemu_shims" \
    PYTHONUNBUFFERED=1 \
    PM3_SCENARIO_FILE="$mock" \
    PM3_MOCK_DELAY=0.3 \
    ICOPY_KEY_FILE="$KF" \
    WRITE_TELEPORT="${tag_type}:${dump_path}" \
    timeout 120 /home/qx/.local/bin/qemu-arm-static \
      /mnt/sdcard/root2/root/usr/local/python-3.8.0/bin/python3.8 \
      -u "$LAUNCHER" > "$logfile" 2>&1 &
    local pid=$!

    # Wait for teleport to complete
    local teleported=false
    for attempt in $(seq 1 60); do
        sleep 1
        if grep -q "Pushed WarningWriteActivity" "$logfile" 2>/dev/null; then
            teleported=true
            break
        fi
        if grep -q "TELEPORT.*FAILED\|TELEPORT.*Error" "$logfile" 2>/dev/null; then
            break
        fi
    done

    if [ "$teleported" != "true" ]; then
        echo "[FAIL] ${name}: teleport failed"
        FAIL=$((FAIL + 1))
        cp "$logfile" "$outdir/log.txt" 2>/dev/null
        kill $pid 2>/dev/null; wait $pid 2>/dev/null
        rm -rf "$raw" "$mock"
        return
    fi

    sleep 3  # Let "Data ready!" screen render

    # Capture "Data ready!" screen
    import -display :99 -window root "$raw/00001.png" 2>/dev/null

    # Press M2 ("Write") on "Data ready!" screen
    echo "M2" >> "$KF"

    # Capture write flow (30 seconds — includes writing progress + toast)
    for i in $(seq 2 120); do
        import -display :99 -window root "$raw/$(printf '%05d' $i).png" 2>/dev/null
        sleep 0.25
    done

    # TOAST_CANCEL
    echo "TOAST_CANCEL" >> "$KF"
    sleep 2

    # Capture after toast
    for i in $(seq 121 140); do
        import -display :99 -window root "$raw/$(printf '%05d' $i).png" 2>/dev/null
        sleep 0.1
    done

    # Dedup
    local idx=0 prev=""
    for f in $(ls "$raw"/*.png 2>/dev/null | sort); do
        local h=$(md5sum "$f" | awk '{print $1}')
        if [ "$h" != "$prev" ]; then
            idx=$((idx+1))
            cp "$f" "$outdir/state_$(printf '%03d' $idx).png"
            prev="$h"
        fi
    done

    # Save log
    cp "$logfile" "$outdir/log.txt" 2>/dev/null

    # Check result
    local has_write_toast=false
    if grep -q "Write successful\|Write failed\|Verification" "$logfile" 2>/dev/null; then
        has_write_toast=true
    fi

    if [ "$idx" -ge "$min_unique" ] && [ "$has_write_toast" = "true" ]; then
        PASS=$((PASS + 1))
        echo "[PASS] ${name}: $idx unique states"
    else
        FAIL=$((FAIL + 1))
        echo "[FAIL] ${name}: $idx unique states, toast=$has_write_toast"
    fi

    kill $pid 2>/dev/null; wait $pid 2>/dev/null
    rm -rf "$raw" "$mock"
}

echo "========================================"
echo "  v1.0.90 WRITE SCENARIO WALKER"
echo "  Output: $SDIR/"
echo "  Teleport: scan via .so → push WarningWriteActivity → M2 → write"
echo "========================================"

# === SCENARIOS ===
# Each: name, scan_fixture, write_fixture, tag_type, dump_path

echo ""
echo "--- [1] m1_s50_1k_4b__write_standard_success ---"
run_write \
    "m1_s50_1k_4b__write_standard_success" \
    "mfc_1k_4b__write_standard_success" \
    1 \
    "/tmp/wdump/mf1/TEST_1.bin"

echo ""
echo "========================================"
echo "  COMPLETE: $PASS PASS, $FAIL FAIL / $TOTAL total"
echo "========================================"
