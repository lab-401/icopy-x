#!/bin/bash
# Run all 44 scan scenarios under QEMU.
# One fresh QEMU boot per scenario. Captures at 0.1s intervals, deduplicates.
# Output: docs/screenshots/v1090_scenarios/<scenario_name>/

set +e
PROJECT="/home/qx/icopy-x-reimpl"
SDIR="$PROJECT/docs/screenshots/v1090_scenarios"
LAUNCHER="$PROJECT/tools/minimal_launch_090.py"
FIXTURES="$PROJECT/tools/pm3_fixtures.py"
KF="/tmp/icopy_keys_090.txt"
SITE1="/mnt/sdcard/root1/home/pi/.local/lib/python3.8/site-packages"
SITE2="/mnt/sdcard/root2/root/home/pi/.local/lib/python3.8/site-packages"

# Verify environment
if [ ! -f "/mnt/sdcard/root2/root/home/pi/ipk_app_main/lib/actmain.so" ]; then
    echo "ERROR: rootfs not mounted. Run tools/setup_qemu_env.sh first."
    exit 1
fi

PASS=0; FAIL=0; TOTAL=0

run_scan() {
    local scenario="$1"
    local min_unique="${2:-3}"
    TOTAL=$((TOTAL + 1))

    local outdir="$SDIR/scan_${scenario}"
    local raw="/tmp/raw_scan_${scenario}"
    local mock="/tmp/mock_${scenario}.py"

    killall -9 qemu-arm-static 2>/dev/null; sleep 1
    rm -rf "$outdir" "$raw"; mkdir -p "$outdir" "$raw"; > "$KF"

    # Generate PM3 mock
    python3 -c "
import sys; sys.path.insert(0, '$PROJECT/tools')
from pm3_fixtures import ALL_SCAN_SCENARIOS
f = ALL_SCAN_SCENARIOS.get('$scenario', {'_default_return': -1})
default_ret = f.get('_default_return', -1)
lines = ['SCENARIO_RESPONSES = {']
for k, v in f.items():
    if k.startswith('_'): continue
    if isinstance(v, tuple): lines.append(\"    '%s': (%d, '''%s'''),\" % (k, v[0], v[1]))
    else: lines.append(\"    '%s': %r,\" % (k, v))
lines.append('}'); lines.append('DEFAULT_RETURN = %d' % default_ret)
print('\n'.join(lines))
" > "$mock" 2>/dev/null

    # Boot QEMU
    QEMU_LD_PREFIX=/mnt/sdcard/root2/root \
    QEMU_SET_ENV="LD_LIBRARY_PATH=/mnt/sdcard/root2/root/usr/local/python-3.8.0/lib:/mnt/sdcard/root2/root/usr/lib/arm-linux-gnueabihf:/mnt/sdcard/root2/root/lib/arm-linux-gnueabihf:/mnt/sdcard/root1/usr/lib/arm-linux-gnueabihf:/mnt/sdcard/root1/lib/arm-linux-gnueabihf" \
    DISPLAY=:99 PYTHONPATH="$SITE1:$SITE2" PYTHONUNBUFFERED=1 \
    PM3_SCENARIO_FILE="$mock" \
    CANVAS_LOG="$outdir/canvas_text.log" \
    timeout 80 /home/qx/.local/bin/qemu-arm-static \
      /mnt/sdcard/root2/root/usr/local/python-3.8.0/bin/python3.8 \
      -u "$LAUNCHER" > "/tmp/log_scan_${scenario}.log" 2>&1 &
    local pid=$!

    # Poll for toast dismiss + HMI binding
    for attempt in $(seq 1 30); do
        sleep 2
        import -display :99 -window root /tmp/poll_check.png 2>/dev/null
        local sz=$(stat -c%s /tmp/poll_check.png 2>/dev/null || echo 0)
        local hmi=$(grep -c "\[HMI\]" "/tmp/log_scan_${scenario}.log" 2>/dev/null || echo 0)
        if [ "$sz" -gt 5000 ] && [ "$sz" -lt 17000 ] && [ "$hmi" -gt 0 ]; then
            break
        fi
    done
    sleep 1

    # GOTO Scan Tag (position 2)
    echo "GOTO:2" >> "$KF"

    # Capture scanning phase (20 seconds — includes progress bar + result toast)
    for i in $(seq 1 200); do
        import -display :99 -window root "$raw/$(printf '%05d' $i).png" 2>/dev/null
        sleep 0.1
    done

    # TOAST_CANCEL to remove toast overlay and reveal clean card details
    echo "TOAST_CANCEL" >> "$KF"
    sleep 2

    # Capture the clean result screen (after toast removed)
    for i in $(seq 201 250); do
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

    # Validate
    local result_screen=false
    for f in "$outdir"/state_*.png; do
        local fsz=$(stat -c%s "$f" 2>/dev/null || echo 0)
        if [ "$fsz" -gt 8000 ] && [ "$fsz" -lt 16000 ]; then
            result_screen=true
        fi
    done

    if [ "$idx" -ge "$min_unique" ]; then
        PASS=$((PASS + 1))
        echo "[PASS] scan_${scenario}: $idx unique states"
    else
        FAIL=$((FAIL + 1))
        echo "[FAIL] scan_${scenario}: $idx unique states (expected >= $min_unique)"
    fi

    kill $pid 2>/dev/null; wait $pid 2>/dev/null
    rm -rf "$raw" "$mock"
}

echo "========================================"
echo "  v1.0.90 SCAN SCENARIO CAPTURE"
echo "  Output: $SDIR/scan_*/"
echo "========================================"

# Run all 44 scan scenarios
for scenario in \
    no_tag mf_classic_1k_4b mf_classic_1k_7b mf_classic_4k_4b mf_classic_4k_7b \
    mf_mini mf_ultralight ntag215 mf_desfire multi_tags \
    mf_possible_4b hf14a_other iclass iso15693_icode iso15693_st \
    legic iso14443b topaz felica em410x hid_prox indala t55xx_blank \
    awid ioprx gprox securakey viking pyramid fdxb \
    gallagher jablotron keri nedap noralsy pac paradox \
    presco visa2000 hitag nexwatch \
    bcc0_incorrect gen2_cuid mf_possible_7b; do

    echo ""
    echo "--- [$TOTAL] scan_${scenario} ---"
    run_scan "$scenario" 3
done

echo ""
echo "========================================"
echo "  COMPLETE: $PASS PASS, $FAIL FAIL / $TOTAL total"
echo "========================================"
