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

"""Application entry point — replaces main.so.

Exports:
    main()  — orchestrate full application startup: mount storage, prepare
              PM3, start RemoteTaskManager, launch UI via application.startApp()

Source: strings extracted from orig_so/main/main.so (57KB ARM ELF)

String table (from binary):
    application, rftask, gadget_linux, os, subprocess, RemoteTaskManager,
    startApp, startManager, auto_ms_remount, pm3_cmd, pm3_cwd, pm3_hp,
    pm3_kill_cmd, chmod_777_R_pm3, sudo_killall_w_q_9_proxmark3,
    sudo_s_pm3_proxmark3_dev_ttyACM0, 0.0.0.0, 8888, NanoPi_NEO, Linux,
    uname_a, shutdown_t_0, PIPE, Popen, stdout, poll, readline, serial,
    abspath, exists, system, shell, lib, pm3, res, pi

Cython version: 0.29.21

Boot chain:
    app.py → main.main() → [mount, PM3 setup, rftask start] → application.startApp()
"""

import os
import sys


def _bootstrap_gd32():
    """Send early boot handshake to GD32 MCU over /dev/ttyS0.

    The GD32 shows "Boot timeout!" if it doesn't receive h3start within
    ~4 seconds of power-on.  This function runs BEFORE any other init
    (PM3, gadget, etc.) to beat the timeout.

    Ground truth: logic analyser trace from
    https://github.com/iCopy-X-Community/icopyx-teardown/blob/main/stm32_commands/README.md

    Boot sequence (exact order from trace):
      1. h3start  → CMD ERR (baud garbage from U-Boot 115200→57600 transition)
      2. h3start  → OK
      3. givemelcd → OK  (LCD handoff from GD32 to H3)
      4. setbaklightBdA → OK
      5. restartpm3 → OK  (sent later by hmi_driver.starthmi())

    Critical: givemelcd takes ~537ms for the GD32 to process (SPI LCD
    release).  A fixed sleep is insufficient — use blocking readline()
    with a 1s timeout to wait for each response, matching the working
    debug bootstrap (verified on real device 2026-04-11).
    Serial connection must stay open — closing it kills button events.
    Connection is passed to hmi_driver via builtins._early_serial.
    """
    import builtins
    import time
    try:
        import serial as _serial_mod
        ser = _serial_mod.Serial('/dev/ttyS0', 57600, timeout=1.0)

        def _send(ser, cmd):
            """Send command, wait for response, drain extras."""
            ser.write(cmd)
            time.sleep(0.1)
            ser.readline()  # block until first response line
            while ser.in_waiting:
                ser.readline()

        # Phase 1: First h3start (expect CMD ERR from baud garbage)
        _send(ser, b'h3start\r\n')

        # Phase 2: Retry h3start (succeeds)
        _send(ser, b'h3start\r\n')

        # Phase 3: Request LCD control (GD32 takes ~537ms to release SPI)
        _send(ser, b'givemelcd\r\n')

        # Phase 4: Set backlight (logic analyser trace: "setbaklightBdA")
        _BL_MAP = {0: 20, 1: 50, 2: 100}  # UI level → HW brightness
        try:
            import configparser as _cp
            _cfg = _cp.ConfigParser()
            _cfg.read('/mnt/sdcard/root2/root/home/pi/ipk_app_main/data/conf.ini')
            _bl_level = int(_cfg.get('DEFAULT', 'backlight'))
        except Exception:
            _bl_level = 2  # High (factory default)
        _bl_hw = _BL_MAP.get(_bl_level, 100)
        _send(ser, b'setbaklightB' + bytes([_bl_hw]) + b'A\r\n')

        # Keep connection open — hmi_driver reuses it
        builtins._early_serial = ser
        print('[main] GD32 bootstrap OK', flush=True)
    except ImportError:
        print('[main] pyserial not available — GD32 bootstrap skipped', flush=True)
    except Exception as e:
        print('[main] GD32 bootstrap failed: %s' % e, flush=True)


def main():
    """Orchestrate full application startup.

    Sequence (reconstructed from main.so string table + ORIGINAL_ANALYSIS.md):
        0. GD32 bootstrap (h3start + givemelcd) — MUST be first
        1. Mount USB storage via gadget_linux.auto_ms_remount()
        2. Ensure PM3 binary is executable (chmod 777 -R pm3)
        3. Kill any stale PM3 processes
        4. Determine PM3 paths and TCP bind address
        5. Create and start rftask.RemoteTaskManager (PM3 subprocess on port 8888)
        6. Start HMI serial driver (button events, battery, backlight)
        7. Launch UI via application.startApp() (blocks in mainloop)
    """
    # ── 0. GD32 bootstrap — FIRST, before anything else ────────────
    # Must arrive within ~4s of power-on to avoid "Boot timeout!" on LCD.
    _bootstrap_gd32()

    # ── 1. Mount USB storage ───────────────────────────────────────
    try:
        import gadget_linux
        gadget_linux.auto_ms_remount()
    except Exception:
        # Non-fatal — /mnt/upan may already be mounted or not available
        pass

    # ── 2. Ensure PM3 binary is executable ─────────────────────────
    # Original: os.system("chmod 777 -R pm3")
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pm3_dir = os.path.join(app_dir, 'pm3')
    if os.path.isdir(pm3_dir):
        os.system('chmod 777 -R %s' % pm3_dir)

    # ── 3. Kill stale PM3 processes and reset USB device node ──────
    os.system('sudo killall -q -9 proxmark3')
    os.system('sudo rm -f /dev/ttyACM0')

    # ── 4. Start RemoteTaskManager (PM3 subprocess on TCP 8888) ────
    # Original string references: pm3_cmd, pm3_cwd, pm3_hp (host:port),
    # pm3_kill_cmd, 0.0.0.0, 8888, RemoteTaskManager, startManager
    pm3_bin = os.path.join(app_dir, 'pm3', 'proxmark3')
    # Original .so string: "sudo_s_pm3_proxmark3_dev_ttyACM0"
    # The original Cython .so passes this as a string to Popen(shell=True).
    # The sudo -s creates a bash intermediate which — combined with shell=True
    # and start_new_session — replicates the exact process tree that the PM3
    # binary requires for a successful USB-CDC handshake.
    pm3_cmd = 'sudo -s %s /dev/ttyACM0 -w --flush' % pm3_bin
    pm3_kill_cmd = 'sudo killall -q -9 proxmark3'
    pm3_hp = '0.0.0.0:8888'

    try:
        import rftask
        rtm = rftask.RemoteTaskManager(
            pm3_cmd=pm3_cmd,
            pm3_cwd=app_dir,
            pm3_hp=pm3_hp,
            pm3_kill_cmd=pm3_kill_cmd,
        )
        rtm.startManager()
    except ImportError:
        # rftask.py not yet implemented — PM3 won't be available but UI works
        print('[main] WARNING: rftask not available — PM3 disabled', flush=True)
    except Exception as e:
        print('[main] WARNING: RemoteTaskManager failed: %s' % e, flush=True)

    # ── 4b. Connect executor to RemoteTaskManager ──────────────────
    # The original .so pre-connects the TCP socket so that the first PM3
    # command succeeds immediately (verified from real-device traces:
    # trace_scan_flow_20260331.txt line 5 — first hf 14a info gets ret=1
    # with no retry).  Without this, _socket_instance stays None until the
    # first command fails and triggers reworkPM3All().
    import time
    time.sleep(2)  # Give RTM time to start TCP server
    try:
        import executor
        executor.connect2PM3()
    except Exception as e:
        print('[main] WARNING: connect2PM3 failed: %s' % e, flush=True)

    # ── 5. Start HMI serial driver ─────────────────────────────────
    # The original firmware initialises the GD32 serial link so that
    # button events flow before the UI renders.  On QEMU this is mocked
    # by the launcher; on real hardware we call starthmi().
    try:
        import hmi_driver
        hmi_driver.starthmi()
    except Exception as e:
        print('[main] WARNING: HMI start failed: %s' % e, flush=True)

    # ── 6. Launch UI (blocks in mainloop) ──────────────────────────
    import application
    application.startApp()
