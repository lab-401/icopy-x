# Read Pipeline Transliteration Spec

## Ground Truth Sources

| Source | Path | Status |
|--------|------|--------|
| Decompiled binary | `decompiled/read_ghidra_raw.txt` | Primary — class hierarchy, exports, method names |
| Binary strings | `docs/v1090_strings/read_strings.txt` | Primary — all string literals |
| Module audit | `docs/V1090_MODULE_AUDIT.txt` | Primary — function signatures, constants, imports |
| Real device trace (MFC) | `docs/Real_Hardware_Intel/trace_read_flow_20260401.txt` | Primary — 2 complete MF1K reads |
| Real device trace (iCLASS) | `docs/Real_Hardware_Intel/trace_iclass_elite_read_20260401.txt` | Primary — iCLASS Elite read |
| Archive transliteration | `archive/lib_transliterated/read.py` | STRUCTURAL REFERENCE ONLY |
| UI layer | `src/lib/activity_read.py` | For understanding call conventions |

---

## 1. Module: read.so — The Orchestrator

### 1.1 Exported Symbols (from Ghidra)

```
PyInit_read           @ 0x00017cf0    -- Module init
__pyx_module_is_main_read @ 0x0003f098
```

### 1.2 Class Hierarchy

```
AbsReader (base)
  ├── MifareClassicReader      (types 0,1,25,26,41,42,43,44)
  ├── MifareUltralightReader   (types 2,3,4,5,6,7)
  ├── LF125KHZReader           (types 8-16,23,24,28-37,45)
  ├── HIDIClassReader          (types 17,18,47)
  ├── LegicMim256Reader        (type 20)
  ├── ISO15693Reader           (types 19,46)
  ├── ISO1443AReader           (type 40)
  └── FelicaReader             (type 21)

Reader (orchestrator)
  -- dispatches to the correct AbsReader subclass
```

### 1.3 AbsReader — Base Class

**Constructor**: `AbsReader(tag_type, tag_data)`
- `tag_type` — integer tag type ID
- `tag_data` — dict with scan results (uid, sak, atqa, etc.)

**Methods**:

| Method | Signature | Description |
|--------|-----------|-------------|
| `isSupport()` | `() -> bool` | Return True if this reader supports the configured tag_type. Must be overridden. |
| `start(listener)` | `(callable) -> None` | Start reading. Calls `listener` with result dict. Must be overridden. |
| `stop()` | `() -> None` | Request stop. Base implementation is no-op. |
| `callReadFailed(listener, infos, ret)` | `@staticmethod` | Calls `listener({'success': False, 'tag_info': infos, 'return': ret})` |
| `callReadSuccess(listener, infos, bundle, is_force=False)` | `@staticmethod` | Calls `listener({'success': True, 'tag_info': infos, 'force': is_force, 'bundle': bundle})` |
| `call_on_finish(ret, listener, infos, bundle)` | `@staticmethod` | If `ret == 1`: `callReadSuccess(...)`, else `callReadFailed(...)` |

**Result dict shapes (returned via listener)**:

Success:
```python
{
    'success': True,
    'tag_info': {<scan_cache>},
    'force': False,       # True when force-read with partial keys
    'bundle': {<read_data>},
}
```

Failure:
```python
{
    'success': False,
    'tag_info': {<scan_cache>},
    'return': -1,          # or other error code
}
```

### 1.4 Reader — Orchestrator

**Constructor**: `Reader()` — no arguments

**Class attribute**:
```python
default_reader = [
    MifareClassicReader,
    MifareUltralightReader,
    LF125KHZReader,
    HIDIClassReader,
    LegicMim256Reader,
    ISO15693Reader,
    ISO1443AReader,
    FelicaReader,
]
```

**Properties**:
| Property | Type | Description |
|----------|------|-------------|
| `call_reading` | `callable` or `None` | Progress/result callback — set by activity |
| `call_exception` | `callable` or `None` | Exception callback — receives traceback string |

**Methods**:

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__()` | `() -> None` | Init `_call_reading=None`, `_call_exception=None`, `_reader=None`, `_reading=False`, `_stop_label=False` |
| `is_reader_class(name)` | `@staticmethod (class) -> bool` | True if `name` is subclass of AbsReader |
| `find_reader(tag_type, tag_data)` | `(int, dict) -> AbsReader or None` | Iterate `default_reader`, return first whose `isSupport()` returns True |
| `find_readers()` | `() -> list` | Return `default_reader` |
| `is_reading()` | `() -> bool` | Return `_reading` |
| `start(tag_type, tag_data)` | `(int, dict) -> None` | Find reader, spawn thread calling `reader.start(self._call_reading)` |
| `stop()` | `() -> None` | Set `_stop_label=True`, call `reader.stop()` |
| `_call_exception_method()` | `() -> None` | Call `self._call_exception(traceback.format_exc())` |

**start() threading model** (from binary string `read.Reader.start.run`):
```python
def start(self, tag_type, tag_data):
    reader = self.find_reader(tag_type, tag_data)
    if reader is None:
        return
    self._reader = reader
    self._reading = True
    self._stop_label = False

    def _run():
        try:
            reader.start(self._call_reading)
        except Exception:
            self._call_exception_method()
        finally:
            self._reading = False

    t = threading.Thread(target=_run, daemon=True)
    t.start()
```

### 1.5 Protocol Dispatch — How Reader Routes

The `start(tag_type, tag_data)` method:
1. Calls `find_reader(tag_type, tag_data)` which iterates `default_reader`
2. For each reader class, instantiates `cls(tag_type, tag_data)` and checks `isSupport()`
3. The first match is used
4. `reader.start(self._call_reading)` is called in a background thread

**Tag type → Reader class mapping** (from `isSupport()` methods, decompiled):

| Tag Type IDs | Reader Class | Protocol Module(s) |
|-------------|--------------|---------------------|
| 0, 1, 25, 26, 41, 42, 43, 44 | MifareClassicReader | hfmfkeys, hfmfread |
| 2, 3, 4, 5, 6, 7 | MifareUltralightReader | hfmfuread |
| 8-16, 23, 24, 28-37, 45 | LF125KHZReader | lfread, lft55xx, lfem4x05 |
| 17, 18, 47 | HIDIClassReader | iclassread, hficlass |
| 20 | LegicMim256Reader | legicread |
| 19, 46 | ISO15693Reader | hf15read |
| 40 | ISO1443AReader | hf14aread |
| 21 | FelicaReader | felicaread |

### 1.6 How ReadActivity Connects to read.so

From `activity_read.py` `_startRead()` (lines 390-474):

```python
import read as _read_mod
self._reader = _read_mod.Reader()
self._reader.call_reading = self.onReading   # bound method
self._reader.call_exception = self._onReadException
self._reader.start(self._tag_type, bundle)
```

Where `bundle = {'infos': scan_cache, 'force': force}`.

**CRITICAL**: The `tag_data` parameter passed to `Reader.start()` contains:
- `'infos'`: The scan cache dict (uid, sak, atqa, type, etc.)
- `'force'`: Boolean for force-read with partial keys

### 1.7 Progress/Callback Pattern

**MFC reads**: `callListener(sector, total_sectors, callback)` fires repeatedly.
From trace: `HFMFREAD.callListener((0, 16, <bound method onReading>))` through `(15, 16, ...)`.
Progress value: `80 + int((sector + 1) / sectorMax * 20)` — range [81..100].

**All readers**: Final result comes via the `listener` callback with the success/failure dict.

### 1.8 Imports (from module audit)

```
appfiles, executor, felicaread, hf14aread, hf15read, hfmfkeys, hfmfread,
hfmfuread, importlib, inspect, legicread, lfem4x05, lfread, lft55xx, os,
platform, tagtypes, threading, traceback
```

### 1.9 Constants from Binary Strings

| String | Context |
|--------|---------|
| `readIfIsGen1a` | MFC Gen1a check function |
| `readAllSector` | MFC sector reader function |
| `sizeGuess` | MFC size from type |
| `FILE_MFU_READ` | Ultralight file constant (None) |
| `FILE_READ` | Various read file constants (None) |
| `KEY_READ` | iCLASS read key constant |
| `DUMP_TEMP` | EM4x05 temp dump path |
| `CREATE_NORMAL_ID` | Tag type creation constant |
| `stopPM3Task` | PM3 task termination |
| `HF14A_OTHER` | Tag type 40 name |
| `FELICA` | Tag type 21 name |
| `LEGIC_MIM256` | Tag type 20 name |

---

## 2. Protocol Module: hfmfread — MIFARE Classic Reading

### 2.1 Exports (from module audit + binary strings)

**Constants**:
| Name | Value | Description |
|------|-------|-------------|
| `A` | `'A'` | Key type A |
| `B` | `'B'` | Key type B |
| `DATA_MAP` | `{}` | Cached read data |
| `FILE_READ` | `None` | Cached file path |

**Functions** (23 total):

| Function | Signature | Description |
|----------|-----------|-------------|
| `cacheFile(file)` | `(str) -> None` | Cache file path in `FILE_READ` global |
| `callListener(sector, sectorMax, listener)` | `(int, int, callable) -> None` | Progress callback: `80 + int((sector+1)/sectorMax * 20)` |
| `createEmptyBlock(block, infos)` | `(int, dict) -> str` | Create empty block hex (32 chars) |
| `createManufacturerBlock(infos)` | `(dict) -> str` | Create block 0 from UID/SAK/ATQA |
| `createTempDatas(size, infos)` | `(int, dict) -> list` | Create full empty card dump |
| `createTempSector(sector, infos)` | `(int, dict) -> list` | Create empty sector blocks |
| `create_name_by_type(infos)` | `(dict) -> str` | Filename from type+UID (e.g., `'1K-4B_AA991523'`) |
| `endian(atqa)` | `(str) -> str` | Swap 2-byte hex endian |
| `fillKeys2DataMap()` | `() -> None` | Copy hfmfkeys.KEYS_MAP to DATA_MAP |
| `getContentFromRegexA(regex)` | `(str) -> list` | `re.findall` on executor cache |
| `getContentFromRegexG(regex, group)` | `(str, int) -> str` | `re.search` group on executor cache |
| `hasKeyword(keywords, line=None)` | `(str, str?) -> bool` | Substring check in executor cache |
| `parseAllKeyFromDataFile(infos, file)` | `(dict, str) -> None` | Parse binary key file into KEYS_MAP |
| `readAllSector(size, infos, listener)` | `(int, dict, callable) -> list` | Read all sectors with available keys |
| `readBlock(block, typ, key)` | `(int, str, str) -> str/-2/None` | Read single block via `hf mf rdbl` |
| `readBlocks(sector, keyA, keyB, infos)` | `(int, str, str, dict) -> list/None` | Read sector trying A then B keys |
| `readIfIsGen1a(infos)` | `(dict) -> True/None` | Check/read Gen1a via `hf mf csave` |
| `readSector(sector, typ, key)` | `(int, str, str) -> list/-2/None` | Read sector via `hf mf rdsc` |
| `save_bin(infos, data_list)` | `(dict, list) -> str/None` | Save to .bin file |
| `save_eml(infos, data_list)` | `(dict, list) -> str/None` | Save to .eml file |
| `sizeGuess(typ)` | `(int) -> int` | Tag type to byte size |
| `startPM3Task(cmd, timeout, listener=None, rework_max=2)` | — | Wrapper around `executor.startPM3Task` |
| `xor(datahex)` | `(str) -> str` | XOR all bytes of hex string |

### 2.2 PM3 Command Sequences (from trace)

**Full MFC 1K read flow**:
```
1. hf 14a info (timeout=5000)
   → parse UID, ATQA, SAK, detect type
2. hf mf cgetblk 0 (timeout=5888)
   → test Gen1a: if "[+] Block 0:" → Gen1a path
   → if "wupC1 error" → not Gen1a, proceed to key recovery
3. hf mf fchk 1 /tmp/.keys/mf_tmp_keys (timeout=600000)
   → fast key check, returns found keys table
4. (if not all keys found): darkside/nested/hardnested
5. hf mf rdsc {sector} {keytype} {key} (per sector)
   → callListener(sector, 16, listener) after each
6. cacheFile('/mnt/upan/dump/mf1/M1-1K-4B_{uid}_{n}.eml')
7. cacheFile('/mnt/upan/dump/mf1/M1-1K-4B_{uid}_{n}.bin')
```

**Gen1a path** (from fixture `read_mf1k_gen1a_csave_success`):
```
1. hf 14a info → detect Gen1a (Magic capabilities : Gen 1a)
2. hf mf cgetblk 0 → success (block 0 data returned)
3. hf mf csave 1 o /tmp/dump.bin → save all 64 blocks via backdoor
```

### 2.3 sizeGuess Mapping

| Type ID | Size (bytes) | Name |
|---------|-------------|------|
| 0, 41 | 4096 | 4K |
| 1, 42, 43, 44 | 1024 | 1K |
| 26 | 2048 | 2K |
| 25 | 320 | Mini |
| all others | 320 | Mini (default) |

### 2.4 MFC Read — MifareClassicReader.start() Flow

From decompiled binary and trace:

```
1. Import hfmfkeys, hfmfread
2. Extract tag_type and tag_data from constructor args
3. Call hfmfkeys.fchks(infos, size) — fast key check
   - Returns 1 on success
   - timeout: 600000ms
4. If not all keys found → darkside / nested / hardnested recovery
5. Call hfmfread.readAllSector(size, infos, listener)
   - Reads each sector with recovered keys
   - Calls callListener(sector, sectorMax, listener) per sector
   - Returns data_list (list of 32-char hex strings)
6. Call hfmfread.cacheFile() twice (eml + bin)
7. readAllSector returns 1 on completion
8. AbsReader.call_on_finish(ret, listener, infos, bundle)
```

### 2.5 Key Recovery Pipeline (hfmfkeys)

From module audit, the key recovery functions in order:

| Function | PM3 Command | Timeout | Description |
|----------|-------------|---------|-------------|
| `fchks(infos, size, with_call=True)` | `hf mf fchk {size_type} /tmp/.keys/mf_tmp_keys` | 600000ms | Fast dictionary check |
| `keysFromPrintParse(size)` | — | — | Parse found keys from PM3 output |
| `darkside()` | `hf mf darkside` | — | Darkside attack (weak PRNG only) |
| `nested(size, infos)` | `hf mf nested` | — | Nested authentication attack |
| `nestedAllKeys(infos, size)` | `hf mf nested` | — | Nested for all missing keys |

Recovery constants:
- `RECOVERY_FCHK = 'ChkDIC'`
- `RECOVERY_DARK = 'Darkside'`
- `RECOVERY_NEST = 'Nested'`
- `RECOVERY_STNE = 'STnested'`
- `TIME_DARKSIDE_ONE = 60` (seconds)
- `TIME_NESTED_ONE = 11` (seconds)
- `TIME_FHCK_ONE = 0.01` (seconds)
- `keyInTagMax = 32` (16 sectors × 2 keys for 1K)

---

## 3. Protocol Module: hfmfuread — Ultralight/NTAG Reading

### 3.1 Exports

**Constants**:
| Name | Value |
|------|-------|
| `FILE_MFU_READ` | `None` |

**Functions**:
| Function | Signature | Description |
|----------|-----------|-------------|
| `createFileNamePreByType(typ)` | `(int) -> str` | Type ID to filename prefix |
| `read(infos)` | `(dict) -> dict` | Dump UL/NTAG tag |

### 3.2 Filename Prefixes

| Type ID | Prefix |
|---------|--------|
| 2 | `'M0-UL'` |
| 3 | `'M0-UL-C'` |
| 4 | `'M0-UL-EV1'` |
| 5 | `'NTAG213'` |
| 6 | `'NTAG215'` |
| 7 | `'NTAG216'` |
| other | `'Unknow'` |

### 3.3 PM3 Command

```
hf mfu dump f {file_path}    (timeout=30000)
```

### 3.4 Return Dict

```python
# Success
{'return': 0, 'file': '/mnt/upan/dump/mfu/M0-UL_04A1B2C3D4E5F6_1.bin'}
# Failure
{'return': -1, 'file': ''}
```

### 3.5 Partial Dump Detection

Checks `executor.hasKeyword('Partial dump created')` — returns success with file path even for partial dumps.

---

## 4. Protocol Module: lfread — LF 125kHz Reading

### 4.1 Exports

**Constants**:
| Name | Value |
|------|-------|
| `READ` | `{8: readEM410X, 9: readHID, ...}` — 22 entries |
| `TIMEOUT` | `10000` |

**Functions** (26 total):

Core helpers:
| Function | Signature | Description |
|----------|-----------|-------------|
| `createRetObj(uid, raw, ret)` | `(str, str, int) -> dict` | `{'return': ret, 'data': uid, 'raw': raw}` |
| `read(cmd, uid_regex, raw_regex, uid_index=0, raw_index=0)` | `(...) -> dict` | Execute PM3 cmd, parse uid/raw with regex |
| `readCardIdAndRaw(cmd, uid_index=0, raw_index=0)` | `(...) -> dict` | Uses `REGEX_CARD_ID` and `REGEX_RAW` |
| `readFCCNAndRaw(cmd, uid_index=0, raw_index=0)` | `(...) -> dict` | Uses `lfsearch.getFCCN()` for uid |

Per-card-type (all signature: `(listener=None, infos=None) -> dict`):

| Function | PM3 Command | Parse Method |
|----------|-------------|--------------|
| `readEM410X` | `lf em 410x_read` | `REGEX_EM410X` (uid), `REGEX_RAW` (raw) |
| `readHID` | `lf hid read` | `REGEX_HID` (uid), `REGEX_RAW` (raw) |
| `readIndala` | `lf indala read` | `REGEX_RAW` for both uid and raw |
| `readAWID` | `lf awid read` | FCCN parsing |
| `readProxIO` | `lf io read` | `REGEX_CARD_ID` |
| `readGProx2` | `lf gproxii read` | FCCN parsing |
| `readSecurakey` | `lf securakey read` | FCCN parsing |
| `readViking` | `lf viking read` | `REGEX_CARD_ID` |
| `readPyramid` | `lf pyramid read` | FCCN parsing |
| `readT55XX` | (delegates to `lft55xx.chkAndDumpT55xx`) | — |
| `readEM4X05` | (delegates to `lfem4x05.dump4X05`) | — |
| `readFDX` | `lf fdx read` | `REGEX_ANIMAL` (uid), `REGEX_RAW` (raw) |
| `readGALLAGHER` | `lf gallagher read` | FCCN parsing |
| `readJablotron` | `lf jablotron read` | `REGEX_CARD_ID` |
| `readKeri` | `lf keri read` | FCCN parsing |
| `readNedap` | `lf nedap read` | `REGEX_CARD_ID` |
| `readNoralsy` | `lf noralsy read` | `REGEX_CARD_ID` |
| `readPAC` | `lf pac read` | `REGEX_CARD_ID` |
| `readParadox` | `lf paradox read` | FCCN parsing |
| `readPresco` | `lf presco read` | `REGEX_CARD_ID` |
| `readVisa2000` | `lf visa2000 read` | `REGEX_CARD_ID` |
| `readNexWatch` | `lf nexwatch read` | `REGEX_CARD_ID` |

### 4.2 READ Dispatch Map

```python
READ = {
    8:  readEM410X,      # EM410X_ID
    9:  readHID,         # HID_PROX_ID
    10: readIndala,      # INDALA_ID
    11: readAWID,        # AWID_ID
    12: readProxIO,      # IO_PROX_ID
    13: readGProx2,      # GPROX_II_ID
    14: readSecurakey,   # SECURAKEY_ID
    15: readViking,      # VIKING_ID
    16: readPyramid,     # PYRAMID_ID
    23: readT55XX,       # T55X7_ID
    24: readEM4X05,      # EM4305_ID
    28: readFDX,         # FDXB_ID
    29: readGALLAGHER,   # GALLAGHER_ID
    30: readJablotron,   # JABLOTRON_ID
    31: readKeri,        # KERI_ID
    32: readNedap,       # NEDAP_ID
    33: readNoralsy,     # NORALSY_ID
    34: readPAC,         # PAC_ID
    35: readParadox,     # PARADOX_ID
    36: readPresco,      # PRESCO_ID
    37: readVisa2000,    # VISA2000_ID
    45: readNexWatch,    # NEXWATCH_ID
}
```

### 4.3 Return Dict Shape

```python
# Success
{'return': 0, 'data': '0F0368568B', 'raw': 'FF00AA5500...'}
# Failure
{'return': -1, 'data': None, 'raw': None}
```

### 4.4 LF Read — LF125KHZReader.start() Flow

```
1. Import lfread
2. Look up tag_type in lfread.READ dispatch map
3. Call the matching readXXX(listener, infos) function
4. Most functions:
   a. executor.startPM3Task(cmd, 10000)
   b. Parse uid/raw from executor cache via regex
   c. Return createRetObj(uid, raw, ret)
5. Special cases:
   - T55XX: delegates to lft55xx.chkAndDumpT55xx(listener)
   - EM4X05: delegates to lfem4x05.dump4X05(infos)
6. AbsReader.call_on_finish(ret, listener, tag_data, result_dict)
```

### 4.5 T55XX Read Flow (from fixture)

```
1. lf t55xx detect (timeout=5000)
   → Parse: Chip Type, Modulation, Block0, Password Set
2. lf t55xx dump (timeout=?)
   → Save blocks to file
```

### 4.6 EM4305 Read Flow (from fixture)

```
1. lf em 4x05_info [key] (timeout=5000)
   → Parse: Chip Type, ConfigWord, Serial
2. lf em 4x05_dump [key] (timeout=5000)
   → Save to binary file
```

---

## 5. Protocol Module: iclassread — iCLASS Reading

### 5.1 Exports

**Constants**:
| Name | Value |
|------|-------|
| `FILE_READ` | `None` |
| `KEY_READ` | `None` |

**Functions**:
| Function | Signature | Description |
|----------|-----------|-------------|
| `read(infos)` | `(dict) -> dict` | Try Legacy then Elite |
| `readFromKey(infos, key, typ)` | `(dict, str, str) -> dict` | Dump with specific key |
| `readLegacy(infos)` | `(dict) -> dict` | Read using Legacy key |
| `readElite(infos)` | `(dict) -> dict` | Read using Elite key |

**Imports**: `appfiles, executor, hficlass, tagtypes`

### 5.2 PM3 Command Sequences (from iCLASS trace)

```
1. hf iclass rdbl b 01 k AFA785A7DAB33378 (timeout=8888)
   → Try standard key (fails: empty response)
2. hf iclass rdbl b 01 k 2020666666668888 (timeout=8888)
   → Try legacy key (fails: empty response)
3. hf iclass rdbl b 01 k 6666202066668888 (timeout=8888)
   → Try another legacy key (fails)
4. hf iclass rdbl b 01 k 2020666666668888 e (timeout=8888)
   → Elite key with 'e' flag: SUCCESS
   → "[+] Using elite algo\n\n[+]  block 01 : 12 FF FF FF..."
5. hf iclass info (timeout=8888)
   → CSN, Config, E-purse, keys
6. hf iclass dump k 2020666666668888 f {path} e (timeout=8888)
   → Full dump with elite flag
   → "saving dump file - 19 blocks read"
```

### 5.3 Return Dict

```python
# Success
{'return': 0, 'file': '/mnt/upan/dump/iclass/Iclass-Elite_{csn}_1.bin', 'key': '2020666666668888', 'typ': 'Elite'}
# Failure
{'return': -1, 'file': '', 'key': '', 'typ': ''}
```

### 5.4 Key Detection Keywords

- `_KW_DUMP_SUCCESS = 'saving dump file - 19 blocks read'`
- `'Using elite algo'` — indicates elite key was used

---

## 6. Protocol Module: hf15read — ISO 15693 Reading

### 6.1 Exports

**Constants**:
| Name | Value |
|------|-------|
| `CMD` | `'hf 15 dump'` |
| `FILE_READ` | `None` |
| `TIMEOUT` | `38000` |

**Functions**:
| Function | Signature | Description |
|----------|-----------|-------------|
| `read(infos)` | `(dict) -> dict` | Dump ISO15693 tag |

### 6.2 PM3 Command

```
hf 15 dump    (timeout=38000)
```

### 6.3 Return Dict

```python
# Success
{'return': 0, 'file': '/mnt/upan/dump/icode/ISO15693_{uid}_1.bin'}
# Failure
{'return': -1, 'file': ''}
```

---

## 7. Protocol Module: legicread — LEGIC Reading

### 7.1 Exports

**Constants**:
| Name | Value |
|------|-------|
| `CMD` | `'hf legic dump'` |
| `TIMEOUT` | `5000` |

**Functions**:
| Function | Signature | Description |
|----------|-----------|-------------|
| `read(infos)` | `(dict) -> dict` | Dump LEGIC Prime tag |

### 7.2 PM3 Command

```
hf legic dump    (timeout=5000)
```

### 7.3 Return Dict

```python
# Success
{'return': 0, 'file': '/mnt/upan/dump/legic/Legic_{mcd}{msn}_1.bin'}
# Failure
{'return': -1, 'file': ''}
```

---

## 8. Protocol Module: felicaread — FeliCa Reading

### 8.1 Exports

**Constants**:
| Name | Value |
|------|-------|
| `CMD` | `'hf felica litedump'` |
| `TIMEOUT` | `5000` |

**Functions**:
| Function | Signature | Description |
|----------|-----------|-------------|
| `read(infos)` | `(dict) -> dict` | Dump FeliCa Lite tag |

### 8.2 PM3 Command

```
hf felica litedump    (timeout=5000)
```

### 8.3 Return Dict

```python
# Success
{'return': 0, 'file': '/mnt/upan/dump/felica/FeliCa_{idm}_1.bin'}
# Failure
{'return': -1, 'file': ''}
```

---

## 9. Protocol Module: hf14aread — Generic ISO 14443A Reading

### 9.1 Exports

**Constants**:
| Name | Value |
|------|-------|
| `FILE_READ` | `None` |

**Functions**:
| Function | Signature | Description |
|----------|-----------|-------------|
| `read(infos)` | `(dict) -> dict` | Save tag info to text file |

### 9.2 Behavior

Unlike other read modules, hf14aread does NOT send a PM3 dump command.
It saves the infos dict content (uid, sak, atqa, etc.) to a `.txt` file
via `appfiles.save2any()`. This is for generic/unknown 14443A tags that
don't have a standard dump protocol.

### 9.3 Return Dict

```python
# Success
{'return': 0, 'file': '/mnt/upan/dump/hf14a/HF14A_{uid}_1.txt'}
# Failure
{'return': -1, 'file': ''}
```

---

## 10. Protocol Module: lfem4x05 — EM4x05 Operations

### 10.1 Exports

**Constants**:
| Name | Value |
|------|-------|
| `CMD` | `'lf em 4x05_info FFFFFFFF'` |
| `DUMP_TEMP` | `None` |
| `KEY_TEMP` | `None` |
| `TIMEOUT` | `5000` |

**Functions**:
| Function | Signature | Description |
|----------|-----------|-------------|
| `parser()` | `() -> dict` | Parse em 4x05_info output |
| `info4X05(key=None)` | `(str?) -> dict` | Get EM4x05 info |
| `dump4X05(infos, key=None)` | `(dict, str?) -> int` | Dump tag, returns 0 or -1 |
| `read4x05(block, key=None)` | `(int, str?) -> str` | Read single block |
| `readBlocks(key=None)` | `(str?) -> list` | Read all 16 blocks |
| `set_key(key)` | `(str) -> int` | Set password block |
| `verify4x05(data1, data2)` | `(str, str) -> bool` | Verify data match |
| `infoAndDumpEM4x05ByKey(key)` | `(str) -> dict` | Info + dump with key |

### 10.2 Parser Output

```python
# Tag found
{'found': True, 'type': 24, 'chip': 'EM4x05/EM4x69', 'sn': 'AABBCCDD', 'cw': '600150E0'}
# Not found
{'found': False}
```

### 10.3 Internal Regex Patterns

```python
_RE_CHIP   = r'.*Chip Type.*\|(.*)'
_RE_CONFIG = r'.*ConfigWord:(.*)\(.*'
_RE_SERIAL = r'.*Serial.*:(.*)'
```

---

## 11. Regex Patterns Used Across Read Modules

From lfsearch (used by lfread):

| Pattern Name | Regex | Description |
|-------------|-------|-------------|
| `REGEX_EM410X` | `'EM TAG ID\\s+:[\\s]+([xX0-9a-fA-F]+)'` | EM410x ID extraction |
| `REGEX_HID` | `'HID Prox - ([xX0-9a-fA-F]+)'` | HID Prox ID |
| `REGEX_CARD_ID` | `'(?:Card\|ID\|id\|CARD\|UID\|uid\|Uid)\\s*:*\\s*([xX0-9a-fA-F ]+)'` | Generic card ID |
| `REGEX_RAW` | `'.*(?:Raw\|RAW\|hex\|HEX\|Hex)\\s*:*\\s*([xX0-9a-fA-F ]+)'` | Raw data |
| `REGEX_ANIMAL` | `'.*ID\\s+([xX0-9A-Fa-f\\-]{2,})'` | FDX-B animal ID |
| `REGEX_PROX_ID_XSF` | `'(XSF\\(.*?\\).*?:[xX0-9a-fA-F]+)'` | XSF format ProxID |

---

## 12. Complete PM3 Command Reference

### 12.1 HF Commands (for read pipeline)

| Command | Timeout (ms) | Used By |
|---------|-------------|---------|
| `hf 14a info` | 5000 | scan phase (before read) |
| `hf mf cgetblk 0` | 5888 | Gen1a detection |
| `hf mf csave {size} o {path}` | 30000 | Gen1a full dump |
| `hf mf fchk {size_type} {keyfile}` | 600000 | Fast key check |
| `hf mf darkside` | varies | Darkside attack |
| `hf mf nested` | varies | Nested auth attack |
| `hf mf rdbl {block} {type} {key}` | 10000 | Read single block |
| `hf mf rdsc {sector} {type} {key}` | 15000 | Read full sector |
| `hf mfu info` | 8888 | Ultralight type info |
| `hf mfu dump f {path}` | 30000 | Ultralight/NTAG dump |
| `hf 15 dump` | 38000 | ISO15693 dump |
| `hf legic dump` | 5000 | LEGIC dump |
| `hf felica litedump` | 5000 | FeliCa Lite dump |
| `hf iclass rdbl b {block} k {key} [e]` | 8888 | iCLASS read block |
| `hf iclass info` | 8888 | iCLASS tag info |
| `hf iclass dump k {key} [f {path}] [e]` | 30000 | iCLASS full dump |

### 12.2 LF Commands (for read pipeline)

| Command | Timeout (ms) | Used By |
|---------|-------------|---------|
| `lf em 410x_read` | 10000 | EM410x read |
| `lf hid read` | 10000 | HID Prox read |
| `lf indala read` | 10000 | Indala read |
| `lf awid read` | 10000 | AWID read |
| `lf io read` | 10000 | IO Prox read |
| `lf gproxii read` | 10000 | G-Prox II read |
| `lf securakey read` | 10000 | Securakey read |
| `lf viking read` | 10000 | Viking read |
| `lf pyramid read` | 10000 | Pyramid read |
| `lf fdx read` | 10000 | FDX-B read |
| `lf gallagher read` | 10000 | Gallagher read |
| `lf jablotron read` | 10000 | Jablotron read |
| `lf keri read` | 10000 | Keri read |
| `lf nedap read` | 10000 | Nedap read |
| `lf noralsy read` | 10000 | Noralsy read |
| `lf pac read` | 10000 | PAC/Stanley read |
| `lf paradox read` | 10000 | Paradox read |
| `lf presco read` | 10000 | Presco read |
| `lf visa2000 read` | 10000 | Visa2000 read |
| `lf nexwatch read` | 10000 | NexWatch read |
| `lf t55xx detect` | 5000 | T55XX chip detect |
| `lf t55xx dump` | varies | T55XX block dump |
| `lf em 4x05_info [key]` | 5000 | EM4x05 info |
| `lf em 4x05_dump [key]` | 5000 | EM4x05 dump |
| `lf em 4x05_read {block} [key]` | 5000 | EM4x05 read block |

---

## 13. Dependencies Graph

```
read.so
├── threading, traceback, importlib, inspect, os, platform
├── tagtypes (tag type constants)
├── appfiles (file path management)
├── executor (PM3 communication)
├── hfmfkeys (MFC key recovery)
│   ├── executor
│   ├── mifare (block/sector math)
│   ├── commons
│   ├── appfiles
│   └── os, re, threading, time
├── hfmfread (MFC sector reading)
│   ├── executor
│   ├── mifare
│   ├── hfmfkeys
│   ├── commons
│   ├── appfiles
│   └── os, re
├── hfmfuread (Ultralight/NTAG)
│   ├── executor
│   ├── appfiles
│   └── tagtypes
├── lfread (LF 125kHz)
│   ├── executor
│   ├── lfsearch
│   ├── lft55xx
│   ├── lfem4x05
│   ├── appfiles
│   └── tagtypes
├── iclassread (iCLASS)
│   ├── executor
│   ├── hficlass
│   ├── appfiles
│   └── tagtypes
├── legicread (LEGIC)
│   ├── executor
│   └── appfiles
├── hf15read (ISO15693)
│   ├── executor
│   └── appfiles
├── hf14aread (Generic 14443A)
│   ├── executor
│   └── appfiles
├── felicaread (FeliCa)
│   ├── executor
│   └── appfiles
├── lfem4x05 (EM4x05 operations)
│   ├── executor
│   ├── appfiles
│   └── re
└── lft55xx (T55xx operations)
    ├── executor
    └── appfiles
```

---

## 14. Return Codes and Constants

### 14.1 startPM3Task Return Values

| Value | Meaning |
|-------|---------|
| `1` | Completed successfully |
| `-1` | Error (timeout, communication failure) |
| `executor.CODE_PM3_TASK_ERROR` | PM3 task error |

### 14.2 AbsReader.call_on_finish Logic

```python
if ret == 1:
    callReadSuccess(listener, infos, bundle)
else:
    callReadFailed(listener, infos, ret)
```

### 14.3 File Path Patterns

| Protocol | Dump Directory | Filename Pattern |
|----------|---------------|-----------------|
| MFC | `/mnt/upan/dump/mf1/` | `M1-{size}-{uidLen}B_{uid}_{n}.{eml,bin}` |
| Ultralight | `/mnt/upan/dump/mfu/` | `{prefix}_{uid}_{n}.bin` |
| iCLASS | `/mnt/upan/dump/iclass/` | `Iclass-{type}_{csn}_{n}.bin` |
| ISO15693 | `/mnt/upan/dump/icode/` | `ISO15693_{uid}_{n}.bin` |
| LEGIC | `/mnt/upan/dump/legic/` | `Legic_{mcd}{msn}_{n}.bin` |
| FeliCa | `/mnt/upan/dump/felica/` | `FeliCa_{idm}_{n}.bin` |
| HF14A | `/mnt/upan/dump/hf14a/` | `HF14A_{uid}_{n}.txt` |
| LF (general) | via lfread result dict | — |
| T55XX | via lft55xx | — |
| EM4x05 | via lfem4x05 | — |

---

## 15. Test Fixture Coverage

The test suite has **89 scenarios** covering:

### MFC Classic (32 scenarios)
- `read_mf1k_all_default_keys` — all 32 keys FFFFFFFFFFFF
- `read_mf1k_gen1a_csave_success` / `_fail` — Gen1a backdoor path
- `read_mf1k_nested_*` — nested attack variants (retry, abort, timeout, partial, not_vulnerable)
- `read_mf1k_darkside_*` — darkside variants (fail, timeout, card_lost, to_nested)
- `read_mf1k_hardnested_*` — hardnested success/fail
- `read_mf1k_force_*` — force read with partial keys
- `read_mf1k_partial_*` — partial fchk, partial nested, partial read
- `read_mf1k_card_lost_mid_read` — tag removed during sector read
- `read_mf1k_all_sectors_fail` — no sectors readable
- `read_mf1k_no_keys` — no keys found at all
- `read_mf1k_tag_lost` — tag removed during key check
- `read_mf1k_fchk_timeout` — 600s timeout on fchk
- `read_mf1k_read_block_error` — individual block read failure
- `read_mf1k_7b_all_keys` — 7-byte UID MFC 1K
- `read_mf1k_console_*` — console view during/on success/failure/partial
- `read_mf1k_no_console_in_list` — no console in list view
- `read_mf4k_*` — MFC 4K variants (7b, gen1a, darkside_fail, all_keys, partial, no_keys)
- `read_mf_mini_all_keys` — MF Mini (type 25)
- `read_mf_plus_2k_all_keys` — MF Plus 2K (type 26)

### Ultralight/NTAG (9 scenarios)
- `read_ultralight_success` / `_empty` / `_partial` / `_card_select_fail`
- `read_ultralight_c_success` — Ultralight C
- `read_ultralight_ev1_success` — Ultralight EV1
- `read_ntag213_success` / `read_ntag215_success` / `read_ntag216_success`
- `read_ultralight_console_*` — console during/on success

### LF (24 scenarios)
- `read_lf_em410x` — EM410x
- `read_lf_hid` — HID Prox
- `read_lf_indala` / `_awid` / `_io` / `_gprox` / `_securakey` / `_viking` / `_pyramid`
- `read_lf_fdxb` / `_gallagher` / `_jablotron` / `_keri` / `_nedap`
- `read_lf_noralsy` / `_pac` / `_paradox` / `_presco` / `_visa2000` / `_nexwatch`
- `read_lf_t55xx` / `_t55xx_with_password` / `_t55xx_block_read` / `_t55xx_detect_fail`
- `read_lf_em4305_success` / `_block_read` / `_fail`
- `read_lf_fail` — general LF read failure
- `read_em410x_console_during_read` — console during LF read

### iCLASS (4 scenarios)
- `read_iclass_legacy` — legacy key success
- `read_iclass_elite` — elite key success
- `read_iclass_dump_fail` — dump fails
- `read_iclass_no_key` — no key found

### ISO15693 (3 scenarios)
- `read_iso15693` — success
- `read_iso15693_st` — ST SA variant (type 46)
- `read_iso15693_no_tag` / `_timeout`

### LEGIC (3 scenarios)
- `read_legic` — success
- `read_legic_identify_fail` / `_card_select_fail`

### FeliCa (2 scenarios)
- `read_felica_success` / `_fail`

### Edge Cases (3 scenarios)
- `read_no_tag` — no tag present
- `read_wrong_type` — scan finds tag but wrong type

---

## 16. Implementation Notes

### 16.1 Threading Model
- `Reader.start()` spawns a background thread
- The reader's `start(listener)` runs in that thread
- `is_reading()` returns True while thread is running
- `_reading` is set to False in the `finally` block
- Activity polls `is_reading()` to detect completion

### 16.2 Gen1a Detection (MFC)
The Gen1a check happens in the scan phase (`hf mf cgetblk 0`), not in the read phase.
If `cgetblk` returns block data, the tag is Gen1a and can be dumped via `hf mf csave`.

### 16.3 Force Read
When key recovery finds partial keys, the UI shows a warning.
User can choose "force read" which sets `force=True` in the bundle.
The reader then reads only sectors where keys are available.

### 16.4 File Caching
`hfmfread.cacheFile(path)` is called TWICE after a successful MFC read:
once for `.eml` and once for `.bin`. These paths are stored for the write pipeline.

### 16.5 Progress Reporting
- Scan phase: 0-80% (from scan.so)
- Read phase: 80-100% (from hfmfread.callListener formula: `80 + int((sector+1)/sectorMax * 20)`)
- LF/UL/iCLASS/etc: no per-sector progress, completion only

### 16.6 Error Handling
All reader `start()` methods wrap their logic in try/except:
- On exception: `AbsReader.callReadFailed(listener, self.tag_data, -1)`
- The Reader orchestrator also catches exceptions and calls `_call_exception_method()`
