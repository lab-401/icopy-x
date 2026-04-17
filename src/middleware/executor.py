##########################################################################
# Required Notice: Copyright ETOILE401 SAS (http://www.lab401.com)
#
# Initial author: ETOILE401 SAS & https://github.com/quantum-x/ as of April 16, 2026
#
# Since this date, each contribution is under the copyright of its respective author.
#
# Copyright of each contribution is tracked by the Git history. See the output of git shortlog -nse for a full list or git log --pretty=short --follow <path/to/sourcefile> |git shortlog -ne to track a specific file.
#
# A mailmap is maintained to map author and committer names and email addresses to canonical names and email addresses.
# If by accident a copyright was removed from a file and is not directly deducible from the Git history, please submit a PR.
#
#
# This software is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this software for commercial purposes.
#
# A copy of the license is available at:
# https://polyformproject.org/licenses/noncommercial/1.0.0
#
# This entire header "Required Notice" must remain in place.
##########################################################################

"""executor — PM3 command executor via TCP to RemoteTaskManager.

Transliterated from executor.so (iCopy-X v1.0.90, Cython 0.29.21, ARM 32-bit).

Ground truth:
    Strings:    docs/v1090_strings/executor_strings.txt
    Traces:     docs/Real_Hardware_Intel/trace_scan_flow_20260331.txt
                docs/Real_Hardware_Intel/trace_lf_scan_flow_20260331.txt
    Spec:       docs/middleware-integration/1-executor_spec.md

Architecture:
    [executor] --TCP:8888--> [RemoteTaskManager] --stdin--> [PM3 subprocess]
    [executor] <--TCP:8888-- [RemoteTaskManager] <--stdout-- [PM3 subprocess]

Module-level function library (no classes), matching original .so interface.

Behavioral notes (from binary analysis + QEMU verification):
    - hasKeyword uses re.search (PyTuple_New(2) + PyObject_Call at 0x198a4)
    - isEmptyContent: '' -> False, whitespace-only -> True (counter-intuitive)
    - getContentFromRegex returns LAST capturing group via m.lastindex
    - getContentFromRegexAll returns FIRST element of re.findall (despite name)
    - getContentFromRegexG group=0 -> last group (same as getContentFromRegex)
    - startPM3Task returns 1=completed, -1=error (NOT the Nikola.D value)
    - isPM3Offline/isCMDTimeout/isUARTTimeout take a `lines` arg (not from cache)
"""

import logging
import re
import select
import socket
import threading
import time

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# PM3 output cleanup — always-on, independent of pm3_compat.
#
# These strip ANSI color codes and RRG/Iceman structural noise ([+] prefixes,
# echo lines, EOR markers) so middleware regex patterns work correctly.
# This is PM3 protocol cleanup, NOT compatibility logic — needed on all
# firmware versions.  Lives here so pm3_compat.py can be deleted when
# legacy firmware support is no longer needed.
# ---------------------------------------------------------------------------
_ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')
_RE_ECHO_LINE = re.compile(r'^\[usb\|script\]\s*pm3\s*-->.*\n?', re.MULTILINE)
_RE_EOR_MARKER = re.compile(r'^pm3\s+-->\s*\n?', re.MULTILINE)
_RE_SECTION_HEADER = re.compile(
    r'^\[=\]\s*-{3,}.*-{3,}\s*\n?', re.MULTILINE)
_RE_BARE_INFO = re.compile(r'^\[=\]\s*$\n?', re.MULTILINE)
_RE_LINE_PREFIX = re.compile(
    r'^\[(?:\+|=|#|!!?|\-|/|\\|\|)\]\s?', re.MULTILINE)


def _clean_pm3_output(text):
    """Strip ANSI codes and RRG/Iceman output noise from PM3 response.

    Removes:
      - ANSI color/formatting escape sequences
      - [usb|script] pm3 --> echo lines (command echo from piped stdin)
      - Bare "pm3 -->" EOR markers (iCopy-X completion patch)
      - [=] section header/separator lines
      - [+]/[=]/[#]/[!!] line prefix markers (PrintAndLogEx prefixes)

    Always runs regardless of firmware version or pm3_compat availability.
    """
    if not text:
        return text
    text = _ANSI_RE.sub('', text)
    text = _RE_ECHO_LINE.sub('', text)
    text = _RE_EOR_MARKER.sub('', text)
    text = _RE_SECTION_HEADER.sub('', text)
    text = _RE_BARE_INFO.sub('', text)
    text = _RE_LINE_PREFIX.sub('', text)
    return text


# ---------------------------------------------------------------------------
# Optional dependency: hmi_driver (for reworkPM3All restart cycle)
# Source: executor_strings.txt — "hmi_driver", "restartpm3"
# ---------------------------------------------------------------------------
try:
    import hmi_driver
except ImportError:
    hmi_driver = None

# ---------------------------------------------------------------------------
# PM3 command compatibility layer — translates old-syntax commands and
# strips ANSI color codes from RRG/Iceman PM3 output.
# ---------------------------------------------------------------------------
try:
    import pm3_compat
except ImportError:
    pm3_compat = None

# ---------------------------------------------------------------------------
# Constants — from binary analysis + executor_strings.txt
# ---------------------------------------------------------------------------
# executor_ghidra_raw.txt: 0x22B8 = 8888
CODE_PM3_TASK_ERROR = -1
PM3_REMOTE_ADDR = '127.0.0.1'
PM3_REMOTE_CMD_PORT = 8888
PRINT_V_MODE = True

# ---------------------------------------------------------------------------
# Module-level state — from binary analysis (module global slots)
# ---------------------------------------------------------------------------
CONTENT_OUT_IN__TXT_CACHE = ''
LABEL_PM3_CMD_TASK_RUNNING = False
LABEL_PM3_CMD_TASK_STOP = True       # starts True (no task running at init)
LABEL_PM3_CMD_TASK_STOPPING = False
LIST_CALL_PRINT = set()
LOCK_CALL_PRINT = threading.RLock()
LOCK_THREAD = threading.RLock()

# ---------------------------------------------------------------------------
# Internal TCP socket
# ---------------------------------------------------------------------------
_socket_instance = None

# Pipeline cleanup flag — set when a PM3 command is interrupted
# (stopPM3Task during active recv), indicating stale data may be
# in the TCP socket buffer.  Checked at the start of startPM3Task.
_pipeline_needs_cleanup = False

# Cumulative rework tracking — fast-fail when PM3 is genuinely unresponsive.
# Incremented on every reworkPM3All(), reset on any successful command.
# When the count reaches MAX_CONSECUTIVE_REWORKS, subsequent startPM3Task
# calls skip reworks and return -1 immediately so flow state machines can
# abort gracefully instead of cascading through every fallback command.
MAX_CONSECUTIVE_REWORKS = 3
_consecutive_reworks = 0

# Nikola.D end-of-response regex — executor_strings.txt: "Nikola.D:"
_RE_NIKOLA_END = re.compile(r'Nikola\.D:\s*-?\d+\s*$', re.MULTILINE)
# Alternative end marker — executor_strings.txt: "pm3 -->"
_RE_PROMPT_END = re.compile(r'pm3\s+-->\s*$', re.MULTILINE)

# ===========================================================================
# State management
# _set_running @0x16774, _set_stopped @0x167b8,
#             _set_stopping @0x167fc, _wait_if_stopping @0x16840
# ===========================================================================

def _set_running(status):
    global LABEL_PM3_CMD_TASK_RUNNING
    LABEL_PM3_CMD_TASK_RUNNING = status

def _set_stopped(status):
    global LABEL_PM3_CMD_TASK_STOP
    LABEL_PM3_CMD_TASK_STOP = status

def _set_stopping(status):
    global LABEL_PM3_CMD_TASK_STOPPING
    LABEL_PM3_CMD_TASK_STOPPING = status

def _wait_if_stopping():
    """Block until LABEL_PM3_CMD_TASK_STOPPING becomes False."""
    while LABEL_PM3_CMD_TASK_STOPPING:
        time.sleep(0.05)

def _stop_task_user():
    """Internal: force-stop from user request.
    Sets stopping flag, brief sleep for task to notice.
    """
    global LABEL_PM3_CMD_TASK_STOPPING
    LABEL_PM3_CMD_TASK_STOPPING = True
    time.sleep(0.1)

# ===========================================================================
# TCP communication
# ===========================================================================

def connect2PM3(serial_port=None, baudrate=None):
    """Connect to PM3 via RemoteTaskManager TCP socket.

    Creates AF_INET SOCK_STREAM to PM3_REMOTE_ADDR:PM3_REMOTE_CMD_PORT
    Strings: "hw connect"
    """
    global _socket_instance

    try:
        _socket_instance = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        _socket_instance.settimeout(5)
        _socket_instance.connect((PM3_REMOTE_ADDR, PM3_REMOTE_CMD_PORT))

        if serial_port is not None:
            connect_cmd = 'hw connect'
            if serial_port:
                connect_cmd += ' -p %s' % serial_port
            _send_raw(connect_cmd)

        return True
    except Exception:
        _socket_instance = None
        return False

def _ensure_pipeline_ready():
    """Pre-flight check: clean up dirty pipeline from an interrupted command.

    When a PM3 command is interrupted (stopPM3Task sets STOPPING while
    _send_and_cache is in its recv loop), the TCP connection may have stale
    response data from the command that was still in flight.

    Cleanup: close the old TCP connection (discards all stale data) and
    reconnect.  The new connection gets a fresh HandleServer thread in
    rftask.py.  If the previous command is still in flight in rftask
    (PM3 hardware stuck), the _cmd_lock in rftask._send_cmd provides a
    3-second timeout — if the lock can't be acquired, rftask auto-recovers
    by calling reworkManager() which restarts the PM3 subprocess via the
    GD32 restartpm3 command.

    This function runs at the start of startPM3Task, NOT during activity
    exit.  This avoids blocking the Tk main thread (the previous agent's
    reworkPM3All-in-onDestroy crash).
    """
    global _socket_instance, _pipeline_needs_cleanup

    if not _pipeline_needs_cleanup:
        return

    _pipeline_needs_cleanup = False
    logger.info('executor: pipeline cleanup — reconnecting')

    if _socket_instance is not None:
        try:
            _socket_instance.close()
        except Exception:
            pass
        _socket_instance = None

    connect2PM3()

def _send_raw(cmd):
    """Send a raw command string and read response (no caching, no callbacks).

    socket.sendall + recv(1024) loop.
    Recv buffer: 0x400 = 1024 bytes.
    """
    if _socket_instance is None:
        return ''

    try:
        _socket_instance.sendall((cmd + '\n').encode('utf-8'))

        buf = b''
        _socket_instance.settimeout(3.0)
        while True:
            try:
                chunk = _socket_instance.recv(1024)
                if not chunk:
                    break
                buf += chunk
                text = buf.decode('utf-8', errors='ignore')
                if _RE_NIKOLA_END.search(text) or _RE_PROMPT_END.search(text):
                    break
                _socket_instance.settimeout(1.0)
            except socket.timeout:
                break

        return buf.decode('utf-8', errors='ignore')
    except Exception:
        return ''

def _send_and_cache(cmd, timeout=5888):
    """Send command, cache result in CONTENT_OUT_IN__TXT_CACHE, fire callbacks.

    Formats via Nikola.D.CMD, accumulates in cache, fires
    LIST_CALL_PRINT callbacks per line.
    Strings: "Nikola.D.CMD = {}", "Nikola.D:", "timeout while waiting for reply"
    """
    global CONTENT_OUT_IN__TXT_CACHE, _pipeline_needs_cleanup

    result = ''
    if _socket_instance is None:
        CONTENT_OUT_IN__TXT_CACHE = result
        return result

    try:
        # Translate command for current PM3 firmware version (old→new syntax)
        translated_cmd = cmd
        if pm3_compat is not None:
            try:
                translated_cmd = pm3_compat.translate(cmd)
            except Exception:
                translated_cmd = cmd
        wire_cmd = 'Nikola.D.CMD = %s\n' % translated_cmd
        timeout_sec = timeout / 1000.0 if timeout > 0 else None
        _socket_instance.settimeout(timeout_sec)
        _socket_instance.sendall(wire_cmd.encode('utf-8'))

        buf = b''
        while True:
            if LABEL_PM3_CMD_TASK_STOPPING:
                _pipeline_needs_cleanup = True
                break
            try:
                # Use select for timeout=-1 (infinite) case
                if timeout_sec is None:
                    readable, _, _ = select.select([_socket_instance], [], [], 0.5)
                    if not readable:
                        continue
                chunk = _socket_instance.recv(1024)
                if not chunk:
                    break
                buf += chunk

                # Fire callbacks per line
                text = buf.decode('utf-8', errors='ignore')
                with LOCK_CALL_PRINT:
                    for cb in list(LIST_CALL_PRINT):
                        try:
                            cb(text)
                        except Exception:
                            pass

                # Check for end-of-response
                if _RE_NIKOLA_END.search(text) or _RE_PROMPT_END.search(text):
                    break
            except socket.timeout:
                result = 'timeout while waiting for reply'
                CONTENT_OUT_IN__TXT_CACHE = result
                return result

        result = buf.decode('utf-8', errors='ignore')

    except socket.timeout:
        result = 'timeout while waiting for reply'
    except Exception:
        result = ''

    # Always: strip ANSI codes and PM3 output noise so middleware
    # regex patterns (hasKeyword, getContentFromRegex) match correctly.
    # This runs unconditionally — independent of pm3_compat availability.
    if result:
        result = _clean_pm3_output(result)

    # Optional: compatibility-layer response normalization.
    # Only active when pm3_compat.py exists and legacy compat is enabled.
    if pm3_compat is not None and result:
        try:
            result = pm3_compat.translate_response(result, translated_cmd)
        except Exception:
            pass

    CONTENT_OUT_IN__TXT_CACHE = result
    return result

def _send_ctrl(cmd, timeout=5888):
    """Send a control command via Nikola.D.CTL channel.

    startPM3Ctrl uses "Nikola.D.CTL = {}" format.
    Strings: "Nikola.D.CTL = {}"
    """
    global CONTENT_OUT_IN__TXT_CACHE

    if _socket_instance is None:
        CONTENT_OUT_IN__TXT_CACHE = ''
        return ''

    try:
        wire_cmd = 'Nikola.D.CTL = %s\n' % cmd
        _socket_instance.settimeout(timeout / 1000.0)
        _socket_instance.sendall(wire_cmd.encode('utf-8'))

        buf = b''
        while True:
            try:
                chunk = _socket_instance.recv(1024)
                if not chunk:
                    break
                buf += chunk
                text = buf.decode('utf-8', errors='ignore')
                if _RE_NIKOLA_END.search(text) or _RE_PROMPT_END.search(text):
                    break
                _socket_instance.settimeout(1.0)
            except socket.timeout:
                break

        result = buf.decode('utf-8', errors='ignore')
        CONTENT_OUT_IN__TXT_CACHE = result
        return result
    except Exception:
        CONTENT_OUT_IN__TXT_CACHE = ''
        return ''

def _send_plat(cmd, timeout=5888):
    """Send a platform command via Nikola.D.PLT channel.

    startPM3Plat uses "Nikola.D.PLT = {}" format.
    Strings: "Nikola.D.PLT = {}"
    """
    global CONTENT_OUT_IN__TXT_CACHE

    if _socket_instance is None:
        CONTENT_OUT_IN__TXT_CACHE = ''
        return ''

    try:
        wire_cmd = 'Nikola.D.PLT = %s\n' % cmd
        _socket_instance.settimeout(timeout / 1000.0)
        _socket_instance.sendall(wire_cmd.encode('utf-8'))

        buf = b''
        while True:
            try:
                chunk = _socket_instance.recv(1024)
                if not chunk:
                    break
                buf += chunk
                text = buf.decode('utf-8', errors='ignore')
                if _RE_NIKOLA_END.search(text) or _RE_PROMPT_END.search(text):
                    break
                _socket_instance.settimeout(1.0)
            except socket.timeout:
                break

        result = buf.decode('utf-8', errors='ignore')
        CONTENT_OUT_IN__TXT_CACHE = result
        return result
    except Exception:
        CONTENT_OUT_IN__TXT_CACHE = ''
        return ''

# ===========================================================================
# PM3 task execution
# startPM3Task @0x1af98 (28KB, Ghidra timeout — reconstructed
#   from startPM3Plat/startPM3Ctrl + traces + archive)
# Returns: 1=completed, -1=error (memory: project_startPM3Task_return.md)
# ===========================================================================

def startPM3Task(cmd, timeout=5000, listener=None, rework_max=2):
    """Execute a PM3 command.

    startPM3Task @0x1af98
    Strings: "Nikola.D.CMD = {}", "Nikola.D.OFFLINE"
    Trace: all PM3 traces show (cmd, timeout, rework) pattern
    Returns: 1=completed, -1=error (NOT the Nikola.D value)
    """
    global CONTENT_OUT_IN__TXT_CACHE, _consecutive_reworks

    _wait_if_stopping()
    _ensure_pipeline_ready()

    # Fast-fail when PM3 has already been reworked MAX_CONSECUTIVE_REWORKS
    # times without a successful command in between — the tag is almost
    # certainly absent or unresponsive and further reworks just extend the
    # "Writing..." UI state.  The flow's state machine gets -1 and aborts.
    if _consecutive_reworks >= MAX_CONSECUTIVE_REWORKS:
        CONTENT_OUT_IN__TXT_CACHE = 'PM3 unresponsive after %d reworks' % _consecutive_reworks
        return CODE_PM3_TASK_ERROR

    if listener is not None:
        add_task_call(listener)

    _set_running(True)
    _set_stopped(False)

    success = False
    for attempt in range(rework_max + 1):
        if LABEL_PM3_CMD_TASK_STOPPING:
            break

        result = _send_and_cache(cmd, timeout)

        # Ground truth: when stopPM3Task() sets STOPPING, _send_and_cache
        # breaks its recv loop and returns partial/empty data.  This is NOT
        # a PM3 failure — do NOT rework.  Original trace shows ret=1 with
        # full simulation output after stop; reworking kills the connection
        # and loses the trace data (OSS trace: ret=-1 + rework cascade).
        if LABEL_PM3_CMD_TASK_STOPPING:
            break

        if result and not isPM3Offline(result) and not isCMDTimeout(result):
            success = True
            _consecutive_reworks = 0  # reset counter on any good response
            break

        if attempt < rework_max:
            if _consecutive_reworks + 1 >= MAX_CONSECUTIVE_REWORKS:
                # One more rework would hit the cap — do the rework so the
                # notification fires, then stop attempting.
                reworkPM3All()
                break
            reworkPM3All()

    _set_running(False)
    _set_stopped(True)

    if listener is not None:
        del_task_call(listener)

    return 1 if success else CODE_PM3_TASK_ERROR

def stopPM3Task(listener=None, wait=True):
    """Stop the current PM3 task.

    Sets STOPPING flag, optionally blocks until RUNNING=False.
    """
    _set_stopping(True)

    if wait:
        while LABEL_PM3_CMD_TASK_RUNNING:
            time.sleep(0.05)
        _set_stopping(False)
    else:
        _set_stopping(False)

    if listener is not None:
        del_task_call(listener)

def startPM3Ctrl(ctrl_cmd='', timeout=5888):
    """Send a control command to PM3.

    Uses Nikola.D.CTL channel, sets RUNNING/STOPPED state.
    Default timeout: 5888ms.
    Default ctrl_cmd='': original .so calls this without arguments from
    PCModeActivity.startPCMode() (activity_main_strings.txt:29912).
    """
    _set_running(True)
    _set_stopped(False)

    result = _send_ctrl(ctrl_cmd, timeout)

    _set_running(False)
    _set_stopped(True)
    return result

def startPM3Plat(plat_cmd, timeout=5888):
    """Send a platform command to PM3.

    Uses Nikola.D.PLT channel, sets RUNNING/STOPPED state.
    Default timeout: 5888ms.
    """
    _set_running(True)
    _set_stopped(False)

    result = _send_plat(plat_cmd, timeout)

    _set_running(False)
    _set_stopped(True)
    return result

def reworkPM3All():
    """Restart the entire PM3 system and reconnect.

    Calls hmi_driver.restartpm3(), closes socket, sleeps 3s, reconnects.
    Strings: "restartpm3", "hmi_driver"
    """
    global _socket_instance, _consecutive_reworks

    _consecutive_reworks += 1

    if hmi_driver is not None:
        try:
            hmi_driver.restartpm3()
        except Exception:
            pass

    if _socket_instance is not None:
        try:
            _socket_instance.close()
        except Exception:
            pass
        _socket_instance = None

    time.sleep(3)
    connect2PM3()

def resetReworkCount():
    """Reset the consecutive-rework counter and request pipeline cleanup.

    Called by flows that want a fresh budget (e.g. at the start of a new
    scan/read/write/erase activity).  The counter also resets automatically
    whenever a PM3 command returns a valid, non-timeout response.

    Additionally sets _pipeline_needs_cleanup so the next startPM3Task runs
    _ensure_pipeline_ready(), which closes and reconnects the TCP socket.
    This clears any stale responses queued in the buffer from a previous
    rework cascade or long-running command that got aborted without a
    stopPM3Task (e.g. when the user exits to the main menu during a chk).
    """
    global _consecutive_reworks, _pipeline_needs_cleanup
    _consecutive_reworks = 0
    _pipeline_needs_cleanup = True

# ===========================================================================
# Callback management
# add_task_call/del_task_call use LOCK_CALL_PRINT + set ops
# ===========================================================================

def add_task_call(call):
    """Register an output callback. Thread-safe via LOCK_CALL_PRINT."""
    with LOCK_CALL_PRINT:
        LIST_CALL_PRINT.add(call)

def del_task_call(call):
    """Unregister an output callback. Uses discard() (no KeyError)."""
    with LOCK_CALL_PRINT:
        LIST_CALL_PRINT.discard(call)

# ===========================================================================
# Content/output query functions
# All read from CONTENT_OUT_IN__TXT_CACHE module global
# ===========================================================================

def getPrintContent():
    """Return the cached output from the last command.

    Simple getter for CONTENT_OUT_IN__TXT_CACHE.
    """
    return CONTENT_OUT_IN__TXT_CACHE

def isEmptyContent():
    """Check if cached output is whitespace-only.

    Checks len(content.strip()) == 0 AND len(content) > 0.
    Truth table:
        ''     -> False  (empty string is NOT "empty" — counter-intuitive)
        ' '    -> True
        'a'    -> False
        '\\n'   -> True
    """
    if not CONTENT_OUT_IN__TXT_CACHE:
        return False
    return len(CONTENT_OUT_IN__TXT_CACHE.strip()) == 0

def getContentFromRegex(regex):
    """Search cached output with regex, return LAST capturing group.

    Uses re.search, returns m.group(m.lastindex).
    Returns '' (not None) on no match.
    """
    if not CONTENT_OUT_IN__TXT_CACHE:
        return ''
    m = re.search(regex, CONTENT_OUT_IN__TXT_CACHE)
    if m is None:
        return ''
    if m.lastindex is None:
        return ''
    return m.group(m.lastindex)

def getContentFromRegexA(regex):
    """Search cached output, return ALL matches via re.findall().

    Returns re.findall(regex, cache). Empty cache -> [].
    """
    if not CONTENT_OUT_IN__TXT_CACHE:
        return []
    result = re.findall(regex, CONTENT_OUT_IN__TXT_CACHE)
    if result is None:
        return []
    return result

def getContentFromRegexAll(regex):
    """Search cached output, return FIRST element from re.findall().

    Despite name "All", returns only results[0].
    getContentFromRegexA is the one that returns ALL matches.
    Empty/no-match -> [].
    """
    if not CONTENT_OUT_IN__TXT_CACHE:
        return []
    results = re.findall(regex, CONTENT_OUT_IN__TXT_CACHE)
    if not results:
        return []
    return results[0]

def getContentFromRegexG(regex, group):
    """Search cached output, return specific capturing group.

    group=0 means "last group" (same as getContentFromRegex).
    group=N returns m.group(N). 1-based indexing confirmed.
    """
    if not CONTENT_OUT_IN__TXT_CACHE:
        return ''
    m = re.search(regex, CONTENT_OUT_IN__TXT_CACHE)
    if m is None:
        return ''
    if group == 0:
        if m.lastindex is None:
            return ''
        return m.group(m.lastindex)
    try:
        return m.group(group)
    except (IndexError, re.error):
        return ''

def hasKeyword(keywords, line=None):
    """Check if keywords exist in cached output or a specific line.

    @0x198a4: uses re.search (confirmed: PyTuple_New(2) + PyObject_Call
    pattern, NOT PySequence_Contains which would indicate `in`).
    Checks PyObject_Size on content first — empty content returns False.
    """
    text = line if line is not None else CONTENT_OUT_IN__TXT_CACHE
    if not text:
        return False
    try:
        return re.search(keywords, text) is not None
    except re.error:
        # Fallback for invalid regex patterns — shouldn't happen with
        # known callers but guards against edge cases
        return keywords in text

# ===========================================================================
# Error detection
# Simple substring checks on the `lines` parameter
# Strings: "Nikola.D.OFFLINE", "timeout while waiting for reply",
#           "UART:: write time-out"
# ===========================================================================

def isPM3Offline(lines):
    """Check if PM3 is offline. Checks for 'Nikola.D.OFFLINE'."""
    if not lines:
        return False
    return 'Nikola.D.OFFLINE' in lines

def isCMDTimeout(lines):
    """Check for command timeout. Checks for 'timeout while waiting for reply'."""
    if not lines:
        return False
    return 'timeout while waiting for reply' in lines

def isUARTTimeout(lines):
    """Check for UART timeout. Checks for 'UART:: write time-out'."""
    if not lines:
        return False
    return 'UART:: write time-out' in lines
