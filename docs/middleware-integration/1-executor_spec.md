# executor.so Transliteration Spec

## Module Identity

- **Source**: `executor.so` — Cython 0.29.21, ARM 32-bit, Python 3.8
- **Size**: 714K decompiled (`decompiled/executor_ghidra_raw.txt`)
- **Role**: PM3 communication foundation — ALL RFID flows depend on this
- **Architecture**: Flat module (no classes), TCP socket client to PM3 process
- **Exports**: 23 Python-callable functions + 11 module-level state variables

## Ground Truth Sources

| Source | Path | Purpose |
|--------|------|---------|
| Decompiled | `decompiled/executor_ghidra_raw.txt` | Primary logic reference |
| Strings | `docs/v1090_strings/executor_strings.txt` | All string literals |
| Module Audit | `docs/V1090_MODULE_AUDIT.txt` (lines 228-264) | Canonical function list |
| Archive (structural only) | `/home/qx/archive/lib_transliterated/executor.py` | Class structure, import patterns |
| Scan trace | `docs/Real_Hardware_Intel/trace_scan_flow_20260331.txt` | HF scan protocol |
| LF scan trace | `docs/Real_Hardware_Intel/trace_lf_scan_flow_20260331.txt` | LF T55XX detection |
| Read trace | `docs/Real_Hardware_Intel/trace_read_flow_20260401.txt` | fchks + readAllSector |
| Write trace | `docs/Real_Hardware_Intel/write_flow_trace_20260326/pm3_write_trace.txt` | Nikola.D return codes |
| Sniff trace | `docs/Real_Hardware_Intel/trace_sniff_enhanced_20260404.txt` | Listener mechanism |
| AutoCopy trace | `docs/Real_Hardware_Intel/trace_autocopy_mf1k_standard.txt` | rework parameter |
| Misc trace | `docs/Real_Hardware_Intel/trace_misc_flows_20260330.txt` | startPM3Plat/Ctrl init |
| Test fixtures | `tests/flows/scan/scenarios/*/fixture.py` (44 files) | Expected behavior |
| Original mock | `tools/launcher_original.py` (lines 344-763) | Mock implementation |
| Current mock | `tools/launcher_current.py` | OSS-path mock |

---

## Wire Protocol (Nikola.D)

```
Python app
    |
    | startPM3Task("hf 14a info", 5000)
    v
executor.so
    |
    | socket.sendall("Nikola.D.CMD = hf 14a info\n")  -- TCP to PM3 client
    v
PM3 client (C process on 127.0.0.1:8888)
    |
    | fd=1 write: "[usb] pm3 --> hf 14a info\n"
    | fd=3 write: PM3a..binary..a3  -- USB packets to PM3 hardware
    | fd=1 write: "[+]  UID: 3A F7 35 01 \n"  (line by line)
    | fd=1 write: "\nNikola.D: 0\n"  -- command done, return code 0
    v
executor.so
    |
    | reads socket, accumulates text into CONTENT_OUT_IN__TXT_CACHE
    | parses "Nikola.D: <N>" as end-of-response marker
    | returns 1 (completed) or -1 (error/timeout)
    v
Python app
    | ret = 1
    | content = executor.CONTENT_OUT_IN__TXT_CACHE
    | executor.hasKeyword("UID")  -> True
    | executor.getContentFromRegex(r"UID: (.+)")  -> "3A F7 35 01"
```

### Three Command Channels

| Channel | Function | Wire Format | Description |
|---------|----------|-------------|-------------|
| CMD | `startPM3Task` | `Nikola.D.CMD = {cmd}\n` | Normal PM3 commands |
| CTL | `startPM3Ctrl` | `Nikola.D.CTL = {cmd}\n` | Control: `restart`, `stop` |
| PLT | `startPM3Plat` | `Nikola.D.PLT = {cmd}\n` | Platform/shell commands |

### End-of-Response Detection

Two regex markers signal response completion:
- `Nikola.D: <number>` — command result code (0 = success, negative = error)
- `pm3 -->` — interactive prompt (alternative marker)

### Return Value Convention

**Critical**: `startPM3Task` does NOT return the Nikola.D value.
- Returns **1** = task completed (regardless of Nikola.D value)
- Returns **-1** = task error (timeout, connection failure, PM3 offline)

The Nikola.D value is embedded in `CONTENT_OUT_IN__TXT_CACHE` for callers to inspect.

---

## Module-Level State Variables (11)

| Variable | Type | Default | Purpose |
|----------|------|---------|---------|
| `CONTENT_OUT_IN__TXT_CACHE` | str | `''` | Last PM3 command response text — the primary data channel |
| `LABEL_PM3_CMD_TASK_RUNNING` | bool | `False` | True while a PM3 command is executing |
| `LABEL_PM3_CMD_TASK_STOP` | bool | `True` | True after task completes or is stopped |
| `LABEL_PM3_CMD_TASK_STOPPING` | bool | `False` | True during stop transition |
| `LIST_CALL_PRINT` | set | `set()` | Registered print callbacks |
| `LOCK_CALL_PRINT` | RLock | `RLock()` | Guards LIST_CALL_PRINT |
| `LOCK_THREAD` | RLock | `RLock()` | General thread lock |
| `CODE_PM3_TASK_ERROR` | int | `-1` | Error return sentinel |
| `PM3_REMOTE_ADDR` | str | `'127.0.0.1'` | PM3 TCP address |
| `PM3_REMOTE_CMD_PORT` | int | `8888` | PM3 TCP port (0x22B8) |
| `PRINT_V_MODE` | bool | `True` | Verbose printing mode |

### Internal State

| Variable | Type | Purpose |
|----------|------|---------|
| `_socket_instance` | socket or None | TCP connection to PM3 client |

---

## Exported Functions (23)

### Command Execution (4 functions)

#### `startPM3Task(cmd, timeout=5000, listener=None, rework_max=2)`
**The most critical function.** Every PM3 interaction goes through it.

- **Parameters**:
  - `cmd` (str): PM3 command string (e.g., `"hf 14a info"`)
  - `timeout` (int): Milliseconds. Default 5000. `-1` = infinite wait.
  - `listener` (callable or None): Per-line callback during execution
  - `rework_max` (int): Max retry attempts on failure. Default 2.
- **Returns**: `1` = completed, `-1` = error
- **Behavior**:
  1. Calls `_wait_if_stopping()` — blocks if a stop is in progress
  2. Sets `LABEL_PM3_CMD_TASK_RUNNING = True`, `LABEL_PM3_CMD_TASK_STOP = False`
  3. If `listener`, calls `add_task_call(listener)`
  4. Formats command as `Nikola.D.CMD = {cmd}\n`
  5. Sends via TCP socket
  6. Reads response in 1024-byte chunks via `socket.recv()`
  7. Accumulates text into `CONTENT_OUT_IN__TXT_CACHE`
  8. For each chunk, fires all registered callbacks in `LIST_CALL_PRINT`
  9. Detects end-of-response via `Nikola.D:` or `pm3 -->` regex
  10. On failure/offline: calls `reworkPM3All()` and retries up to `rework_max` times
  11. Sets `LABEL_PM3_CMD_TASK_RUNNING = False`, `LABEL_PM3_CMD_TASK_STOP = True`
  12. If `listener`, calls `del_task_call(listener)`
  13. Returns 1 or -1
- **Timeout handling**: Uses `select.select()` or `socket.settimeout()` to enforce timeout
- **Ground truth**: Decompiled at 0x1af98 (28KB, Ghidra timeout — reconstructed from Ctrl/Plat + traces)
- **Observed timeouts**: 5000 (default), 5888, 8888, 10000, 18888, 28888, 180000, 600000, -1

#### `startPM3Ctrl(ctrl_cmd, timeout=5888)`
- **Parameters**: `ctrl_cmd` (str): Control command (`"restart"`, `"stop"`)
- **Returns**: Response string (e.g., `"True"`)
- **Behavior**: Sends `Nikola.D.CTL = {ctrl_cmd}\n`, reads response
- **Ground truth**: Decompiled successfully, structurally similar to startPM3Task but simpler

#### `startPM3Plat(plat_cmd, timeout=5888)`
- **Parameters**: `plat_cmd` (str): Shell command (e.g., `"sudo date -s ..."`)
- **Returns**: Response string (shell stdout)
- **Behavior**: Sends `Nikola.D.PLT = {plat_cmd}\n`, reads response
- **Ground truth**: Decompiled successfully

#### `stopPM3Task(listener=None, wait=True)`
- **Parameters**: `listener` (callable or None), `wait` (bool): Block until stopped
- **Returns**: None
- **Behavior**: Sets `LABEL_PM3_CMD_TASK_STOPPING = True`, if `wait` blocks until `RUNNING = False`
- **Used by**: Erase cancel, sniff stop, simulation stop

---

### Response Parsing (7 functions)

All read from `CONTENT_OUT_IN__TXT_CACHE` unless a `line` parameter overrides.

#### `hasKeyword(keywords, line=None)`
- **Parameters**: `keywords` (str), `line` (str or None)
- **Returns**: bool
- **Behavior**: Uses `re.search(keywords, content)` — NOT simple `in` substring check
  - If `line` is None, searches `CONTENT_OUT_IN__TXT_CACHE`
  - If `line` is provided, searches that string instead
- **Ground truth**: Decompiled at ~0x8091-0x8291; calls `PyObject_GetAttrString` for `re.search`, creates 2-element tuple `(keyword, content)`, checks `PyObject_Size` on result
- **Critical note**: Because it uses `re.search`, keywords containing regex metacharacters (`.`, `[`, `(`, etc.) are treated as regex patterns

#### `getContentFromRegex(regex)`
- **Parameters**: `regex` (str): Regex pattern with capture groups
- **Returns**: str — the **last** capture group from `re.search()`, or `''`
- **Behavior**:
  1. `match = re.search(regex, CONTENT_OUT_IN__TXT_CACHE)`
  2. If match: returns `match.group(match.lastindex)` (last capturing group)
  3. If no match: returns `''`
- **Ground truth**: Decompiled; uses `lastindex` attribute

#### `getContentFromRegexA(regex)`
- **Parameters**: `regex` (str)
- **Returns**: list — `re.findall(regex, CONTENT_OUT_IN__TXT_CACHE)`
- **Behavior**: Returns all matches as a list

#### `getContentFromRegexAll(regex)`
- **Parameters**: `regex` (str)
- **Returns**: First element of `re.findall()`, or `[]`
- **Behavior**: Despite the name "All", returns only the **first** element
  - `results = re.findall(regex, CONTENT_OUT_IN__TXT_CACHE)`
  - Returns `results[0]` if results, else `[]`

#### `getContentFromRegexG(regex, group)`
- **Parameters**: `regex` (str), `group` (int): 1-based group index
- **Returns**: str — specific capture group, or `''`
- **Behavior**:
  - `group=0` → same as `getContentFromRegex` (returns last group)
  - `group=N` → returns `match.group(N)`
- **Ground truth**: 1-based indexing confirmed in decompilation

#### `getPrintContent()`
- **Parameters**: None
- **Returns**: str — raw `CONTENT_OUT_IN__TXT_CACHE`
- **Used by**: activity_tools.py (diagnosis), .so modules internally

#### `isEmptyContent()`
- **Parameters**: None
- **Returns**: bool
- **Behavior**: Returns `True` if `CONTENT_OUT_IN__TXT_CACHE` is whitespace-only AND non-empty
  - `''` → `False` (counter-intuitive!)
  - `' '` → `True`
  - `'data'` → `False`
- **Ground truth**: Decompiled; checks `strip()` then `len()`

---

### Error Detection (3 functions)

#### `isPM3Offline(lines)`
- **Parameters**: `lines` (str): Text to check
- **Returns**: bool
- **Checks for**: `'Nikola.D.OFFLINE'` in `lines`

#### `isCMDTimeout(lines)`
- **Parameters**: `lines` (str)
- **Returns**: bool
- **Checks for**: `'timeout while waiting for reply'` in `lines`

#### `isUARTTimeout(lines)`
- **Parameters**: `lines` (str)
- **Returns**: bool
- **Checks for**: `'UART:: write time-out'` in `lines`

---

### State Management (5 functions)

#### `_set_running(status)`
Sets `LABEL_PM3_CMD_TASK_RUNNING = status`

#### `_set_stopped(status)`
Sets `LABEL_PM3_CMD_TASK_STOP = status`

#### `_set_stopping(status)`
Sets `LABEL_PM3_CMD_TASK_STOPPING = status`

#### `_wait_if_stopping()`
Polls until `LABEL_PM3_CMD_TASK_STOPPING == False` (with `time.sleep(0.1)` between polls)

#### `_stop_task_user()`
Sets `LABEL_PM3_CMD_TASK_STOPPING = True`, sleeps 0.1s

---

### Callback Management (2 functions)

#### `add_task_call(call)`
- Thread-safe (`LOCK_CALL_PRINT`): adds `call` to `LIST_CALL_PRINT` set

#### `del_task_call(call)`
- Thread-safe: removes `call` from `LIST_CALL_PRINT` via `discard()`

---

### Connection Management (2 functions)

#### `connect2PM3(serial_port=None, baudrate=None)`
- Opens TCP socket to `PM3_REMOTE_ADDR:PM3_REMOTE_CMD_PORT` (127.0.0.1:8888)
- Returns `True` on success
- May send `"hw connect"` after socket open
- On failure, can invoke `hmi_driver.restartpm3()` and retry

#### `reworkPM3All()`
- Full reconnect cycle:
  1. Calls `hmi_driver.restartpm3()`
  2. Closes existing socket
  3. Sleeps 3s
  4. Calls `connect2PM3()` to reconnect

---

## Import Pattern

executor is always imported inside function bodies, never at module level:
```python
def some_method(self):
    import executor
    executor.startPM3Task("hf 14a info", 5000)
```

This avoids circular imports and allows late binding for mocking.

---

## Test Mock Behavior

### Original target (launcher_original.py)
- `executor.startPM3Task` is monkey-patched
- Mock looks up command in `_RESPONSES` dict (from fixture), sets `executor.CONTENT_OUT_IN__TXT_CACHE`, returns 1 or -1
- `hasKeyword`/`getContentFromRegex` are NOT mocked — they read from the real .so's C-level cache
- `_propagate_pm3_mock()` patches cached function references in Cython modules

### Current target (launcher_current.py)
- Creates a `types.ModuleType('executor')` stub injected into `sys.modules`
- Only mocks: `startPM3Task`, `startPM3Ctrl`, `stopPM3Task`, `connect2PM3`, `reworkPM3All`, `add_task_call`, `del_task_call`
- Does NOT mock `hasKeyword`/`getContentFromRegex` — Python middleware accesses `CONTENT_OUT_IN__TXT_CACHE` directly

### Fixture Structure
```python
SCENARIO_RESPONSES = {
    'hf 14a info': (0, '''[usb] pm3 --> hf 14a info\n[+]  UID: 2C AD C2 72\n...'''),
    'hf mf cgetblk': (0, '''[-] Can't set magic card block\n[-] isOk:00\n'''),
}
DEFAULT_RETURN = -1
TAG_TYPE = 1
```
- Return code 0 in fixture → mock returns 1 (completed)
- Return code -1 → mock returns -1 (error)
- Command matching by substring, longest match first
- Sequential responses use lists: `'hf mf wrbl': [(0, 'resp1'), (0, 'resp2')]`

---

## Implementation Notes

### startPM3Task Decompilation Gap
The `startPM3Task` function at 0x1af98 (~28KB) failed Ghidra decompilation due to timeout. Its behavior is reconstructed from:
1. `startPM3Plat`/`startPM3Ctrl` (structurally similar, DID decompile)
2. Real device traces (protocol observed end-to-end)
3. Archive reference (structural patterns)
4. Test fixture mock behavior (return conventions)
5. String analysis (`executor_strings.txt`)

### Socket Communication Constants
- Recv buffer: 1024 bytes (0x400)
- Default timeout: 5000ms (0x1388)
- Ctrl/Plat default timeout: 5888ms
- Socket type: `AF_INET`, `SOCK_STREAM` (TCP)

### Thread Safety
- `LOCK_THREAD` guards task execution
- `LOCK_CALL_PRINT` guards callback list
- Both are `threading.RLock` (reentrant)

### Dependencies
- `re` — regex for response parsing
- `socket` — TCP communication
- `select` — socket readiness polling
- `threading` — locks and synchronization
- `time` — sleeps and timeouts
- `hmi_driver` (optional) — `restartpm3()` for rework cycle
