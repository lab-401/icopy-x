# Original iCopy-X v1.0.90 Firmware Analysis

Comprehensive reverse engineering analysis of the original firmware extracted from IPK
v1.0.90 (SN 02150004, HW 1.7, device type iCopy-XS).

All findings derived from QEMU ARM user-mode introspection of the original compiled
Cython `.so` modules and binary string extraction.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Boot Sequence](#2-boot-sequence)
3. [Executor / PM3 Communication](#3-executor--pm3-communication)
4. [Scan Flow](#4-scan-flow)
5. [Tag Types System](#5-tag-types-system)
6. [Read Flow](#6-read-flow)
7. [Key Recovery (MIFARE Classic)](#7-key-recovery-mifare-classic)
8. [Write Flow](#8-write-flow)
9. [Complete PM3 Command Reference](#9-complete-pm3-command-reference)
10. [Activity UI Flow](#10-activity-ui-flow)
11. [File Storage Layout](#11-file-storage-layout)
12. [Discrepancies with Reimplementation](#12-discrepancies-with-reimplementation)

---

## 1. Architecture Overview

### Module Layout

```
app.py                   -- Plain Python entry point
main/
  main.so                -- main() function, bootstraps everything
  rftask.so              -- RemoteTaskManager + RFServer (PM3 subprocess manager)
  install.so             -- IPK installation logic
lib/
  executor.so            -- TCP client to PM3, command dispatch, response parsing
  scan.so                -- Scanner class, scan_14a/hfsea/lfsea/t55xx/em4x05/felica
  read.so                -- Reader factory, 8 AbsReader subclasses
  write.so               -- Write dispatcher, calls module-specific writers
  tagtypes.so            -- Tag type ID constants + name/capability registry
  mifare.so              -- MIFARE Classic geometry (sectors, blocks, sizes)
  hf14ainfo.so           -- `hf 14a info` parser (UID, ATQA, SAK, PRNG, Gen1a)
  hfsearch.so            -- `hf sea` parser
  lfsearch.so            -- `lf sea` parser (regex-based ID/RAW extraction)
  hfmfkeys.so            -- Key recovery: fchk, nested, staticnested, darkside
  hfmfread.so            -- MF Classic sector/block reading, EML/BIN save
  hfmfwrite.so           -- MF Classic writing (gen1a, standard, UID-only)
  hfmfuinfo.so           -- `hf mfu info` parser
  hfmfuread.so           -- MF Ultralight dump reader
  hfmfuwrite.so          -- MF Ultralight restore writer
  hf14aread.so           -- ISO14443A generic reader
  hf15read.so            -- ISO15693 dump reader
  hf15write.so           -- ISO15693 restore writer
  hficlass.so            -- iClass key check, info, block read
  iclassread.so          -- iClass dump reader (legacy + elite)
  iclasswrite.so         -- iClass block writer + key calc
  felicaread.so          -- FeliCa Lite dump reader
  hffelica.so            -- `hf felica reader` parser
  legicread.so           -- LEGIC MIM256 dump reader
  lfread.so              -- LF read functions (20 card types)
  lfwrite.so             -- LF write/clone functions
  lft55xx.so             -- T55xx detect/dump/read/write/wipe/chk
  lfem4x05.so            -- EM4x05 info/dump/read
  lfverify.so            -- LF write verification
  sniff.so               -- Sniff start + trace parsing
  appfiles.so            -- File path management (/mnt/upan/dump/...)
  activity_main.so       -- All UI Activities (Scan/Read/Write/Simulate/...)
  ... (62 total .so modules)
```

### Key Design Patterns

- All `.so` modules are **Cython-compiled** (`.pyx` -> `.c` -> `.so`)
- Compiled on Windows: source paths like `C:\Users\ADMINI~1\AppData\Local\Temp\1\tmp*\*.py`
- Module-level functions (not OOP) for most middleware
- `Scanner` and `Reader` are the only major classes in middleware
- Activities use Android-like lifecycle: `onCreate`, `onResume`, `onPause`, `onDestroy`
- All `parser()` functions take **no arguments** -- they read from `executor.CONTENT_OUT_IN__TXT_CACHE` (the last command output cached at module level)
- `commons.PATH_UPAN = '/mnt/upan/'` -- shared USB storage mount point
- `commons.startPlatformCMD(cmd)` -- runs OS-level commands via the platform

---

## 2. Boot Sequence

### app.py (verbatim)

```python
import sys

if __name__ == '__main__':
    sys.path.append("main")
    sys.path.append("lib")
    try:
        from main import main
        main.main()
    except Exception as e:
        print("启动脚本无法启动程序，出现异常: ", e)
        exit(44)
```

### main.main()

`main.so` exposes only `main()`. It:
1. Sets up the UI (tkinter Canvas, 240x240 display)
2. Starts `RemoteTaskManager` (spawns PM3 subprocess)
3. Launches the activity stack with the main menu activity

### manifest.json

```json
{
  "package": "ipk",
  "level": "full",
  "uuid": "d526e98ec461496fa22cd4f2a6c28f72",
  "manifest": {
    "info": {
      "sn": "02150004",
      "hw": "1.7"
    },
    "path": ["main/", "lib/", "pm3/", "res/"],
    "file": ["app.py", "nikola", "pm3/proxmark3", ...]
  }
}
```

---

## 3. Executor / PM3 Communication

### Architecture

```
[UI/Middleware]
    |
    v
[executor.so] -- TCP socket --> [rftask.RemoteTaskManager (port 8888)]
                                    |
                                    v
                               [PM3 subprocess (pm3/proxmark3)]
                                    |
                                    v
                               [stdout/stderr parsing]
```

### Protocol

The original uses a **Nikola protocol** over TCP on `127.0.0.1:8888`:

| Message Type | Format | Purpose |
|---|---|---|
| Command | `Nikola.D.CMD = {pm3_command}` | Execute a PM3 command |
| Control | `Nikola.D.CTL = {control}` | Control PM3 (restart, etc.) |
| Platform | `Nikola.D.PLT = {platform}` | Platform-specific command |
| Offline | `Nikola.D.OFFLINE` | PM3 is disconnected |
| Response End | `Nikola\.D:.*?\d+\s+` (regex) | Marks end of response |

### executor.so API (confirmed signatures)

```python
# Core command execution
startPM3Task(cmd, timeout, listener=None, rework_max=2)
startPM3Plat(plat_cmd, timeout=5888)
startPM3Ctrl(ctrl_cmd, timeout=5888)
stopPM3Task(listener=None, wait=True)

# Connection
connect2PM3(serial_port=None, baudrate=None)  # sends "hw connect"

# Output access
getPrintContent()              # Returns full response text
getContentFromRegex(regex)     # Single regex match
getContentFromRegexA(regex)    # Match with group A
getContentFromRegexG(regex, group)  # Match with specific group
getContentFromRegexAll(regex)  # All matches
hasKeyword(keywords, line=None)  # Check for keyword in output
isEmptyContent()               # Check if no output

# Error detection
isCMDTimeout(lines)    # "timeout while waiting for reply"
isUARTTimeout(lines)   # "UART:: write time-out"
isPM3Offline(lines)    # "Communicating with PM3"

# State
LABEL_PM3_CMD_TASK_RUNNING = False  # module-level boolean
LABEL_PM3_CMD_TASK_STOP = False
LABEL_PM3_CMD_TASK_STOPPING = False
CODE_PM3_TASK_ERROR = -1
PM3_REMOTE_ADDR = '127.0.0.1'
PM3_REMOTE_CMD_PORT = 8888
```

### rftask.so RemoteTaskManager

```python
class RemoteTaskManager:
    DEFAULT_CMD_START = 'Nikola.D.CMD'
    DEFAULT_CTL_START = 'Nikola.D.CTL'
    DEFAULT_PLT_START = 'Nikola.D.PLT'
    DEFAULT_OFFLINE = 'Nikola.D.OFFLINE'
    DEFAULT_END_WITH = r'Nikola\.D:.*?\d+\s+'

    # Methods:
    startManager()       # Start PM3 subprocess + TCP server
    stopManger()         # Stop everything
    destroy()            # Cleanup
    hasManager()         # Is manager running?
    hasTasking()         # Is a task in progress?
    requestTask(cmd, listener)  # Send command to PM3
    reworkManager()      # Restart PM3 subprocess
    createCMD(cmd)       # Format CMD message
    createCTL(cmd)       # Format CTL message
    createPLT(cmd)       # Format PLT message
```

The RTM creates:
- A TCP server (ThreadingTCPServer on port 8888)
- A subprocess running `pm3/proxmark3`
- A stdout reader thread
- A HandleServer that processes incoming TCP commands

---

## 4. Scan Flow

### scan.so Architecture

The scan module implements a **multi-stage scan pipeline**:

```
Scanner.scan_all_synchronous()
  |
  +-> scan_14a()          -- hf 14a info (parsed by hf14ainfo.parser)
  |     |-> If M1 found: return tag info
  |     |-> If Ultralight: hfmfuinfo (hf mfu info)
  |     |-> If DESFire: mark unsupported
  |
  +-> scan_hfsea()        -- hf sea (parsed by hfsearch.parser)
  |     |-> ISO15693, ISO14443B, Topaz, FeliCa, iClass, LEGIC
  |
  +-> scan_lfsea()        -- lf sea (parsed by lfsearch.parser)
  |     |-> EM410x, HID, Indala, AWID, etc.
  |
  +-> scan_t55xx()        -- lf t55xx detect (+ key check)
  |     |-> T55xx with/without password
  |
  +-> scan_em4x05()       -- lf em 4x05_info [key]
  |     |-> EM4305/EM4x69
  |
  +-> scan_felica()       -- hf felica reader
       |-> FeliCa tags
```

### Scanner Class (confirmed signatures)

```python
class Scanner:
    __init__(self)   # No arguments (not even executor!)

    # Properties (callbacks):
    call_progress    # Progress callback property
    call_resulted    # Result callback property
    call_exception   # Exception callback property

    # Synchronous scanning:
    scan_all_synchronous(self)        # Scan all types, blocking
    scan_type_synchronous(self, typ)  # Scan specific type, blocking

    # Asynchronous scanning:
    scan_all_asynchronous(self)       # Scan all types, threaded
    scan_type_asynchronous(self, typ) # Scan specific type, threaded

    # Control:
    scan_stop(self)  # Stop current scan
```

**CRITICAL DIFFERENCE**: The original Scanner takes **no constructor arguments**.
It uses `executor` as a **module-level import** (not dependency injection). Our
reimplementation incorrectly passes `executor` to the constructor.

### Module-Level Scan Functions

```python
# Individual scan functions (called by Scanner internally):
scan_14a()           # HF ISO14443A scan
scan_hfsea()         # HF search
scan_lfsea()         # LF search
scan_t55xx()         # T55xx detect
scan_em4x05()        # EM4x05 info
scan_felica()        # FeliCa reader

# Type-specific scan dispatcher:
scanForType(listener, typ)   # Scan for a specific tag type

# Result code checking:
isTagFound(maps) -> bool
isTagLost(maps) -> bool
isTagMulti(maps) -> bool
isTimeout(value) -> bool
isCanNext(value) -> bool
isTagTypeWrong(maps) -> bool

# Result code factories:
createExecTimeout(progress) -> dict
createTagLost(progress) -> dict
createTagMulti(progress) -> dict
createTagNoFound(progress) -> dict
createTagTypeWrong(progress) -> dict

# Cache management:
setScanCache(infos)
getScanCache()
clearScanCahe()   # Note: typo in original! "Cahe" not "Cache"
set_infos_cache(enable)
INFOS_CACHE_ENABLE = True

# Key management for password-protected LF tags:
set_scan_t55xx_key(key)
set_scan_em4x05_key(key)

# LF waveform:
lf_wav_filter()

# Return codes:
CODE_TIMEOUT = -1
CODE_TAG_LOST = -2
CODE_TAG_MULT = -3
CODE_TAG_NO = -4
CODE_TAG_TYPE_WRONG = -5
```

### Scan Commands and Parsing

#### HF 14A Info (`hf14ainfo.so`)

```
Command: "hf 14a info"
Timeout: 5000ms

Regex patterns:
  UID:          .*UID:(.*)\n
  ATQA:         .*ATQA:(.*)\n
  SAK:          .*SAK:(.*)\[.*\n
  PRNG:         .*Prng detection: (.*)\n
  ATS:          .*ATS:(.*)
  MANUFACTURER: .*MANUFACTURER:(.*)

Detection strings:
  "Multiple tags detected"           -> CODE_TAG_MULT
  "Card doesn't support standard iso14443-3 anticollision" -> skip
  "Magic capabilities : Gen 1a"     -> gen1a magic card
  "Magic capabilities : Gen 2 / CUID" -> gen2 magic card
  "Static nonce: yes"               -> static nonce (use staticnested)
  "MIFARE Classic"                   -> M1 type
  "MIFARE Classic 1K"               -> 1K (check 4B vs 7B UID)
  "MIFARE Classic 4K"               -> 4K
  "MIFARE Mini"                     -> Mini
  "MIFARE Plus"                     -> Plus
  "MIFARE Plus 4K"                  -> Plus 4K
  "MIFARE Ultralight"               -> UL type
  "MIFARE DESFire"                  -> DESFire (unsupported)
  "NTAG"                            -> NTAG type

Gen1a detection:
  Command: "hf mf cgetblk 0"
  If successful -> gen1a magic card
```

#### HF Search (`hfsearch.so`)

```
Command: "hf sea"    (NOT "hf search"!)
Timeout: 10000ms

Detection strings:
  "MIFARE"                     -> MIFARE type
  "Valid ISO14443-B"           -> ISO14443B
  "Valid ISO15693"             -> ISO15693/ICODE
  "Valid ISO18092 / FeliCa"   -> FeliCa
  "Valid LEGIC Prime"          -> LEGIC
  "Valid Topaz"                -> Topaz
  "Valid iCLASS tag"           -> iClass
  "No known/supported 13.56 MHz tags found" -> not found

Regex:
  UID:  .*UID.*:(.*) or .*UID:\s(.*)
  ATQA: .*ATQA.*:(.*)
  ATQB: .*ATQB.*:(.*)     (for ISO14443B)
  MCD:  .*MCD:\s(.*)       (for LEGIC)
  MSN:  .*MSN:\s(.*)
```

#### LF Search (`lfsearch.so`)

```
Command: "lf sea"    (NOT "lf search"!)
Timeout: 10000ms

Detection strings:
  "Valid EM410x ID"        -> EM410x
  "Valid Securakey ID"     -> Securakey
  "Valid Hitag"            -> Hitag2 (unsupported)
  "No known 125/134 kHz tags found!" -> not found
  "No data found!"         -> no data
  "Chipset detection: EM4x05 / EM4x69" -> EM4x05
  "T5577"                  -> T5577/T55xx
  "EM4305"                 -> EM4305

Regex patterns:
  REGEX_EM410X    = 'EM TAG ID\s+:[\s]+([xX0-9a-fA-F]+)'
  REGEX_CARD_ID   = '(?:Card|ID|id|CARD|ID|UID|uid|Uid)\s*:*\s*([xX0-9a-fA-F ]+)'
  REGEX_RAW       = '.*(?:Raw|Raw|RAW|hex|HEX|Hex)\s*:*\s*([xX0-9a-fA-F ]+)'
  REGEX_ANIMAL    = '.*ID\s+([xX0-9A-Fa-f\-]{2,})'
  FC/CN parsing:  '(CN|Card|Card ID):*\s+(\d+)'

Functions:
  parser()                    # Parse lf search output
  setUID(infos, uid)          # Set UID in result
  setRAW(infos, raw)          # Set RAW data
  setUID2Raw(infos)           # Set UID from RAW
  setUID2FCCN(infos)          # Set UID from FC/CN
  setRAWForRegex(infos)       # Extract RAW via regex
  cleanAndSetRaw(infos)       # Clean and set raw
  cleanHexStr(s)              # Remove spaces from hex
  getFCCN(content)            # Get Facility Code / Card Number
  getXsf(content)             # Get XSF format
  hasFCCN(content)            # Check FC/CN presence
  parseFC(content)            # Parse facility code
  parseCN(content)            # Parse card number
  parseLen(content)           # Parse bit length
```

#### T55xx Scan

```
Command: "lf t55xx detect"        (no key)
Command: "lf t55xx detect p FFFFFFFF"  (with password)
Timeout: 10000ms

Detection: "Could not detect modulation automatically" -> not detected
```

#### EM4x05 Scan

```
Command: "lf em 4x05_info "      (note trailing space)
Command: "lf em 4x05_info FFFFFFFF"  (with key)
Timeout: 5000ms
```

#### FeliCa Scan

```
Command: "hf felica reader"
Timeout: 10000ms
```

#### LF Waveform Filter

```
Command: "data save f "     (saves LF waveform to file)
Path: /tmp/lf_trace_tmp
```

---

## 5. Tag Types System

### `tagtypes.so` Complete Registry

| ID | Name | Can Read | Can Write |
|---|---|---|---|
| -1 | Unsupported | No | No |
| 0 | M1 S70 4K 4B | Yes | Yes |
| 1 | M1 S50 1K 4B | Yes | Yes |
| 2 | Ultralight | Yes | Yes |
| 3 | Ultralight C | Yes | Yes |
| 4 | Ultralight EV1 | Yes | Yes |
| 5 | NTAG213 144b | Yes | Yes |
| 6 | NTAG215 504b | Yes | Yes |
| 7 | NTAG216 888b | Yes | Yes |
| 8 | EM410x ID | Yes | Yes |
| 9 | HID Prox ID | Yes | Yes |
| 10 | Indala ID | Yes | Yes |
| 11 | AWID ID | Yes | Yes |
| 12 | IO Prox ID | Yes | Yes |
| 13 | GProx II ID | Yes | Yes |
| 14 | Securakey ID | Yes | Yes |
| 15 | Viking ID | Yes | Yes |
| 16 | Pyramid ID | Yes | Yes |
| 17 | iClass Legacy | Yes | Yes |
| 18 | iClass Elite | Yes | Yes |
| 19 | ISO15693 ICODE | Yes | Yes |
| 20 | Legic MIM256 | Yes | **No** |
| 21 | Felica | Yes | **No** |
| 22 | ISO14443B | **No** | **No** |
| 23 | T55x7_ID | Yes | Yes |
| 24 | EM4305_ID | Yes | Yes |
| 25 | M1 Mini | Yes | Yes |
| 26 | M1 Plus 2K | Yes | Yes |
| 27 | Topaz | **No** | **No** |
| 28 | FDXB ID | Yes | Yes |
| 29 | GALLAGHER ID | Yes | Yes |
| 30 | Jablotron ID | Yes | Yes |
| 31 | KERI ID | Yes | Yes |
| 32 | NEDAP ID | Yes | Yes |
| 33 | Noralsy ID | Yes | Yes |
| 34 | PAC ID | Yes | Yes |
| 35 | Paradox ID | Yes | Yes |
| 36 | Presco ID | Yes | Yes |
| 37 | Visa2000 ID | Yes | Yes |
| 38 | Hitag2 ID | **No** | **No** |
| 39 | MIFARE DESFire | **No** | **No** |
| 40 | HF14A Other | Yes | Yes |
| 41 | M1 S70 4K 7B | Yes | Yes |
| 42 | M1 S50 1K 7B | Yes | Yes |
| 43 | M1 POSSIBLE 4B | Yes | Yes |
| 44 | M1 POSSIBLE 7B | Yes | Yes |
| 45 | NexWatch ID | Yes | Yes |
| 46 | ISO15693 ST SA | Yes | Yes |
| 47 | iClass SE | Yes | Yes |

### Type Groupings

```python
getM1Types()      -> [25, 1, 0, 26, 42, 41, 43, 44]  # All MIFARE Classic
getM14BTypes()    -> [25, 1, 0, 26, 43]                # 4-byte UID M1
getM17BTypes()    -> [42, 41, 44]                       # 7-byte UID M1
getM14KTypes()    -> [0, 41]                            # 4K M1
getM11KTypes()    -> [42, 1, 44, 43]                    # 1K M1
getM12KTypes()    -> [26]                               # 2K M1 (Plus)
getM1MiniTypes()  -> [25]                               # Mini M1
getULTypes()      -> [2, 3, 4, 5, 6, 7]                # All Ultralight/NTAG
getiClassTypes()  -> [17, 18, 47]                       # All iClass

getAllHigh()       -> [19, 46, 20, 21, 17, 18]          # Other HF
getAllLow()        -> [8, 9, 10, 11, 12, 13, 14, 15, 16, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 45, 23, 24]
getAllLowCanDump() -> [24, 23]                           # LF with dump (T55xx, EM4305)
getAllLowNoDump()  -> [8, 9, 10, 11, 12, 13, 14, 15, 16, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 45]

getHfOtherTypes() -> [20, 19, 46, 21, 40, 17, 18, 47]  # HF non-M1/non-UL
getUnreadable()   -> ['Unsupported', 'ISO14443B', 'Topaz', 'Hitag2 ID', 'MIFARE DESFire']
```

### Type Check Functions

```python
isTagCanRead(type_id) -> bool
isTagCanWrite(type_id) -> bool
getName(type_id) -> str
```

---

## 6. Read Flow

### Reader Factory (`read.so`)

The `Reader` class dispatches to specialized `AbsReader` subclasses:

```python
class Reader:
    default_reader = [
        MifareClassicReader,      # M1 types (0,1,25,26,41,42,43,44)
        MifareUltralightReader,   # UL types (2,3,4,5,6,7)
        LF125KHZReader,           # All LF types
        HIDIClassReader,          # iClass (17,18,47)
        LegicMim256Reader,        # LEGIC (20)
        ISO15693Reader,           # ISO15693 (19,46)
        ISO1443AReader,           # HF14A Other (40)
        FelicaReader,             # FeliCa (21)
    ]

    # Properties:
    call_reading    # Reading progress callback
    call_exception  # Exception callback

    # Methods:
    start(self, tag_type, tag_data)     # Start reading
    stop(self)                          # Stop reading
    find_reader(self, tag_type, tag_data)   # Find appropriate reader
    find_readers(self)                  # Get all readers
    is_reader_class(name)              # Check if class is a reader
    is_reading(self)                   # Is currently reading?

class AbsReader:
    isSupport(self) -> bool            # Can this reader handle the tag?
    start(self, listener)              # Start the read operation
    stop(self)                         # Stop reading
    callReadFailed(listener, infos, ret)      # Callback on failure
    callReadSuccess(listener, infos, bundle, is_force=False)  # Callback on success
    call_on_finish(ret, listener, infos, bundle)  # Finish callback
```

### MIFARE Classic Read (`hfmfread.so`)

```python
# Module-level state:
DATA_MAP = {}     # Block data storage
FILE_READ = None  # Current read file

# Key functions:
readIfIsGen1a()                        # Read block 0 via "hf mf csave {} o {}"
readBlock(block, key_type, key)        # "hf mf rdbl {} {} {}"
readBlocks(start, end, key_type, key)  # Read range of blocks
readSector(sector, key_a, key_b)       # "hf mf rdsc {} {} {}"
readAllSector(listener, infos)         # Read all sectors with keys

# File operations:
save_eml(data, file)                   # Save as .eml text format
save_bin(data, file)                   # Save as .bin binary format
cacheFile(file)                        # Cache file for later use

# Data management:
fillKeys2DataMap(keys_map)             # Fill DATA_MAP with keys
createTempDatas(sector_count)          # Create empty data structure
createTempSector(block_count)          # Create empty sector
createEmptyBlock()                     # "00000000000000000000000000000000"
createManufacturerBlock(uid, sak, atqa)  # "{uid}{xor}{sak}{atqa}{mcode}"
sizeGuess()                            # Guess tag size from data

# Read error detection:
regex: "Read sector\s+\d+\s+block\s+\d+\s+error"
keyword: "Auth error"
keyword: "Can't select card"
keyword: "Read block error"
```

### MIFARE Classic Read Commands

| Command | Purpose |
|---|---|
| `hf mf rdbl {block} {A/B} {key}` | Read single block |
| `hf mf rdsc {sector} {A/B} {key}` | Read entire sector |
| `hf mf csave {type} o {file}` | Dump Gen1a via Chinese backdoor |

### MF Ultralight Info (`hfmfuinfo.so`)

```
Command: "hf mfu info"
Timeout: 8888ms

parser() -> detects type from output:
  "NTAG 213" -> NTAG213_144B (5)
  "NTAG 215" -> NTAG215_504B (6)
  "NTAG 216" -> NTAG216_888B (7)
  "TYPE: Unknown" -> may be generic Ultralight
  Uses tagtypes constants ULTRALIGHT, ULTRALIGHT_C, ULTRALIGHT_EV1

getUID() -> extracts UID from: .*UID:(.*)\n

Returns dict with keys: 'type', 'uid'
```

### MF Ultralight Read (`hfmfuread.so`)

```
Command: " hf mfu dump f {file}"   (note leading space!)
Detection: "iso14443a card select failed" -> failure
Detection: "Partial dump created" -> partial success

File prefix by type:
  NTAG213 -> "NTAG213"
  NTAG215 -> "NTAG215"
  NTAG216 -> "NTAG216"
  Ultralight -> "M0-UL"
  Ultralight C -> "M0-UL-C"
  Ultralight EV1 -> "M0-UL-EV1"
```

### ISO15693 Read (`hf15read.so`)

```
Command: "hf 15 dump"
Timeout: 38000ms (long timeout!)
Detection: "No tag found." -> failure
```

### FeliCa Read (`felicaread.so`)

```
Command: "hf felica litedump"
Timeout: 5000ms
```

### LEGIC Read (`legicread.so`)

```
Command: "hf legic dump"
Command: "hf legic dump h"   (alternate)
Timeout: 5000ms
```

### iClass Read (`iclassread.so`)

```
Command: "hf iclass dump k {key}"
Detection: "saving dump file - 19 blocks read" -> success
Functions:
  readLegacy()      # Dump with known key
  readElite()       # Dump with elite key
  readFromKey(key)  # Dump with specific key
```

### LF Read (`lfread.so`)

Each LF card type has its own read function:

| Function | Command |
|---|---|
| `readEM410X()` | `lf em 410x_read` |
| `readHID()` | `lf hid read` |
| `readIndala()` | `lf indala read` |
| `readAWID()` | `lf awid read` |
| `readProxIO()` | `lf io read` |
| `readGProx2()` | `lf gproxii read` |
| `readSecurakey()` | `lf securakey read` |
| `readViking()` | `lf viking read` |
| `readPyramid()` | `lf pyramid read` |
| `readFDX()` | `lf fdx read` |
| `readGALLAGHER()` | `lf gallagher read` |
| `readJablotron()` | `lf jablotron read` |
| `readKeri()` | `lf keri read` |
| `readNedap()` | `lf nedap read` |
| `readNoralsy()` | `lf noralsy read` |
| `readPAC()` | `lf pac read` |
| `readParadox()` | `lf paradox read` |
| `readPresco()` | `lf presco read` |
| `readVisa2000()` | `lf visa2000 read` |
| `readNexWatch()` | `lf nexwatch read` |
| `readEM4X05()` | EM4x05 via `lfem4x05` module |
| `readT55XX()` | T55xx via `lft55xx` module |

### T55xx Read (`lft55xx.so`)

```python
# Commands:
CMD_DETECT_NO_KEY  = 'lf t55xx detect'
CMD_DETECT_ON_KEY  = 'lf t55xx detect p FFFFFFFF'
CMD_DUMP_NO_KEY    = 'lf t55xx dump'
KEYWORD_CASE1      = 'Could not detect modulation automatically'
TIMEOUT            = 10000

# Functions:
detectT55XX()                    # Detect T55xx
dumpT55XX()                      # Dump all blocks
dumpT55XX_Text()                 # Dump as text
readBlock(block, key)            # Read single block
chkT55xx()                       # Check with key dictionary
chkAndDumpT55xx()                # Check keys then dump
detectAndDumpT55xxByKey()        # Detect with key, then dump
getB0WithKey(key)                # Read block 0 with key
getB0WithKeys(keys)              # Try multiple keys

# Block commands:
'lf t55xx read b 0'             # Read block 0
'lf t55xx read b {} p {} o {}'  # Read block with password, override
'lf t55xx read b {} {}'         # Read block with args
'lf t55xx chk f '               # Check keys from file
'lf t55xx wipe'                 # Wipe tag
'lf t55xx write b 0 d '        # Write block 0
'lf t55xx write b 7 d '        # Write block 7 (password block)
```

### EM4x05 Read (`lfem4x05.so`)

```python
CMD     = 'lf em 4x05_info FFFFFFFF'
TIMEOUT = 5000

# Functions:
info4X05()           # Get info
dump4X05()           # Dump all
read4x05(block, key) # Read specific block: "lf em 4x05_read {} {}"
readBlocks()         # Read all blocks
verify4x05()         # Verify write
set_key(key)         # Set access key

# Commands:
'lf em 4x05_info'          # Info without key
'lf em 4x05_info FFFFFFFF' # Info with default key
'lf em 4x05_dump'          # Dump all blocks
'lf em 4x05_read {} {}'    # Read block with key
```

---

## 7. Key Recovery (MIFARE Classic)

### `hfmfkeys.so` Key Recovery Pipeline

```
fchks()                      # Dictionary check (fast)
  |-> "hf mf fchk {} {}"    # {size} {key_file}
  |
nested()                     # Nested attack
  |-> nestedAllKeys()
  |   |-> nestedOneKey()
  |       |-> "hf mf nested o {knownBlock} {knownType} {knownKey} {targetBlock} {targetType}"
  |
  +-> If "Tag isn't vulnerable to Nested Attack":
      |-> Try staticnested
      |-> "hf mf {{loudong}} {size} {block} {type} {key}"
      |   where {loudong} is "nested" or "staticnested"
      |
darkside()
  |-> darksideOneKey()
  |-> "hf mf darkside"
```

### Key Recovery Constants

```python
DEFAULT_KEYS = [104 keys]  # Starting with FFFFFFFFFFFF, 000000000000, ...
KEYS_MAP = {}              # Runtime key storage {sector: {A: key, B: key}}
KEY_FILE_USER_NAME = 'user'
RECOVERY_FCHK = 'ChkDIC'
RECOVERY_NEST = 'Nested'
RECOVERY_STNE = 'STnested'
RECOVERY_DARK = 'Darkside'
RECOVERY_ALL  = 'REC_ALL'

# Timing estimates:
TIME_FHCK_ONE     = 0.01   # per key check
TIME_NESTED_ONE   = 11     # per nested attack
TIME_DARKSIDE_ONE = 60     # per darkside attack

# Regex:
'found valid key.*([a-zA-Z0-9]{12}).*'  # Parse found key
'Can\'t select card \(ALL\)'            # Card lost
'Wrong key. Can\'t authenticate to block'  # Wrong key
'No keys found'                         # Darkside failed
'no candidates found, trying again'     # Retry needed

# Static nonce detection:
'Try use `hf mf staticnested`'  -> use staticnested
'Try use `hf mf nested`'        -> use nested
'Fast staticnested decrypt'     -> staticnested success
```

### Key Recovery Functions

```python
fchks(size, key_file)           # Dictionary attack
nested(size, block, type, key)  # Nested attack wrapper
nestedAllKeys(known_key_map, listener)  # Recover all keys via nested
nestedOneKey(size, known_block, known_type, known_key, target_block, target_type)
darkside()                      # Darkside attack for first key
darksideOneKey()                # Single darkside attempt
keys(infos, listener)           # Full key recovery pipeline

# Key management:
putKey2Map(sector, type, key)   # Store recovered key
getKey4Map(sector, type)        # Retrieve key
delKey4Map(sector, type)        # Delete key
hasKeyA(sector)                 # Check if key A known
hasKeyB(sector)                 # Check if key B known
hasAllKeys(sector_count)        # All keys recovered?
getAnyKey()                     # Get any known key
getLostKeySector()               # Get sectors missing keys
getKeyMax4Size(size)            # Max keys for size
updateKeyFound()                # Update found count
updateKeyMax()                  # Update max count
```

### The `{loudong}` Template

The command `hf mf {{loudong}} {size} {block} {type} {key}` uses Python
`.format()` where `loudong` is substituted with either `"nested"` or
`"staticnested"`. The double braces `{{loudong}}` produce `{loudong}` after
the first format pass, then `loudong` is resolved in a second pass. This is
the "vulnerability" command - "loudong" means "vulnerability" in Chinese.

---

## 8. Write Flow

### Write Dispatcher (`write.so`)

```python
# Functions:
write(tag_type, infos, listener)         # Main write entry
verify(tag_type, infos, listener)        # Verify after write
run_action(action, listener)             # Run write/verify action
call_on_state(listener, state)           # State callback
call_on_finish(listener, success)        # Finish callback
callReadSuccess(listener, infos, bundle) # Read-back success
callReadFailed(listener, infos, ret)     # Read-back failure
```

### MIFARE Classic Write (`hfmfwrite.so`)

```python
# Write strategies (in order of attempt):
write(infos, listener)
  |-> tagChk1: Check if Gen1a magic
  |   |-> "hf 14a raw -p -a -b 7 40"   # Halt
  |   |-> "hf 14a raw -p -a 43"         # Magic wakeup
  |   |-> response check -> gen1a detected
  |
  |-> tagChk2: Check tag presence
  |-> tagChk3: Check write capability
  |-> tagChk4: Final verification
  |
  |-> If gen1a:
  |   |-> write_with_gen1a()
  |   |   |-> "hf mf cload b {file}"    # Load entire dump via Chinese backdoor
  |   |-> write_with_gen1a_only_uid()
  |   |   |-> "hf mf csetuid {uid} {sak} {atqa} w"
  |
  |-> If standard:
  |   |-> write_with_standard()
  |   |   |-> write_internal() per block
  |   |   |   |-> "hf mf wrbl {block} {A/B} {key} {data}"
  |   |-> write_with_standard_only_uid()
  |
  |-> write_unlimited()    # Write without key check
  |-> write_only_uid()     # UID-only write (gen1a or standard)
  |-> write_only_uid_unlimited()
  |-> write_only_blank()   # Write blank card
  |-> write_common()       # Common write logic

# Gen1a magic commands:
'hf 14a raw -p -a -b 7 40'                           # Magic wakeup step 1
'hf 14a raw -p -a 43'                                 # Magic wakeup step 2
'hf 14a raw -c -p -a e000'                            # Read block 0
'hf 14a raw -c -p -a e100'                            # Read block 1
'hf 14a raw -c -p -a 85000000000000000000000000000008' # Write special
'hf 14a raw -c -a 5000'                               # Halt

# Gen1a freeze (lock UID):
gen1afreeze()

# Write commands:
'hf mf wrbl {block} {A/B} {key} {data}'  # Standard write
'hf mf cload b {file}'                    # Gen1a dump load
'hf mf csetuid {uid} {sak} {atqa} w'     # Gen1a UID set

# Verify:
verify(infos)         # Verify write success
verify_only_uid()     # Verify UID only

# Error detection:
'Can\'t set magic card block'           -> gen1a write failed
'Card loaded \d+ blocks from file'      -> gen1a load success
```

### MF Ultralight Write (`hfmfuwrite.so`)

```
Command: "hf mfu restore s e f {file}"
Detection: "Can't select card" -> failure
Detection: "failed to write block" -> partial failure
```

### ISO15693 Write (`hf15write.so`)

```
Command: "hf 15 restore f {file}.bin"    # Restore dump
Command: "hf 15 csetuid {uid}"           # Set UID
Detection: "Write OK" -> success
Detection: "setting new UID (ok)" -> UID set success
Detection: "restore failed" -> failure
Detection: "can't read card UID" -> card lost
```

### iClass Write (`iclasswrite.so`)

```
Command: "hf iclass wrbl -b {block} -d {data} -k {key}"  # Write block
Command: "hf iclass calcnewkey o {old} n {new}"            # Calculate new key
Detection: "Writing failed" -> failure
Detection: "Xor div key : ([0-9A-Fa-f ]+)" -> key calc result
Detection: "failed tag-select" -> card lost
Detection: "successful" -> success
```

### LF Write (`lfwrite.so`)

| Card Type | Write Command |
|---|---|
| EM410x | `lf em 410x_write {id} 1` |
| HID | `lf hid clone {raw}` |
| Indala | `lf indala clone {type} -r {raw}` |
| FDX-B | `lf fdx clone c {country} n {id}` |
| Pyramid | (via raw clone) |
| AWID | (via raw clone) |
| Viking | (via raw clone) |
| Securakey | `lf securakey clone b {raw}` |
| Gallagher | `lf gallagher clone b {raw}` |
| NexWatch | `lf nexwatch clone r {raw}` |
| PAC | `lf pac clone b {raw}` |
| Paradox | `lf paradox clone b {raw}` |
| Jablotron | (via raw clone) |
| Keri | (via raw clone) |
| Nedap | (via raw clone) |
| Noralsy | (via raw clone) |
| Presco | (via raw clone) |
| Visa2000 | (via raw clone) |
| T55xx dump | `lf t55xx restore f {file}` |
| T55xx block | `lf t55xx write b {block} d {data}` |
| EM4x05 block | `lf em 4x05_write {block} {data} {key}` |

### LF Verify (`lfverify.so`)

```python
verify(tag_type, infos)       # Main verify
verify_t55xx(infos)           # T55xx verify
verify_em4x05(infos)          # EM4x05 verify
```

---

## 9. Complete PM3 Command Reference

### All commands extracted from binaries

#### HF Commands

```
hf 14a info                                     # Tag identification
hf 14a reader                                   # Continuous reader
hf 14a raw -p -a -b 7 40                       # Magic wakeup
hf 14a raw -p -a 43                             # Magic confirm
hf 14a raw -c -p -a e000                        # Read block 0
hf 14a raw -c -p -a e100                        # Read block 1
hf 14a raw -c -p -a 85{32hex}                   # Write special
hf 14a raw -c -a 5000                           # Halt
hf 14a sim t {type} u {uid}                     # Simulate 14A
hf 14a list                                      # List traces
hf 14a sniff                                     # Sniff 14A
hf 14b sniff                                     # Sniff 14B

hf sea                                           # HF search (abbreviated!)

hf mf rdbl {block} {A/B} {key}                  # Read block
hf mf rdsc {sector} {A/B} {key}                 # Read sector
hf mf wrbl {block} {A/B} {key} {data}           # Write block
hf mf fchk {size} {key_file}                    # Dictionary check
hf mf nested o {b} {t} {k} {tb} {tt}           # Nested attack
hf mf staticnested {size} {b} {t} {k}          # Static nested
hf mf darkside                                   # Darkside attack
hf mf cgetblk 0                                 # Gen1a read block 0
hf mf csetblk 0 {data}                          # Gen1a write block 0
hf mf csetuid {uid} {sak} {atqa} w              # Gen1a set UID
hf mf cload b {file}                            # Gen1a load dump
hf mf csave {type} o {file}                     # Gen1a save dump
hf mf cwipe                                     # Gen1a wipe
hf list mf                                       # List MF traces

hf mfu info                                      # Ultralight info
hf mfu dump f {file}                             # Ultralight dump
hf mfu restore s e f {file}                      # Ultralight restore

hf 15 dump                                       # ISO15693 dump
hf 15 restore f {file}.bin                       # ISO15693 restore
hf 15 csetuid {uid}                              # ISO15693 set UID

hf iclass info                                   # iClass info
hf iclass chk f {dic_file}                       # iClass key check
hf iclass rdbl b {block} k {key}                # iClass read block
hf iclass dump k {key}                           # iClass dump
hf iclass wrbl -b {block} -d {data} -k {key}    # iClass write block
hf iclass calcnewkey o {old} n {new}             # iClass calc key
hf iclass sniff                                  # iClass sniff
hf list iclass                                   # List iClass traces

hf felica reader                                 # FeliCa reader
hf felica litedump                               # FeliCa Lite dump

hf legic dump                                    # LEGIC dump
hf legic dump h                                  # LEGIC dump (alt)

hf tune                                          # HF antenna tune
hf topaz sniff                                   # Topaz sniff
hf list 14b                                      # List 14B traces
hf list topaz                                    # List Topaz traces
```

#### LF Commands

```
lf sea                                           # LF search (abbreviated!)

lf em 410x_read                                  # EM410x read
lf em 410x_sim {id}                              # EM410x simulate
lf em 410x_write {id} 1                          # EM410x write
lf em 410x_watch                                 # EM410x watch
lf em 4x05_info                                  # EM4x05 info (no key)
lf em 4x05_info FFFFFFFF                         # EM4x05 info (with key)
lf em 4x05_dump                                  # EM4x05 dump
lf em 4x05_read {block} {key}                    # EM4x05 read block
lf em 4x05_write {block} {data} {key}            # EM4x05 write block

lf t55xx detect                                  # T55xx detect (no key)
lf t55xx detect p FFFFFFFF                       # T55xx detect (with key)
lf t55xx dump                                    # T55xx dump
lf t55xx read b 0                                # T55xx read block 0
lf t55xx read b {b} p {key} o {override}         # T55xx read with key
lf t55xx write b {b} d {data}                    # T55xx write block
lf t55xx write b 0 d {data}                      # T55xx write block 0
lf t55xx write b 7 d {data}                      # T55xx write password
lf t55xx restore f {file}                        # T55xx restore dump
lf t55xx chk f {dic_file}                        # T55xx key check
lf t55xx wipe                                    # T55xx wipe
lf t55xx sniff                                   # T55xx sniff

lf hid read                                      # HID read
lf hid sim {raw}                                 # HID simulate
lf hid clone {raw}                               # HID clone
lf indala read                                   # Indala read
lf indala clone {type} -r {raw}                  # Indala clone
lf awid read                                     # AWID read
lf awid sim {fc} {cn} {bits}                     # AWID simulate
lf io read                                       # IO Prox read
lf io sim {fc} {cn} {ver}                        # IO Prox simulate
lf fdx read                                      # FDX-B read
lf fdx clone c {country} n {id}                  # FDX-B clone
lf FDX sim c {c} n {n} e/s {extra}              # FDX-B simulate
lf gproxii read                                  # G-Prox II read
lf gproxii sim {fc} {cn} {bits}                  # G-Prox II simulate
lf securakey read                                # Securakey read
lf securakey clone b {raw}                       # Securakey clone
lf viking read                                   # Viking read
lf Viking sim {id}                               # Viking simulate
lf pyramid read                                  # Pyramid read
lf Pyramid sim {fc} {cn}                         # Pyramid simulate
lf gallagher read                                # Gallagher read
lf gallagher clone b {raw}                       # Gallagher clone
lf nexwatch read                                 # NexWatch read
lf nexwatch clone r {raw}                        # NexWatch clone
lf jablotron read                                # Jablotron read
lf Jablotron sim {id}                            # Jablotron simulate
lf keri read                                     # Keri read
lf nedap read                                    # Nedap read
lf nedap sim s {sub} c {code} i {id}             # Nedap simulate
lf noralsy read                                  # Noralsy read
lf pac read                                      # PAC read
lf pac clone b {raw}                             # PAC clone
lf paradox read                                  # Paradox read
lf paradox clone b {raw}                         # Paradox clone
lf presco read                                   # Presco read
lf visa2000 read                                 # Visa2000 read

lf sniff                                         # LF sniff
lf config a 0 t 20 s 10000                       # LF config for sniff
lf tune                                          # LF antenna tune

data save f {file}                               # Save waveform data
```

#### HW Commands

```
hw connect                                       # Connect to PM3
hw ver                                           # PM3 version info
```

---

## 10. Activity UI Flow

### Activity Hierarchy

```
BaseActivity (actbase.so)
  |-> AutoExceptCatchActivity
  |     |-> ScanActivity
  |     |     |-> ReadActivity
  |     |     |     |-> AutoCopyActivity
  |     |     |     |     |-> ReadListActivity
  |     |-> WriteActivity
  |-> SniffActivity
  |     |-> SniffForMfReadActivity
  |-> WarningWriteActivity
  |-> AboutActivity
  |-> BacklightActivity
  |-> CardWalletActivity
  |-> ConsolePrinterActivity
  |-> KeyEnterM1Activity
  |-> IClassSEActivity
  |-> LUAScriptCMDActivity
  ... (many more)
```

### ScanActivity Flow

```python
class ScanActivity(AutoExceptCatchActivity):
    # Entry:
    onCreate()          # Set up UI, start auto-scan
    onAutoScan()        # Called automatically, starts scan
    startScan()         # Creates Scanner, begins scan

    # Callbacks:
    onScanning(progress)     # Update UI with scan progress
    onScanFinish(data)       # Handle scan result
    showScanToast(found, multi)  # Show toast notification
    showButton(found, cansim=False)  # Show Read/Sim buttons

    # Navigation:
    how2Scan()          # Instructions
    canidle(infos)      # Check if can show idle
    playScanning()      # Play scanning sound
```

### ReadActivity Flow

```python
class ReadActivity(ScanActivity):
    FORCE_READ_M1    = 'ReadActivity.FORCE_READ_M1'
    FORCE_READ_T55XX = 'ReadActivity.FORCE_READ_T55XX'
    FORCE_READ_EM4305 = 'ReadActivity.FORCE_READ_EM4305'

    # After scan succeeds:
    startRead(infos=None, force=False)  # Start read operation
    onReading(progress)                  # Update read progress
    showReadToast(success, is_force=False)  # Show result
    stopRead()                           # Stop reading
    hideReadToast()                      # Hide result

    seconds_to_time(seconds)  # Format time estimate
```

### WriteActivity Flow

```python
class WriteActivity(AutoExceptCatchActivity):
    # Entry:
    onCreate()           # Set up UI
    onKeyEvent(event)    # Handle button presses

    # Write:
    startWrite()         # Begin write operation
    on_write(progress)   # Write progress callback
    playWriting()        # Play writing sound

    # Verify:
    startVerify()        # Begin verification
    on_verify(progress)  # Verify progress callback
    playVerifying()      # Play verifying sound

    # UI:
    setBtnEnable(v_enable, w_enable)  # Enable/disable buttons
```

### Simulation Commands (from `activity_main.so`)

| Tag Type | Simulate Command |
|---|---|
| M1 1K 4B | `hf 14a sim t 1 u {uid}` |
| M1 4K 4B | `hf 14a sim t 2 u {uid}` |
| M1 7B | `hf 14a sim t 7 u {uid}` |
| UL | `hf 14a sim t 8 u {uid}` |
| DESFire | `hf 14a sim t 9 u {uid}` |
| EM410x | `lf em 410x_sim {id}` |
| HID | `lf hid sim {raw}` |
| AWID | `lf awid sim {fc} {cn} {bits}` |
| IO Prox | `lf io sim {fc} {cn} {ver}` |
| GProx II | `lf gproxii sim {fc} {cn} {bits}` |
| FDX-B | `lf FDX sim c {c} n {n} e/s {extra}` |
| Jablotron | `lf Jablotron sim {id}` |
| Viking | `lf Viking sim {id}` |
| Pyramid | `lf Pyramid sim {fc} {cn}` |
| Nedap | `lf nedap sim s {sub} c {code} i {id}` |

Also from WriteActivity:
```
hf mf csetblk 0 {data}   # Set block 0 for simulation prep
hf mf cwipe               # Wipe gen1a card
```

---

## 11. File Storage Layout

### Dump Storage (`appfiles.so`)

All dumps stored under `/mnt/upan/dump/`:

```
/mnt/upan/
  dump/
    mf1/           # MIFARE Classic (.eml, .bin)
    mfu/           # MIFARE Ultralight
    14443a/        # ISO14443A Other
    icode/         # ISO15693
    iclass/        # iClass
    legic/         # LEGIC
    felica/        # FeliCa
    em410x/        # EM410x
    hid/           # HID Prox
    indala/        # Indala
    awid/          # AWID
    ioprox/        # IO Prox
    gproxii/       # G-Prox II
    securakey/     # Securakey
    viking/        # Viking
    pyramid/       # Pyramid
    t55xx/         # T55xx
    em4x05/        # EM4x05
    fdx/           # FDX-B
    gallagher/     # Gallagher
    jablotron/     # Jablotron
    keri/          # Keri
    nedap/         # Nedap
    nexwatch/      # NexWatch
    noralsy/       # Noralsy
    pac/           # PAC
    paradox/       # Paradox
    presco/        # Presco
    visa2000/      # Visa2000
  keys/
    mf1/           # MIFARE Classic keys
    t55xx/         # T55xx keys
  trace/           # Sniff traces
  app.log          # Application log
```

### File Naming Conventions

| Type | Prefix | Example |
|---|---|---|
| M1 | (by UID) | `AB12CD34.eml` |
| UL | `M0-UL-{num}` | `M0-UL-001.bin` |
| NTAG213 | `NTAG213-{num}` | `NTAG213-001.bin` |
| EM410x | `EM410x-ID-{id}` | `EM410x-ID-1234567890.txt` |
| HID | `HID-Prox-ID-{raw}` | `HID-Prox-ID-2004...txt` |
| T55xx | `T55xx-{b0}-{b1}-{b2}` | `T55xx-00148040-...txt` |
| iClass | `Iclass-{num}` | `Iclass-001.bin` |

---

## 12. Discrepancies with Reimplementation

### Critical Differences

#### 1. Search Command Names
- **Original**: `hf sea` and `lf sea` (abbreviated)
- **Reimpl**: `hf search` and `lf search` (full)
- **Impact**: Commands will fail on the original PM3 firmware

#### 2. Scanner Constructor
- **Original**: `Scanner()` takes no arguments, uses module-level `executor`
- **Reimpl**: `Scanner(executor)` takes executor as argument
- **Impact**: Different initialization pattern

#### 3. Scan Pipeline
- **Original**: 6-stage pipeline: `scan_14a` -> `scan_hfsea` -> `scan_lfsea` -> `scan_t55xx` -> `scan_em4x05` -> `scan_felica`
- **Reimpl**: 2-stage: `_scan_hf()` -> `_scan_lf()`
- **Impact**: Missing T55xx/EM4x05/FeliCa-specific scan stages, missing `scan_14a` (which does `hf 14a info` separately before `hf sea`)

#### 4. Tag Type IDs
- **Original**: Integer IDs (0-47) with specific groupings
- **Reimpl**: String-based tag type names
- **Impact**: Type routing for read/write/simulate will differ

#### 5. hf14ainfo Parsing
- **Original**: Uses specific regex patterns:
  - `.*UID:(.*)\n`
  - `.*ATQA:(.*)\n`
  - `.*SAK:(.*)\[.*\n`
  - `.*Prng detection: (.*)\n`
  - Checks for "Magic capabilities : Gen 1a" and "Gen 2 / CUID"
  - Checks "Static nonce: yes"
  - Issues `hf mf cgetblk 0` to detect Gen1a
- **Reimpl**: Generic regex parsing, missing Gen1a detection, missing PRNG/static nonce detection

#### 6. Reader Factory Pattern
- **Original**: `Reader` class with `default_reader` list of 8 AbsReader subclasses, uses `find_reader(tag_type, tag_data)` dispatch
- **Reimpl**: Direct function calls without Reader factory

#### 7. Key Recovery Flow
- **Original**: `fchk` -> `nested` (with static nonce detection -> `staticnested`) -> `darkside`
- **Reimpl**: Likely missing `staticnested` and proper flow control
- **Critical**: The `{loudong}` template for `nested`/`staticnested` switching

#### 8. MIFARE Classic Write Strategies
- **Original**: Multiple write paths: `write_with_gen1a`, `write_with_standard`, `write_unlimited`, `write_only_uid`, `write_only_uid_unlimited`, `write_only_blank`
- **Original**: Gen1a detection via raw commands (`hf 14a raw -p -a -b 7 40`, etc.)
- **Reimpl**: Likely simplified write flow

#### 9. Error Detection
- **Original**: Specific keyword/regex checks per operation:
  - `isCMDTimeout`: "timeout while waiting for reply"
  - `isUARTTimeout`: "UART:: write time-out"
  - `isPM3Offline`: "Communicating with PM3"
  - Per-module error strings (see Read/Write sections)
- **Reimpl**: May have different/incomplete error detection

#### 10. Module-Level State
- **Original**: Many modules use module-level mutable state (e.g., `hfmfread.DATA_MAP`, `hfmfkeys.KEYS_MAP`, `scan.INFOS`)
- **Reimpl**: May use instance state instead
- **Impact**: State management differs, especially for caching between scan/read/write

#### 11. LF WAV Filter
- **Original**: `scan.lf_wav_filter()` saves waveform to `/tmp/lf_trace_tmp` via `data save f`
- **Reimpl**: Likely missing this step

#### 12. Typos Preserved in Original
- `clearScanCahe` (not `clearScanCache`) - typo in original!
- Module imports `hffelica` alongside `felicaread` for different purposes

#### 13. Version Constants
- **Original**: `VERSION_STR = '1.0.90'`, `TYP = 'iCopy-XS'`, `PM3_VER = '1.0.2'`, `PM3_VER_APP = 'NIKOLA: v3.1'`, `PM3_VER_TAG = 'NIKOLA: v'`
- These are used for PM3 firmware version matching

#### 14. iClass Key Handling
- **Original**: `hficlass.KEYS_ICLASS_NIKOLA` contains a large encrypted/encoded key blob (base64, 7000+ chars)
- This is likely an encrypted key dictionary decoded at runtime

#### 15. T55xx Key Dictionary
- **Original**: `lft55xx.DEFAULT_KEYS` contains 100+ known passwords including comments
- Used by `lf t55xx chk f` for password recovery

---

## Summary of Scan -> Read -> Write Pipeline

```
1. SCAN:
   Scanner.scan_all_synchronous()
     -> scan_14a():  "hf 14a info" (5s timeout)
        Parse: UID, ATQA, SAK, Magic, PRNG, type
     -> scan_hfsea(): "hf sea" (10s timeout)
        Parse: ISO15693, ISO14443B, Topaz, FeliCa, iClass, LEGIC
     -> scan_lfsea(): "lf sea" (10s timeout)
        Parse: EM410x, HID, Indala, + 17 other types
     -> scan_t55xx(): "lf t55xx detect" (10s timeout)
     -> scan_em4x05(): "lf em 4x05_info" (5s timeout)
     -> scan_felica(): "hf felica reader" (10s timeout)

   Returns: {tag_type: int, uid, atqa, sak, gen1a, prng, ...}

2. READ:
   Reader.start(tag_type, tag_data)
     -> find_reader(tag_type) dispatches to:
        MifareClassicReader:  hfmfkeys.keys() then hfmfread.readAllSector()
        MifareUltralightReader: "hf mfu dump f {file}"
        LF125KHZReader: lfread.read{Type}()
        HIDIClassReader: iclassread.read()
        LegicMim256Reader: "hf legic dump"
        ISO15693Reader: "hf 15 dump"
        ISO1443AReader: hf14aread.read()
        FelicaReader: "hf felica litedump"

   Returns: dump file path + tag data dict

3. WRITE:
   write.write(tag_type, infos, listener)
     -> Dispatches to module-specific writer:
        hfmfwrite.write()   # Gen1a or standard
        hfmfuwrite.write()  # UL restore
        lfwrite.write()     # LF clone/write
        hf15write.write()   # ISO15693 restore
        iclasswrite.write() # iClass write
     -> write.verify(tag_type, infos, listener)
        -> Re-reads and compares
```
