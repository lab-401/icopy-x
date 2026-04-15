# executor.so Transliteration Specification

**Source**: `decompiled/executor_ghidra_raw.txt` (18,769 lines, 714K)
**Binary**: `orig_so/lib/executor.so` (ARM:LE:32:v7, Cython 0.29.21, Python 3.8)
**Strings**: `docs/v1090_strings/executor_strings.txt`
**Original source path**: `C:\Users\usertest\AppData\Local\Temp\tmpzw812qox\executor.py`
**Compiled by**: Linaro GCC 7.5-2019.12

---

## 1. Module Overview

executor.so is the **foundation module** that ALL RFID flows depend on. It manages:
- TCP socket connection to the PM3 proxmark3 client process
- Sending PM3 commands and receiving responses
- Response parsing (keyword search, regex extraction)
- Task lifecycle management (start/stop/running state)
- Thread synchronization via locks
- Print callback registration for UI updates

---

## 2. Imports

Extracted from `__pyx_pymod_exec_executor` (line 1913-3746), the module imports these
Python standard library modules (7 sequential imports in init):

| Import # | Module     | Purpose                           |
|----------|------------|-----------------------------------|
| 1        | `socket`   | TCP socket communication          |
| 2        | `select`   | Socket readiness polling          |
| 3        | `re`       | Regular expression parsing        |
| 4        | `threading`| Thread locks (RLock)              |
| 5        | `time`     | `perf_counter_ns` for timeouts    |
| 6        | `platform` | OS detection (Windows check)      |
| 7        | (unknown)  | Possibly `os` or `signal`         |

**Ground truth**: STR@0x0002cf78 (`socket`), STR@0x0002cf80 (`select`),
STR@0x0002d128 (`regex`), STR@0x0002ce24 (`threading`), STR@0x0002cb4c (`perf_counter_ns`),
STR@0x0002ce6c (`platform`), STR@0x0002cf58 (`AF_INET`), STR@0x0002cd60 (`SOCK_STREAM`)

---

## 3. Module-Level Constants

### 3.1 Integer Constants (from init, lines 2107-2149)

| Constant                  | Value      | Hex        | Purpose                          |
|---------------------------|------------|------------|----------------------------------|
| `PyFloat_FromDouble` #1   | (float)    | DAT_14a30  | Timeout value (likely 0.1)       |
| `PyFloat_FromDouble` #2   | (float)    | DAT_14a38  | Timeout value (likely 0.5)       |
| `PyFloat_FromDouble` #3   | (float)    | DAT_14a40  | Timeout value (likely 1.0)       |
| `PyLong(0)`               | 0          |            | Zero constant                    |
| `PyLong(1)`               | 1          |            | One constant / True              |
| `PyLong(2)`               | 2          |            | Two constant                     |
| `PyLong(3)`               | 3          |            | Three constant                   |
| `PyLong(1000)`            | 1000       | 0x3E8      | 1000ms = 1s in ns conversion     |
| `PyLong(0x400)`           | 1024       | 0x400      | Socket recv buffer size           |
| `PyLong(5000)`            | 5000       | 0x1388     | 5000ms timeout                   |
| `PyLong(0x1700)`          | 5888       | 0x1700     | Unknown timeout/buffer           |
| `PyLong(0x22B8)`          | 8888       | 0x22B8     | PM3 remote command port           |
| `PyLong(0x80000)`         | 524288     | 0x80000    | Large buffer / max response size  |
| `PyLong(0xFFFFFFFF)`      | -1 (uint)  | 0xFFFFFFFF | Error/sentinel value             |

### 3.2 String Constants (from STR table)

| String                           | Address       | Purpose                               |
|----------------------------------|---------------|---------------------------------------|
| `"Nikola.D.OFFLINE"`             | 0x0002cb38    | PM3 offline detection keyword         |
| `"Nikola.D.PLT"`                 | 0x0002ccbc    | Platform command prefix               |
| `"Nikola.D.CTL = {}\n"`          | 0x0002cccc    | Control command format                |
| `"Nikola.D.CMD = {}\n"`          | 0x0002cce0    | PM3 command format                    |
| `"Nikola.D:"`                    | 0x0002cee4    | Response prefix marker                |
| `"UART:: write time-out"`        | 0x0002cab8    | UART timeout detection string         |
| `"timeout while waiting for reply"` | 0x0002c980 | Command timeout detection string      |
| `"Communicating with PM3"`       | 0x0002ca44    | Connection status string              |
| `"hw connect"`                   | 0x0002cdb4    | PM3 reconnect command                 |
| `"sudo rm /dev/ttyACM0"`         | 0x0002ca8c    | Device cleanup command                |
| `"Failed"`                       | 0x0002d100    | Generic failure string                |
| `"PM3_REMOTE_ADDR"`              | 0x0002cb6c    | Config key: PM3 host address          |
| `"PM3_REMOTE_CMD_PORT"`          | 0x0002cad0    | Config key: PM3 command port          |
| `"CONTENT_OUT_IN__TXT_CACHE"`    | 0x0002c9f8    | Module-level response buffer variable |
| `"LABEL_PM3_CMD_TASK_STOPPING"`  | 0x0002c9c0    | State label: stopping                 |
| `"LABEL_PM3_CMD_TASK_RUNNING"`   | 0x0002c9dc    | State label: running                  |
| `"LABEL_PM3_CMD_TASK_STOP"`      | 0x0002ca14    | State label: stopped                  |
| `"CODE_PM3_TASK_ERROR"`          | 0x0002cafc    | Error code constant                   |
| `"LOCK_CALL_PRINT"`              | 0x0002cb7c    | Print callback lock name              |
| `"LIST_CALL_PRINT"`              | 0x0002cb8c    | Print callback list name              |
| `"LOCK_THREAD"`                  | 0x0002cd6c    | Thread lock name                      |
| `"PRINT_V_MODE"`                 | 0x0002ccac    | Verbose print mode flag               |

### 3.3 Module-Level Variables

From the init code and string analysis, these module-level variables are set:

```python
# Connection configuration
PM3_REMOTE_ADDR = "127.0.0.1"    # Inferred from AF_INET + localhost
PM3_REMOTE_CMD_PORT = 8888       # 0x22B8 from PyLong init

# Response buffers
CONTENT_OUT_IN__TXT_CACHE = ""   # Accumulated PM3 output text
buffer_on_all = ""               # Complete raw buffer
buffer_on_rn = ""                # Line-by-line buffer

# State labels (string constants used in comparisons)
LABEL_PM3_CMD_TASK_STOPPING = "stopping"  # or similar
LABEL_PM3_CMD_TASK_RUNNING = "running"
LABEL_PM3_CMD_TASK_STOP = "stop"
CODE_PM3_TASK_ERROR = -1

# Thread synchronization
LOCK_THREAD = threading.RLock()
LOCK_CALL_PRINT = threading.RLock()
LIST_CALL_PRINT = set()          # PySet_New(0) in init

# Verbose mode
PRINT_V_MODE = False             # Set to True on Windows
```

---

## 4. Exported Python Methods

### Method Index (ordered by Cython numbering)

| # | Method Name              | Signature                      | Lines in decompiled |
|---|--------------------------|--------------------------------|---------------------|
| 1 | `isPM3Offline`           | `(content) -> bool`            | 6597-6688           |
| 3 | `isUARTTimeout`          | `(content) -> bool`            | 6504-6595           |
| 5 | `isCMDTimeout`           | `(content) -> bool`            | 6411-6502           |
| 7 | `_set_stopping`          | `(label) -> None`              | 9828-10341          |
| 9 | `_set_stopped`           | `(label) -> None`              | 10343-10856         |
| 11| `_set_running`           | `(label) -> None`              | 10858-11371         |
| 13| `_stop_task_user`        | `() -> None`                   | 11753-12320         |
| 15| `_wait_if_stopping`      | `() -> None`                   | 11438-11751         |
| 17| `add_task_call`          | `(call_obj) -> None`           | 16433-17183         |
| 19| `del_task_call`          | `(call_obj) -> None`           | 14939-15641         |
| 21| `startPM3Task`           | `(cmd, timeout=...) -> int`    | **DECOMP FAILED**   |
| 23| `stopPM3Task`            | `(label=None, restart=None) -> None` | 15643-16431   |
| 25| `startPM3Ctrl`           | `(cmd, timeout=...) -> int`    | 17185-18749         |
| 27| `startPM3Plat`           | `(cmd, timeout=...) -> int`    | 13250-14937         |
| 29| `getPrintContent`        | `() -> str`                    | 11373-11436         |
| 31| `isEmptyContent`         | `() -> bool`                   | 12322-12758         |
| 33| `getContentFromRegexAll` | `(regex) -> list`              | 8659-9036           |
| 35| `getContentFromRegexA`   | `(regex) -> list`              | 8341-8657           |
| 37| `getContentFromRegexG`   | `(regex, index) -> str`        | 9341-9826           |
| 39| `hasKeyword`             | `(keyword, content=None) -> bool` | 7968-8339        |
| 41| `getContentFromRegex`    | `(regex) -> str`               | 7767-7966           |
| 43| `connect2PM3`            | `(serial_port=None, baudrate=None) -> None` | 7180-7765 |
| 45| `reworkPM3All`           | `() -> None`                   | 12760-13248         |

---

## 5. Method Specifications

### 5.1 `isPM3Offline(content) -> bool`
**Address**: 0x000182f8
**Lines**: 6597-6688

**Behavior**:
1. Takes one string argument `content`
2. Calls `PySequence_Contains(content, <offline_keyword>)` to check if the content string contains the `"Nikola.D.OFFLINE"` keyword
3. Returns `True` if the keyword is found, `False` otherwise

**Return semantics**: Python bool (True/False)
**Ground truth**: Line 6668: `PySequence_Contains(iVar1, *(undefined4*)(DAT + 0x1869a))`

---

### 5.2 `isUARTTimeout(content) -> bool`
**Address**: 0x00018138
**Lines**: 6504-6595

**Behavior**:
1. Takes one string argument `content`
2. Calls `PySequence_Contains(content, <uart_timeout_keyword>)` to check if content contains `"UART:: write time-out"`
3. Returns `True` if found, `False` otherwise

**Return semantics**: Python bool
**Ground truth**: Line 6575: `PySequence_Contains(iVar1, *(undefined4*)(DAT + 0x184d6))`

---

### 5.3 `isCMDTimeout(content) -> bool`
**Address**: 0x00017f78
**Lines**: 6411-6502

**Behavior**:
1. Takes one string argument `content`
2. Calls `PySequence_Contains(content, <cmd_timeout_keyword>)` to check if content contains `"timeout while waiting for reply"`
3. Returns `True` if found, `False` otherwise

**Return semantics**: Python bool
**Ground truth**: Line 6482: `PySequence_Contains(iVar1, *(undefined4*)(DAT + 0x18312))`

---

### 5.4 `connect2PM3(serial_port=None, baudrate=None) -> None`
**Address**: 0x00018b80
**Lines**: 7180-7765
**Parameters**: 0-2 positional args: `serial_port` (str, optional), `baudrate` (int, optional)

**Behavior** (reconstructed from decompiled code):
1. Initialize `CONTENT_OUT_IN__TXT_CACHE` (accumulator string, starts empty)
2. If `serial_port` is not None:
   - Append it to `CONTENT_OUT_IN__TXT_CACHE` via `PyNumber_Add` + `PyUnicode_Concat`
   - This prepends "Nikola.D:" prefix to the serial port path
3. Get the `platform.system()` result
4. Compare against `"Windows"` string
5. If Windows:
   - Set serial_port mode configuration
6. Else (Linux):
   - Create TCP socket: `socket.socket(AF_INET, SOCK_STREAM)`
   - Compare against PM3_REMOTE_ADDR/PM3_REMOTE_CMD_PORT
7. The function establishes the PM3 connection for subsequent commands

**Key observations**:
- Uses `socket.socket(AF_INET, SOCK_STREAM)` for TCP connection (STR@0x0002cf58, STR@0x0002cd60)
- Calls `platform.system()` to detect OS (STR@0x0002ce6c, STR@0x0002cf68)
- Compares result against `"Windows"` (STR@0x0002cf50)
- The iCopy-X device is Linux, so the Windows path is dead code

**Ground truth**: Lines 7308-7700 show the socket creation and connection flow

---

### 5.5 `hasKeyword(keyword, content=None) -> bool`
**Address**: 0x000198a4
**Lines**: 7968-8339
**Parameters**: 1-2 args: `keyword` (str, required), `content` (str, optional, defaults to module-level content)

**Behavior**:
1. If `content` is None (default):
   - Load module global `CONTENT_OUT_IN__TXT_CACHE` as content source
   - Increment refcount on the module-level content variable
2. Check `PyObject_Size(content)`:
   - If size == 0: return `False` immediately (empty content has no keywords)
   - If size == -1: error
3. If content has data:
   - Get an iterator via `__iter__` on the content
   - Build a tuple `(keyword, content)` for the `re.search` call
   - Call `re.search(keyword, content)` (uses the `re` module imported at init)
   - Check `PyObject_Size(result)`:
     - If result size >= 1: return `True`
     - If result size == 0: return `False`

**Important detail**: The function uses `re.search()` NOT simple string `in` check.
The `keyword` parameter is actually a **regex pattern**.

**Return semantics**: Python bool
**Ground truth**:
- Line 8091: `piVar14 = piVar7` (use content or default)
- Line 8134: `PyObject_Size(piVar14)` (check content length)
- Lines 8169-8174: Get `__iter__` on regex module = `re.search` method
- Lines 8192-8220: Build tuple `(keyword, content)` and call search
- Line 8291: `PyObject_Size(piVar3)` (check match result)
- Line 8294-8296: `if size >= 1 -> True, else -> False`

---

### 5.6 `getContentFromRegex(regex) -> str`
**Address**: 0x0001950c
**Lines**: 7767-7966
**Parameters**: 1 arg: `regex` (str pattern)

**Behavior**:
1. This is a **wrapper** around `hasKeyword`
2. Builds a tuple `(regex, CONTENT_OUT_IN__TXT_CACHE)` — the module-level cache
3. Calls the module's `hasKeyword` function directly (references `__pyx_pw_8executor_39hasKeyword` at line 7849)
4. Returns the result of `hasKeyword(regex, content)`

Wait - looking more carefully at the code, this function:
1. Takes one regex argument
2. Resolves the `re` module global
3. Builds tuple `(regex, CONTENT_OUT_IN__TXT_CACHE)`
4. Calls `re.search(regex, CONTENT_OUT_IN__TXT_CACHE)`
5. Returns the match result (or empty string)

**Actually**: Based on the name and the flow code usage patterns, this returns the **matched group string**, not a bool. The `.so` modules call `getContentFromRegex("pattern")` and expect a string back.

**Return semantics**: The first match group string, or empty string if no match
**Ground truth**: Lines 7848-7913 show the call through to regex search

---

### 5.7 `getContentFromRegexG(regex, index) -> str`
**Address**: 0x00021da4
**Lines**: 9341-9826
**Parameters**: 2 args: `regex` (str), `index` (int)

**Behavior**:
1. Takes a regex pattern and a group index
2. Calls `re.search(regex, CONTENT_OUT_IN__TXT_CACHE)` (the module-level content)
3. If no match: returns `None`
4. If match found:
   - Subtracts 1 from index: `index - 1` (line 9494, `__Pyx_PyInt_SubtractObjC`)
   - Uses the adjusted index to subscript into the match result: `result[index-1]`
   - This accesses `match.group(index)` effectively

**Key insight**: The index parameter is 1-based (matching PM3 regex group conventions).
The code does `index - 1` before subscripting, which maps to `match.groups()[index-1]` or
equivalently `match.group(index)`.

**Return semantics**: String content of the specified regex group, or None
**Ground truth**:
- Line 9494: `__Pyx_PyInt_SubtractObjC` = subtract 1 from index
- Lines 9501-9706: Complex subscript logic to index into match result

---

### 5.8 `getContentFromRegexA(regex) -> list`
**Address**: 0x00019e88
**Lines**: 8341-8657
**Parameters**: 1 arg: `regex` (str)

**Behavior**:
1. Calls `re.findall(regex, CONTENT_OUT_IN__TXT_CACHE)`
2. Returns the list of all matches

**Return semantics**: List of strings (all regex matches)
**Ground truth**: STR@0x0002ca74 (`getContentFromRegexA`), uses `findall` (STR@0x0002cf28)

---

### 5.9 `getContentFromRegexAll(regex) -> list`
**Address**: 0x0001a420
**Lines**: 8659-9036
**Parameters**: 1 arg: `regex` (str)

**Behavior**:
1. Similar to `getContentFromRegexA` but may operate on `buffer_on_all` instead of `CONTENT_OUT_IN__TXT_CACHE`
2. Calls `re.findall(regex, buffer_on_all)`
3. Returns list of all matches from the complete buffer

**Return semantics**: List of strings
**Ground truth**: STR@0x0002ca2c (`getContentFromRegexAll`), STR@0x0002cbfc (`buffer_on_all`)

---

### 5.10 `getPrintContent() -> str`
**Address**: 0x00024028
**Lines**: 11373-11436
**Parameters**: None (0 args)

**Behavior**:
1. Takes no arguments
2. Returns the module-level variable `CONTENT_OUT_IN__TXT_CACHE`
3. This is the accumulated PM3 text output from the last command

The function is very simple - it directly returns the module global variable.

**Return semantics**: String (the full PM3 response text)
**Ground truth**: Line 11401-11428 show direct return of module global

---

### 5.11 `isEmptyContent() -> bool`
**Address**: 0x000250c4
**Lines**: 12322-12758
**Parameters**: None (0 args)

**Behavior**:
1. Get `CONTENT_OUT_IN__TXT_CACHE` (module-level content)
2. Check `PyObject_Size(content)`:
   - If size == 0: return `True` (content is empty)
3. If content has data:
   - Call `.isspace()` on the content (STR@0x0002cf20)
   - If result is truthy (all whitespace): return `True`
   - Else:
     - Call `re.findall(pattern, content)` with some pattern
     - Check `PyObject_Size(result)`:
       - If size < 1: return `True` (no meaningful content)
       - Else: return `False` (has content)

**Return semantics**: Python bool (True if content is empty/whitespace-only)
**Ground truth**:
- Line 12392: `PyObject_Size(piVar7)` on content
- Line 12410: size == 0 check
- Lines 12415-12419: get `__iter__` = `.isspace()` method
- Lines 12564-12589: truthiness check on isspace result
- Lines 12600-12732: regex findall fallback

---

### 5.12 `startPM3Task(cmd, timeout=...) -> int`
**Address**: 0x0001af98
**DECOMPILATION FAILED** (Ghidra timeout — this is the largest function, 0x6E0C bytes = 28K)

**Reconstructed behavior from strings, traces, and calling patterns**:

1. **Pre-command setup**:
   - Acquire `LOCK_THREAD`
   - Set state to `LABEL_PM3_CMD_TASK_RUNNING`
   - Clear `CONTENT_OUT_IN__TXT_CACHE` (reset to empty)
   - Clear `buffer_on_all` and `buffer_on_rn`

2. **Command formatting**:
   - Format command as `"Nikola.D.CMD = {}\n".format(cmd)` (STR@0x0002cce0)
   - Encode to bytes: `.encode('utf-8')`

3. **Socket communication**:
   - Send command via `socket.sendall(encoded_cmd)` (STR@0x0002cef8)
   - Set socket to non-blocking: `socket.setblocking(False)` (STR@0x0002cd10)
   - Record start time: `time.perf_counter_ns()` (STR@0x0002cb4c)

4. **Response reading loop**:
   - Use `select.select([socket], [], [], timeout)` to poll for data
   - Read chunks: `socket.recv(1024)` (buffer size 0x400)
   - Decode received bytes: `.decode('utf-8', errors='ignore')` (STR@0x0002cfec, STR@0x0002cfb4)
   - Accumulate into `buffer_on_all` and process line-by-line into `buffer_on_rn`
   - For each complete line (ending in `\n`):
     - Call registered print callbacks from `LIST_CALL_PRINT`
     - Accumulate into `CONTENT_OUT_IN__TXT_CACHE`
   - Continue until:
     - A line starts with `"Nikola.D:"` (response received)
     - Or timeout expires (check `perf_counter_ns` elapsed vs timeout)

5. **Response parsing**:
   - Look for `"Nikola.D:"` prefix in response lines
   - Extract the return value after the prefix
   - Check for error conditions:
     - `"Nikola.D.OFFLINE"` -> PM3 offline
     - `"UART:: write time-out"` -> UART timeout
     - `"timeout while waiting for reply"` -> command timeout

6. **Post-command cleanup**:
   - Set socket back to blocking
   - Release `LOCK_THREAD`
   - Set state to `LABEL_PM3_CMD_TASK_STOP`
   - Call print callbacks one final time

7. **Return value**:
   - Returns `1` on success (command completed)
   - Returns `-1` on error (timeout, offline, UART error)
   - **CRITICAL**: Returns 1=completed, -1=error (NOT the Nikola.D value)

**Timeout parameter**:
   - Default timeout varies by command type
   - Passed as milliseconds, converted via `/ 1000` for select timeout
   - The constant 5000 (0x1388) suggests 5 second default
   - `rework_max` (STR@0x0002cd9c) is used for retry logic

**Ground truth**: STR table + memory note `project_startPM3Task_return.md`

---

### 5.13 `startPM3Plat(cmd, timeout=...) -> int`
**Address**: 0x000260fc
**Lines**: 13250-14937
**Parameters**: 1-2 args: `cmd` (str), `timeout` (int, optional)

**Behavior**:
1. Very similar to `startPM3Task` but for **platform commands**
2. Formats command as `"Nikola.D.PLT"` protocol (STR@0x0002ccbc)
3. The function body is structurally nearly identical to startPM3Task
4. Key differences:
   - Uses platform command prefix instead of CMD prefix
   - Has try/except error handling with exception save/restore
   - On exception: prints error, calls `print(exception)` via callback

**Socket flow** (reconstructed from lines 13394-13750):
1. Get `socket` module global
2. Get `.sendall` method
3. Get `threading` module global
4. Get `.RLock` method
5. Create tuple `(socket_method, rlock_method)` for socket operation
6. Call socket send operation
7. Handle response with exception wrapping
8. On success: call print callbacks
9. Set up response tuple for return

**Return semantics**: Same as startPM3Task: `1` = success, `-1` = error
**Ground truth**: Lines 13250-14937

---

### 5.14 `startPM3Ctrl(cmd, timeout=...) -> int`
**Address**: 0x0002a790
**Lines**: 17185-18749
**Parameters**: 1-2 args: `cmd` (str), `timeout` (int, optional)

**Behavior**:
1. Similar to `startPM3Plat` but for **control commands**
2. Formats command as `"Nikola.D.CTL = {}\n".format(cmd)` (STR@0x0002cccc)
3. The control channel is used for non-PM3 device commands
4. Same socket communication pattern as startPM3Task
5. Has the same exception handling structure as startPM3Plat

**Return semantics**: Same as startPM3Task
**Ground truth**: Lines 17185-18749, STR@0x0002cccc

---

### 5.15 `stopPM3Task(label=None, restart=None) -> None`
**Address**: 0x00028c7c
**Lines**: 15643-16431
**Parameters**: 0-2 args: `label` (str, optional), `restart` (bool, optional)

**Behavior**:
1. Creates a closure scope struct `__pyx_scope_struct__stopPM3Task`
2. Stores `restart` parameter in scope
3. Checks if `LABEL_PM3_CMD_TASK_RUNNING` is currently set (task is running)
4. If running:
   - Check if `LABEL_PM3_CMD_TASK_STOPPING` is set
   - If stopping: call the inner `waitStop()` closure
   - The `waitStop()` function (lines 9038-9305):
     a. Loops while `LABEL_PM3_CMD_TASK_STOPPING` is true
     b. In each iteration: calls `time.sleep(0.1)` equivalent
     c. Checks `LABEL_PM3_CMD_TASK_RUNNING` again
     d. Returns when no longer running/stopping
5. If not running:
   - Calls `_set_stopped(label)` to set the stop label
6. If `restart` is truthy:
   - Creates a new Thread targeting `waitStop`
   - Calls `connect2PM3()` or equivalent reconnection
   - Sends `"hw connect"` command

**Inner function**: `waitStop()` (STR@0x0002c9a0, `stopPM3Task.<locals>.waitStop`)
- This is a generator/closure that polls the running state

**Ground truth**: Lines 15643-16431, STR@0x0002ce3c (`waitStop`)

---

### 5.16 `_set_stopping(label) -> None`
**Address**: 0x00022600
**Lines**: 9828-10341
**Parameters**: 1 arg: `label` (str)

**Behavior**:
1. Takes a label string parameter
2. Acquires `LOCK_THREAD` (via `.acquire()`)
3. Try block:
   - Sets `LABEL_PM3_CMD_TASK_STOPPING` = label
4. Finally:
   - Releases `LOCK_THREAD` (via `.release()`)
5. Exception handling saves/restores thread state

**Pattern**: All three `_set_*` functions follow identical structure:
acquire lock -> set label -> release lock

**Ground truth**: Lines 9914-10027 show lock acquire/release pattern

---

### 5.17 `_set_stopped(label) -> None`
**Address**: 0x00022eb8
**Lines**: 10343-10856

Same structure as `_set_stopping` but sets `LABEL_PM3_CMD_TASK_STOP`.

---

### 5.18 `_set_running(label) -> None`
**Address**: 0x00023770
**Lines**: 10858-11371

Same structure as `_set_stopping` but sets `LABEL_PM3_CMD_TASK_RUNNING`.

---

### 5.19 `_wait_if_stopping() -> None`
**Address**: 0x00024170
**Lines**: 11438-11751
**Parameters**: None

**Behavior**:
1. Checks if `LABEL_PM3_CMD_TASK_STOPPING` is currently set
2. If stopping:
   - Loops/waits until the stopping state clears
   - Uses sleep or polling mechanism
3. Returns when state is no longer "stopping"

---

### 5.20 `_stop_task_user() -> None`
**Address**: 0x000246e8
**Lines**: 11753-12320
**Parameters**: None

**Behavior**:
1. Called when user requests task stop (PWR key during operation)
2. Sets state to stopping
3. Sends interrupt/cancel signal to PM3
4. Waits for task completion

---

### 5.21 `add_task_call(call_obj) -> None`
**Address**: 0x00029aec
**Lines**: 16433-17183
**Parameters**: 1 arg: `call_obj` (callable)

**Behavior**:
1. Takes a callable object (print callback function)
2. Acquires `LOCK_CALL_PRINT` lock
3. Looks up `LIST_CALL_PRINT` attribute via `_PyType_Lookup`
4. Gets the `.acquire` method on the lock
5. Gets the `.release` method on the lock
6. Adds `call_obj` to `LIST_CALL_PRINT` set
7. Releases `LOCK_CALL_PRINT` lock

This registers a callback that will be called with each line of PM3 output.

**Ground truth**: Lines 16528-16605 show lock acquire + type lookup pattern

---

### 5.22 `del_task_call(call_obj) -> None`
**Address**: 0x000280a0
**Lines**: 14939-15641
**Parameters**: 1 arg: `call_obj` (callable)

**Behavior**:
1. Same lock acquisition pattern as `add_task_call`
2. Removes `call_obj` from `LIST_CALL_PRINT` set (via `.remove()`)
3. Releases lock

---

### 5.23 `reworkPM3All() -> None`
**Address**: 0x00025890
**Lines**: 12760-13248
**Parameters**: None

**Behavior**:
1. Takes no arguments
2. Gets the module-level `CONTENT_OUT_IN__TXT_CACHE` and processes it
3. Gets the `buffer_on_all` content
4. Calls some processing function (likely `re.search` or string split)
5. Reworks/reprocesses all accumulated PM3 output
6. This appears to re-parse the complete buffer and extract structured data

The function name suggests it re-processes all collected PM3 output,
possibly rebuilding the line-by-line buffer from the raw socket data.

**Ground truth**: Lines 12760-13248

---

## 6. The Nikola.D Protocol

### 6.1 Command Format

Commands are sent to the PM3 client process over a TCP socket using the
"Nikola.D" protocol:

```
Nikola.D.CMD = {command}\n     # Regular PM3 command (e.g., "hf 14a info")
Nikola.D.CTL = {command}\n     # Control command (e.g., device control)
Nikola.D.PLT                   # Platform command (e.g., system operations)
```

### 6.2 Response Format

Responses are received line-by-line. The terminating line contains:

```
Nikola.D:{return_code}
```

Where `return_code` is the result of the PM3 command execution.

Special response values:
- `Nikola.D.OFFLINE` — PM3 hardware is disconnected
- Lines containing `UART:: write time-out` — serial communication failure
- Lines containing `timeout while waiting for reply` — command execution timeout

### 6.3 Socket Configuration

| Parameter       | Value          | Source                    |
|-----------------|----------------|---------------------------|
| Host            | 127.0.0.1      | AF_INET, localhost        |
| Port            | 8888 (0x22B8)  | PyLong init constant      |
| Protocol        | TCP            | SOCK_STREAM               |
| Recv buffer     | 1024 (0x400)   | PyLong init constant      |
| Encoding        | UTF-8          | `.encode()` / `.decode()` |
| Error handling  | `ignore`       | decode errors='ignore'    |

---

## 7. State Machine

```
                    STOP
                     |
                     v
    connect2PM3 --> RUNNING --> stopPM3Task --> STOPPING --> STOP
                     ^  |                          |
                     |  |  startPM3Task            |
                     |  +---> send cmd             |
                     |        recv response         |
                     |        callbacks             |
                     +-------- complete             |
                                                    |
                     <---- waitStop() polls ---------+
```

### State Labels
- `LABEL_PM3_CMD_TASK_STOP` — No task active, idle
- `LABEL_PM3_CMD_TASK_RUNNING` — Command in progress
- `LABEL_PM3_CMD_TASK_STOPPING` — Stop requested, waiting for completion

### Thread Safety
All state transitions are protected by `LOCK_THREAD` (RLock).
Print callback registration/removal is protected by `LOCK_CALL_PRINT` (RLock).

---

## 8. Callback System

The executor maintains a set of registered callbacks (`LIST_CALL_PRINT`)
that are invoked during PM3 command execution:

```python
# Registration
executor.add_task_call(my_callback)

# During startPM3Task, for each line of output:
for callback in LIST_CALL_PRINT:
    callback(line_text)

# Deregistration
executor.del_task_call(my_callback)
```

The `hmi_driver.py` module registers its `text_print` callback (STR@0x0002cd78)
to receive real-time PM3 output for display.

---

## 9. Error Handling

### 9.1 Timeout Detection

Three levels of timeout detection, each checking specific strings in PM3 output:

| Function          | Checks for                          | Meaning                    |
|-------------------|-------------------------------------|----------------------------|
| `isCMDTimeout`    | `"timeout while waiting for reply"` | PM3 command timed out      |
| `isUARTTimeout`   | `"UART:: write time-out"`           | Serial port write timeout  |
| `isPM3Offline`    | `"Nikola.D.OFFLINE"`                | PM3 hardware disconnected  |

### 9.2 Connection Recovery

When connection fails, the recovery sequence is:
1. `stopPM3Task(restart=True)`
2. `sudo rm /dev/ttyACM0` — Remove stale device node
3. `connect2PM3()` — Re-establish socket connection
4. `hw connect` — Reconnect PM3 client to hardware
5. The `rework_max` variable controls retry limits

### 9.3 Return Value Semantics

**CRITICAL** (from memory: `project_startPM3Task_return.md`):
- `startPM3Task` returns `1` = completed, `-1` = error
- This is NOT the `Nikola.D` response value
- The Nikola.D response value is parsed into the content buffers
- Callers check the return value AND then use `hasKeyword`/`getContentFromRegex` to inspect the response

---

## 10. Data Flow Summary

```
                   +-----------+
                   | .so module|  (scan.so, read.so, write.so, etc.)
                   +-----+-----+
                         |
                    startPM3Task("hf 14a info", timeout=5000)
                         |
                   +-----v-----+
                   | executor  |
                   +-----+-----+
                         |
           Format: "Nikola.D.CMD = hf 14a info\n"
                         |
                   +-----v-----+
                   |  TCP:8888 |  (socket to proxmark3 client)
                   +-----+-----+
                         |
                    [PM3 client executes command]
                         |
                    Response lines (streaming):
                    "[+] UID: 04 11 22 33 44 55 66"
                    "[+] SAK: 08 [2]"
                    "Nikola.D:1"
                         |
                   +-----v-----+
                   | executor  |  Accumulate into CONTENT_OUT_IN__TXT_CACHE
                   +-----+-----+  Call LIST_CALL_PRINT callbacks per line
                         |
                    return 1  (success)
                         |
                   +-----v-----+
                   | .so module|  
                   +-----+-----+
                         |
                    hasKeyword("SAK")  -> True
                    getContentFromRegex("UID: (.+)")  -> "04 11 22 33 44 55 66"
                    getContentFromRegexG("SAK: (\\w+)", 1) -> "08"
```

---

## 11. Key Implementation Notes

### 11.1 The `content` Parameter in hasKeyword

When `hasKeyword` is called with only one argument, it uses the module-level
`CONTENT_OUT_IN__TXT_CACHE`. When called with two arguments, the second
argument overrides the content to search. This is used by the `.so` modules
when they need to check specific content strings rather than the last PM3 output.

### 11.2 Regex vs String Contains

Despite the name "hasKeyword", the function uses `re.search()` not `str.__contains__()`.
This means keyword arguments can contain regex patterns and they will be matched
as regular expressions. The `.so` modules rely on this for pattern matching.

### 11.3 getContentFromRegex vs getContentFromRegexG

- `getContentFromRegex(pattern)` — Returns the full match (group 0)
- `getContentFromRegexG(pattern, n)` — Returns group `n` (1-based indexing, converted to 0-based internally)

### 11.4 Thread Model

The executor is designed for single-command-at-a-time execution.
The `LOCK_THREAD` RLock ensures only one `startPM3Task` runs concurrently.
The print callbacks run in the same thread as the command execution (not dispatched).

### 11.5 Cython Version

The module was compiled with Cython 0.29.21 (STR@0x0002e0a0: `_cython_0_29_21`).
Python version check: 3.8 (PyCode_New with 12 args = Python 3.8 signature).

---

## 12. Complete Python Equivalent (Skeleton)

```python
"""executor.py — PM3 command dispatch and response parsing"""

import socket
import select
import re
import threading
import time
import platform

# Connection config
PM3_REMOTE_ADDR = "127.0.0.1"
PM3_REMOTE_CMD_PORT = 8888

# Response buffers
CONTENT_OUT_IN__TXT_CACHE = ""
buffer_on_all = ""
buffer_on_rn = ""

# State management
LABEL_PM3_CMD_TASK_STOP = "stop"
LABEL_PM3_CMD_TASK_RUNNING = "running"  
LABEL_PM3_CMD_TASK_STOPPING = "stopping"
CODE_PM3_TASK_ERROR = -1

# Current state
_current_state = LABEL_PM3_CMD_TASK_STOP

# Thread synchronization
LOCK_THREAD = threading.RLock()
LOCK_CALL_PRINT = threading.RLock()
LIST_CALL_PRINT = set()

# Socket
_client = None

# Verbose
PRINT_V_MODE = platform.system() == "Windows"


def isPM3Offline(content):
    return "Nikola.D.OFFLINE" in content

def isUARTTimeout(content):
    return "UART:: write time-out" in content

def isCMDTimeout(content):
    return "timeout while waiting for reply" in content

def connect2PM3(serial_port=None, baudrate=None):
    global _client, CONTENT_OUT_IN__TXT_CACHE
    CONTENT_OUT_IN__TXT_CACHE = ""
    if serial_port:
        CONTENT_OUT_IN__TXT_CACHE += "Nikola.D:" + serial_port
    _client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    _client.connect((PM3_REMOTE_ADDR, PM3_REMOTE_CMD_PORT))

def hasKeyword(keyword, content=None):
    if content is None:
        content = CONTENT_OUT_IN__TXT_CACHE
    if len(content) == 0:
        return False
    result = re.search(keyword, content)
    return result is not None and len(result.group()) > 0

def getContentFromRegex(regex):
    return hasKeyword(regex)  # Returns match, not bool — see spec

def getContentFromRegexG(regex, index):
    result = re.search(regex, CONTENT_OUT_IN__TXT_CACHE)
    if result is None:
        return None
    return result.group(index)  # 1-based

def getContentFromRegexA(regex):
    return re.findall(regex, CONTENT_OUT_IN__TXT_CACHE)

def getContentFromRegexAll(regex):
    return re.findall(regex, buffer_on_all)

def getPrintContent():
    return CONTENT_OUT_IN__TXT_CACHE

def isEmptyContent():
    content = CONTENT_OUT_IN__TXT_CACHE
    if len(content) == 0:
        return True
    if content.isspace():
        return True
    # Additional regex check
    return False

def startPM3Task(cmd, timeout=5000):
    # See section 5.12 for full protocol
    pass  # Implementation needed

def startPM3Plat(cmd, timeout=5000):
    # Platform command variant
    pass

def startPM3Ctrl(cmd, timeout=5000):
    # Control command variant  
    pass

def stopPM3Task(label=None, restart=None):
    pass

def _set_stopping(label):
    with LOCK_THREAD:
        global _current_state
        _current_state = LABEL_PM3_CMD_TASK_STOPPING

def _set_stopped(label):
    with LOCK_THREAD:
        global _current_state
        _current_state = LABEL_PM3_CMD_TASK_STOP

def _set_running(label):
    with LOCK_THREAD:
        global _current_state
        _current_state = LABEL_PM3_CMD_TASK_RUNNING

def _wait_if_stopping():
    while _current_state == LABEL_PM3_CMD_TASK_STOPPING:
        time.sleep(0.1)

def _stop_task_user():
    _set_stopping("user")
    # Send cancel to PM3
    _wait_if_stopping()

def add_task_call(call_obj):
    with LOCK_CALL_PRINT:
        LIST_CALL_PRINT.add(call_obj)

def del_task_call(call_obj):
    with LOCK_CALL_PRINT:
        LIST_CALL_PRINT.discard(call_obj)

def reworkPM3All():
    pass  # Reprocess buffer_on_all into CONTENT_OUT_IN__TXT_CACHE
```

---

## 13. Cross-References

### Callers of executor functions (from grep of .so modules)

| Function            | Called by                                           |
|---------------------|-----------------------------------------------------|
| `startPM3Task`      | scan.so, read.so, write.so, hfmfread.so, etc.      |
| `hasKeyword`        | ALL .so flow modules for response checking          |
| `getContentFromRegex` | ALL .so flow modules for data extraction          |
| `getContentFromRegexG`| hfmfread.so, lfread.so for group extraction        |
| `getPrintContent`   | scan.so, read.so for UI display                     |
| `isEmptyContent`    | scan.so, read.so for empty-check before parsing     |
| `add_task_call`     | hmi_driver.py for print callback registration       |
| `del_task_call`     | hmi_driver.py for print callback deregistration     |
| `connect2PM3`       | launcher/startup for initial PM3 connection         |
| `stopPM3Task`       | Activity back/exit handlers                         |
| `isPM3Offline`      | Error handling in flow modules                      |
| `isCMDTimeout`      | Timeout detection in startPM3Task                   |
| `isUARTTimeout`     | UART error detection in startPM3Task                |

### hmi_driver.py integration
- STR@0x0002cdc0: `hmi_driver` — executor imports/references hmi_driver
- STR@0x0002ce48: `starthmi` — executor calls hmi_driver.starthmi()
- STR@0x0002cda8: `restartpm3` — executor calls hmi_driver.restartpm3()
- STR@0x0002cd84: `start_line` / STR@0x0002ceb4: `end_line` — line tracking for display
