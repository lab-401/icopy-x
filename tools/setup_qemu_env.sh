#!/bin/bash
# Self-healing QEMU environment setup.
# Run this after any reboot/reset to restore the full environment.
# Safe to run multiple times — checks before acting.

set -e

PROJECT="/home/qx/icopy-x-reimpl"
QEMU="/home/qx/.local/bin/qemu-arm-static"
IMG="/home/qx/02150004-1_0_90.img"
IMG_RAR="/home/qx/icpyximg.rar"
SHIMS="$PROJECT/tools/qemu_shims"

log() { echo "[SETUP] $1"; }

# === 1. Check QEMU binary ===
if [ -f "$QEMU" ]; then
    log "QEMU binary: OK ($QEMU)"
else
    log "FATAL: QEMU binary not found at $QEMU"
    exit 1
fi

# === 2. Check/decompress SD card image ===
if [ ! -f "$IMG" ]; then
    log "SD card image not found at $IMG"
    if [ -f "$IMG_RAR" ]; then
        log "Decompressing from $IMG_RAR..."
        cd /home/qx && unrar x "$IMG_RAR" 2>/dev/null || 7z x "$IMG_RAR" 2>/dev/null || {
            log "FATAL: Cannot decompress $IMG_RAR (need unrar or 7z)"
            exit 1
        }
        # Find the extracted .img
        extracted=$(find /home/qx -name "*.img" -newer "$IMG_RAR" -size +1G 2>/dev/null | head -1)
        if [ -n "$extracted" ] && [ "$extracted" != "$IMG" ]; then
            mv "$extracted" "$IMG"
        fi
    else
        log "FATAL: No image file found. Need $IMG or $IMG_RAR"
        exit 1
    fi
fi
log "SD card image: OK ($IMG, $(stat -c%s "$IMG") bytes)"

# === 3. Mount SD card partitions ===
BOOT="/mnt/sdcard/boot"
ROOT1="/mnt/sdcard/root1"
ROOT2="/mnt/sdcard/root2"
DATA="/mnt/sdcard/data"

sudo mkdir -p "$BOOT" "$ROOT1" "$ROOT2" "$DATA"

# Get partition offsets from the image
# Typical layout: boot(FAT32), root1(ext4), root2(ext4), data(FAT32)
mount_if_needed() {
    local mnt="$1" offset="$2" fstype="$3"
    if mountpoint -q "$mnt" 2>/dev/null; then
        log "  $mnt: already mounted"
    else
        sudo mount -o loop,offset=$offset,ro${fstype:+,} "$IMG" "$mnt" 2>/dev/null && \
            log "  $mnt: mounted (offset=$offset)" || \
            log "  $mnt: FAILED to mount"
    fi
}

# Check if already mounted correctly
if [ -f "$ROOT2/root/home/pi/ipk_app_main/lib/actmain.so" ]; then
    log "Partitions: already mounted correctly"
else
    log "Mounting partitions from $IMG..."
    # Use fdisk to get partition offsets
    PARTS=$(sudo fdisk -l "$IMG" 2>/dev/null | grep "$IMG" | tail -4)

    # Parse partition table
    P1_START=$(echo "$PARTS" | sed -n '1p' | awk '{print $2}')
    P2_START=$(echo "$PARTS" | sed -n '2p' | awk '{print $2}')
    P3_START=$(echo "$PARTS" | sed -n '3p' | awk '{print $2}')
    P4_START=$(echo "$PARTS" | sed -n '4p' | awk '{print $2}')

    # Known partition layout for iCopy-XS SD image (02150004-1_0_90.img):
    # P1: boot  FAT32  start=49152    sectors=81920
    # P2: root1 ext4   start=131072   sectors=3481601
    # P3: root2 ext4   start=4589568  sectors=3213312
    # P4: data  ext4   start=7802880  sectors=23146496

    # Clean up any existing loop devices for this image
    sudo losetup -j "$IMG" 2>/dev/null | awk -F: '{print $1}' | while read dev; do
        sudo losetup -d "$dev" 2>/dev/null
    done

    # Create separate loop devices (avoids "overlapping loop device" errors)
    sudo losetup -o $((49152*512))   --sizelimit $((81920*512))    /dev/loop10 "$IMG" 2>/dev/null
    sudo losetup -o $((131072*512))  --sizelimit $((3481601*512))  /dev/loop11 "$IMG" 2>/dev/null
    sudo losetup -o $((4589568*512)) --sizelimit $((3213312*512))  /dev/loop12 "$IMG" 2>/dev/null
    sudo losetup -o $((7802880*512)) --sizelimit $((23146496*512)) /dev/loop13 "$IMG" 2>/dev/null

    sudo mount -o ro /dev/loop10 "$BOOT"  2>/dev/null && log "  boot: OK"  || log "  boot: FAIL"
    sudo mount -o ro /dev/loop11 "$ROOT1" 2>/dev/null && log "  root1: OK" || log "  root1: FAIL"
    sudo mount -o ro /dev/loop12 "$ROOT2" 2>/dev/null && log "  root2: OK" || log "  root2: FAIL"
    sudo mount -o ro /dev/loop13 "$DATA"  2>/dev/null && log "  data: OK"  || log "  data: FAIL"

    # Verify
    if [ -f "$ROOT2/root/home/pi/ipk_app_main/lib/actmain.so" ]; then
        log "Partitions: mounted successfully"
    else
        log "WARN: actmain.so not found after mount. Check partition offsets."
        log "Try: sudo fdisk -l $IMG"
    fi
fi

# === 4. Create /mnt/upan symlink if needed ===
if [ ! -d "/mnt/upan" ]; then
    sudo ln -sf "$DATA" /mnt/upan 2>/dev/null || true
    log "/mnt/upan: symlinked to $DATA"
else
    log "/mnt/upan: exists"
fi

# === 4b. Prepare QEMU-mapped /mnt/upan (rootfs overlay) ===
# CRITICAL: Under QEMU user-mode, QEMU_LD_PREFIX rewrites file paths.
# When firmware accesses /mnt/upan/, QEMU maps it to ROOT2/root/mnt/upan/.
# This rootfs directory needs ipk_old/ for the install flow (firmware moves
# processed IPKs there). Clean any stale IPKs from previous test runs.
QEMU_UPAN="$ROOT2/root/mnt/upan"
if [ -d "$QEMU_UPAN" ]; then
    mkdir -p "$QEMU_UPAN/ipk_old"
    find "$QEMU_UPAN" -name "*.ipk" -delete 2>/dev/null || true
    log "QEMU /mnt/upan: ipk_old/ created, stale IPKs cleaned"
else
    log "WARN: QEMU-mapped /mnt/upan ($QEMU_UPAN) does not exist"
fi

# === 5. Set up QEMU shims (resources.py replacement) ===
mkdir -p "$SHIMS/Crypto/Cipher"
if [ ! -f "$SHIMS/resources.py" ]; then
    log "Creating resources.py shim..."
    # Copy from project if it exists in orig_so analysis, or generate
    if [ -f "$PROJECT/tools/qemu_shims/resources.py" ]; then
        log "  resources.py: already in project"
    else
        log "  WARN: resources.py shim needs to be created"
        log "  Run the string extraction to generate it"
    fi
fi

# Create Crypto shim (replaces pycryptodome for aesutils)
cat > "$SHIMS/Crypto/__init__.py" << 'EOF'
"""Crypto shim for QEMU — provides AES stubs."""
EOF
cat > "$SHIMS/Crypto/Cipher/__init__.py" << 'EOF'
"""AES cipher shim."""
class AES:
    MODE_ECB = 1
    MODE_CBC = 2
    MODE_CFB = 3
    block_size = 16
    @staticmethod
    def new(key, mode=1, iv=None):
        class _C:
            def encrypt(self, data): return data
            def decrypt(self, data): return data
        return _C()
EOF
log "Crypto shims: OK"

# === 6. Xvfb check ===
if pgrep -f "Xvfb :99" > /dev/null 2>&1; then
    log "Xvfb: running on :99"
else
    log "Starting Xvfb on :99..."
    Xvfb :99 -screen 0 240x240x24 &
    sleep 1
    log "Xvfb: started"
fi

# === 7. Image overlay directory ===
mkdir -p "$PROJECT/tools/qemu_img_overlay"
log "Image overlay dir: OK"

# === Summary ===
echo ""
echo "============================================"
echo "  QEMU Environment Ready"
echo "============================================"
echo "  QEMU:    $QEMU"
echo "  Image:   $IMG"
echo "  Root2:   $ROOT2/root/"
echo "  App:     $ROOT2/root/home/pi/ipk_app_main/"
echo "  Shims:   $SHIMS/"
echo "  Display: :99"
echo "============================================"
