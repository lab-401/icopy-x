# iCopy-X Open
An Open-Source version of the iCopy-X RFID Cloner device.

## What this is:

 - Usable: A **complete** rebuild of the iCopy-X device. All device functions are included.
 - Jailbroken: Installable without needing to build individual IPKs
 - Up-to-date: Runs __latest iceman firmware__
 - Flexible: Complete plugin system + Simplified JSON-based UI system
 - **NEW**: ICS Decoder integration for SEOS SIO credential cloning

## What this is not:

 - It's not built on the original author's IP. All code written from scratch.
 - It's (Probably not) Bug-Free. This was a massive task. Despite thousands of UI, Functional and Regression tests, there's going to be gaps.
 - It's not useable commercially. This software cannot be used in a commercial context. See LICENCE for more information.

## What's new?
 - Full access to everything!
 - Plugin architecture - allows for building UI apps that interact with the proxmark or linux sub-system just from JSON. Also allows a "full-screen" mode for running other binaries (ie DOOM)
 - Screen mirroring: Allows the screen to be streamed to a device via USB. Can't be used at the same time as PC-Mode: Disable / Enable in settings.
 - **ICS Decoder Bridge**: Read SEOS SIO credentials via USB decoder, write to iClass Legacy/Picopass or T5577 blanks

---

# ICS Decoder Integration

## Overview
The ICS Decoder integration bridges an external USB ICS Decoder dongle to the iCopy-X, enabling SEOS SIO credential extraction and cloning to legacy iClass/Picopass or T5577 blanks.

### Attack Flow
```
1. User places SEOS/SE source tag on USB decoder (NOT coil)
2. ICS Decoder hardware performs:
   - ISO 7816 ADF selection
   - Challenge-response mutual authentication
   - EAX/EAX' decryption with diversified KDF key
   - Outputs decrypted PACS payload via serial
3. iCopy-X middleware parses SIO payload:
   - Extracts NN padding byte
   - Applies right bit-shift (>> NN)
   - Parses Wiegand frame (FC + CN)
4. User removes source, places legacy blank on PM3 coil
5. Firmware auto-detects blank type (HF or LF)
6. Firmware writes credential to blank
7. Post-write verification confirms data integrity
```

## Hardware Requirements

### ICS Decoder Dongle

**Required:** External USB ICS Decoder dongle for SEOS credential extraction.

| Decoder | Status | Repository |
|---------|--------|------------|
| DIY ICS Decoder | ✅ Tested & Working | [Dysonian-Lab/icopy-x-ics-decoder](https://github.com/Dysonian-Lab/icopy-x-ics-decoder) |
| Nikola ICS Decoder | ⏳ Testing Pending | [Dysonian-Lab/icopy-x-ics-decoder](https://github.com/Dysonian-Lab/icopy-x-ics-decoder) |

> **Note:** This integration has only been tested with the DIY ICS Decoder hardware. Testing with the Nikola ICS Decoder is yet to be completed. See the [device repository](https://github.com/Dysonian-Lab/icopy-x-ics-decoder) for build instructions and compatibility updates.

### Supported Target Blanks

| Target | Frequency | Card Types | Detection | Write Method |
|--------|-----------|------------|-----------|--------------|
| HF iClass | 13.56 MHz | Picopass 2k/16k, Magic iClass, HID iClass Legacy | `hf iclass rdbl` with multi-key | `hf iclass wrbl` Block 7 |
| LF T5577 | 125 kHz | T5577 (HID Prox emulation) | `lf t55xx detect` | `lf hid clone -w H10301` |

### Multi-Key Support
Detection and writing support both:
- `AFA785A7DAB33378` - Standard HID iClass key (formatted cards like HID 2124)
- `2020666666668888` - Virgin Picopass transport key

## SIO Wiegand Parsing

### NN Right-Shift Bit Extraction

**SIO PACS Format:** `[NN] [Payload Bytes]`
- `NN` = number of trailing zero padding bits (byte 0)
- `Payload Bytes` = Wiegand data (bytes 1..N)

**Extraction Algorithm:**
```python
# 1. Read shift count from first byte
shift_nn = payload[0]

# 2. Convert remaining bytes to big-endian integer
bitstream = int.from_bytes(payload[1:], byteorder="big")

# 3. Right-shift out trailing padding bits
shifted_bits = bitstream >> shift_nn

# 4. Parse 26-bit Wiegand frame (H10301)
fc = (shifted_bits >> 17) & 0xFF      # Facility Code (8 bits)
cn = (shifted_bits >> 1) & 0xFFFF     # Card Number (16 bits)
```

### ASN.1 TLV Container Handling

**Tag 0x85 Container Format:**
```
[0x85] [Length] [Cipher Bytes + 16-byte MAC]
```

## Target Handling Rules

### Credential Type Matrix

| Credential Type | Detected Blank | Action |
|-----------------|----------------|--------|
| Standard 26-bit (fc > 0, cn > 0) | LF T5577 | Execute `lf hid clone -w H10301 --fc {fc} --cn {cn}` |
| Standard 26-bit (fc > 0, cn > 0) | HF iClass | Execute `hf iclass wrbl` (Block 7) |
| Extended/Custom (fc == 0, cn == 0) | LF T5577 | **Blocked** - Shows "Non-26b SIO! HF iClass Blank Required" |
| Extended/Custom (fc == 0, cn == 0) | HF iClass | Execute `hf iclass wrbl` (Block 7 raw 8-byte copy) |

### Why Non-26-bit Payloads Are Blocked on T5577

Extended/48-bit SEOS payloads (e.g., Block 7: `0000801EC2000A7A`) are structured for 13.56 MHz ISO 14443 / Picopass memory layouts. Writing raw 48-bit hex to T5577 creates a non-standard 125 kHz modulation stream that LF readers will reject.

## State Machine

```
READING → (card detected) → WAIT_BLANK → (Write pressed) → WRITING → (done) → RESULT
                     ↑                                                    │
                     └──────────────── (Retry) ←─────────────────────────┘
```

### State Descriptions

| State | Left Button | Right Button | Description |
|-------|-------------|--------------|-------------|
| READING | Back | (none) | Polling USB decoder for source SE tag |
| WAIT_BLANK | Back | Write | Source decoded, detecting target blank |
| WRITING | (none) | (none) | Write + verify in progress |
| RESULT | Back | Retry | Show result, can retry or exit |

### Result Screen Messages

| Message | Meaning |
|---------|---------|
| Write & Verify OK! | Write succeeded, verification passed |
| Verify Mismatch! | Write succeeded but readback mismatch |
| Write Failed! | Write command failed |
| Non-26b SIO! | Extended format blocked on LF T5577 |
| No card detected! | No target blank detected |

## Post-Write Verification

After writing, the firmware automatically reads back the target card to confirm data integrity:

- **HF iClass**: Reads Block 7 with both HID keys, compares to source
- **LF T5577**: Reads FC/CN, compares to source

## PM3 Commands Reference

| Command | Purpose |
|---------|---------|
| `hf iclass rdbl --blk 06 -k AFA785A7DAB33378` | Detect HF iClass (standard key) |
| `hf iclass rdbl --blk 06 -k 2020666666668888` | Detect HF iClass (transport key) |
| `hf iclass wrbl -b 7 -d <data> -k <key>` | Write Block 7 to iClass |
| `lf t55xx detect` | Detect LF T5577 blank |
| `lf hid clone -w H10301 --fc <fc> --cn <cn>` | Clone HID Prox to T5577 |
| `lf hid reader` | Read HID Prox from T5577 |

**IMPORTANT:** `hf iclass info` HANGS on iCopy-X hardware (FPGA mismatch) - DO NOT USE

---

# Installation
There are **two flavours** to choose from: "No Flash" and "Flash".

 - **"No Flash"**: Full open-source system, but leaves your iCopy-X's proxmark module untouched. You can easily move back and forth between factory/vanilla middleware. However, you will be limited to circa ~2022 proxmark client + firmware.
 - **"Flash"**: Full open-source system, running latest iceman firmware + client. You'll be prompted to flash after you install the IPK. Flashing **does not touch the bootloader** - you will NOT brick your device. Likewise, the iCopy-X has protections to recover from a soft-brick.

Installation is simple: 

 0. Ensure that your device is up to date (1.0.90 - get it from here: https://icopyx.com/pages/update-your-icopy-x)
 1. Download the IPK of your choice
 2. Put your iCopy-X into PC-Mode
 3. Delete ALL OTHER IPK files from the device
 4. Transfer the IPK onto your device and close PC-Mode
 5. Navigate to About > Update, and press [OK]
 6. Device will restart
 7. While restarting, the screen will flash and stay blank for up to 10 seconds. Don't panic!

If you're using the "flash" version, there will be some extra steps:

 7. Device will restart and detect that you need to flash your device. Click OK.
 8. Read the instructions: Make sure your device has charge, make sure it's plugged in, and then Start
 9. After flashing, your device will restart.
 10. While restarting, the screen will stay blank for up to 10 seconds. Don't panic!

## I've installed it - everything looks the same

The upgrade is designed to be seamless: visually and functionally.
A good way to tell if the update worked is if your battery indicator is coloured, or if you see the "Plugins" option on the menu.

## The Plugins don't do anything (useful).

The plugins are designed as examples for developers : how to use the JSON UI framework, how to send commands to the proxmark, how to chain screens, etc.
Try DOOM for a "working" plugin.

## Companion PM3 Clients (for PC-Mode)

When your iCopy-X is in "PC-Mode", you can connect to your iCopy-X's Proxmark module directly from your computer.
Each release contains multi-platform binaries, compiled to match your device's version:
 - `clients-noflash.zip` : Contains windows, linux and macos clients for the "factory firmware" / "no flash" version
 - `clients-flash.zip` : Contains windows, linux and macos clients for the latest iceman / "flash" version.

### Using the companion client

1. Download the matching `clients-[flash|noflash].zip` for your IPK variant
2. Extract to a folder on your computer
3. Put your iCopy-X into PC-Mode
4. Connect via USB
5. Run: `proxmark3 /dev/ttyACM0` (Linux/macOS) or `proxmark3.exe COMx` (Windows)
Adjust `ttyACM0` and `COMx` according to the real port assigned to your iCopy-X.

## Screen Mirroring?

1) On your device, go to "Settings" and enable "Screen Mirror"
2) Reboot your iCopy-X (__important__)

On your computer:
1) Grab the `tools/screen_mirror/` tool from the repository.
2) Run: `python -m pip install -r requirements.txt`
3) Then: `python mirror_client.py`

And everything should work.

# Technical Bits

## Why
The last official iCopy-X update was in 2022. Without updates, for many users the device is an expensive paperweight.
Open-Sourcing the device gives new life to a very capable, well-made portable RFID tool.

## How

Over 350 hours of work. A 48-core, 96GB RAM QEMU testing environment.

The project was actually multiple projects in one, each one as complex and time-consuming as the other.

 - Reliable jailbreak + proof of concept
 - Mapping & Testing: Building exhaustive testing for every function, every logic branch down to the leaf
 - Replacing the UI layer, iterating against tests until complete
 - Building the middleware, iterating against tests until complete
 - Adding support for iceman fork (requires stable upgrade + flash mechanisms)
 - Rebuilding middleware to match iceman fork (or specifically, a compatibility layer)

### Great, but how?

After multiple PoCs, attempts, and failed iterations, the winning strategy was TDD - test driven design.

Despite its enormous complexity, the iCopy-X has a very well defined inputs and outputs - which is the core of TDD.

Based on the UI and possible proxmark outcomes, the entire logic tree was derived.

The iCopy-X was mocked entirely in QEMU, and exhaustive "flow" tests were built against every function. The branches were triggered by building thousands of
mocked RFID fixtures that would trigger Proxmark behavior.

Once the tests were functional, the UI layer was built and tested against the emulated flows.

When the UI was functional, the middleware was built, flow by flow.

When all flows were passing tests, real-device testing began, with thousands of traces being taken to replace the mocked behavior and confirm real behavior.

This process was then repeated across all phases: prototyping, "no flash", and finally "flash" versions.

The Github CI/CD pipelines and tooling evolved along the way to allow anyone to be able to compile without needing to build an environment locally.

## Who?

https://github.com/quantum-x from https://www.lab401.com

## I flashed my device and I don't like it and I want to go back to vanilla...

### Via the UI
Add a factory pm3 firmware image (found in an original .IPK archive:  `res/firmware/pm3/fullimage.elf`) inside the `res/firmware/pm3` folder of a "flash". Copy to your device, install and flash. Then, install the "noflash.ipk" on your device. __or__

### Via SSH
1) Connect to your device via SSH (You'll need USB-C Ethernet connector/hub): login: root/fa
2) Transfer the factory pm3 firmware image (found in an original .IPK archive:  `res/firmware/pm3/fullimage.elf`) to the icopy-x.
3) `systemctl stop icopy`
4) `/home/pi/ipk_app_main/pm3/proxmark3 /dev/ttyACM0 --flash --force --image /path/to/fullimage.elf`
5) Reboot your device, install "noflash.ipk"

### Via PC-Mode
1) Place your iCopy-X in PC-Mode
2) Use the latest proxmark3 client to flash your device: proxmark3 /dev/ttyACM0 --flash --force --image fullimage.elf

## Does this solve the "Boot Timeout" problem?
Not directly. "Boot Timeout" means that the GD32 (Microcontroller, that controls that hardware) hasn't received the signal to handoff the screen to the linux device / UI. There are multiple things that can cause this - but the fasted solution is: reflash the microSD card.

Please see the following page for more information, and factory images to reflash your microSD!
https://lab401.com/blogs/academy/icopy-xs-fixing-the-boot-timeout-problem

Once your device is reflashed and booting, you can apply the Open Source IPKs.

## Known issues

- Only tested on the iCopy-XS - other versions __probably__ will work with the no-flash version.
- External Auto-Hardnested UI tool: Out of scope, marked as non-critical
- On iceman firmware, issues with specific chipsets. These weren't detected by the module - it's a PM3 issue (or a problem with our testing fixtures)
  - GproxII
  - NexWatch
  - IDTek
  - Noralsy
  - Original iCopy-X Gen1a tags appear to be undetectable. __This is not a bug!__ Curiously, for some reason - the device's read range is enhanced on iceman's release. You may need to have a gap of up to 2cm above the device for stable reading! Anything closer over saturates the reader/tag.
- "Flash" version is built directly from the latest tagged release of the iceman repo. If an update changes command syntax or responses, this will break functionality on the iCopy-X device. Our goal was to get the device running on latest iceman. There's a full CI/CD build pipeline, allowing you to mix and match your own proxmark versions. However keeping the iCopy-X's compatibility layer mapped to changes in the iceman repo is up to the community.
- "Flow Tests" - the backbone of this project - are not passing as of the official release. After the project got 1:1 parity with the original middleware, these decoupled. In an ideal world - these should be made to work (and also be made to mock the iceman firmware+client responses). They're an excellent tool for ensuring stability across the entire codebase.
- **ICS Decoder**: Requires external USB ICS Decoder dongle. Currently only tested with the [DIY ICS Decoder](https://github.com/Dysonian-Lab/icopy-x-ics-decoder). Nikola ICS Decoder compatibility testing is pending.

### ICS Decoder Technical Notes

**Working Configurations:**
SEOS cards write to iClass Legacy (48-bit and 26-bit payloads) and T5577 (26-bit only).

**PM3 Return Code Behavior:**
The executor returns 0 or 1 when a command completes. Only -1 means timeout/crash. This matters for T5577 writes - requiring strictly ret=0 causes false failures.

**T5577 Detection:**
Parser targets the [H10301] line and extracts FC/CN via regex. PM3 output varies by firmware version (sometimes "Chip type: T55x7", sometimes "Valid T55xx chip found") so the check accepts several keyword combinations. This avoids matching secondary decodes like Indala that appear in the same output buffer.

**Log Location:**
/mnt/upan/dump/ics_decoder/ - each session creates a new numbered file (001.log, 002.log, etc.)
## Disclaimer

There are multiple hardware revisions of the iCopy-X.
Testing was performed against the first revision, but should work on all revisions.

## Wait! There's a .so file! You said there's no closed source!
This is the jailbreak - the vanilla firmware requires a valid `version.so` to process an IPK.

# What's next

The goal of this project was to open-source the iCopy-X. The future maintenance is beyond the scope of the original project, but we hope that the community will appreciate the value of this project and keep it alive!

Some suggestions would be:

  - Integrate 4+ years of iceman repo functions, tag types and progress into the UI
  - Integrate new magic cards
  - Expand ICS Decoder support for additional SEOS card formats
  - Complete Nikola ICS Decoder compatibility testing
  - Add support for additional LF/HF card types

# Licence

This code is distributed under PolyForm Noncommercial License 1.0.0.
Why this licence? When we'd discussed open-source with the original manufacturers they had concerns about cloning. Out of respect for the genuinely incredible hard work that they put into the iCopy-X - we do not want to be an avenue for cloners.

This code is intended for pentesters and RFID enthusiasts. It is intended to open a closed device to progress and provoke community evolution - not for profit.
If you plan on selling the code, selling an SD card with the code, or embedding the code or its derivatives in a device and selling the device: this is NOT permitted.