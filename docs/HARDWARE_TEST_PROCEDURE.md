# Real Hardware Test Procedure

## Prerequisites

- iCopy-X device with firmware v1.0.90
- SSH access via reverse tunnel (port 2222, root:fa)
- USB cable for IPK transfer
- Backup of original firmware
- RFID tags for testing:
  - MIFARE Classic 1K (for scan/read/write)
  - Gen1a Magic card (for write/erase)
  - T55XX LF tag (for LF operations)
  - iClass tag (optional, for HF iClass)

## IMPORTANT: Safety Rules

- **NEVER flash PM3 bootrom** -- no JTAG means a bricked device with zero recovery
- **NEVER access ~/.ssh on any device**
- **NEVER run strace and framebuffer capture simultaneously** (use 2-run protocol)
- Always have a rollback plan before installing

## Pre-Test Checklist

- [ ] Backup current firmware and app files
  ```bash
  mkdir -p ./backup/$(date +%Y%m%d)
  scp -P 2222 -r root@localhost:/home/pi/ipk_app_main/lib/ ./backup/$(date +%Y%m%d)/lib_orig/
  scp -P 2222 -r root@localhost:/home/pi/ipk_app_main/main/ ./backup/$(date +%Y%m%d)/main_orig/
  ```
- [ ] Verify device boots normally with original firmware
- [ ] Record current settings (backlight level, volume level)
- [ ] Verify PM3 hardware responds (HF + LF LEDs on antenna test)
- [ ] Ensure USB storage (/mnt/upan/) has free space

## IPK Installation

### 1. Transfer IPK to device

```bash
scp -P 2222 dist/icopy-x-oss.ipk root@localhost:/mnt/upan/
```

### 2. Install IPK

```bash
ssh -p 2222 root@localhost

# Verify the IPK arrived
ls -la /mnt/upan/icopy-x-oss.ipk

# Extract and install (standard IPK = ar archive with data.tar.gz)
cd /tmp
ar x /mnt/upan/icopy-x-oss.ipk
tar xzf data.tar.gz -C /

# Or if the device uses opkg:
# opkg install /mnt/upan/icopy-x-oss.ipk
```

### 3. Verify installation

```bash
# Check that our Python modules are in place
ls -la /home/pi/ipk_app_main/lib/*.py

# Check that replaced .so files are gone
for f in actbase actstack widget batteryui hmi_driver keymap resources images actmain activity_main activity_tools activity_update; do
    [ -f /home/pi/ipk_app_main/lib/${f}.so ] && echo "WARNING: stale ${f}.so" || echo "OK: ${f}.so removed"
done

# Check that middleware .so files remain
for f in executor scan read write sniff tagtypes container; do
    [ -f /home/pi/ipk_app_main/lib/${f}.so ] && echo "OK: ${f}.so present" || echo "ERROR: ${f}.so missing!"
done

# Check JSON screens
ls /home/pi/ipk_app_main/screens/*.json | wc -l
```

### 4. Reboot device

```bash
reboot
```

## Test Matrix

### Level 1: Basic Boot (MUST PASS -- rollback if any fail)

| # | Test | Expected | Pass |
|---|------|----------|------|
| 1.1 | Device boots to main menu | 14 menu items visible | [ ] |
| 1.2 | Scroll down through all pages | Page 1 (4 items), Page 2 (4 items), Page 3 (4 items), Page 4 (2 items) | [ ] |
| 1.3 | Scroll back up to top | Returns to first page | [ ] |
| 1.4 | Battery icon displays | Top-right corner, shows level | [ ] |
| 1.5 | PWR key exits from main menu | Returns to main menu (no crash) | [ ] |
| 1.6 | No crash after 30 seconds idle | Screen stays rendered | [ ] |

### Level 2: Settings (MUST PASS)

| # | Test | Expected | Pass |
|---|------|----------|------|
| 2.1 | Backlight: navigate to setting | Radio list: Low/Mid/High | [ ] |
| 2.2 | Backlight: change Low to Mid | Toast confirms, display brightness changes | [ ] |
| 2.3 | Backlight: change Mid to High | Toast confirms, display brightness changes | [ ] |
| 2.4 | Backlight: PWR exits | Returns to main menu | [ ] |
| 2.5 | Volume: navigate to setting | Radio list: Off/Low/Mid/High | [ ] |
| 2.6 | Volume: change Off to Mid | Toast confirms, audio plays | [ ] |
| 2.7 | Volume: PWR exits | Returns to main menu | [ ] |
| 2.8 | Diagnosis: run HF reader test | Shows test progress and result | [ ] |
| 2.9 | Diagnosis: run LF reader test | Shows test progress and result | [ ] |
| 2.10 | About: shows version info | Firmware version, device serial visible | [ ] |

### Level 3: RFID Operations

| # | Test | Tags Needed | Expected | Pass |
|---|------|-------------|----------|------|
| 3.1 | Scan: detect MIFARE Classic 1K | MF Classic 1K | Tag type and UID displayed | [ ] |
| 3.2 | Scan: detect T55XX | T55XX tag | Tag type displayed | [ ] |
| 3.3 | Scan: no tag present | (none) | "Tag not found" toast | [ ] |
| 3.4 | Read: read MIFARE Classic 1K | MF Classic 1K | Key recovery + data read | [ ] |
| 3.5 | Read: read with default keys | MF Classic 1K (default keys) | Fast read, all sectors | [ ] |
| 3.6 | Write: write to Gen1a | Gen1a + source data | Write succeeds, verify pass | [ ] |
| 3.7 | Auto Copy: full MF1K cycle | MF Classic 1K + Gen1a | Scan, read, prompt swap, write, verify | [ ] |
| 3.8 | Erase: wipe Gen1a | Gen1a | Erase succeeds, tag blanked | [ ] |
| 3.9 | Sniff: capture 14A trace | 2x MF Classic (reader + card) | Trace captured | [ ] |

### Level 4: Edge Cases

| # | Test | Expected | Pass |
|---|------|----------|------|
| 4.1 | PWR exits from scan screen | Returns to main menu | [ ] |
| 4.2 | PWR exits from read progress | Cancels read, returns | [ ] |
| 4.3 | PWR exits from write confirm | Cancels write, returns | [ ] |
| 4.4 | Scan with wrong tag type | "Wrong tag type" toast | [ ] |
| 4.5 | Multiple tags on reader | Warning displayed | [ ] |
| 4.6 | Read tag removed mid-read | Error toast, recoverable | [ ] |
| 4.7 | PC-Mode toggle | USB bridge instructions shown | [ ] |
| 4.8 | Time settings | Can navigate date/time fields | [ ] |
| 4.9 | LUA Script | File list shown (if scripts present) | [ ] |
| 4.10 | Low battery display | Battery icon turns red/yellow | [ ] |

### Level 5: Stress Tests (optional)

| # | Test | Expected | Pass |
|---|------|----------|------|
| 5.1 | Rapid key presses (10x in 2s) | No crash, responsive | [ ] |
| 5.2 | 50 scan/exit cycles | No memory leak, stays responsive | [ ] |
| 5.3 | Full read + write 5x in a row | All succeed | [ ] |
| 5.4 | Leave device on 10 minutes | Auto-sleep activates, wakes on key | [ ] |

## Instrumentation (if debugging needed)

Follow the standard 2-run capture protocol:

### Run 1: strace capture
```bash
# On the device
PID=$(pgrep -f "python.*app.py" | head -1)
strace -ff -p $PID -e trace=write -o /mnt/upan/trace/run1 &
# Perform the operation being debugged
# Stop strace
kill %1
```

### Run 2: framebuffer capture
```bash
# On the device (500ms interval, RGB565 from /dev/fb1)
while true; do
    ts=$(date +%s%N)
    cp /dev/fb1 /mnt/upan/trace/fb_${ts}.raw
    sleep 0.5
done &
FB_PID=$!
# Perform the operation being debugged
kill $FB_PID
```

**NEVER run strace and framebuffer capture at the same time.**

## Rollback

If any Level 1 test fails, immediately rollback:

```bash
ssh -p 2222 root@localhost

# Restore original .so files
scp -P 2222 ./backup/$(date +%Y%m%d)/lib_orig/*.so root@localhost:/home/pi/ipk_app_main/lib/

# Remove our Python modules
rm -f /home/pi/ipk_app_main/lib/*.py
rm -rf /home/pi/ipk_app_main/screens/

# Reboot
reboot
```

If SSH is unavailable (device bricked at UI level):
1. Remove SD card from device
2. Mount on Linux host
3. Restore files from backup
4. Re-insert SD card and boot

## Reporting

Record results in a new file `docs/HARDWARE_TEST_RESULTS.md` with:
- Date and time of test
- Device serial number (from About screen or cpuinfo)
- Firmware version
- IPK build identifier / git commit
- Pass/fail for each test in the matrix above
- Screenshots of any failures (captured via framebuffer or photo)
- Any error messages from logs (`/tmp/icopy_*.log` on device)
