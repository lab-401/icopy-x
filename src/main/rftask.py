##########################################################################
# Required Notice: Copyright ETOILE401 SAS (http://www.lab401.com)
#
# Copyright (c) 2026: ETOILE401 SAS & https://github.com/quantum-x/
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
DEFAULT_OFFLINE = "Nikola.D.OFFLINE"

# End-of-command regex (from binary: "Nikola\.D:.*?\d+\s+")
# The genuine Lab401 PM3 binary emits "Nikola.D: 0" (success) or
# "Nikola.D: -10" (error) after each command.
NIKOLA_PATTERN = re.compile(r'Nikola\.D:\s*-?\d+\s*$')

# Fallback prompt for simulator / non-Lab401 PM3 builds
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
        # Serialize _send_cmd access — prevents concurrent HandleServer
        # threads from corrupting shared state after socket reconnection.
        # 3s timeout acts as the pipeline probe: if the previous command
        # hasn't finished in 3s, the caller escalates to reworkManager().
        self._cmd_lock = threading.Lock()

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
        self._has_manager = False
        self._destroy_read_thread()
        self._destroy_subprocess()
        # /dev/ttyACM0 needs 2-3s to re-enumerate after PM3 power cycle.
        # 1s was too short — new PM3 process couldn't connect to device.
        time.sleep(3)
        if not self._create_subprocess():
            return False
        self._has_manager = True
        self._create_read_thread()
        # Wait for PM3 to finish startup (banner + prompt)
        time.sleep(1)
        return True

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
    # rftask.so terminates these by sending '\n' to PM3 stdin after the
    # first batch of samples (~0.5s).  Without this, tune runs forever.
    _INTERACTIVE_CMDS = frozenset({'hf tune', 'lf tune'})

    def _request_task_cmd(self, cmd):
        """Execute a PM3 command and collect output, with auto-recovery.

        Binary: request_task_cmd closure inside __init__.
        Timeout: 120s (matches archive — long commands like darkside, nested,
        dump can take 25-60+ seconds).

        Auto-recovery (invisible to middleware):
          1. Send command, wait for EOR marker.
          2. If no EOR (timeout) → restart PM3 subprocess, retry once.
          3. If EOR but empty response (RF dead) → send hw ping to
             wake the module, retry once.
          4. Return whatever we get — middleware sees a normal response.

        Race-condition fix (2026-04-12): _expecting_response MUST be set True
        BEFORE writing the command to stdin. Otherwise, for fast-responding
        commands (hw version — cache-based, instant), the reader thread may
        see the Nikola.D marker before _expecting_response is True, and never
        set the event. This caused intermittent timeouts on fast commands.
        """
        result = self._send_cmd(cmd)

        # Auto-recovery: no EOR marker received (timeout) → restart PM3
        if result is None:
            logger.warning('rftask: no response for "%s" — restarting PM3',
                           cmd[:60])
            if self.reworkManager():
                # Wait for PM3 to reinitialize after restart
                time.sleep(2)
                result = self._send_cmd(cmd)
            if result is None:
                return DEFAULT_OFFLINE

        # Auto-recovery: EOR received but response is effectively empty
        # (just whitespace / EOR marker). PM3 is alive but returned nothing.
        # Retry once with a short delay.
        stripped = result.strip()
        is_empty = (not stripped or stripped in ('pm3 -->', ''))
        if is_empty and cmd.strip() not in ('hw ping', 'hw version'):
            logger.info('rftask: empty response for "%s" — retrying',
                        cmd[:60])
            self._send_cmd('hw ping')
            time.sleep(0.3)
            retry = self._send_cmd(cmd)
            if retry is not None:
                result = retry

        return result

    def _send_cmd(self, cmd):
        """Low-level: send a single command and wait for EOR.

        Returns the response string, or None if no EOR was received
        (timeout / subprocess dead / lock timeout).

        Lock timeout (3s): when a previous command is still in flight
        (e.g. PM3 stuck after presspm3 abort), the lock won't be acquired.
        Returning None triggers _request_task_cmd's auto-recovery which
        calls reworkManager() — restarting the PM3 subprocess via GD32
        restartpm3 command.  This is the escalation path for stuck PM3.
        """
        acquired = self._cmd_lock.acquire(timeout=3)
        if not acquired:
            logger.warning('rftask: _send_cmd lock timeout — '
                           'previous command still in flight')
            return None
        try:
            self._expecting_response = False
            with self._output_lock:
                self._output_lines.clear()
            self._output_event.clear()
            self._expecting_response = True

            # Check subprocess health
            if not self._process or self._process.poll() is not None:
                self._expecting_response = False
                return None

            # For interactive commands (hf tune, lf tune), schedule a delayed
            # Enter keystroke to terminate the measurement after a few samples.
            is_interactive = cmd.strip() in self._INTERACTIVE_CMDS
            if is_interactive:
                proc = self._process

                def _send_enter():
                    time.sleep(0.5)
                    try:
                        proc.stdin.write(b'\n')
                        proc.stdin.flush()
                    except Exception:
                        pass

                threading.Thread(target=_send_enter, daemon=True).start()

            # Write command to PM3 stdin
            try:
                self._process.stdin.write(('%s\n' % cmd).encode('utf-8'))
                self._process.stdin.flush()
            except Exception:
                self._expecting_response = False
                return None

            # Wait for end-of-command marker from reader thread
            got_eor = self._output_event.wait(timeout=120)
            self._expecting_response = False

            with self._output_lock:
                result = '\n'.join(self._output_lines)

            return result if got_eor else None
        finally:
            self._cmd_lock.release()

    def _request_task_ctl(self, ctl):
        """Handle control commands.

        Binary: request_task_ctl closure. String "restart" confirmed in binary.
        """
        if ctl == 'restart':
            self.reworkManager()
            return 'OK'
        return ''

    def _request_task_plt(self, plt_cmd):
        """Handle platform commands.

        Binary: request_task_plt closure. No-op in practice.
        """
        return ''

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
                pass
            self._process = None

        if self._pm3_kill_cmd:
            os.system(self._pm3_kill_cmd)

    # ── Thread management ────────────────────────────────────────

    def _create_read_thread(self):
        """Start the stdout reader thread.

        Binary: method index 15 (_create_read_thread).
        stderr is merged into stdout (subprocess.STDOUT), so a single
        reader thread handles all PM3 output.
        """
        self._read_thread = threading.Thread(
            target=self._run_std_output_error,
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

    def _run_std_output_error(self):
        """Read PM3 stdout line by line, signal on end-of-command markers.

        Binary: method index 5 (_run_std_output_error). Detects both
        Lab401 "Nikola.D: N" markers AND standard "pm3 -->" prompts.

        Pipeline isolation: lines are ONLY appended to _output_lines when
        _expecting_response is True.  This prevents stale output from a
        previous command (e.g. felica timeout arriving late) from leaking
        into the next command's response.
        """
        while self._process and self._has_manager:
            try:
                line = self._process.stdout.readline()
                if not line:
                    if self._process and self._process.poll() is not None:
                        break
                    continue

                text = line.decode('utf-8', errors='ignore').rstrip()

                # Only collect output when a command is actively pending.
                # Stale data arriving between commands is discarded.
                if self._expecting_response:
                    with self._output_lock:
                        self._output_lines.append(text)

                for listener in self._line_listeners:
                    try:
                        listener(text)
                    except Exception:
                        pass

                # End-of-command detection
                stripped = text.strip()
                if NIKOLA_PATTERN.match(stripped) or _RE_PM3_PROMPT.match(stripped):
                    if self._expecting_response:
                        self._output_event.set()

            except Exception as e:
                if self._has_manager:
                    logger.error('rftask reader error: %s', e)
                break

        # Reader exiting — unblock any _send_cmd blocked on output_event.
        # This happens when the subprocess dies (readline returns EOF) or
        # when _has_manager is set to False by reworkManager/stopManger.
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
