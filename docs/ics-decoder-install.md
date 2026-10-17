# ICS-Decoder Installation Guide

## Overview

The ICS-Decoder feature lets your iCopy-X read **iCLASS SE/SEOS** cards via an external USB decoder (HID RP10/RP40 reader + ATmega32U4 Pro Micro), then write the captured legacy Wiegand downgrade credential to a blank **iClass/Picopass (HF)** or **T5577 (LF)** card.

**Important:** This is a **downgrade copy**, not a true SEOS-to-SEOS clone. The decoder captures the SEOS card's legacy Wiegand credential (PACS data). iCopy-X writes that credential to a legacy blank. The reader accepts it because most access-control systems still allow legacy Wiegand fallback.

---

## Hardware Required

| Item | Details |
|------|---------|
| iCopy-X device | Running this open-source firmware (v1.0.ICS or later) |
| HID RP10 or RP40 reader | multiCLASS SE, 5–16V |
| ATmega32U4 Pro Micro | 5V/16MHz (SparkFun or clone) |
| USB cable | Pro Micro → iCopy-X (USB-A to Micro-USB, data-capable) |
| Jumper wires | 4-conductor to reader pigtail |
| Legacy blank | iClass/Picopass (HF) **or** T5577 (LF) for write target |

---

## Wiring: RP10/RP40 → Pro Micro

The reader's 4-wire pigtail:

| Reader wire | Color | Pro Micro pin |
|-------------|-------|---------------|
| D0 | Green | Pin 2 |
| D1 | White | Pin 3 |
| VCC | Red | VCC (5V) |
| GND | Black | GND |

**Notes:**
- RP10/RP40 accept 5–16V. Powering from Pro Micro VCC (5V) is fine.
- **Common ground is mandatory.** Black must connect to Pro Micro GND.
- The Pro Micro connects to the iCopy-X via its USB port (it appears as a CDC serial device).

---

## Step 1: Flash the Pro Micro (Decoder Firmware)

**Critical:** Disconnect the RP10/RP40 reader **before** flashing the Pro Micro. Uploads will fail (and appear to brick the board) if the reader is connected.

1. Install [Arduino IDE](https://www.arduino.cc/en/software).
2. In Arduino IDE: **Tools → Board → SparkFun Pro Micro**.
3. Processor: **ATmega32U4 (5V, 16MHz)**.
4. Open the decoder firmware:
   ```
   icopy-x-ics-decoder/firmware/ics-decoder/ics-decoder.ino
   ```
5. Click **Upload**.
6. After upload succeeds, reconnect the RP10/RP40 reader.

### Verify the decoder is working

1. Open Arduino **Serial Monitor** at **115200 baud**, line ending **Newline**.
2. Type `Who` and press Enter. You should see:
   ```
   ISE
   ```
3. Present an iCLASS SE/SEOS card to the reader. You should see the LED go red→green + beep.
4. Type `RD` and press Enter. You should see:
   ```
   OK
   $A_CARD_START$
   wiedata#:...
   Bit#:26 (or 34/35/37/48)
   FC#:...
   ID#:...
   Hex#:...
   Blk7#:...
   Bits#:...
   $A_CARD_STOP$
   ```

If you see `??` instead of `OK`, no card was captured since the last `RD`. Present a card and try again.

---

## Step 2: Install the iCopy-X Firmware

### Option A: Pre-built IPK (recommended)

Download the latest release from the [icopy-x-ics-decoder releases page](https://github.com/Dysonian-Lab/icopy-x-ics-decoder/releases).

You need **two** files:
- `icopy-x-flash.ipk` — includes PM3 firmware + client (use if you want the latest PM3)
- `icopy-x-noflash.ipk` — keeps your existing PM3 firmware (use if you already have v4.23346+)

**Installation steps:**
1. Ensure your iCopy-X is on **stock 1.0.90** or later (update from icopyx.com if needed).
2. Put the iCopy-X into **PC-Mode**.
3. **Delete ALL other IPK files** from the device.
4. Copy the downloaded `.ipk` onto the device.
5. Close PC-Mode.
6. Navigate to **About → Update → OK**.
7. Device reboots; screen stays blank for up to 10 seconds (normal).

If you used the **flash** IPK:
8. After reboot, you'll be prompted to flash the PM3. Follow on-screen instructions (plug in, charge, Start).

### Option B: Build from source

If you want to build the IPK yourself:

```bash
# Clone the repo
git clone https://github.com/Dysonian-Lab/icopy-x.git
cd icopy-x

# Build no-flash IPK
python tools/build_ipk.py --no-flash --output icopy-x-ics-decoder.ipk
```

The build requires **Python 3.10+** and the `build/` directory with PM3 client binaries. For a full flash IPK, you also need the PM3 firmware `.elf` placed at `res/firmware/pm3/fullimage.elf`.

---

## Step 3: Connect the Decoder to iCopy-X

1. Flash the Pro Micro with the decoder firmware (Step 1 above).
2. Connect the Pro Micro to the iCopy-X's USB port.
3. Power on the iCopy-X.

The iCopy-X should detect the decoder automatically on boot. You'll see **"ICS Decoder"** in the main menu.

---

## Step 4: Use the ICS Decoder

1. From the iCopy-X main menu, select **ICS Decoder** (or **iClass SE** depending on firmware version).
2. Place your **iCLASS SE/SEOS source card** on the RP10/RP40 reader.
3. The iCopy-X will:
   - Detect the decoder
   - Poll for a card read
   - Parse the captured Wiegand data
   - Show the source card info (FC, ID, Blk7)
4. Remove the source card and place your **legacy blank** (iClass/Picopass or T5577) on the iCopy-X's PM3 coil.
5. Press **Write** (right button).
6. The iCopy-X writes the captured credential to the blank.

### Target Types

| Source Card | Detected Blank | Write Method |
|-------------|----------------|--------------|
| Standard 26-bit (FC > 0, CN > 0) | LF T5577 | `lf hid clone -w H10301 --fc {fc} --cn {cn}` |
| Standard 26-bit (FC > 0, CN > 0) | HF iClass | `hf iclass wrbl` (Block 7) |
| Extended/Custom (FC = 0, CN = 0) | LF T5577 | Blocked: "Incompatible: Requires HF iClass" |
| Extended/Custom (FC = 0, CN = 0) | HF iClass | `hf iclass wrbl` (Block 7 raw 8-byte copy) |

---

## Troubleshooting

### PM version shows `?` on About screen

This means the PM3 client in your IPK doesn't match the firmware on your device's SAMD21.

**Fix:** Flash the **`icopy-x-flash.ipk`** (includes matching PM3 firmware + client). The no-flash IPK keeps your current PM3 firmware; if PM3 is unresponsive, the flash IPK will update it.

### "Processing..." hangs forever on boot

This is caused by a PM3 version check timeout. The firmware now includes a 60-second safety timeout — if the toast persists longer, the PM3 subprocess is unresponsive.

**Fix:**
1. Force-reboot the iCopy-X.
2. If it still hangs, re-flash the **flash IPK** to update PM3 firmware.

### No decoder detected

- Ensure the Pro Micro is connected via USB.
- Open Arduino Serial Monitor — does it respond to `Who` with `ISE`?
- Check wiring: Green→pin2, White→pin3, Black→GND, Red→VCC.
- Try a different USB cable/port on the iCopy-X.

### Card reads but `Blk7#` is all zeros

The reader detected a card but couldn't decode it. This happens with **legacy iClass cards** (not SE/SEOS). The ICS-Decoder is designed for SE/SEOS only.

**Fix:** Use iCopy-X's standard **Read → Clone** flow for legacy iClass cards (PM3 coil directly, no decoder needed).

### Write fails: "No card detected!"

- Make sure the blank is placed on the PM3 coil (not the reader).
- Try removing and re-placing the blank.
- Ensure the blank is not locked or already written.

---

## Files

| File | Purpose |
|------|---------|
| `src/middleware/ics_decoder.py` | Serial protocol + Wiegand parsing |
| `src/lib/activity_main.py` | `IclassSEActivity` UI + state machine |
| `src/lib/actmain.py` | Activity registry |
| `src/screens/main_menu.json` | Menu entry |
| `icopy-x-ics-decoder/firmware/ics-decoder/ics-decoder.ino` | Pro Micro firmware |
| `icopy-x-ics-decoder/firmware/wiegand-sniffer/wiegand-sniffer.ino` | Debug sniffer |

---

## Logs

Verbose logs are written to:
- **USB (PC-accessible):** `H:\logs\app.log`
- **Internal fallback:** `/home/pi/dump/logs/app.log`

These contain boot sequence, PM3 commands, and middleware debug info. If reporting issues, attach the latest `app.log`.
