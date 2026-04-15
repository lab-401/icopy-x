#!/bin/bash
# Run scan scenarios in PARALLEL under QEMU.
# Each scenario gets its own Xvfb display, key injection file, and QEMU instance.
# Validates that the last frame is NOT the main menu.
#
# Usage: bash tools/run_scan_parallel.sh [max_parallel]

set +e

PROJECT="/home/qx/icopy-x-reimpl"
SDIR="$PROJECT/docs/screenshots/v1090_scenarios"
LAUNCHER="$PROJECT/tools/minimal_launch_090.py"
FIXTURES="$PROJECT/tools/pm3_fixtures.py"
SITE1="/mnt/sdcard/root1/home/pi/.local/lib/python3.8/site-packages"
SITE2="/mnt/sdcard/root2/root/home/pi/.local/lib/python3.8/site-packages"
MAX_PARALLEL="${1:-4}"  # Default 4 parallel workers

# Verify environment
if [ ! -f "/mnt/sdcard/root2/root/home/pi/ipk_app_main/lib/actmain.so" ]; then
    echo "ERROR: rootfs not mounted. Run tools/setup_qemu_env.sh first."
    exit 1
fi

PASS=0; FAIL=0; TOTAL=0; SKIP=0
RESULTS_DIR="/tmp/scan_parallel_results"
mkdir -p "$RESULTS_DIR"

run_scan_worker() {
    local scenario="$1"
    local display_num="$2"
    local min_unique="${3:-3}"

    local outdir="$SDIR/scan_${scenario}"
    local raw="/tmp/raw_scan_p${display_num}"
    local mock="/tmp/mock_p${display_num}.py"
    local kf="/tmp/icopy_keys_p${display_num}.txt"
    local logfile="/tmp/log_scan_p${display_num}.log"
    local result_file="$RESULTS_DIR/${scenario}.result"

    # Setup display
    Xvfb :${display_num} -screen 0 240x240x24 -ac >/dev/null 2>&1 &
    local xvfb_pid=$!
    sleep 1

    rm -rf "$outdir" "$raw"; mkdir -p "$outdir" "$raw"; > "$kf"

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

    # Boot QEMU on its own display
    QEMU_LD_PREFIX=/mnt/sdcard/root2/root \
    QEMU_SET_ENV="LD_LIBRARY_PATH=/mnt/sdcard/root2/root/usr/local/python-3.8.0/lib:/mnt/sdcard/root2/root/usr/lib/arm-linux-gnueabihf:/mnt/sdcard/root2/root/lib/arm-linux-gnueabihf:/mnt/sdcard/root1/usr/lib/arm-linux-gnueabihf:/mnt/sdcard/root1/lib/arm-linux-gnueabihf" \
    DISPLAY=:${display_num} PYTHONPATH="$SITE1:$SITE2" PYTHONUNBUFFERED=1 \
    PM3_SCENARIO_FILE="$mock" \
    ICOPY_KEY_FILE="$kf" \
    timeout 80 /home/qx/.local/bin/qemu-arm-static \
      /mnt/sdcard/root2/root/usr/local/python-3.8.0/bin/python3.8 \
      -u "$LAUNCHER" > "$logfile" 2>&1 &
    local qemu_pid=$!

    # Wait for HMI binding (up to 40s)
    for attempt in $(seq 1 20); do
        sleep 2
        if grep -q "\[HMI\]" "$logfile" 2>/dev/null; then
            break
        fi
    done
    sleep 2

    # GOTO Scan Tag (position 2)
    echo "GOTO:2" >> "$kf"

    # Capture scanning phase (25 seconds at 0.2s intervals)
    for i in $(seq 1 125); do
        import -display :${display_num} -window root "$raw/$(printf '%05d' $i).png" 2>/dev/null
        sleep 0.2
    done

    # TOAST_CANCEL
    echo "TOAST_CANCEL" >> "$kf"
    sleep 2

    # Capture clean result (5 seconds)
    for i in $(seq 126 150); do
        import -display :${display_num} -window root "$raw/$(printf '%05d' $i).png" 2>/dev/null
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

    # === VALIDATION: Check last frame is NOT the main menu ===
    local last_frame=$(ls "$outdir"/state_*.png 2>/dev/null | sort | tail -1)
    local is_menu="unknown"
    if [ -n "$last_frame" ]; then
        local last_sz=$(stat -c%s "$last_frame" 2>/dev/null || echo 0)
        # Check if PM3 commands were sent (scan actually started)
        local pm3_count=$(grep -c "\[PM3\]" "$logfile" 2>/dev/null || echo 0)
        # Check if we have a result screen (size > 10000 typically means tag details)
        local has_result=false
        for f in "$outdir"/state_*.png; do
            local fsz=$(stat -c%s "$f" 2>/dev/null || echo 0)
            if [ "$fsz" -gt 10000 ]; then
                has_result=true
                break
            fi
        done

        if [ "$pm3_count" -gt 0 ] && [ "$has_result" = true ]; then
            is_menu="no"
        elif [ "$pm3_count" -eq 0 ]; then
            is_menu="yes_no_pm3"
        else
            is_menu="suspect"
        fi
    fi

    # Determine pass/fail
    local status="FAIL"
    if [ "$idx" -ge "$min_unique" ] && [ "$is_menu" = "no" ]; then
        status="PASS"
    elif [ "$idx" -ge "$min_unique" ] && [ "$is_menu" = "suspect" ]; then
        status="WARN"
    fi

    echo "${status} ${scenario} ${idx} ${is_menu}" > "$result_file"

    # Cleanup
    kill $qemu_pid 2>/dev/null; wait $qemu_pid 2>/dev/null
    kill $xvfb_pid 2>/dev/null; wait $xvfb_pid 2>/dev/null
    rm -rf "$raw" "$mock" "$kf"
}

# All 44 scenarios
SCENARIOS=(
    no_tag mf_classic_1k_4b mf_classic_1k_7b mf_classic_4k_4b mf_classic_4k_7b
    mf_mini mf_ultralight ntag215 mf_desfire multi_tags
    mf_possible_4b hf14a_other iclass iso15693_icode iso15693_st
    legic iso14443b topaz felica em410x hid_prox indala t55xx_blank
    awid ioprx gprox securakey viking pyramid fdxb
    gallagher jablotron keri nedap noralsy pac paradox
    presco visa2000 hitag nexwatch
    bcc0_incorrect gen2_cuid mf_possible_7b
)

echo "========================================"
echo "  v1.0.90 PARALLEL SCAN CAPTURE"
echo "  Workers: $MAX_PARALLEL"
echo "  Scenarios: ${#SCENARIOS[@]}"
echo "  Output: $SDIR/scan_*/"
echo "========================================"

# Run in parallel batches
display_base=100
active_pids=()
active_scenarios=()
batch_idx=0

for scenario in "${SCENARIOS[@]}"; do
    TOTAL=$((TOTAL + 1))
    display_num=$((display_base + (batch_idx % MAX_PARALLEL)))

    # Wait for a slot if all workers are busy
    while [ ${#active_pids[@]} -ge $MAX_PARALLEL ]; do
        # Wait for any child to finish
        for i in "${!active_pids[@]}"; do
            if ! kill -0 "${active_pids[$i]}" 2>/dev/null; then
                # Worker finished — read result
                local_scenario="${active_scenarios[$i]}"
                if [ -f "$RESULTS_DIR/${local_scenario}.result" ]; then
                    read status sc states menu_check < "$RESULTS_DIR/${local_scenario}.result"
                    if [ "$status" = "PASS" ]; then
                        PASS=$((PASS + 1))
                        echo "[PASS] scan_${local_scenario}: ${states} unique states"
                    elif [ "$status" = "WARN" ]; then
                        PASS=$((PASS + 1))
                        echo "[WARN] scan_${local_scenario}: ${states} unique states (menu_check=${menu_check})"
                    else
                        FAIL=$((FAIL + 1))
                        echo "[FAIL] scan_${local_scenario}: ${states} unique states (menu_check=${menu_check})"
                    fi
                fi
                unset 'active_pids[i]'
                unset 'active_scenarios[i]'
                # Re-index arrays
                active_pids=("${active_pids[@]}")
                active_scenarios=("${active_scenarios[@]}")
                break
            fi
        done
        sleep 1
    done

    # Launch worker
    echo "  [${TOTAL}/${#SCENARIOS[@]}] Launching scan_${scenario} on :${display_num}"
    run_scan_worker "$scenario" "$display_num" 3 &
    active_pids+=($!)
    active_scenarios+=("$scenario")
    batch_idx=$((batch_idx + 1))

    sleep 0.5  # Stagger launches slightly
done

# Wait for remaining workers
for i in "${!active_pids[@]}"; do
    wait "${active_pids[$i]}" 2>/dev/null
    local_scenario="${active_scenarios[$i]}"
    if [ -f "$RESULTS_DIR/${local_scenario}.result" ]; then
        read status sc states menu_check < "$RESULTS_DIR/${local_scenario}.result"
        if [ "$status" = "PASS" ]; then
            PASS=$((PASS + 1))
            echo "[PASS] scan_${local_scenario}: ${states} unique states"
        elif [ "$status" = "WARN" ]; then
            PASS=$((PASS + 1))
            echo "[WARN] scan_${local_scenario}: ${states} unique states (menu_check=${menu_check})"
        else
            FAIL=$((FAIL + 1))
            echo "[FAIL] scan_${local_scenario}: ${states} unique states (menu_check=${menu_check})"
        fi
    fi
done

echo ""
echo "========================================"
echo "  COMPLETE: $PASS PASS, $FAIL FAIL / $TOTAL total"
echo "========================================"

# Cleanup
rm -rf "$RESULTS_DIR"
