# scan.so Middleware Spec — Scanner Orchestrator

> Ground truth: decompiled `scan.so` (ARM Cython, `scan_ghidra_raw.txt`),
> v1090 strings (`scan_strings.txt`), real device traces
> (`trace_scan_flow_20260331.txt`, `trace_lf_scan_flow_20260331.txt`),
> module audit (`V1090_MODULE_AUDIT.txt`), and 45 test fixtures.
>
> Archive `scan.py` used for STRUCTURAL reference only.

---

## 1. Module Overview

`scan.so` is a Cython-compiled module that orchestrates RFID tag detection.
It delegates to leaf parser modules (`hf14ainfo`, `hfsearch`, `lfsearch`,
`hffelica`, `lft55xx`, `lfem4x05`, `hfmfuinfo`, `hficlass`) and PM3
execution (`executor`).  It provides:

- **Module-level constants** for return codes
- **Module-level state** (scan cache)
- **Module-level functions** for scan operations, cache management, predicates
- **Scanner class** for orchestrated async/sync multi-step scans

### Imports (from binary string table)

```
commons, executor, hf14ainfo, hffelica, hficlass, hfmfuinfo,
hfsearch, lfem4x05, lfread, lfsearch, lft55xx,
platform, tagtypes, threading, traceback
```

---

## 2. Constants

### Return Codes (from binary `__pyx_int_neg_*` and string table)

| Constant              | Value | Meaning                           |
|-----------------------|-------|-----------------------------------|
| `CODE_TIMEOUT`        | -1    | PM3 task timed out                |
| `CODE_TAG_LOST`       | -2    | Tag was lost during scan          |
| `CODE_TAG_MULT`       | -3    | Multiple tags detected            |
| `CODE_TAG_NO`         | -4    | No tag found                      |
| `CODE_TAG_TYPE_WRONG` | -5    | Tag found but wrong type          |
| `CODE_PM3_TASK_ERROR` | ?     | PM3 task error (string exists)    |

### Internal Integer Constants (from `__pyx_int_*`)

| Name              | Value | Usage                                |
|-------------------|-------|--------------------------------------|
| `__pyx_int_0`     | 0     | Progress value for scan_14a          |
| `__pyx_int_1`     | 1     | Progress value for scan_lfsea        |
| `__pyx_int_2`     | 2     | Progress value for scan_hfsea        |
| `__pyx_int_3`     | 3     | Progress value for scan_t55xx        |
| `__pyx_int_4`     | 4     | Progress value for scan_em4x05       |
| `__pyx_int_5`     | 5     | Progress value for scan_felica       |
| `__pyx_int_7`     | 7     | ?                                    |
| `__pyx_int_20`    | 20    | LEGIC_MIM256 type ID                 |
| `__pyx_int_23`    | 23    | T55X7_ID type ID                     |
| `__pyx_int_53`    | 53    | ?                                    |
| `__pyx_int_83`    | 83    | ?                                    |
| `__pyx_int_90`    | 90    | lf_wav_filter amplitude threshold    |
| `__pyx_int_100`   | 100   | Progress complete (100%)             |
| `__pyx_int_neg_1` | -1    | CODE_TIMEOUT                         |
| `__pyx_int_neg_2` | -2    | CODE_TAG_LOST                        |
| `__pyx_int_neg_3` | -3    | CODE_TAG_MULT                        |
| `__pyx_int_neg_4` | -4    | CODE_TAG_NO                          |
| `__pyx_int_neg_5` | -5    | CODE_TAG_TYPE_WRONG                  |

### Module-Level State

```python
INFOS = None              # Cached scan result dict (or None)
INFOS_CACHE_ENABLE = True  # Whether caching is active
```

---

## 3. Result Dict Shape

All scan functions return result dicts with this structure:

```python
{
    'found': bool,        # True if a tag was identified
    'return': int,        # Return code (type ID if found, negative code if not)
    'progress': int,      # Step number (0-5) indicating which scan produced this
    'type': int,          # Tag type ID from tagtypes module

    # HF 14443-A fields (from hf14ainfo.parser()):
    'uid': str,           # UID hex string, e.g. '3AF73501'
    'len': int,           # UID length in bytes (4 or 7)
    'sak': str,           # SAK hex string, e.g. '08'
    'atqa': str,          # ATQA hex string, e.g. '0004'
    'isMifare': bool,     # True if MIFARE Classic detected
    'isUL': bool,         # True if Ultralight family detected
    'isIclass': bool,     # True if iCLASS detected
    'hasMulti': bool,     # True if collision / multiple tags
    'hf_found': bool,     # True if HF tag detected
    'is_found': bool,     # Alias for found

    # LF fields (from lfsearch.parser()):
    'data': str,          # Raw data string
    'raw': str,           # Raw hex data
    'known': bool,        # True if LF tag type is known/recognized
    'isT55XX': bool,      # True if T55XX detected
    'is4xXX': bool,       # True if EM4x05 detected

    # T55XX-specific (from lft55xx):
    'key': str,           # T55XX key if known

    # Additional runtime fields:
    'bbcEr': bool,        # BCC error flag (from hf14ainfo)
}
```

> **Note**: Not all fields are present in every result. The fields depend on
> which scan function produced the result. The `found`, `return`, `progress`,
> and `type` fields are always present.

---

## 4. Module-Level Functions

### 4.1 Cache Management

```python
def setScanCache(infos):
    """Store scan result in INFOS global."""
    global INFOS
    INFOS = infos

def getScanCache():
    """Return cached scan result (or None)."""
    return INFOS

def clearScanCahe():  # NOTE: typo is intentional — matches binary
    """Clear scan cache."""
    global INFOS
    INFOS = None

def set_infos_cache(enable):
    """Enable/disable INFOS cache."""
    global INFOS_CACHE_ENABLE
    INFOS_CACHE_ENABLE = enable
```

### 4.2 Key Management

```python
def set_scan_t55xx_key(key):
    """Set temporary T55xx scan key. Delegates to lft55xx.set_key(key)."""

def set_scan_em4x05_key(key):
    """Set temporary EM4x05 scan key. Delegates to lfem4x05.set_key(key)."""
```

### 4.3 Factory Functions (create result dicts)

| Function                     | `return` | `found` | Notes                           |
|------------------------------|----------|---------|----------------------------------|
| `createExecTimeout(progress)`| -1       | False   | PM3 timeout                     |
| `createTagLost(progress)`    | -2       | False   | Tag lost                        |
| `createTagMulti(progress)`   | -3       | **True**| Multiple tags — `found=True`!   |
| `createTagNoFound(progress)` | -4       | False   | No tag                          |
| `createTagTypeWrong(progress)`| -5      | False   | Wrong type                      |

All return: `{'progress': progress, 'return': code, 'found': bool, 'type': -1}`

> **Critical**: `createTagMulti` sets `found=True` (not False). This matches
> the binary and is important for the `_is_can_next` logic.

### 4.4 Predicate Functions

```python
def isTagFound(maps):      return maps['found']
def isTagLost(maps):       return maps['return'] == CODE_TAG_LOST       # == -2
def isTagMulti(maps):      return maps['return'] == CODE_TAG_MULT       # == -3
def isTimeout(value):      return value['return'] == CODE_TIMEOUT       # == -1
def isTagTypeWrong(maps):  return maps['return'] == CODE_TAG_TYPE_WRONG # == -5

def isCanNext(value):
    """Can scanning proceed to the next step?
    False if found=True (tag found, done).
    False if return is CODE_TIMEOUT (-1) or CODE_TAG_LOST (-2).
    True otherwise (CODE_TAG_NO, CODE_TAG_TYPE_WRONG → keep scanning).
    """
    if value.get('found', False):
        return False
    ret = value['return']
    return ret != CODE_TIMEOUT and ret != CODE_TAG_LOST
```

---

## 5. Low-Level Scan Functions

Each function sends PM3 commands via `executor.startPM3Task()`, then delegates
to a leaf parser module.

### 5.1 scan_14a() — HF 14443-A (progress=0)

```
PM3 command: "hf 14a info" (timeout=5000)
Parser: hf14ainfo.parser()
```

- If `executor.startPM3Task` returns -1 → `createExecTimeout(0)`
- If parser returns `found=True` → return parser result with `progress=0`
- If parser returns `found=False` → `createTagNoFound(0)` (allows pipeline to continue)

**Real device trace** (from `trace_scan_flow_20260331.txt`):
```
PM3> hf 14a info (timeout=5000)
PM3< ret=1 \n\n[+]  UID: 3A F7 35 01 \n[+] ATQA: 00 04\n[+]  SAK: 08 [2]...
```

When 14A found with SAK 08 (Classic), also runs:
```
PM3> hf mf cgetblk 0 (timeout=5888)    # Gen1a test
```

When 14A found with SAK 00 (Ultralight), also runs:
```
PM3> hf mfu info (timeout=8888)         # Ultralight info
```

> **Note**: The `hf mf cgetblk 0` and `hf mfu info` commands are sent by
> `hf14ainfo.parser()`, not by scan_14a() itself. scan_14a() just calls the
> parser which internally may send additional commands.

### 5.2 scan_lfsea() — LF Search (progress=1)

```
PM3 command: "lf sea" (timeout=10000)
Parser: lfsearch.parser()
```

- If PM3 returns -1 → `createExecTimeout(1)`
- If parser returns `found=True` → return with `progress=1`
- If no known tag found → `createTagNoFound(1)`

**Real device trace** — LF tag found (EM410x):
```
PM3> lf sea (timeout=10000)
PM3< ret=1 ...[+] EM410x pattern found\n\nEM TAG ID...
→ type=8
```

**Real device trace** — no LF tag:
```
PM3> lf sea (timeout=10000)
PM3< ret=1 ...[=] Checking for known tags...\n...[|]Searching for MOTOROLA tag...
→ no tag keyword found
```

### 5.3 scan_hfsea() — HF Search (progress=2)

```
PM3 command: "hf sea" (timeout=10000)
Parser: hfsearch.parser()
```

- If PM3 returns -1 → `createExecTimeout(2)`
- If parser returns `found=True` → return with `progress=2`
- If no tag found → `createTagNoFound(2)`

**Real device trace** — ISO15693 found:
```
PM3> hf sea (timeout=10000)
PM3< ret=1 ...[-] Searching for ThinFilm tag...[\]...
→ type=19 (ISO15693)
```

### 5.4 scan_t55xx() — T55xx Detection (progress=3)

```
Delegates to: lft55xx.detectT55XX()
PM3 command (internal): "lf t55xx detect" (timeout=10000)
```

- Calls `lft55xx.detectT55XX()` which returns dict on success, int on failure
- If found → return with `progress=3`, `type=23` (T55X7_ID)
- If not found → `createTagNoFound(3)`

### 5.5 scan_em4x05() — EM4x05 Detection (progress=4)

```
Delegates to: lfem4x05.infoAndDumpEM4x05ByKey()
PM3 command (internal): "lf em 4x05_info" (from string table)
```

- Calls `lfem4x05.infoAndDumpEM4x05ByKey()`
- If found → return with `progress=4`, `type=24` (EM4305_ID)
- If not found → `createTagNoFound(4)`

### 5.6 scan_felica() — FeliCa Detection (progress=5)

```
PM3 command: "hf felica reader" (timeout=10000)
Parser: hffelica.parser()
```

- If PM3 returns -1 → `createExecTimeout(5)`
- If parser returns `found=True` → return with `progress=5`, `type=21` (FELICA)
- If not found → `createExecTimeout(5)` (note: ExecTimeout, NOT TagNoFound)

**Real device trace** — no FeliCa:
```
PM3> hf felica reader (timeout=10000)
PM3< ret=1 \n[!] card timeout\n
```

### 5.7 lf_wav_filter() — LF Signal Amplitude Filter

T55XX gatekeeper function. Saves PM3 graph buffer and analyzes waveform
amplitude to confirm a real LF signal is present.

**Flow:**
1. Send `data save f /tmp/lf_trace_tmp` (PM3 auto-appends `.pm3`)
2. Read `/tmp/lf_trace_tmp.pm3` directly (Linux) or via PM3 `cat` proxy (Windows)
3. Parse integer samples from file (one per line)
4. Compute amplitude: `max(values) - min(values)`
5. Return `amplitude >= 90` (threshold from `__pyx_int_90`)
6. Cleanup: `commons.delfile_on_icopy(file_path)`

**Chinese label strings** in binary (logging only, not parsed):
- `__pyx_kp_u__8` = `峰值最大值: ` (Peak Maximum Value)
- `__pyx_kp_u__9` = `峰值最小值: ` (Peak Minimum Value)

**Real device trace** — lf_wav_filter invoked:
```
PM3> data save f /tmp/lf_trace_tmp (timeout=10000)
PM3< ret=1 \n[+] saved 30000 bytes to PM3 file '/tmp/lf_trace_tmp.pm3'\n
```

---

## 6. Scanner Class

### 6.1 Constructor

```python
class Scanner:
    def __init__(self):
        self._call_progress = None    # Callback for progress updates
        self._call_resulted = None    # Callback for final result
        self._call_exception = None   # Callback for exceptions
        self._call_value_max = 100    # Max progress value
        self._scan_lock = threading.RLock()
        self._scan_running = False
        self._stop_label = False
```

### 6.2 Properties (getter/setter pairs)

```python
@property
def call_progress(self): return self._call_progress
@call_progress.setter
def call_progress(self, value): self._call_progress = value

@property
def call_resulted(self): return self._call_resulted
@call_resulted.setter
def call_resulted(self, value): self._call_resulted = value

@property
def call_exception(self): return self._call_exception
@call_exception.setter
def call_exception(self, value): self._call_exception = value
```

### 6.3 Internal Callback Dispatch

```python
def _call_progress_method(self, progress):
    """Call progress callback with (progress, _call_value_max) tuple."""
    if self._call_progress is not None:
        self._call_progress((progress, self._call_value_max))

def _call_resulted_method(self, resulted):
    """Call result callback with the result dict."""
    if self._call_resulted is not None:
        self._call_resulted(resulted)

def _call_exception_method(self):
    """Call exception callback with traceback.format_exc() string."""
    if self._call_exception is not None:
        self._call_exception(traceback.format_exc())
```

### 6.4 State Management

```python
def _raise_on_multi_scan(self):
    """Raise if scan already running."""
    if self._scan_running:
        raise Exception("不允许对一个设备同时开启多次查询任务。")
        # "Not allowed to open multiple query tasks on one device simultaneously."

def _set_run_label(self, value):
    """Set running state. When True: running=True, stop=False.
       When False: running=False, stop=False."""
    with self._scan_lock:
        self._scan_running = value
        self._stop_label = False

def _set_stop_label(self, value):
    """Set stop label (does NOT change _scan_running)."""
    with self._scan_lock:
        self._stop_label = value

def _is_can_next(self, value):
    """Can scanning continue to next step?
    False if _stop_label is True (scan_stop() called).
    False if found=True (tag found).
    False if return is CODE_TIMEOUT or CODE_TAG_LOST.
    True otherwise."""
    if self._stop_label:
        return False
    if value.get('found', False):
        return False
    ret = value['return']
    return ret != CODE_TIMEOUT and ret != CODE_TAG_LOST
```

### 6.5 scan_all_synchronous() — Full Scan (Blocking)

The main scan pipeline. Runs all scan functions in sequence with early exit.

```python
def scan_all_synchronous(self):
    self._raise_on_multi_scan()
    self._set_run_label(True)
    try:
        result = None

        # Step 1: HF 14443-A (progress=0)
        r = scan_14a()
        if r.get('found'):
            result = r
        elif not self._is_can_next(r):
            result = r
        else:
            # Step 2: HF Search (progress=2) — NOT step 1, note progress gap
            r = scan_hfsea()
            if r.get('found'):
                result = r
            elif not self._is_can_next(r):
                result = r
            else:
                # Step 3: LF Search (progress=1)
                r = scan_lfsea()
                if r.get('found'):
                    result = r
                elif not self._is_can_next(r):
                    result = r
                else:
                    # Step 4: T55xx (progress=3)
                    r = scan_t55xx()
                    if r.get('found'):
                        result = r
                    elif not self._is_can_next(r):
                        result = r
                    else:
                        # Step 5: EM4x05 (progress=4)
                        r = scan_em4x05()
                        if r.get('found'):
                            result = r
                        elif not self._is_can_next(r):
                            result = r
                        else:
                            # Step 6: FeliCa (progress=5) — terminal
                            r = scan_felica()
                            result = r

        # Cache result if enabled and tag found
        if INFOS_CACHE_ENABLE and result and result.get('found'):
            setScanCache(result)

        # Signal completion
        self._call_progress_method(100)
        self._call_resulted_method(result)

    except Exception:
        self._call_exception_method()
    finally:
        self._set_stop_label(True)
        self._set_run_label(False)
```

**Pipeline order** (verified via traces):

| Step | Function     | Progress | PM3 Command          | Timeout |
|------|-------------|----------|----------------------|---------|
| 1    | scan_14a    | 0        | `hf 14a info`        | 5000ms  |
| 2    | scan_hfsea  | 2        | `hf sea`             | 10000ms |
| 3    | scan_lfsea  | 1        | `lf sea`             | 10000ms |
| 4    | scan_t55xx  | 3        | `lf t55xx detect`    | 10000ms |
| 5    | scan_em4x05 | 4        | `lf em 4x05_info`   | varies  |
| 6    | scan_felica | 5        | `hf felica reader`   | 10000ms |

> **Critical observation from traces**: Steps 3 (LF search) and 4 (T55xx)
> are only reached when steps 1 and 2 find nothing. The "no known" LF result
> triggers the `lf_wav_filter` → `data save` → `lf t55xx detect` sequence.

### 6.6 scan_all_asynchronous() — Full Scan (Non-Blocking)

```python
def scan_all_asynchronous(self):
    """Run full scan in a background daemon thread."""
    t = threading.Thread(target=self.scan_all_synchronous, daemon=True)
    t.start()
```

### 6.7 scan_type_synchronous(typ) — Type-Specific Scan (Blocking)

Dispatches to specific scan functions based on tag type, then checks type match.

```python
def scan_type_synchronous(self, typ):
    self._raise_on_multi_scan()
    self._set_run_label(True)
    try:
        import tagtypes
        result = None

        # HF 14443-A types (M1, MFU, NTAG, DESFire, HF14A_OTHER)
        hf_14a_types = {
            tagtypes.M1_S70_4K_4B,    # 0
            tagtypes.M1_S50_1K_4B,    # 1
            tagtypes.M1_S70_4K_7B,    # 41
            tagtypes.M1_S50_1K_7B,    # 42
            tagtypes.M1_MINI,          # 25
            tagtypes.M1_PLUS_2K,       # 26
            tagtypes.M1_POSSIBLE_4B,   # 43
            tagtypes.M1_POSSIBLE_7B,   # 44
            tagtypes.ULTRALIGHT,       # 2
            tagtypes.ULTRALIGHT_C,     # 3
            tagtypes.ULTRALIGHT_EV1,   # 4
            tagtypes.NTAG213_144B,     # 5
            tagtypes.NTAG215_504B,     # 6
            tagtypes.NTAG216_888B,     # 7
            tagtypes.HF14A_OTHER,      # 40
            tagtypes.MIFARE_DESFIRE,   # 39
        }

        # LF types
        lf_types = {
            tagtypes.EM410X_ID,    # 8
            tagtypes.HID_PROX_ID,  # 9
            tagtypes.INDALA_ID,    # 10
            tagtypes.AWID_ID,      # 11
            tagtypes.IO_PROX_ID,   # 12
            tagtypes.GPROX_II_ID,  # 13
            tagtypes.SECURAKEY_ID, # 14
            tagtypes.VIKING_ID,    # 15
            tagtypes.PYRAMID_ID,   # 16
            tagtypes.FDXB_ID,      # 28
            tagtypes.GALLAGHER_ID, # 29
            tagtypes.JABLOTRON_ID, # 30
            tagtypes.KERI_ID,      # 31
            tagtypes.NEDAP_ID,     # 32
            tagtypes.NORALSY_ID,   # 33
            tagtypes.PAC_ID,       # 34
            tagtypes.PARADOX_ID,   # 35
            tagtypes.PRESCO_ID,    # 36
            tagtypes.VISA2000_ID,  # 37
            tagtypes.NEXWATCH_ID,  # 45
        }

        if typ in hf_14a_types:
            r = scan_14a()
            if r.get('found'):
                result = r
            elif self._is_can_next(r):
                r = scan_hfsea()
                result = r
            else:
                result = r

        elif typ in lf_types:
            r = scan_lfsea()
            if r.get('found'):
                result = r
            elif self._is_can_next(r):
                r = scan_t55xx()
                result = r
            else:
                result = r

        elif typ == tagtypes.T55X7_ID:       # 23
            result = scan_t55xx()

        elif typ == tagtypes.EM4305_ID:      # 24
            result = scan_em4x05()

        elif typ in {tagtypes.ICLASS_LEGACY, tagtypes.ICLASS_ELITE, tagtypes.ICLASS_SE}:
            result = scan_hfsea()            # 17, 18, 47

        elif typ in {tagtypes.ISO15693_ICODE, tagtypes.ISO15693_ST_SA}:
            result = scan_hfsea()            # 19, 46

        elif typ == tagtypes.LEGIC_MIM256:   # 20
            result = scan_hfsea()

        elif typ == tagtypes.FELICA:         # 21
            result = scan_felica()

        elif typ == tagtypes.ISO14443B:      # 22
            result = scan_hfsea()

        elif typ == tagtypes.HITAG2_ID:      # 38
            result = scan_hfsea()

        else:
            result = None  # Unknown type

        # Type match check
        if result and result.get('found') and result.get('type', -1) != typ:
            result = createTagTypeWrong(result.get('progress', 0))

        # Cache if appropriate
        if INFOS_CACHE_ENABLE and result and result.get('found'):
            setScanCache(result)

        self._call_progress_method(100)
        self._call_resulted_method(result)

    except Exception:
        self._call_exception_method()
    finally:
        self._set_stop_label(True)
        self._set_run_label(False)
```

### 6.8 scan_type_asynchronous(typ) — Type-Specific Scan (Non-Blocking)

```python
def scan_type_asynchronous(self, typ):
    """Run type-specific scan in a background daemon thread."""
    t = threading.Thread(target=self.scan_type_synchronous, args=(typ,), daemon=True)
    t.start()
```

### 6.9 scan_stop()

```python
def scan_stop(self):
    """Request scan stop. Sets _stop_label=True, checked by _is_can_next."""
    self._stop_label = True
```

---

## 7. scanForType() — Module-Level Type-Specific Scan

A standalone module-level function (not on Scanner class) for type-specific
scanning with a listener callback.

```python
def scanForType(listener, typ):
    """Scan for specific tag type, call listener with result.

    Defines inner function run() with closure over listener/typ.
    run() dispatches to appropriate scan_*() based on type,
    checks type match, and calls listener({'progress': 100, 'return': result}).
    """
```

The inner `run()` function also defines `call_listener_on_success()` as
a nested closure (visible in string table:
`scanForType.<locals>.run.<locals>.call_listener_on_success`).

---

## 8. Tag Type Helper Functions (for tagtypes grouping)

The binary references several tagtypes helper functions used internally
to determine scan dispatch:

| Function               | Returns                           | Usage                  |
|------------------------|-----------------------------------|------------------------|
| `tagtypes.getM1Types()`| Set of M1 Classic type IDs        | 14A scan dispatch      |
| `tagtypes.getM14BTypes()`| Set of M1 4-byte UID types      | UID length routing     |
| `tagtypes.getM17BTypes()`| Set of M1 7-byte UID types      | UID length routing     |
| `tagtypes.getULTypes()`| Set of Ultralight/NTAG type IDs   | 14A sub-type routing   |
| `tagtypes.getAllHigh()` | Set of all HF type IDs            | HF vs LF dispatch      |
| `tagtypes.getAllLow()`  | Set of all LF type IDs            | HF vs LF dispatch      |
| `tagtypes.getAllLowCanDump()`| Set of LF types with dump support | lf_wav_filter gate  |

---

## 9. PM3 Command Sequence — Verified from Real Device Traces

### 9.1 No Tag Present (Full Scan Cycle)

From `trace_scan_flow_20260331.txt` lines 5-21:

```
1. hf 14a info (timeout=5000)        → ret=1, empty (no 14A)
2. lf sea (timeout=10000)            → ret=1, "Searching for MOTOROLA..." (no known tag)
3. hf sea (timeout=10000)            → ret=1, "Searching for ThinFilm..." (no known tag)
4. hf felica reader (timeout=10000)  → ret=1, "[!] card timeout"
   ---- pause ~3s, retry ----
5. hf 14a info (timeout=5000)        → same
6. lf sea (timeout=10000)            → same
7. hf sea (timeout=10000)            → same
8. hf felica reader (timeout=10000)  → same
   ---- FINISH ----
```

> **Key insight**: When no tag is found, the scan loop runs **twice** (two full
> cycles) before giving up. This is visible in the trace at lines 14-21.

### 9.2 MIFARE Classic 1K Found (SAK=08, 4-byte UID)

From `trace_scan_flow_20260331.txt` lines 65-70:

```
1. hf 14a info (timeout=5000)  → UID: 3A F7 35 01, ATQA: 00 04, SAK: 08
2. hf mf cgetblk 0 (timeout=5888)  → wupC1 error (not Gen1a)
   → type=1, uid=3AF73501
```

### 9.3 MIFARE Ultralight Found (SAK=00, 7-byte UID)

From `trace_scan_flow_20260331.txt` lines 24-34:

```
1. hf 14a info (timeout=5000)  → UID: 00 00 00 00 00 00 00, ATQA: 00 44, SAK: 00
2. hf mf cgetblk 0 (timeout=5888)  → wupC1 error (not Gen1a)
3. hf mfu info (timeout=8888)  → TYPE: Unknown 000000, UID: 00 00 00...
   → type=2, uid=00000000000000
```

### 9.4 LF Tag Found (EM410x)

From `trace_lf_scan_flow_20260331.txt` lines 29-37:

```
1. hf 14a info (timeout=5000)  → empty (no 14A)
2. lf sea (timeout=10000)      → "[+] EM410x pattern found\n\nEM TAG..."
   → type=8
```

### 9.5 T55XX Blank Card (No Known Modulation)

From `trace_lf_scan_flow_20260331.txt` lines 57-68:

```
1. hf 14a info (timeout=5000)  → empty
2. lf sea (timeout=10000)      → "[-] No known 125/134 kHz tags found"
3. data save f /tmp/lf_trace_tmp (timeout=10000)  → saved 30000 bytes
4. lf t55xx detect (timeout=10000)  → "Could not detect modulation..."
5. hf sea (timeout=10000)      → ThinFilm/LTO-CM search (nothing)
6. hf felica reader (timeout=10000)  → card timeout
   ---- retry cycle ----
   → type=23
```

> **Critical**: When `lf sea` finds no known tag, the pipeline:
> 1. Runs `data save f /tmp/lf_trace_tmp` (the `lf_wav_filter` function)
> 2. If signal present, runs `lf t55xx detect`
> 3. If T55xx not detected, falls through to `hf sea` + `hf felica reader`
> 4. May retry the full cycle

### 9.6 ISO15693 (HF Search)

From `trace_scan_flow_20260331.txt` lines 36-47:

```
1. hf 14a info (timeout=5000)  → empty
2. lf sea (timeout=10000)      → Searching for MOTOROLA...
3. hf sea (timeout=10000)      → (found ISO15693 in truncated output)
   → type=19, uid=E0530110CCA96A11
```

---

## 10. UI Integration — How ScanActivity Calls scan.so

### 10.1 Starting a Scan

From `activity_main.py` lines 1136-1141:

```python
# ScanActivity._startScan():
scanner = scan.Scanner()                           # Instantiate
scanner.call_progress = self.onScanning             # Progress callback
scanner.call_resulted = self.onScanFinish           # Result callback
scanner.call_exception = self.onScanFinish          # Exception callback (same!)
scanner.scan_all_asynchronous()                     # Start background thread
```

> **Important**: `call_exception` is set to `self.onScanFinish` — the same
> callback as `call_resulted`. So exceptions (traceback strings) arrive at
> `onScanFinish`, which must handle both dicts and strings.

### 10.2 Cancelling a Scan

```python
# ScanActivity._cancelScan():
scanner.scan_stop()  # Sets _stop_label = True
```

### 10.3 Processing Scan Results

`onScanFinish(result)` receives either:
- A **dict** with scan data: `{'found': True, 'type': 1, 'uid': '3AF73501', ...}`
- A **string** (traceback from exception)
- An **int** code

Decision tree:
```
if found=True  →  STATE_FOUND   →  template.draw(), setScanCache(), "Tag Found" toast
if hasMulti    →  STATE_MULTI   →  "Multiple tags detected!" toast
if CODE_TAG_TYPE_WRONG → STATE_WRONG_TYPE → "No tag found Or Wrong type found!" toast
else           →  STATE_NOT_FOUND → "No tag found" toast
```

### 10.4 Scan Cache Integration

```python
# ScanActivity.setScanCache(result):
self._scan_cache = result
scan.setScanCache(result)           # Also set in scan module global

# ScanActivity.getScanCache():
return self._scan_cache

# Downstream (ReadActivity, AutoCopyActivity):
infos = scan.getScanCache()         # Read from scan module global
```

The scan cache is shared across activities via the module-level `INFOS` global,
allowing ReadActivity and AutoCopyActivity to access the last scan result.

### 10.5 AutoCopy Integration

AutoCopyActivity uses the **same** Scanner pattern:

```python
# AutoCopyActivity.startScan():
scanner = scan.Scanner()
scanner.call_resulted = self.onScanFinish
scanner.call_exception = self.onScanFinish
scanner.scan_all_asynchronous()
```

---

## 11. Thread/Async Pattern

1. **`scan_all_asynchronous()`** creates a daemon `threading.Thread` targeting
   `scan_all_synchronous()` and starts it immediately.

2. **`scan_all_synchronous()`** runs on that background thread:
   - Acquires `_scan_lock` (RLock) to set state
   - Calls scan functions sequentially (each blocks on PM3 I/O)
   - Between steps, checks `_is_can_next()` which reads `_stop_label`
   - Calls back `_call_resulted_method()` with the result — this calls
     the UI callback from the **background thread**

3. **UI callbacks** (`onScanFinish`, `onScanning`) are called from the scan
   thread, NOT the main thread. The UI must handle cross-thread rendering.

4. **`scan_stop()`** simply sets `_stop_label = True`. The scan thread
   checks this between steps and short-circuits if set. It does NOT
   immediately kill the thread — the current PM3 command completes first.

5. The `finally` block always calls `_set_stop_label(True)` and
   `_set_run_label(False)`, ensuring clean state regardless of outcome.

---

## 12. Complete Function Index

### Module-Level Functions (24 total from `__pyx_mdef`)

| #  | Cython Name | Public Name            | Args                |
|----|-------------|------------------------|---------------------|
| 1  | scan_1      | createTagNoFound       | (progress)          |
| 3  | scan_3      | createTagLost          | (progress)          |
| 5  | scan_5      | createTagMulti         | (progress)          |
| 7  | scan_7      | createExecTimeout      | (progress)          |
| 9  | scan_9      | createTagTypeWrong     | (progress)          |
| 11 | scan_11     | isTagTypeWrong         | (maps)              |
| 13 | scan_13     | isTagLost              | (maps)              |
| 15 | scan_15     | isTagMulti             | (maps)              |
| 17 | scan_17     | isTagFound             | (maps)              |
| 19 | scan_19     | isTimeout              | (value)             |
| 21 | scan_21     | isCanNext              | (value)             |
| 23 | scan_23     | set_infos_cache        | (enable)            |
| 25 | scan_25     | scan_14a               | ()                  |
| 27 | scan_27     | lf_wav_filter          | ()                  |
| 29 | scan_29     | scan_lfsea             | ()                  |
| 31 | scan_31     | scan_hfsea             | ()                  |
| 33 | scan_33     | scan_t55xx             | ()                  |
| 35 | scan_35     | scan_em4x05            | ()                  |
| 37 | scan_37     | scan_felica            | ()                  |
| 39 | scan_39     | scanForType            | (listener, typ)     |
| 41 | scan_41     | getScanCache           | ()                  |
| 43 | scan_43     | clearScanCahe          | ()                  |
| 45 | scan_45     | setScanCache           | (infos)             |
| 47 | scan_47     | set_scan_t55xx_key     | (key)               |
| 49 | scan_49     | set_scan_em4x05_key    | (key)               |

### Scanner Class Methods (19 total from `__pyx_mdef_4scan_7Scanner_*`)

| #  | Method                      | Args           |
|----|-----------------------------|----------------|
| 1  | __init__                    | (self)         |
| 3  | call_progress (getter)      | (self)         |
| 5  | call_progress (setter)      | (self, value)  |
| 7  | call_resulted (getter)      | (self)         |
| 9  | call_resulted (setter)      | (self, value)  |
| 11 | call_exception (getter)     | (self)         |
| 13 | call_exception (setter)     | (self, value)  |
| 15 | _call_progress_method       | (self, progress)|
| 17 | _call_resulted_method       | (self, resulted)|
| 19 | _call_exception_method      | (self)         |
| 21 | _set_stop_label             | (self, value)  |
| 23 | _set_run_label              | (self, value)  |
| 25 | _is_can_next                | (self, value)  |
| 27 | _raise_on_multi_scan        | (self)         |
| 29 | scan_all_synchronous        | (self)         |
| 31 | scan_all_asynchronous       | (self)         |
| 33 | scan_type_synchronous       | (self, typ)    |
| 35 | scan_type_asynchronous      | (self, typ)    |
| 37 | scan_stop                   | (self)         |

---

## 13. Key Behavioral Notes

1. **Progress values are NOT sequential**: scan_14a=0, scan_lfsea=1,
   scan_hfsea=2, scan_t55xx=3, scan_em4x05=4, scan_felica=5.
   But the execution order is: 0→2→1→3→4→5.

2. **createTagMulti sets found=True**: This is counterintuitive but correct.
   Multiple tags IS a "found" condition — the pipeline stops.

3. **scan_felica returns createExecTimeout on no-FeliCa, NOT createTagNoFound**:
   Since FeliCa is the last step, there's no next step to "continue" to.

4. **clearScanCahe typo**: The misspelling "Cahe" (not "Cache") is
   intentional — it matches the original .so binary exactly.

5. **Two retry cycles**: When no tag is found, the full scan cycle runs
   twice before reporting failure (visible in traces).

6. **lf_wav_filter gating**: When `lf sea` finds no known tag but there's
   LF signal, `lf_wav_filter` checks amplitude >= 90. If true, proceeds
   to `lf t55xx detect`. This is the T55XX detection path.

7. **Exception callback goes to same handler as result callback**: The UI
   sets `call_exception = self.onScanFinish`, so the handler must
   distinguish between dict results and string tracebacks.

8. **Thread safety**: `_scan_lock` (RLock) protects `_scan_running` and
   `_stop_label` state. But callback dispatch is NOT synchronized — the
   UI callback is invoked from the scan thread.

9. **scan_stop is non-blocking**: It just sets a flag. The current PM3
   command (which may take up to 10000ms) will complete before the scan
   thread checks the flag and exits.

---

## 14. Cross-Reference: Test Fixtures

The 45 test scenarios in `tests/flows/scan/scenarios/` cover:

| Category           | Scenarios                                                    |
|--------------------|--------------------------------------------------------------|
| HF 14443-A (14)    | mf_classic_1k_4b, mf_classic_1k_7b, mf_classic_4k_4b,     |
|                    | mf_classic_4k_7b, mf_ultralight, mf_desfire, mf_mini,      |
|                    | mf_possible_4b, mf_possible_7b, ntag215, gen2_cuid,        |
|                    | bcc0_incorrect, hf14a_other, topaz                          |
| HF Search (5)      | iclass, iso15693_icode, iso15693_st, iso14443b, legic       |
| LF Search (14)     | em410x, hid_prox, indala, awid, ioprx, gprox, securakey,   |
|                    | viking, pyramid, fdxb, gallagher, jablotron, keri, nedap    |
| LF Exotic (6)      | nexwatch, noralsy, pac, paradox, presco, visa2000           |
| LF Special (2)     | hitag, t55xx_blank                                          |
| FeliCa (1)         | felica                                                      |
| Edge Cases (3)     | no_tag, multi_tags, no_console_on_right                     |

Each fixture provides `SCENARIO_RESPONSES` (PM3 command→response map),
`DEFAULT_RETURN` (-1), and `TAG_TYPE` (expected tag type ID).
