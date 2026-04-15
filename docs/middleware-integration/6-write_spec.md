# Write Pipeline Transliteration Spec

## Ground Truth Sources

| Source | Path | Status |
|--------|------|--------|
| Binary strings (write.so) | `docs/v1090_strings/write_strings.txt` | Primary — all string literals |
| Binary strings (hfmfwrite.so) | `docs/v1090_strings/hfmfwrite_strings.txt` | Primary — all string literals |
| Binary strings (lfwrite.so) | `docs/v1090_strings/lfwrite_strings.txt` | Primary — all string literals |
| Binary strings (hf15write.so) | `docs/v1090_strings/hf15write_strings.txt` | Primary — all string literals |
| Binary strings (hfmfuwrite.so) | `docs/v1090_strings/hfmfuwrite_strings.txt` | Primary — all string literals |
| Binary strings (iclasswrite.so) | `docs/v1090_strings/iclasswrite_strings.txt` | Primary — all string literals |
| Module audit | `docs/V1090_MODULE_AUDIT.txt` | Primary — function signatures, constants, imports |
| Real device trace (MFC write) | `docs/Real_Hardware_Intel/trace_write_activity_attrs_20260402.txt` | Primary — full MF1K write+verify with attrs |
| Archive transliteration | `archive/lib_transliterated/write.py` | STRUCTURAL REFERENCE ONLY |
| UI layer | `src/lib/activity_main.py` WriteActivity | For understanding call conventions |
| DRM knowledge base | `docs/DRM-KB.md` | DRM mechanism for hfmfwrite.so |
| Test fixtures | `tests/flows/write/scenarios/` | 63 scenarios — cross-reference |

---

## 1. Module: write.so — The Dispatcher

### 1.1 Exported Functions (from binary strings)

```
write(listener, infos, bundle, run_on_subthread=True)
verify(listener, infos, bundle, run_on_subthread=True)
callReadFailed(listener, ret)
callReadSuccess(listener)
call_on_finish(ret, listener)
call_on_state(state, listener)
run_action(run, run_on_subthread)
```

Note: `write.so` does NOT contain a class. It is a flat module with dispatch functions.

### 1.2 Imports

```python
import threading
import tagtypes
```

### 1.3 Callback Helpers

```python
def callReadFailed(listener, ret):
    """listener({'success': False, 'return': ret})"""

def callReadSuccess(listener):
    """listener({'success': True})"""

def call_on_finish(ret, listener):
    """If ret == 1: callReadSuccess(listener). Else: callReadFailed(listener, ret)."""

def call_on_state(state, listener):
    """listener({'state': state})"""
```

### 1.4 Thread Helper

```python
def run_action(run, run_on_subthread):
    """If run_on_subthread: Thread(target=run, daemon=True).start(). Else: run()."""
```

### 1.5 Type Dispatch Map

From binary strings `__pyx_k_*` entries and archive cross-reference:

| Type IDs | Protocol | Write Module | Verify Module |
|----------|----------|-------------|--------------|
| 0,1,25,26,40,41,42,43,44 | MIFARE Classic | `hfmfwrite.write()` | `hfmfwrite.verify()` |
| 2,3,4,5,6,7 | MIFARE Ultralight/NTAG | `hfmfuwrite.write()` | `hfmfuwrite.verify()` |
| 8-16,28-37,45 | LF 125kHz (clone-based) | `lfwrite.write()` | `lfverify.verify()` |
| 23 | T55xx (dump-based) | `lfwrite.write_dump_t55xx()` | `lfverify.verify_t55xx()` |
| 24 | EM4305 (dump-based) | `lfwrite.write_dump_em4x05()` | `lfverify.verify_em4x05()` |
| 17,18,47 | iCLASS | `iclasswrite.write()` | `iclasswrite.verify()` |
| 19,46 | ISO 15693 | `hf15write.write()` | `hf15write.verify()` |
| 20,21,22,27,38,39 | Unsupported | `callReadFailed(listener, -1)` | `callReadFailed(listener, -1)` |

String evidence for type sets:
- `__pyx_k_getM1Types`, `__pyx_k_getULTypes`, `__pyx_k_getAllLow`, `__pyx_k_getAllLowCanDump`, `__pyx_k_getiClassTypes` — internal type-set builders
- `__pyx_k_ISO15693_ST_SA`, `__pyx_k_ISO15693_ICODE` — ISO15693 subtypes
- `__pyx_k_HF14A_OTHER` — catch-all HF14A

### 1.6 write() Function

```python
def write(listener, infos, bundle, run_on_subthread=True):
    """
    Args:
        listener: Callback — WriteActivity.on_write method.
                  write.so accesses listener.__self__ to call:
                    - playWriting()
                    - playVerifying()
                    - setBtnEnable(True/False)
        infos:    Dict from scan cache. Must have 'type' key (int).
        bundle:   Read result. For MFC: file path string.
                  For LF: dict with 'data'/'raw' keys.
                  For iCLASS: dict with dump data.
                  For ISO15693: file path or dict with 'file' key.
        run_on_subthread: If True (default), run in daemon thread.
    """
```

**Ground truth from trace** (trace_write_activity_attrs_20260402.txt):
```
write() arg0: WriteActivity.on_write
write() arg1: dict {'found': True, 'uid': 'AA991523', 'len': 4, 'sak': '08',
                     'atqa': '0004', 'bbcErr': False, 'static': False,
                     'gen1a': False, 'type': 1}
write() arg2: str '/mnt/upan/dump/mf1/M1-1K-4B_AA991523_5.bin'
```

### 1.7 verify() Function

Same signature as `write()`. Dispatches to verify sub-modules.

**Ground truth from trace**:
```
verify() arg0: WriteActivity.on_verify
verify() arg1: dict {same infos as write}
verify() arg2: str '/mnt/upan/dump/mf1/M1-1K-4B_AA991523_5.bin'
```

### 1.8 Result Dict Shapes

**Success** (via callReadSuccess):
```python
{'success': True}
```

**Failure** (via callReadFailed):
```python
{'success': False, 'return': <int>}
```

**State update** (via call_on_state):
```python
{'state': <string>}
```

### 1.9 WriteActivity Interface (what write.so expects from its caller)

From trace_write_activity_attrs_20260402.txt, write.so reads these attributes on
the activity object (accessed via `listener.__self__`):

| Attribute | Type | Description |
|-----------|------|-------------|
| `.infos` | dict | Scan cache (type, uid, sak, atqa, gen1a, etc.) |
| `.can_verify` | bool | False initially, set True after first write |
| `._bundle` | str/dict | Read result (dump path or data dict) |
| `._write_progressbar` | ProgressBar | Progress bar widget |
| `._write_toast` | Toast | Toast widget |
| `.playWriting()` | method | Show "Writing..." progress |
| `.playVerifying()` | method | Show "Verifying..." progress |
| `.setBtnEnable(bool)` | method | Enable/disable buttons |
| `.setLeftButton(str)` | method | Set left button text |
| `.setRightButton(str)` | method | Set right button text |
| `.text_rewrite` | str | "Rewrite" |
| `.text_verify` | str | "Verify" |
| `.text_verify_failed` | str | "Verification failed!" |
| `.text_verify_success` | str | "Verification successful!" |
| `.text_verifying` | str | "Verifying..." |
| `.text_write_failed` | str | "Write failed!" |
| `.text_write_success` | str | "Write successful!" |
| `.text_write_tag` | str | "Write Tag" |
| `.text_writing` | str | "Writing..." |
| `.text_t55xx_checking` | str | "T55xx keys checking..." |

---

## 2. Module: hfmfwrite.so — MIFARE Classic Writer

### 2.1 DRM Check — tagChk1

**CRITICAL**: hfmfwrite.so contains a DRM gate (`tagChk1`) that blocks all write
operations if the license check fails. This is the known DRM blocker.

**DRM mechanism** (from binary strings + DRM-KB.md):

```python
def tagChk1(infos, file, newinfos):
    """DRM verification gate.

    Steps:
    1. subprocess.check_output(['cat', '/proc/cpuinfo'])
    2. re.search(r'Serial\s*:\s*([a-fA-F0-9]+)', output)
    3. hashlib.md5(sn_str).hexdigest()
    4. base64.b64decode(version.UID)
    5. from Crypto.Cipher import AES
       aes_obj = AES.new(key, AES.MODE_CFB, iv=iv)
       result = aes_obj.decrypt(encrypted_data)
    6. Compare derived value against 'AA55C396' marker
    7. Return: init_tag / init_tag1 (lambda-based tag factory)
    """
```

**DRM string evidence**:
- `__pyx_k_cat_proc_cpuinfo` — subprocess command
- `__pyx_k_Serial_s_s_a_fA_F0_9` — regex pattern `Serial\s*:\s*([a-fA-F0-9]+)`
- `__pyx_k_VB1v2qvOinVNIlv2` — encrypted DRM key constant
- `__pyx_k_AA55C396` — verification marker
- `__pyx_k_Crypto_Cipher` — PyCryptodome import
- `__pyx_k_MODE_CFB` — AES cipher mode
- `__pyx_k_hashlib`, `__pyx_k_hexdigest`, `__pyx_k_b64decode`, `__pyx_k_decrypt`

**Status**: DRM passes natively under QEMU with:
- Correct cpuinfo serial: `02c000814dfb3aeb`
- Real PyCryptodome (not the no-op shim)

### 2.2 Exported Functions

```
verify(infos, bundle)
tagChk1(infos, file, newinfos)           — DRM gate
write_common(listener, infos, bundle)    — shared write logic
write_block(...)                         — per-block write
write_unlimited(...)                     — unlimited magic card write
write_success_list(...)                  — track successful blocks
write_internal(...)                      — internal dispatcher
write_with_standard(...)                 — standard (non-magic) card write
write_only_blank(...)                    — write blank card
write_only_uid(...)                      — UID-only write
write_only_uid_unlimited(...)            — UID-only on unlimited magic
write_with_gen1a(...)                    — Gen1a magic card write
write_with_gen1a_only_uid(...)           — Gen1a UID-only write
write_with_standard_only_uid(...)        — Standard UID-only write
gen1afreeze(...)                         — Gen1a freeze sequence
read_blocks_4file(...)                   — Read blocks for file creation
blockToSector(blockIndex)                — Block→Sector conversion
createManufacturerBlock(...)             — Create block 0 data
```

### 2.3 Imports

```python
import executor
import hfmfkeys    # Key management
import hfmfread    # Block reading
import mifare      # Constants (BLOCK_SIZE, EMPTY_KEY, etc.)
import scan        # scan_14a()
import tagtypes    # Type classification
import platform    # OS detection
import subprocess  # DRM: cat /proc/cpuinfo
import hashlib     # DRM
import base64      # DRM: b64decode
import re          # DRM: Serial regex
```

### 2.4 PM3 Commands

From binary strings + real device trace:

| Command | Purpose | Timeout |
|---------|---------|---------|
| `hf 14a info` | Card presence check before write | default |
| `hf mf cgetblk 0` | Gen1a detection (if wupC1 error → not gen1a) | default |
| `hf mf fchk {size} {keyfile}` | Key recovery/verification before write | 600000ms |
| `hf mf wrbl {block} {A\|B} {key} {data}` | Write single block | default |
| `hf mf csetuid {uid_bytes} {sak} {atqa} w` | Set UID on Gen1a magic card | default |
| `hf mf cload b {filepath}` | Load dump to Gen1a card | default |
| `hf 14a raw -p -a -b 7 40` | Gen1a wakeup (backdoor) | default |
| `hf 14a raw -c -p -a e000` | Gen1a select block 0 | default |
| `hf 14a raw -c -p -a e100` | Gen1a select block 1 | default |
| `hf 14a raw -c -a 5000` | Gen1a halt | default |
| `hf 14a raw -p -a 43` | Gen1a wakeup variant | default |
| `hf 14a raw -c -p -a 85000000000000000000000000000008` | Gen1a freeze command | default |

### 2.5 Write Flow — Standard Card (from trace)

**Real device trace**: trace_write_activity_attrs_20260402.txt

1. `hf 14a info` — verify card present, extract UID
2. `hf mf cgetblk 0` — check Gen1a (wupC1 error → standard)
3. `hf mf fchk {size} /tmp/.keys/mf_tmp_keys` — verify keys are known
4. Write blocks in **REVERSE sector order** (sector 15→0):
   - For each sector: write data blocks first, then trailer block
   - Block 0 (manufacturer block) written last within sector 0
   - Command: `hf mf wrbl {block} A {key} {data}`
5. Write trailer blocks (sector keys) after data blocks
6. Verify: `hf 14a info` + `hf mf cgetblk 0` (post-write card check)

**Block write order** (from trace, 1K card with 64 blocks):
- Data blocks: 60,61,62, 56,57,58, 52,53,54, 48,49,50, ..., 4,5,6, 0,1,2
- Block 0 data: manufacturer block with UID
- Trailer blocks: 63, 59, 55, 51, 47, 43, 39, 35, 31, 27, 23, 19, 15, 11, 7, 3

### 2.6 Write Flow — Gen1a Card

1. `hf 14a info` — verify card present
2. `hf mf cgetblk 0` — Gen1a detection (success → gen1a confirmed)
3. `hf mf cload b {filepath}` — bulk load entire dump to card
4. Verify: check `Card loaded %d blocks from file` in response
5. On failure: `Can't set magic card block` message

### 2.7 Gen1a Freeze Sequence

```
hf 14a raw -p -a -b 7 40     — Backdoor wakeup
hf 14a raw -c -p -a 43       — Wakeup variant
hf 14a raw -c -p -a e000     — Select block 0
hf 14a raw -c -p -a 85000000000000000000000000000008  — Freeze block 0
hf 14a raw -c -a 5000        — Halt
```

### 2.8 hasKeyword Checks

```python
hasKeyword("isOk:01")           — Write block success
hasKeyword("Card loaded")       — Gen1a cload success
hasKeyword("Can't set magic")   — Gen1a write failure
```

### 2.9 Constants (from mifare.so, cross-referenced)

```python
BLOCK_SIZE = 16
EMPTY_DATA = '00000000000000000000000000000000'
EMPTY_KEY = 'FFFFFFFFFFFF'
EMPTY_TRAI = 'FFFFFFFFFFFFFF078069FFFFFFFFFFFF'
MAX_BLOCK_COUNT = 256
SECTOR_1K = 16
SECTOR_4K = 40
SIZE_1K = 1024
SIZE_2K = 2048
SIZE_4K = 4096
SIZE_MINI = 320
```

### 2.10 Key Variables

```python
__pyx_k_M1_S50_1K_4B     — MFC 1K 4-byte UID type name
__pyx_k_M1_POSSIBLE_4B   — MFC possible 4-byte type
__pyx_k_M1_MINI          — MFC Mini type name
__pyx_k_HF14A_OTHER      — Generic HF14A type
__pyx_k_FFFFFFFFFFFF     — Default empty key
__pyx_k_E00000000000     — Alternative empty key prefix
```

### 2.11 Pyx Integer Constants

```python
__pyx_int_1        — Success return code
__pyx_int_neg_1    — Failure return code
__pyx_int_neg_10   — Critical failure return code
```

---

## 3. Module: lfwrite.so — LF 125kHz Writer

### 3.1 Exported Functions

```
write(listener, typ, infos, raw_par, key=None)
write_b0_need(typ, key=None)
write_block_em4x05(blocks, start, end, key)
write_dump_em4x05(file, key=None)
write_dump_t55xx(file, key=None)
write_em410x(em410x_id)
write_fdx_par(animal_id)
write_hid(hid_id)
write_indala(raw)
write_nedap(raw)
write_raw(typ, raw, key=None)
write_raw_clone(typ, raw)
write_raw_t55xx(raw)
```

### 3.2 Imports

```python
import executor
import lft55xx       # T55xx chip operations
import platform      # OS detection
import re
import tagtypes      # Type classification
```

### 3.3 Constants — Write Maps

**B0_WRITE_MAP** — Block 0 configuration for each LF tag type:
```python
B0_WRITE_MAP = {
    37: '00148068',   # type 37
    15: '00088040',   # type 15
    33: '00088C6A',   # type 33
    36: '00088088',   # type 36
    9:  '00107060',   # type 9
    11: '00107060',   # type 11
    16: ...,          # (truncated in audit)
}
```

**DUMP_WRITE_MAP** — Dump-based write handlers:
```python
DUMP_WRITE_MAP = {
    23: write_dump_t55xx,    # T55xx dump write
    24: write_dump_em4x05,   # EM4x05 dump write
}
```

**PAR_CLONE_MAP** — Parameter-based clone handlers:
```python
PAR_CLONE_MAP = {
    28: write_fdx_par,    # FDX-B
    8:  write_em410x,     # EM410x
    9:  write_hid,        # HID (one of)
    ...
}
```

**RAW_CLONE_MAP** — Raw data clone command templates:
```python
RAW_CLONE_MAP = {
    14: 'lf securakey clone b {}',
    29: 'lf gallagher clone b {}',
    34: 'lf pac clone b {}',
    35: 'lf paradox clone b {}',
    ...
}
```

### 3.4 PM3 Commands

| Command | Purpose | Used By |
|---------|---------|---------|
| `lf em 410x_write {id} 1` | Write EM410x ID | `write_em410x()` |
| `lf hid clone {params}` | Clone HID Prox | `write_hid()` |
| `lf indala clone {params} -r {raw}` | Clone Indala | `write_indala()` |
| `lf fdx clone c {country} n {id}` | Clone FDX-B | `write_fdx_par()` |
| `lf securakey clone b {raw}` | Clone Securakey | RAW_CLONE_MAP |
| `lf gallagher clone b {raw}` | Clone Gallagher | RAW_CLONE_MAP |
| `lf nexwatch clone r {raw}` | Clone NexWatch | RAW_CLONE_MAP |
| `lf paradox clone b {raw}` | Clone Paradox | RAW_CLONE_MAP |
| `lf pac clone b {raw}` | Clone PAC | RAW_CLONE_MAP |
| `lf t55xx write b 0 d {data}` | Write T55xx block 0 | `write_b0_need()` |
| `lf t55xx write b {n} d {data}` | Write T55xx block N | `write_raw_t55xx()` |
| `lf t55xx restore f {path}` | Restore T55xx dump | `write_dump_t55xx()` |
| `lf em 4x05_write {block} {data} {key}` | Write EM4x05 block | `write_block_em4x05()` |

### 3.5 Write Flow — Clone-Based LF Tags

1. `check_detect()` — Detect T55xx chip presence via `lft55xx.detectT55XX()`
2. If password-protected: wipe with `lf t55xx wipe p {password}`
3. Write config block 0 via `write_b0_need()` if needed
4. Dispatch to clone command from RAW_CLONE_MAP or PAR_CLONE_MAP
5. Verify via separate `lfverify.verify()` (not in lfwrite.so)

### 3.6 LF Tag Type IDs

```python
EM410X_ID      = 8
HID_PROX_ID    = 9
INDALA_ID      = 10
AWID_ID        = 11
IO_PROX_ID     = 12
KERI_ID        = 13
SECURAKEY_ID   = 14
FDXB_ID        = 28
NEXWATCH_ID    = 29
JABLOTRON_ID   = 30
GALLAGHER_ID   = 31
VIKING_ID      = 32
PARADOX_ID     = 33
PAC_ID         = 34
PRESCO_ID      = 35
VISA2000_ID    = 36
NORALSY_ID     = 37
PYRAMID_ID     = 15
GPROX_II_ID    = 16
NEDAP_ID       = ...
T55X7_ID       = 23
EM4305_ID      = 24
```

### 3.7 Block 0 Configuration Values

From binary strings:
```
00148068  — type 37 (Noralsy)
00088040  — type 15 (Pyramid)
00088C6A  — type 33 (Paradox)
00088088  — type 36 (Visa2000)
00107060  — type 9 (HID), type 11 (AWID)
00107080  — (variant)
00147040  — (variant)
00150060  — (variant)
00158040  — (variant)
603E1040  — (variant)
907F0042  — (variant)
00148040  — EM410x default config
```

### 3.8 Success/Failure Keywords

```
"Success writing to tag"     — clone success
"Done"                       — write complete
"failed"                     — write failure
"lock_unavailable_list"      — lock status check
```

### 3.9 Special: startPM3Plat

lfwrite.so uses `startPM3Plat` (platform-aware PM3 start) in addition to
`startPM3Task`. This suggests platform-specific behavior (possibly using
`sudo xxd -ps` on non-ARM).

---

## 4. Module: hf15write.so — ISO 15693 Writer

### 4.1 Exported Functions

```
write(infos, file)
verify(infos, file)
```

### 4.2 Imports

```python
import executor
import scan          # scan_hfsea(), isTagFound(), set_infos_cache()
```

### 4.3 PM3 Commands

| Command | Purpose | Timeout |
|---------|---------|---------|
| `hf 15 restore f {path}.bin` | Restore data blocks from dump file | 28888ms |
| `hf 15 csetuid {uid}` | Set UID on target card | 5000ms |

### 4.4 Write Flow

1. `hf 15 restore f {path}.bin` — restore all data blocks
2. Check response for `Write OK` AND `done`
3. On failure: check `restore failed`, `Too many retries`
4. `hf 15 csetuid {uid}` — set UID to match source
5. Check response for `setting new UID (ok)`
6. On failure: `can't read card UID`

### 4.5 Verify Flow

1. Re-scan via `scan.scan_hfsea()`
2. Check `scan.isTagFound()`
3. Compare UID, data blocks against source dump

### 4.6 Constants

```python
__pyx_int_5000     — Timeout for csetuid
__pyx_int_28888    — Timeout for restore
__pyx_int_1        — Success
__pyx_int_neg_1    — Failure
__pyx_int_neg_10   — Critical failure
```

### 4.7 hasKeyword Checks

```python
hasKeyword("Write OK")              — Block write success
hasKeyword("done")                  — Restore complete
hasKeyword("restore failed")        — Restore failure
hasKeyword("Too many retries")      — Retry exhaustion
hasKeyword("setting new UID (ok)")  — UID set success
hasKeyword("can't read card UID")   — UID read failure
```

---

## 5. Module: hfmfuwrite.so — MIFARE Ultralight/NTAG Writer

### 5.1 Exported Functions

```
write(infos, file)
write_call(line)
verify(infos, file=None)
```

### 5.2 Imports

```python
import executor
import scan          # scan_14a(), isTagFound()
import tagtypes      # ULTRALIGHT, ULTRALIGHT_C, ULTRALIGHT_EV1,
                     #   NTAG213_144B, NTAG215_504B, NTAG216_888B
```

### 5.3 PM3 Commands

| Command | Purpose |
|---------|---------|
| `hf mfu restore s e f {path}` | Restore Ultralight/NTAG dump |

The `s e` flags mean "special" + "end" — tells PM3 to handle OTP/lock pages.

### 5.4 Write Flow

1. Determine subtype from `infos['type']`:
   - ULTRALIGHT, ULTRALIGHT_C, ULTRALIGHT_EV1
   - NTAG213_144B, NTAG215_504B, NTAG216_888B
2. Build file path from `infos` type prefix + file suffix `.bin`
3. `hf mfu restore s e f {filepath}` — restore dump
4. Check response for success/failure

### 5.5 Verify Flow

1. `scan.scan_14a()` — re-scan for tag
2. `scan.isTagFound()` — verify tag present
3. Read back data and compare against source

### 5.6 hasKeyword Checks

```python
hasKeyword("Can't select card")      — Card not present
hasKeyword("failed to write block")  — Block write failure
```

### 5.7 Constants

```python
__pyx_int_1        — Success
__pyx_int_neg_1    — Failure
__pyx_int_neg_10   — Critical failure
```

### 5.8 write_call(line)

Callback function for per-block progress reporting during restore.
Called by executor with each line of PM3 output.

---

## 6. Module: iclasswrite.so — HID iCLASS Writer

### 6.1 Exported Functions

```
write(infos, bundle)
verify(infos, bundle)
append_suffix(file)
calcNewKey(typ, oldkey, newkey, l2e=False)
getNeedWriteBlock(typ)
make_se_data(blk7)
readBlockHex(file, block, block_size=8)
writeDataBlock(typ, block, data, key)
writeDataBlocks(typ, file_or_dict, key='2020666666668888')
writePassword(typ, new_key, oldkey='2020666666668888', l2e=False)
readTagBlock(...)
verify_block(...)
checkKey(...)
```

### 6.2 Constants

```python
ICLASS_E_WRITE_BLOCK = [6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18]
ICLASS_L_WRITE_BLOCK = [6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18]
```

Both Legacy and Elite write blocks 6-18 (application zone).

**Key constants**:
```python
'2020666666668888'     — Default iCLASS password (ICLASS_L default key)
'AFA785A7DAB33378'     — Standard key for Legacy
'6666202066668888'     — Alternative key
'000000000000E014'     — Config block data
'0000000000000000'     — Empty block data
```

### 6.3 Imports

```python
import executor
import hficlass      # iCLASS scan/auth helpers
import tagtypes      # ICLASS_LEGACY, ICLASS_ELITE
```

### 6.4 PM3 Commands

| Command | Purpose |
|---------|---------|
| `hf iclass wrbl -b {block} -d {data} -k {key}` | Write single block |
| `hf iclass calcnewkey o {oldkey} n {newkey}` | Calculate diversified key for password change |
| `hf iclass rdbl b {block} k {key}` | Read block for verification |

### 6.5 Write Flow

1. Determine iCLASS type: ICLASS_LEGACY (17) or ICLASS_ELITE (18)
2. `getNeedWriteBlock(typ)` — get list of blocks to write (6-18)
3. `writePassword()` — change access password from default to target key:
   a. `hf iclass calcnewkey o {oldkey} n {newkey}` — compute XOR diversified key
   b. Check response for `Xor div key` with regex `getContentFromRegexG`
   c. Write computed key to password block
4. `writeDataBlocks()` — write blocks 6-18 from dump file/dict:
   a. For each block: `hf iclass wrbl -b {block} -d {data} -k {key}`
   b. Check response for `successful`
   c. On failure: `Writing failed`, `failed tag select`
5. Return 1 (success) or -1 (failure)

### 6.6 Verify Flow

1. For each block in write block list:
   a. `readTagBlock()` — read block from card
   b. `verify_block()` — compare against expected data
2. Return 1 if all blocks match, -1 otherwise

### 6.7 hasKeyword/getContentFromRegexG Checks

```python
hasKeyword("successful")           — Block write success
hasKeyword("Writing failed")       — Block write failure
hasKeyword("failed tag select")    — Card not present
getContentFromRegexG(r"Xor div key\s*:\s*([0-9A-Fa-f ]+)")  — Key calc result
```

---

## 7. Module: lfverify.so — LF Verification

### 7.1 Exported Functions

```
verify(typ, uid_par, raw_par)
verify_em4x05(file)
verify_t55xx(file)
```

### 7.2 Imports

```python
import lfem4x05     # EM4x05 operations
import lfread       # LF read operations
import lft55xx      # T55xx operations
import os
import platform
import scan         # Re-scan for verification
import tagtypes     # Type classification
```

### 7.3 Verify Flow

1. Re-scan the tag via `scan`
2. Compare UID/raw data against expected values
3. For dump types (23, 24):
   - T55xx: `verify_t55xx(file)` — read back blocks, compare to file
   - EM4x05: `verify_em4x05(file)` — read back blocks, compare to file

---

## 8. Activity Integration (WriteActivity + WarningWriteActivity)

### 8.1 Flow: Read → WarningWrite → Write

```
ReadActivity finishes with bundle (dump path or data dict)
  → actstack.start_activity(WarningWriteActivity, bundle)

WarningWriteActivity shows "Data ready!" confirmation
  M1/PWR → cancel (finish)
  M2/OK  → finish with result {'action': 'write', 'read_bundle': bundle}
    → parent's onActivity() calls actstack.start_activity(WriteActivity, bundle)

WriteActivity:
  onCreate:
    - Title: "Write Tag"
    - M1: "Write", M2: "Verify"
    - Create ProgressBar, Toast widgets
    - infos = scan.getScanCache()
    - _read_bundle = bundle

  IDLE state:
    M1/OK → startWrite()
    M2    → startVerify()
    PWR   → finish()

  startWrite():
    1. setBtnEnable(False)
    2. playWriting() — show "Writing..." with progress bar
    3. write.write(self.on_write, self.infos, self._read_bundle)
    4. write.so spawns thread, calls on_write with result

  on_write(data):
    - Progress: {'max': N, 'progress': M} → update progress bar
    - Completion: {'success': True/False} → _onWriteComplete()

  _onWriteComplete(result):
    1. Hide progress bar
    2. Show success/fail toast
    3. setBtnEnable(True)
    4. Swap buttons: M1="Verify", M2="Rewrite"

  After completion:
    M1/OK → startVerify()
    M2    → startWrite() (rewrite)
    PWR   → finish()
```

### 8.2 Bundle Format by Tag Type

| Tag Type | bundle Format | Source |
|----------|--------------|--------|
| MFC (1,0,25,26,...) | `str` — file path to .bin dump | ReadActivity reads and saves dump |
| LF clone (8-16,...) | `dict` — `{'data': {...}, 'raw': '...'}` | Scan data |
| LF dump (23,24) | `str` — file path to dump | ReadActivity saves dump |
| Ultralight (2-7) | `str` — file path to .bin dump | ReadActivity saves dump |
| iCLASS (17,18,47) | `dict` — `{'file': path, 'key': key, 'type': typ}` | ReadActivity/iclassread |
| ISO15693 (19,46) | `str` or `dict` with `'file'` key | ReadActivity saves dump |

---

## 9. Modules to Implement (Middleware)

### 9.1 Implementation Order

1. **write.py** — Dispatcher (depends on all sub-modules)
2. **hfmfwrite.py** — MIFARE Classic writer (DRM gated — use real .so)
3. **lfwrite.py** — LF writer
4. **lfverify.py** — LF verifier
5. **hf15write.py** — ISO 15693 writer
6. **hfmfuwrite.py** — MIFARE Ultralight writer
7. **iclasswrite.py** — iCLASS writer

### 9.2 Strategy

**For hfmfwrite.so**: Use the REAL binary .so module under QEMU. The DRM check
passes natively with the correct cpuinfo serial. Do NOT transliterate the DRM
logic — use the real module.

**For all other write modules**: These have no DRM checks. Transliterate from
binary strings + module audit + test fixtures.

**For write.so**: The dispatcher is simple enough to transliterate directly.
It imports sub-modules dynamically and dispatches based on `infos['type']`.

### 9.3 Existing Middleware Dependencies

These middleware modules already exist and are dependencies:

| Module | Path | Used By |
|--------|------|---------|
| `executor` | `src/middleware/executor.py` | All write modules |
| `scan` | `src/middleware/scan.py` | write.so, hf15write, hfmfuwrite |
| `lft55xx` | `src/middleware/lft55xx.py` | lfwrite |
| `lfem4x05` | `src/middleware/lfem4x05.py` | lfverify |
| `lfread` | `src/middleware/lfread.py` | lfverify |
| `hficlass` | `src/middleware/hficlass.py` | iclasswrite |
| `hf14ainfo` | `src/middleware/hf14ainfo.py` | scan_14a path |
| `hfsearch` | `src/middleware/hfsearch.py` | scan_hfsea path |
| `template` | `src/middleware/template.py` | Not used by write |

### 9.4 NOT Yet Implemented (Needed)

| Module | Needed By | Priority |
|--------|-----------|----------|
| `hfmfkeys` | hfmfwrite (key management) | HIGH — but use real .so |
| `hfmfread` | hfmfwrite (block reading for verify) | HIGH — but use real .so |
| `mifare` | hfmfwrite (constants) | MEDIUM — constants only |
| `lfverify` | write.so verify dispatch | MEDIUM |
| `tagtypes` | write.so, lfwrite, hfmfuwrite | Use real .so |

---

## 10. Test Coverage Summary

63 test scenarios in `tests/flows/write/scenarios/`:

| Category | Count | Scenarios |
|----------|-------|-----------|
| MFC standard | 8 | 1k success/fail/partial/verify_fail, 4k success/fail, mini, plus_2k, 7b variants |
| MFC Gen1a | 3 | success, fail, uid_only |
| LF clone | 18 | em410x, hid, awid, indala, io, fdxb, keri, securakey, nexwatch, jablotron, gallagher, viking, paradox, pac, presco, pyramid, visa2000, noralsy |
| LF fail/verify | 2 | fail, em410x_verify_fail |
| T55xx | 5 | restore success/fail, block success/fail, password_write |
| EM4305 | 2 | dump success/fail |
| Ultralight | 6 | success, fail, verify_fail, cant_select, ev1, c |
| NTAG | 3 | 213, 215, 216 |
| ISO15693 | 4 | success, st_success, uid_fail, restore_fail, verify_fail |
| iCLASS | 5 | legacy success/fail, elite success, tag_select_fail, key_calc variants |

---

## 11. Key Implementation Notes

### 11.1 Return Code Convention

All write sub-modules return:
- `1` — success (maps to `callReadSuccess`)
- `-1` — failure (maps to `callReadFailed`)
- `-10` — critical failure

`write.so`'s `call_on_finish()` checks `ret == 1` for success, everything else is failure.

### 11.2 Progress Reporting

write.so does NOT report progress directly. The sub-modules (hfmfwrite) call
the listener with progress dicts:
```python
listener({'max': 64, 'progress': N})   # N increments per block
```

This is delivered via the `on_write` callback to WriteActivity, which updates
the progress bar.

### 11.3 Threading

write.so wraps the dispatch in `run_action(run, run_on_subthread)`. When
`run_on_subthread=True` (default), the write runs in a daemon thread. The
callback (listener) is called from that thread. WriteActivity uses
`canvas.after(0, lambda: ...)` to marshal UI updates to the main thread.

### 11.4 hfmfwrite.so Block Write Order

From real device trace, blocks are written in REVERSE sector order:
- Sector 15 (blocks 60,61,62,63) → Sector 14 → ... → Sector 0 (blocks 0,1,2,3)
- Within each sector: data blocks first, trailer block last
- Block 0 (with UID) is written as part of sector 0's data blocks
- Trailer block format: `{keyA}{access_bits}{keyB}` = `FFFFFFFFFFFFFF078069FFFFFFFFFFFF`

### 11.5 hfmfwrite.so Gen1a vs Standard Detection

```
hf mf cgetblk 0
  → success (Block 0 data returned)  → gen1a = True  → use cload
  → "wupC1 error" / "Can't read block" → gen1a = False → use wrbl per block
```

### 11.6 lfwrite.so T55xx Password Handling

Before cloning, lfwrite checks if T55xx has a password set:
1. `lf t55xx detect` — check config
2. If `Password Set: Yes`: `lf t55xx wipe p {password}` with known password
3. After wipe: `lf t55xx detect` again to verify clean state
4. Then proceed with clone command

Default T55xx password: `20206666` (from lft55xx constants).
