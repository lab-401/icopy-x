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
import socket
import threading
from contextlib import contextmanager
from functools import wraps
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
# PM3/system status-phrase localization — translates recognized user-facing
# phrases into the active UI language (strict no-op on English).
# ---------------------------------------------------------------------------
try:
    import pm3_localize
except ImportError:
    pm3_localize = None

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

# A scan/read owns the socket AND the shared parser cache until it unwinds.
# Command-only locking would release the cache before protocol code parses it.
_operation_local = threading.local()
_owner_lock = threading.Lock()
_active_operation = None
_active_command = None


class PM3OperationCancelled(BaseException):
    """Unwind a cancelled protocol, including its broad ``except Exception``.

    Caught only at the Scanner/Reader operation boundary. Protocol finally
    blocks still run; this is not a transport failure or a reason to restart.
    """


def _check_operation():
    cancelled = getattr(_operation_local, 'cancelled', None)
    if cancelled is not None and cancelled.is_set():
        raise PM3OperationCancelled()


@contextmanager
def pm3_operation(cancelled):
    """Own PM3 across commands and parsing; waiting is cancellable off the UI.

    The caller supplies a per-run Event and catches PM3OperationCancelled.
    The hardware abort remains the caller's responsibility. An in-flight recv
    retains ownership until it returns; setting the Event never lends its
    socket to a new worker.
    """
    global _active_operation
    while not LOCK_THREAD.acquire(timeout=.05):
        if cancelled.is_set():
            raise PM3OperationCancelled()
    previous = getattr(_operation_local, 'cancelled', None)
    try:
        if previous is not None:
            raise RuntimeError('Nested PM3 operations are not supported')
        _operation_local.cancelled = cancelled
        with _owner_lock:
            _active_operation = cancelled
        _check_operation()
        yield
        _check_operation()
    finally:
        if previous is None:
            with _owner_lock:
                _active_operation = None
        _operation_local.cancelled = previous
        LOCK_THREAD.release()


def _serialized(function):
    """Serialize socket/cache mutations, including calls outside scan/read."""
    @wraps(function)
    def wrapped(*args, **kwargs):
        with LOCK_THREAD:
            _check_operation()
            return function(*args, **kwargs)
    return wrapped


def _command(function):
    """Keep cancellation attached to this command, not the next queued one."""
    @wraps(function)
    def wrapped(*args, **kwargs):
        global _active_command, _pipeline_needs_cleanup
        with LOCK_THREAD:
            _check_operation()
            done = threading.Event()
            with _owner_lock:
                if _active_command is not None:
                    raise RuntimeError('A PM3 response callback cannot start another command')
                _active_command = (threading.get_ident(), done)
                _set_stopping(False)
            try:
                result = function(*args, **kwargs)
                _check_operation()
                return result
            finally:
                with _owner_lock:
                    cancelled = getattr(_operation_local, 'cancelled', None)
                    if LABEL_PM3_CMD_TASK_STOPPING or (cancelled is not None and cancelled.is_set()):
                        _pipeline_needs_cleanup = True
                    _set_running(False)
                    _set_stopped(True)
                    _set_stopping(False)
                    _active_command = None
                    done.set()
    return wrapped

# ---------------------------------------------------------------------------
# Internal TCP socket
# ---------------------------------------------------------------------------
_socket_instance = None

# Pipeline cleanup flag — set when a PM3 command is interrupted
# (stopPM3Task during active recv), indicating stale data may be
# in the TCP socket buffer.  Checked at the start of startPM3Task.
_pipeline_needs_cleanup = False
# A reconnect alone cannot establish that the daemon finished the old command.
_pipeline_uncertain = False
RESPONSE_POLL_SECONDS = 0.1
RESPONSE_DRAIN_SECONDS = 3.0

# Cumulative rework tracking — fast-fail when PM3 is genuinely unresponsive.
# Incremented on every reworkPM3All(), reset on any successful command.
# When the count reaches MAX_CONSECUTIVE_REWORKS, subsequent startPM3Task
# calls skip reworks and return -1 immediately so flow state machines can
# abort gracefully instead of cascading through every fallback command.
MAX_CONSECUTIVE_REWORKS = 3
_consecutive_reworks = 0

# Nikola.D end-of-response regex — executor_strings.txt: "Nikola.D:"
_RE_NIKOLA_END = re.compile(r'(?:^|\n)Nikola\.D:[ \t]*-?\d+[ \t]*\r?\n\Z')
# Alternative end marker — executor_strings.txt: "pm3 -->"
_RE_PROMPT_END = re.compile(r'(?:^|\n)(?:\[[^\n]*\][ \t]+)?pm3[ \t]+-->[ \t]*\r?\n\Z')

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

@_serialized
def connect2PM3(serial_port=None, baudrate=None):
    """Connect to PM3 via RemoteTaskManager TCP socket.

    Creates AF_INET SOCK_STREAM to PM3_REMOTE_ADDR:PM3_REMOTE_CMD_PORT
    Strings: "hw connect"
    """
    global _socket_instance

    _close_socket()
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
        _close_socket()
        return False

def _close_socket():
    global _socket_instance
    if _socket_instance is not None:
        try:
            _socket_instance.close()
        except OSError:
            pass
        _socket_instance = None


def _ensure_pipeline_ready():
    """Reconnect when necessary; an uncertain command requires daemon proof.

    BUSY is a bounded failure, never permission to reset another owner. DIRTY
    permits one explicit restart, but never replay of the interrupted command.
    """
    global _pipeline_needs_cleanup, _pipeline_uncertain
    if _pipeline_needs_cleanup or _socket_instance is None:
        _close_socket()
        if not connect2PM3():
            return False
        _pipeline_needs_cleanup = False
    if _pipeline_uncertain:
        status = _send_ctrl('sync', timeout=4000)
        if status.strip() == 'DIRTY\nNikola.D: -1':
            return False if LABEL_PM3_CMD_TASK_STOPPING else reworkPM3All()
        if status.strip() != 'READY\nNikola.D: 0':
            _pipeline_needs_cleanup = True
            return False
        _pipeline_uncertain = False
    return True


def _exchange(wire_cmd, timeout, callbacks=False):
    """Receive one framed response with an absolute deadline and bounded drain.

    An abandoned response is discarded, even if its terminator arrives during
    the grace period. Ownership remains held throughout the drain. A missing
    terminator poisons the pipeline until the daemon confirms it is idle.
    """
    global _pipeline_needs_cleanup, _pipeline_uncertain
    if _socket_instance is None:
        return ''
    deadline = time.monotonic() + timeout / 1000.0 if timeout > 0 else None
    abandoned = False
    buf = b''
    try:
        _socket_instance.settimeout(5.0)
        _socket_instance.sendall(wire_cmd.encode('utf-8'))
        while True:
            now = time.monotonic()
            if not abandoned and (LABEL_PM3_CMD_TASK_STOPPING or
                                  (deadline is not None and now >= deadline)):
                abandoned = True
                deadline = now + RESPONSE_DRAIN_SECONDS
                _pipeline_needs_cleanup = True
            if abandoned and now >= deadline:
                break
            remaining = RESPONSE_POLL_SECONDS
            if deadline is not None:
                remaining = min(remaining, max(0.001, deadline - now))
            _socket_instance.settimeout(remaining)
            try:
                chunk = _socket_instance.recv(1024)
            except socket.timeout:
                continue
            if not chunk:
                break
            buf += chunk
            text = buf.decode('utf-8', errors='ignore')
            complete = bool(_RE_NIKOLA_END.search(text) or _RE_PROMPT_END.search(text))
            if callbacks and not abandoned and not LABEL_PM3_CMD_TASK_STOPPING:
                with LOCK_CALL_PRINT:
                    for cb in list(LIST_CALL_PRINT):
                        try:
                            cb(text)
                        except Exception:
                            pass
            if complete:
                # A daemon failure has a terminator, but its PM3 may be dirty.
                if 'Nikola.D.OFFLINE' in text:
                    _pipeline_uncertain = True
                    _pipeline_needs_cleanup = True
                return '' if abandoned or LABEL_PM3_CMD_TASK_STOPPING else text
    except (OSError, ValueError):
        pass
    _pipeline_needs_cleanup = True
    _pipeline_uncertain = True
    return ''


def _send_raw(cmd):
    """Send an uncached command using the same response ownership rules."""
    if not _ensure_pipeline_ready():
        return ''
    return _exchange('Nikola.D.CMD = %s\n' % cmd, 3000)


def _send_and_cache(cmd, timeout=5888):
    """Send command, cache result in CONTENT_OUT_IN__TXT_CACHE, fire callbacks.

    Formats via Nikola.D.CMD, accumulates in cache, fires
    LIST_CALL_PRINT callbacks per line.
    Strings: "Nikola.D.CMD = {}", "Nikola.D:", "timeout while waiting for reply"
    """
    global CONTENT_OUT_IN__TXT_CACHE

    CONTENT_OUT_IN__TXT_CACHE = ''
    translated_cmd = cmd
    if pm3_compat is not None:
        try:
            translated_cmd = pm3_compat.translate(cmd)
        except Exception:
            pass
    result = _exchange('Nikola.D.CMD = %s\n' % translated_cmd, timeout, callbacks=True)
    if not result:
        return ''

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

    # Localize recognized user-facing status phrases for the active language.
    # Strict no-op on English; never touches hex dumps or structured output.
    if pm3_localize is not None and result:
        try:
            result = pm3_localize.localize(result)
        except Exception:
            pass

    CONTENT_OUT_IN__TXT_CACHE = result
    return result

def _send_ctrl(cmd, timeout=5888):
    """Send a framed control request. Partial acknowledgements are failures."""
    global CONTENT_OUT_IN__TXT_CACHE
    result = _exchange('Nikola.D.CTL = %s\n' % cmd, timeout)
    CONTENT_OUT_IN__TXT_CACHE = result
    return result


def _send_plat(cmd, timeout=5888):
    global CONTENT_OUT_IN__TXT_CACHE
    result = _exchange('Nikola.D.PLT = %s\n' % cmd, timeout)
    CONTENT_OUT_IN__TXT_CACHE = result
    return result

# ===========================================================================
# PM3 task execution
# startPM3Task @0x1af98 (28KB, Ghidra timeout — reconstructed
#   from startPM3Plat/startPM3Ctrl + traces + archive)
# Returns: 1=completed, -1=error (memory: project_startPM3Task_return.md)
# ===========================================================================

@_command
def startPM3Task(cmd, timeout=5000, listener=None, rework_max=2):
    """Execute a PM3 command.

    startPM3Task @0x1af98
    Strings: "Nikola.D.CMD = {}", "Nikola.D.OFFLINE"
    Trace: all PM3 traces show (cmd, timeout, rework) pattern
    Returns: 1=completed, -1=error (NOT the Nikola.D value)
    """
    global CONTENT_OUT_IN__TXT_CACHE, _consecutive_reworks

    CONTENT_OUT_IN__TXT_CACHE = ''
    if not _ensure_pipeline_ready():
        CONTENT_OUT_IN__TXT_CACHE = ''
        return CODE_PM3_TASK_ERROR

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

    try:
        # A command may already have changed a card when its reply is lost.
        # Keep rework_max in the public signature for callers, but never replay.
        _check_operation()
        if LABEL_PM3_CMD_TASK_STOPPING:
            return CODE_PM3_TASK_ERROR
        result = _send_and_cache(cmd, timeout)
        _check_operation()
        if (not LABEL_PM3_CMD_TASK_STOPPING and result and
                not isPM3Offline(result) and not isCMDTimeout(result)):
            _consecutive_reworks = 0
            return 1
        return CODE_PM3_TASK_ERROR
    finally:
        if listener is not None:
            del_task_call(listener)

def stopPM3Task(listener=None, wait=True):
    """Stop the current PM3 task.

    Cancel the current owner; optionally wait for that command to unwind.
    A nonblocking stop stays latched until command cleanup. Waiting never
    follows a new command, and callbacks cannot wait for their own thread.
    """
    with _owner_lock:
        if _active_operation is not None:
            _active_operation.set()
        command = _active_command
        if command is not None:
            _set_stopping(True)

    if wait and command is not None and command[0] != threading.get_ident():
        command[1].wait()

    if listener is not None:
        del_task_call(listener)

@_command
def startPM3Ctrl(ctrl_cmd='', timeout=5888):
    """Send a control command to PM3.

    Uses Nikola.D.CTL channel, sets RUNNING/STOPPED state.
    Default timeout: 5888ms.
    Default ctrl_cmd='': original .so calls this without arguments from
    PCModeActivity.startPCMode() (activity_main_strings.txt:29912).
    """
    if not _ensure_pipeline_ready():
        return ''
    _set_running(True)
    _set_stopped(False)

    result = _send_ctrl(ctrl_cmd, timeout)

    _set_running(False)
    _set_stopped(True)
    return result

@_command
def startPM3Plat(plat_cmd, timeout=5888):
    """Send a platform command to PM3.

    Uses Nikola.D.PLT channel, sets RUNNING/STOPPED state.
    Default timeout: 5888ms.
    """
    if not _ensure_pipeline_ready():
        return ''
    _set_running(True)
    _set_stopped(False)

    result = _send_plat(plat_cmd, timeout)

    _set_running(False)
    _set_stopped(True)
    return result

@_serialized
def reworkPM3All():
    """Restart the entire PM3 system and reconnect.

    Calls hmi_driver.restartpm3(), closes socket, sleeps 3s, reconnects.
    Strings: "restartpm3", "hmi_driver"

    Clears CONTENT_OUT_IN__TXT_CACHE (2026-04-17): without this, a stale
    response from the previous PM3 session lingers in the cache and later
    callers reading via getPrintContent/hasKeyword/getContentFromRegex*
    see phantom output. Observed during PC-mode teardown — the PM3 Raw
    plugin returned a previous tag's "Felica select failed" response on
    a fresh scan of a different tag. Rework implies cache-is-stale by
    definition, so clear before reconnect.
    """
    global _consecutive_reworks, CONTENT_OUT_IN__TXT_CACHE
    global _pipeline_uncertain, _pipeline_needs_cleanup
    if _consecutive_reworks >= MAX_CONSECUTIVE_REWORKS:
        return False
    _consecutive_reworks += 1
    CONTENT_OUT_IN__TXT_CACHE = ''
    _pipeline_uncertain = True
    _pipeline_needs_cleanup = True
    if hmi_driver is not None:
        try:
            hmi_driver.restartpm3()
        except Exception:
            pass
    _close_socket()
    time.sleep(3)
    if not connect2PM3():
        return False
    result = _send_ctrl('restart', timeout=15000)
    CONTENT_OUT_IN__TXT_CACHE = ''
    if result.strip() != 'OK\nNikola.D: 0':
        return False
    _pipeline_uncertain = False
    _pipeline_needs_cleanup = False
    return True


@_serialized
def resetReworkCount():
    """Reset the consecutive-rework counter and request pipeline cleanup.

    Called by flows that want a fresh budget (e.g. at the start of a new
    scan/read/write/erase activity).  The counter also resets automatically
    whenever a PM3 command returns a valid, non-timeout response.

    Reconnect before the next command, preserving _pipeline_uncertain so
    reset cannot bypass the daemon's ownership/recovery acknowledgement.
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
