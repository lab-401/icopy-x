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

"""rftask — PM3 subprocess manager with TCP command server.

Replaces orig_so/main/rftask.so (160KB ARM ELF, Cython 0.29.21).

Ground truth:
    Binary strings: strings orig_so/main/rftask.so (full method table extracted)
    Archive ref:    /home/qx/archive/infra/rftask.py (484 lines, known working)
    Docs:           docs/ORIGINAL_ANALYSIS.md Section 3 (Executor/PM3 Communication)
    Caller:         src/main/main.py lines 58-79

Architecture:
    [executor] --TCP:8888--> [RemoteTaskManager] --stdin--> [PM3 subprocess]
    [executor] <--TCP:8888-- [RemoteTaskManager] <--stdout-- [PM3 subprocess]

Protocol (Nikola):
    Request:  "Nikola.D.CMD = {pm3_command}" | "Nikola.D.CTL = {control}"
              "Nikola.D.PLT = {platform}"
    Response: PM3 stdout lines, terminated by "Nikola.D: <int>" or "pm3 -->"
    Offline:  "Nikola.D.OFFLINE"

Binary method table (from strings orig_so/main/rftask.so):
    RemoteTaskManager.__init__
    RemoteTaskManager.__init__.<locals>.HandleServer.__init__
    RemoteTaskManager.__init__.<locals>.HandleServer.handle
    RemoteTaskManager.__init__.<locals>.HandleServer.task
    RemoteTaskManager.__init__.<locals>.parse_cmd_map_actions
    RemoteTaskManager.__init__.<locals>.request_task_cmd
    RemoteTaskManager.__init__.<locals>.request_task_ctl
    RemoteTaskManager.__init__.<locals>.request_task_plt
    RemoteTaskManager._create_read_thread
    RemoteTaskManager._create_server_thread
    RemoteTaskManager._create_server_thread.<locals>.startInternal
    RemoteTaskManager._create_subprocess
    RemoteTaskManager._destroy_read_thread
    RemoteTaskManager._destroy_server_thread
    RemoteTaskManager._destroy_subprocess
    RemoteTaskManager._run_std_output_error
    RemoteTaskManager._set_has_tasking
    RemoteTaskManager.createCMD
    RemoteTaskManager.createCTL
    RemoteTaskManager.createPLT
    RemoteTaskManager.destroy
    RemoteTaskManager.hasManager
    RemoteTaskManager.hasTasking
    RemoteTaskManager.requestTask
    RemoteTaskManager.reworkManager
    RemoteTaskManager.startManager
    RemoteTaskManager.stopManger               (typo preserved from original)
"""

import logging
import os
import re
import signal
import socketserver
import subprocess
import threading
import time

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Protocol constants (from binary string table)
# ---------------------------------------------------------------------------
DEFAULT_CMD_START = "Nikola.D.CMD"
DEFAULT_CTL_START = "Nikola.D.CTL"
DEFAULT_PLT_START = "Nikola.D.PLT"
DEFAULT_OFFLINE = "Nikola.D.OFFLINE\nNikola.D: -1"
COMMAND_LOCK_SECONDS = 3.0
COMMAND_TIMEOUT_SECONDS = 120.0

# End-of-command regex (from binary: "Nikola\.D:.*?\d+\s+")
# The factory PM3 binary emits "Nikola.D: 0" (success) or
# "Nikola.D: -10" (error) after each command.
NIKOLA_PATTERN = re.compile(r'Nikola\.D:\s*-?\d+\s*$')

# Fallback prompt for simulator / upstream PM3 builds
_RE_PM3_PROMPT = re.compile(r'^(\[.*?\]\s+)?pm3\s+-->\s*$')


class RemoteTaskManager:
    """Manages PM3 subprocess and TCP command server.

    Constructor matches the call site in src/main/main.py:
        rftask.RemoteTaskManager(
            pm3_cmd=pm3_cmd,       # full subprocess command string
            pm3_cwd=app_dir,       # working directory
            pm3_hp=pm3_hp,         # "host:port" for TCP bind
            pm3_kill_cmd=pm3_kill_cmd,  # cleanup kill command
        )
    """

    def __init__(self, pm3_cmd='', pm3_cwd='.', pm3_hp='0.0.0.0:8888',
                 pm3_kill_cmd=''):
        # Parse host:port binding
        parts = pm3_hp.split(':')
        self._server_host = parts[0] if len(parts) >= 2 else '0.0.0.0'
        self._server_port = int(parts[1]) if len(parts) >= 2 else 8888

        self._pm3_cmd = pm3_cmd
        self._pm3_cwd = os.path.abspath(pm3_cwd)
        self._pm3_kill_cmd = pm3_kill_cmd

        # Instance state (from binary: has_manager, has_tasking, has_read_thread,
        # server, thread, lock_tasking, output, line_listener, byte_buffer)
        self._process = None
        self._server = None
        self._server_thread = None
        self._read_thread = None
        self._has_manager = False
        self._has_tasking = False
        self._lock_tasking = threading.Lock()
        self._output_lines = []
        self._output_lock = threading.Lock()
        self._output_event = threading.Event()
        self._expecting_response = False
        self._line_listeners = []
        # The command lock covers stdin, response ownership and lifecycle.
        self._cmd_lock = threading.Lock()
        self._lifecycle_lock = threading.Lock()
        self._generation = 0
        self._command_sequence = 0
        self._response_complete = False
        self._needs_recovery = False

        # Set up TCP handler class (closure over self, matching binary's
        # HandleServer + request_task_cmd/ctl/plt inner functions)
        self._setup_handler()

    def _setup_handler(self):
        """Create the TCP request handler class as a closure over self.

        Binary structure: HandleServer is defined inside __init__ with
        handle(), task(), and the request_task_cmd/ctl/plt closures.
        """
        manager = self

        class HandleServer(socketserver.StreamRequestHandler):
            """TCP handler for Nikola protocol commands."""

            def handle(self):
                try:
                    while True:
                        data = self.rfile.readline()
                        if not data:
                            break
                        line = data.decode('utf-8', errors='ignore').strip()
                        if not line:
                            continue
                        response = self.task(line)
                        if response:
                            self.wfile.write((response + '\n').encode('utf-8'))
                            self.wfile.flush()
                except Exception as e:
                    logger.error('TCP handler error: %s', e)

            def task(self, line):
                """Parse and dispatch a Nikola protocol message.

                Binary: parse_cmd_map_actions maps the prefix to the
                appropriate request_task_* closure.
                """
                if line.startswith(DEFAULT_CMD_START):
                    cmd = line.split('=', 1)[1].strip().strip('{}')
                    return manager._request_task_cmd(cmd)
                elif line.startswith(DEFAULT_CTL_START):
                    ctl = line.split('=', 1)[1].strip().strip('{}')
                    return manager._request_task_ctl(ctl)
                elif line.startswith(DEFAULT_PLT_START):
                    plt_cmd = line.split('=', 1)[1].strip()
                    return manager._request_task_plt(plt_cmd)
                return ''

        self._handler_class = HandleServer

    # ── Lifecycle ─────────────────────────────────────────────────

    def startManager(self):
        """Start PM3 subprocess + TCP server.

        Binary: method index 25 (startManager).
        """
        if self._has_manager:
            return True

        if not self._create_subprocess():
            return False

        with self._output_lock:
            self._generation += 1
            self._needs_recovery = False
        self._has_manager = True
        self._create_read_thread()
        self._create_server_thread()
        return True

    def stopManger(self):
        """Stop the PM3 manager.

        Binary: method index 27. Typo preserved from original .so.
        """
        self._has_manager = False
        self._destroy_server_thread()
        self._destroy_read_thread()
        self._destroy_subprocess()

    def reworkManager(self):
        """Restart the PM3 subprocess without killing the TCP server.

        Binary: method index 29.

        Bug fix (2026-04-12): the original stopManger() + startManager()
        sequence calls _destroy_server_thread() which does server.shutdown().
        When reworkManager is called from within a TCP handler (e.g. CTL
        restart, or executor.reworkPM3All), this deadlocks because shutdown()
        waits for all handlers to finish — but WE ARE a handler.

        Fix: only restart the subprocess and reader thread. The TCP server
        stays running throughout.
        """
        if not self._lifecycle_lock.acquire(timeout=COMMAND_LOCK_SECONDS):
            return False
        try:
            # Invalidate and wake the old owner BEFORE waiting for its lock.
            # A wakeup from a restart is not an end-of-response marker.
            with self._output_lock:
                self._needs_recovery = True
                self._generation += 1
                self._output_event.set()
            if not self._cmd_lock.acquire(timeout=COMMAND_LOCK_SECONDS):
                return False
            try:
                self._has_manager = False
                if not self._destroy_subprocess():
                    return False
                self._destroy_read_thread()
                # Preserve the device's USB re-enumeration delay.
                time.sleep(3)
                if not self._create_subprocess():
                    return False
                self._has_manager = True
                self._create_read_thread()
                time.sleep(1)
                # This confirms a fresh live process, not RF/card readiness.
                with self._output_lock:
                    if (self._process is None or self._process.poll() is not None or
                            not self._read_thread.is_alive()):
                        return False
                    self._needs_recovery = False
                return True
            finally:
                self._cmd_lock.release()
        finally:
            self._lifecycle_lock.release()

    def destroy(self):
        """Full cleanup.

        Binary: method index 33.
        """
        self.stopManger()

    # ── Task management ──────────────────────────────────────────

    def requestTask(self, cmd, listener=None):
        """Submit a command to PM3 and wait for response.

        Binary: method index 35. The listener parameter is present in the
        binary string table (request_listener) but unused in practice —
        the executor module handles callbacks at its own layer.
        """
        if self._has_tasking:
            return None

        self._set_has_tasking(True)
        try:
            return self._request_task_cmd(cmd)
        finally:
            self._set_has_tasking(False)

    # Interactive commands that run until Enter/button is pressed.
    # Ground truth (trace_original_diagnosis_20260411.txt): the original
    # rftask.so terminates these by sending '\n' to PM3 stdin after the
    # first batch of samples (~0.5s).  Without this, tune runs forever.
    _INTERACTIVE_CMDS = frozenset({'hf tune', 'lf tune'})

    def _request_task_cmd(self, cmd):
        """Execute once. A lost reply is never permission to replay a write."""
        result = self._send_cmd(cmd)
        return DEFAULT_OFFLINE if result is None else result

    def _send_cmd(self, cmd):
        """Return only a completed response from this process generation.

        Lock contention, EOF, reset and timeout are failures. They do not
        restart PM3 or repeat commands, including commands that write cards.
        """
        acquired = self._cmd_lock.acquire(timeout=COMMAND_LOCK_SECONDS)
        if not acquired:
            logger.warning('rftask: _send_cmd lock timeout — '
                           'previous command still in flight')
            return None
        try:
            with self._output_lock:
                if self._needs_recovery:
                    return None
                proc, generation = self._process, self._generation
                if proc is None or proc.poll() is not None:
                    self._needs_recovery = True
                    return None
                self._output_lines.clear()
                self._output_event.clear()
                self._response_complete = False
                self._command_sequence += 1
                sequence = self._command_sequence
                self._expecting_response = True

            # For interactive commands (hf tune, lf tune), schedule a delayed
            # Enter keystroke to terminate the measurement after a few samples.
            is_interactive = cmd.strip() in self._INTERACTIVE_CMDS
            if is_interactive:
                def _send_enter():
                    time.sleep(0.5)
                    try:
                        with self._output_lock:
                            if (generation == self._generation and
                                    sequence == self._command_sequence and
                                    self._expecting_response and not self._response_complete):
                                proc.stdin.write(b'\n')
                                proc.stdin.flush()
                    except Exception:
                        pass

                threading.Thread(target=_send_enter, daemon=True).start()

            # Write command to PM3 stdin
            try:
                proc.stdin.write(('%s\n' % cmd).encode('utf-8'))
                proc.stdin.flush()
            except Exception:
                with self._output_lock:
                    self._needs_recovery = True
                return None

            self._output_event.wait(timeout=COMMAND_TIMEOUT_SECONDS)
            with self._output_lock:
                complete = self._response_complete and generation == self._generation
                if not complete:
                    self._needs_recovery = True
                    return None
                return '\n'.join(self._output_lines)
        finally:
            with self._output_lock:
                self._expecting_response = False
            self._cmd_lock.release()

    def _request_task_ctl(self, ctl):
        """Handle control commands.

        Binary: request_task_ctl closure. String "restart" confirmed in binary.

        Empty CTL payload (sent by PCModeActivity.startPCMode via
        executor.startPM3Ctrl with default empty arg) instructs rftask to
        tear down the PM3 subprocess so socat can claim /dev/ttyACM0
        exclusively for the PC-mode USB-gadget bridge. Without this,
        proxmark3 -w --flush and socat both hold the tty, their reads
        interleave, and the PC client sees truncated/corrupted frames
        (symptoms observed 2026-04-17: "Received packet OLD frame with
        payload too short? 258/534", "frame preamble too short: 2/10",
        hf search failures).

        Factory ground truth: docs/Real_Hardware_Intel/pcmode_live_audit_20260411.txt
          §1 "PM3 subprocess: NOT RUNNING (killed/gone during PC Mode)"
          §5 post-stop PM3 back to RUNNING state

        The subprocess is restored later by PCModeActivity.stopPCMode() ->
        executor.reworkPM3All() -> reworkManager(), which fully re-spawns
        proxmark3 and the reader thread.

        Only the subprocess + reader thread are torn down here. The TCP
        server thread stays listening (factory audit §1: "RTM (port 8888):
        STILL LISTENING").
        """
        if ctl == 'sync':
            if not self._cmd_lock.acquire(timeout=COMMAND_LOCK_SECONDS):
                return 'BUSY\nNikola.D: -1'
            try:
                with self._output_lock:
                    dirty = (self._needs_recovery or self._process is None or
                             self._process.poll() is not None)
                return 'DIRTY\nNikola.D: -1' if dirty else 'READY\nNikola.D: 0'
            finally:
                self._cmd_lock.release()

        if ctl == 'restart':
            return ('OK\nNikola.D: 0' if self.reworkManager()
                    else 'FAIL\nNikola.D: -1')

        if ctl == '':
            # PC mode takes exclusive ownership of the PM3 serial port.
            with self._lifecycle_lock:
                self._has_manager = False
                stopped = self._destroy_subprocess()
                self._destroy_read_thread()
            return 'OK\nNikola.D: 0' if stopped else 'FAIL\nNikola.D: -1'

        return 'FAIL\nNikola.D: -1'

    def _request_task_plt(self, plt_cmd):
        """Handle platform commands.

        Binary: request_task_plt closure. No-op in practice.
        """
        return 'Nikola.D: 0'

    def _set_has_tasking(self, tasking):
        """Thread-safe tasking flag setter.

        Binary: method index 3 (_set_has_tasking). Uses lock_tasking.
        """
        with self._lock_tasking:
            self._has_tasking = tasking

    def hasManager(self):
        """Check if manager is running.

        Binary: method index 31.
        """
        return self._has_manager

    def hasTasking(self):
        """Check if a task is in progress.

        Binary: method index 37.
        """
        return self._has_tasking

    # ── Protocol helpers ─────────────────────────────────────────

    def createCMD(self, cmd):
        """Format a CMD protocol message.

        Binary: method index 19. Output: "Nikola.D.CMD = {cmd}"
        """
        return '%s = {%s}' % (DEFAULT_CMD_START, cmd)

    def createCTL(self, ctl):
        """Format a CTL protocol message.

        Binary: method index 21. Output: "Nikola.D.CTL = {ctl}"
        """
        return '%s = {%s}' % (DEFAULT_CTL_START, ctl)

    def createPLT(self, plt):
        """Format a PLT protocol message.

        Binary: method index 23. Output: "Nikola.D.PLT = plt"
        Note: PLT does NOT wrap in braces (confirmed from executor.py line 286).
        """
        return '%s = %s' % (DEFAULT_PLT_START, plt)

    # ── Subprocess management ────────────────────────────────────

    def _create_subprocess(self):
        """Spawn the PM3 subprocess.

        Binary: method index 13 (_create_subprocess). Uses Popen with
        shell=True, stdin/stdout PIPE, stderr merged to stdout,
        close_fds=True, start_new_session=True.

        Ground truth (from running original .so on real device):
            Process tree: python3 → sh → sudo → proxmark3
            The command string is passed whole to Popen(shell=True) which
            creates /bin/sh -c "sudo -s .../proxmark3 ...".  stderr is
            redirected to stdout (both fds point to the same pipe).
        """
        if not self._pm3_cmd:
            logger.error('rftask: no pm3_cmd configured')
            return False

        logger.info('rftask: launching PM3: %s', self._pm3_cmd)

        try:
            self._process = subprocess.Popen(
                self._pm3_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=self._pm3_cwd,
                shell=True,
                close_fds=True,
                start_new_session=True,
            )
            logger.info('rftask: PM3 started (pid=%d)', self._process.pid)
            return True
        except Exception as e:
            logger.error('rftask: subprocess creation failed: %s', e)
            return False

    def _destroy_subprocess(self):
        """Kill the PM3 subprocess.

        Binary: method index 7 (_destroy_subprocess). Uses killpg + SIGTERM,
        falls back to kill(). Binary strings confirm killpg and signal imports.

        Real-device fix: always reap the child process to avoid zombies.
        The original Cython .so didn't have this problem because it managed
        the subprocess at C level.  Python's Popen requires an explicit
        wait() to reap.  Also avoid `killall -w` which hangs on zombies.
        """
        # Unblock any _send_cmd waiting on _output_event before killing
        # the process.  Without this, a concurrent _send_cmd (from an old
        # HandleServer thread) stays blocked on output_event.wait(120s),
        # holding _cmd_lock and preventing the new HandleServer from
        # sending commands after reworkManager().
        with self._output_lock:
            self._needs_recovery = True
            self._generation += 1
            self._output_event.set()

        if self._process:
            try:
                os.killpg(os.getpgid(self._process.pid), signal.SIGTERM)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
            # Always reap to prevent zombie
            try:
                self._process.wait(timeout=5)
            except Exception:
                # Never launch a replacement while an unreaped child may still
                # own the serial device. Escalate once, then fail closed.
                try:
                    os.killpg(os.getpgid(self._process.pid), signal.SIGKILL)
                except Exception:
                    try:
                        self._process.kill()
                    except Exception:
                        return False
                try:
                    self._process.wait(timeout=2)
                except Exception:
                    return False
            self._process = None

        if self._pm3_kill_cmd:
            try:
                cleanup = subprocess.run(self._pm3_kill_cmd, shell=True, timeout=3,
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                # main.py configures killall: 1 means no matching process.
                if cleanup.returncode not in (0, 1):
                    return False
            except (OSError, subprocess.TimeoutExpired):
                return False
        return True

    # ── Thread management ────────────────────────────────────────

    def _create_read_thread(self):
        """Start the stdout reader thread.

        Binary: method index 15 (_create_read_thread).
        stderr is merged into stdout (subprocess.STDOUT), so a single
        reader thread handles all PM3 output.
        """
        self._read_thread = threading.Thread(
            target=self._run_std_output_error,
            args=(self._process, self._generation),
            daemon=True,
            name='pm3_reader',
        )
        self._read_thread.start()

    def _destroy_read_thread(self):
        """Stop the reader thread and wait for it to exit.

        Binary: method index 9.  The original just set the reference to None
        and relied on daemon thread cleanup.  But this causes zombie readers
        that compete with the new reader thread for PM3 stdout after rework.
        Fix: _has_manager=False signals the loop to exit, then join() waits
        for it to actually stop (with a timeout to avoid deadlock).
        """
        old_thread = self._read_thread
        self._read_thread = None
        if old_thread and old_thread.is_alive():
            try:
                old_thread.join(timeout=3)
            except Exception:
                pass

    def _run_std_output_error(self, process=None, generation=None):
        """Bind a reader to one process; stale readers cannot finish new work."""
        process = self._process if process is None else process
        generation = self._generation if generation is None else generation
        try:
            while process is not None and self._has_manager:
                line = process.stdout.readline()
                if not line:
                    break
                text = line.decode('utf-8', errors='ignore').rstrip()
                with self._output_lock:
                    if generation != self._generation or process is not self._process:
                        return
                    if self._expecting_response and not self._response_complete:
                        self._output_lines.append(text)
                        if line.endswith(b'\n') and (NIKOLA_PATTERN.match(text.strip()) or
                                                     _RE_PM3_PROMPT.match(text.strip())):
                            self._response_complete = True
                            self._output_event.set()
                for listener in self._line_listeners:
                    try:
                        listener(text)
                    except Exception:
                        pass
        except Exception as e:
            logger.error('rftask reader error: %s', e)
        finally:
            with self._output_lock:
                if generation == self._generation and process is self._process:
                    self._needs_recovery = True
                    self._output_event.set()

    def _create_server_thread(self):
        """Start the TCP server thread.

        Binary: method index 17 (_create_server_thread) with inner
        startInternal closure (index 21 variant).
        """
        if self._server:
            return

        def startInternal():
            try:
                socketserver.ThreadingTCPServer.allow_reuse_address = True
                self._server = socketserver.ThreadingTCPServer(
                    (self._server_host, self._server_port),
                    self._handler_class,
                )
                logger.info('rftask: TCP server on %s:%d',
                            self._server_host, self._server_port)
                self._server.serve_forever()
            except Exception as e:
                logger.error('rftask: TCP server error: %s', e)

        self._server_thread = threading.Thread(
            target=startInternal,
            daemon=True,
            name='pm3_tcp_server',
        )
        self._server_thread.start()

    def _destroy_server_thread(self):
        """Stop the TCP server.

        Binary: method index 11 (_destroy_server_thread).
        """
        if self._server:
            try:
                self._server.shutdown()
            except Exception:
                pass
            self._server = None
