#!/bin/bash
# Stub PM3 flash tool — mimics proxmark3 --flash output for UI testing.
# Accepts the same CLI args as the real tool. Does NOT touch hardware.
#
# Usage:
#   stub_pm3_flash.sh /dev/ttyACM0 --flash --force --image fullimage.elf
#   stub_pm3_flash.sh --fail /dev/ttyACM0 --flash --force --image fullimage.elf
#
# Modes:
#   Normal (default): simulates successful flash (~8 seconds)
#   --fail: simulates flash failure at block write stage

FAIL_MODE=0
if [ -f /mnt/upan/stub_fail ] || [ "$1" = "--fail" ]; then
    FAIL_MODE=1
    [ "$1" = "--fail" ] && shift
fi

# Parse args: proxmark3 <device> --flash [--force] --image <file>
DEVICE="$1"
IMAGE=""
while [ $# -gt 0 ]; do
    if [ "$1" = "--image" ]; then
        IMAGE="$2"
        shift
    fi
    shift
done

echo "[=] Session log /root/.proxmark3/logs/log_$(date +%Y%m%d%H%M%S).txt"
sleep 0.5

echo "[+] Waiting for Proxmark3 to appear on $DEVICE"
sleep 1

echo "[+] 1 found"
sleep 0.5

echo "[+] Entering bootloader..."
sleep 1

echo "[+] 1 found"
sleep 0.5

echo "[+] Loading ELF file $IMAGE"
sleep 0.5

echo "[+] Flashing..."
sleep 0.5

echo "[+] Writing segments for file: $IMAGE"
echo "0x00102000..0x0013e0eb [0x3c0ec / 481 blocks]"
sleep 0.5

# Simulate block writing with dots
for i in $(seq 1 48); do
    printf "."
    sleep 0.1
done

if [ "$FAIL_MODE" = "1" ]; then
    echo ""
    echo "[!!] ERROR: block write failed at offset 0x00120000"
    echo "[!!] Flash FAILED"
    exit 1
fi

echo "mm OK"
sleep 0.5

echo "[+] All done."
echo ""
echo "Have a nice day!"
exit 0
