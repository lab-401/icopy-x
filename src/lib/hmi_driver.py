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

"""HMI serial driver — replaces hmi_driver.so.

Manages serial communication with the GD32 MCU over /dev/ttyS0 @ 57600 baud.
Handles hardware button input, battery monitoring, backlight control, and
Proxmark3 power/restart commands.

executor.so imports this module and calls restartpm3(), turnonpm3(), etc.
All exported function names MUST match the original .so API exactly.

Serial protocol (GD32 MCU):
  NanoPi -> GD32:  plain text + \\r\\n  (e.g. "restartpm3\\r\\n")
  GD32 -> NanoPi:  event lines + \\r\\n (e.g. "KEYOK_PRES!\\r\\n")

Key events:
  v1.0.90 format: KEYOK_PRES!, KEYM1_PRES!, KEYDOWN_PRES!, etc.
  Legacy format:   OK_PRES!, M1_PRES!, DOWN_PRES!, etc.
  Special:         _PWR_CAN_PRES!, _ALL_PRES!

Status events:
  CHARGING!        charger connected
  DISCHARGIN!      charger disconnected
  ARE YOU OK?      heartbeat (respond with "i'm alive")
  AUTO POWER ON!   auto power on signal
  LOWBATTERY!!     low battery warning

Battery queries:
  Send "pctbat"    -> receive "#batpct:NNN"  (NNN = 0-100)
  Send "rcharge"   -> receive "#charge:0" or "#charge:1"


"""

import logging
import threading
import time

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════
# Module-level state (matches original .so globals)
# ═══════════════════════════════════════════════════════════
_ser = None              # serial.Serial instance (or None in emulation)
_read_thread = None      # Background serial read thread
_running = False         # Read loop control flag
_key_callback = None     # Deprecated callback (use keymap.key.onKey)
_status_callback = None  # Status event callback
_charging = False        # Current charging state
_bat_percent = 100       # Current battery percentage (0-100)
_bat_vol = 0.0           # Current battery voltage
_vcc_vol = 0.0           # Current VCC voltage
_shutdown_flag = False   # Shutdown in progress
_hmi_version = ""        # HMI firmware version string
_stid = ""               # Station/device ID string
_com_readback = None     # Registered serial data callback (SetComReadBack)

# Serial port defaults (from .so string table: PORT_DEFAULT, __pyx_int_57600)
PORT_DEFAULT = "/dev/ttyS0"
BAUD_DEFAULT = 57600

# ═══════════════════════════════════════════════════════════
# Serial port management
# ═══════════════════════════════════════════════════════════

def DOpenPort(port=PORT_DEFAULT, baudrate=BAUD_DEFAULT):
    """Open serial port to GD32 MCU.

    Catches import/open errors gracefully so the system works
    without hardware (QEMU, test).
    """
    global _ser
    try:
        import serial
        _ser = serial.Serial(port, baudrate, timeout=0.1)
        logger.info("Serial port opened: %s @ %d", port, baudrate)
    except ImportError:
        logger.warning("Serial not found, hmi disabled.")
        _ser = None
    except Exception as e:
        logger.warning("Serial not found, hmi disabled. %s", e)
        _ser = None


def DClosePort():
    """Close serial port."""
    global _ser
    if _ser is not None:
        try:
            if _ser.is_open:
                _ser.close()
        except Exception as e:
            logger.debug("Error closing serial: %s", e)
        _ser = None
    logger.debug("Serial port closed")


def DOpenReadThread():
    """Start background serial read thread."""
    global _read_thread, _running
    if _running:
        return
    _running = True
    _read_thread = threading.Thread(
        target=run_serial_loop,
        daemon=True,
        name="hmi_serial",
    )
    _read_thread.start()
    logger.debug("Read thread started")


def DCloseReadThread():
    """Stop background serial read thread."""
    global _running, _read_thread
    _running = False
    if _read_thread is not None:
        _read_thread.join(timeout=2)
        _read_thread = None
    logger.debug("Read thread stopped")


# ═══════════════════════════════════════════════════════════
# HMI lifecycle
# ═══════════════════════════════════════════════════════════

def starthmi():
    """Full HMI initialization: open port, start read thread, boot sequence.

    Boot sequence:
      1. Reuse early serial from _bootstrap_gd32() if available
      2. DOpenPort() (opens new connection only if no early serial)
      3. DOpenReadThread()
      4. Send "restartpm3" — restart PM3

    h3start + givemelcd are already sent by _bootstrap_gd32() in main.py
    which runs before any other init to beat the GD32 4-second timeout.
    """
    global _ser

    # Reuse the serial connection from _bootstrap_gd32() if available.
    # This avoids closing and reopening the port, which kills button events.
    import builtins
    early = getattr(builtins, '_early_serial', None)
    if early is not None and hasattr(early, 'is_open') and early.is_open:
        _ser = early
        builtins._early_serial = None  # consumed
        logger.info("Reusing early serial connection from bootstrap")
    else:
        DOpenPort()

    DOpenReadThread()

    # h3start + givemelcd already sent by bootstrap.
    # Send restartpm3 to ensure PM3 is in a clean state.
    _ser_write("restartpm3")

    logger.info("[main]-> start ok!")


def stophmi():
    """Shutdown HMI: close thread, close port."""
    DCloseReadThread()
    DClosePort()
    logger.info("HMI stopped")


# ═══════════════════════════════════════════════════════════
# Serial read loop (background thread)
# ═══════════════════════════════════════════════════════════

def run_serial_loop():
    """Main loop: read serial lines, parse events, dispatch keys.

    Runs in background thread started by DOpenReadThread().
    Reads lines from serial (blocking with timeout), strips whitespace,
    and dispatches to _serial_key_handle().
    """
    global _running
    logger.debug("Serial read loop entered")

    while _running:
        try:
            if _ser is not None and _ser.is_open:
                raw = _ser.readline()
                if raw:
                    line = raw.strip()
                    if isinstance(line, bytes):
                        line = line.decode("utf-8", errors="ignore")
                    if line:
                        logger.debug("[seri]<- data received: %s", line)
                        _serial_key_handle(line)
            else:
                # No serial — sleep to avoid busy-spin
                time.sleep(0.1)
        except Exception as e:
            logger.debug("Serial read error: %s", e)
            time.sleep(0.1)

    logger.debug("Serial read loop exited")


def _serial_key_handle(keycode):
    """Parse key code string and dispatch to keymap.key.onKey().

    Handles key events, status events, battery responses, heartbeats,
    and version/ID responses from the GD32.
    """
    global _charging, _bat_percent, _bat_vol, _vcc_vol
    global _hmi_version, _stid

    if not keycode:
        return

    # --- Key events ---
    # Key events end with "_PRES!" or "PRES!" and are dispatched
    # to the keymap module for translation and routing.
    if keycode.endswith("PRES!"):
        try:
            from lib import keymap
            keymap.key.onKey(keycode)
        except ImportError:
            logger.debug("keymap not available, key ignored: %s", keycode)
        except Exception:
            logger.exception("Error dispatching key %s", keycode)
        return

    # --- Status events ---
    if keycode == "CHARGING!":
        _charging = True
        if _status_callback:
            _status_callback("charging")
        try:
            from lib import batteryui
            batteryui.notifyCharging(True)
        except Exception:
            pass
        return

    if keycode == "DISCHARGIN!":
        _charging = False
        if _status_callback:
            _status_callback("discharging")
        try:
            from lib import batteryui
            batteryui.notifyCharging(False)
        except Exception:
            pass
        return

    if keycode == "AUTO POWER ON!":
        logger.info("Auto power on signal received")
        return

    if keycode == "LOWBATTERY!!":
        logger.warning("Low battery warning")
        return

    # --- Shutdown command from GD32 (long power button press) ---
    # after a long press of the power button.  H3 must respond with:
    #   1. giveyoulcd   — hand LCD control back to GD32
    #   2. shutdowning  — acknowledge shutdown to GD32
    #   3. stopscreen   — turn off display
    #   4. sudo shutdown -t 0 — halt Linux
    #         logic analyser: giveyoulcd → I'm alive → shutdowning
    if keycode == "SHUTDOWN H3!":
        logger.info("Shutdown command received from GD32")
        _ser_write("giveyoulcd")
        _ser_write("shutdowning")
        _ser_write("stopscreen")
        import os
        os.system("sudo shutdown -t 0")
        return

    # --- Heartbeat ---
    if keycode == "ARE YOU OK?":
        _ser_write("i'm alive")
        return

    # --- Battery responses ---
    if keycode.startswith("#batpct:"):
        try:
            _bat_percent = int(keycode.split(":")[1])
        except (ValueError, IndexError):
            pass
        return

    if keycode.startswith("#charge:"):
        try:
            _charging = int(keycode.split(":")[1]) != 0
        except (ValueError, IndexError):
            pass
        return

    # --- Voltage responses ---
    if keycode.startswith("#batvol:"):
        try:
            _bat_vol = float(keycode.split(":")[1])
        except (ValueError, IndexError):
            pass
        return

    if keycode.startswith("#vccvol:"):
        try:
            _vcc_vol = float(keycode.split(":")[1])
        except (ValueError, IndexError):
            pass
        return

    # --- Version / ID responses ---
    if keycode.startswith("#version:"):
        _hmi_version = keycode.split(":")[1].strip()
        return

    if keycode.startswith("#stid:"):
        _stid = keycode.split(":")[1].strip()
        return

    # --- Command acknowledgments (ignore) ---
    if keycode in ("-> OK", "-> CMD ERR, try: help", "-> PARA. ERR"):
        return

    # --- Registered readback callback ---
    if _com_readback is not None:
        try:
            _com_readback(keycode)
        except Exception:
            logger.exception("Error in com readback callback")
        return

    logger.debug("Unknown serial data: %s", keycode)


# ═══════════════════════════════════════════════════════════
# PM3 hardware control (called by executor.so!)
# ═══════════════════════════════════════════════════════════

def restartpm3():
    """Send restart command to PM3 via GD32."""
    _ser_write("restartpm3")


def turnonpm3():
    """Power on PM3."""
    _ser_write("turnonpm3")


def turnoffpm3():
    """Power off PM3."""
    _ser_write("turnoffpm3")


def presspm3():
    """Simulate PM3 button press."""
    _ser_write("presspm3")


def ledpm3():
    """Control PM3 LED."""
    _ser_write("ledpm3")


# ═══════════════════════════════════════════════════════════
# Battery
# ═══════════════════════════════════════════════════════════

def readbatpercent():
    """Query battery percentage. Returns 0-100.

    Sends "pctbat" to GD32 and returns cached value.
    In emulation mode returns _bat_percent (default 100).
    """
    _ser_write("pctbat")
    return _bat_percent


def readbatvol():
    """Query battery voltage.

    GD32 responds with "#batvol:NNN".
    """
    _ser_write("volbat")
    return _bat_vol


def readvccvol():
    """Query VCC voltage.

    GD32 responds with "#vccvol:NNN".
    """
    _ser_write("volvcc")
    return _vcc_vol


def requestChargeState():
    """Query charging status. Returns bool.

    GD32 responds with "#charge:0" or "#charge:1".
    """
    _ser_write("charge")
    return _charging


# ═══════════════════════════════════════════════════════════
# Display
# ═══════════════════════════════════════════════════════════

def startscreen():
    """Initialize display."""
    _ser_write("startscreen")


def stopscreen():
    """Turn off display."""
    _ser_write("stopscreen")


def setbaklight(level):
    """Set backlight brightness.

    Protocol (strace of original firmware, 2026-04-10):
        Three separate write() calls on /dev/ttyS0:
          write(fd, "setbaklight", 11)
          write(fd, "B" + chr(brightness) + "A", 3)
          write(fd, "\r\n", 2)
        GD32 responds: '-> OK'

    The brightness is a SINGLE RAW BYTE inside B...A framing.
    Observed values: Low=0x14(20), Middle=0x32(50), High=0x64(100).
    """
    val = max(0, min(int(level), 100))
    if _ser is None:
        logger.debug("[emu] setbaklight(%d)", val)
        return
    try:
        if _ser.is_open:
            _ser.write(b"setbaklight")
            _ser.write(b"B" + bytes([val]) + b"A")
            _ser.write(b"\r\n")
            _ser.flush()
    except Exception as e:
        logger.debug("setbaklight error: %s", e)


def gotobl():
    """Go to bootloader mode."""
    _ser_write("gotobl")


# ═══════════════════════════════════════════════════════════
# Device info
# ═══════════════════════════════════════════════════════════

def readstid():
    """Read device serial/station ID."""
    _ser_write("readstid")
    return _stid


def readhmiversion():
    """Read HMI firmware version.

    GD32 command is "version" (not "readhmiversion").
    Response: "#version:X.Y.Z.W"
    Ref: https://github.com/iCopy-X-Community/icopyx-teardown/blob/master/stm32_commands/README.md
    """
    _ser_write("version")
    return _hmi_version


# ═══════════════════════════════════════════════════════════
# Serial I/O primitives
# ═══════════════════════════════════════════════════════════

def ser_byte_mode():
    """Switch to byte mode (raw serial, no line buffering)."""
    if _ser is not None:
        _ser.timeout = 0.01
    logger.debug("Switched to byte mode")


def ser_cmd_mode():
    """Switch to command mode (line-buffered serial)."""
    if _ser is not None:
        _ser.timeout = 1.0
    logger.debug("Switched to cmd mode")


def readline():
    """Read line from serial. Returns decoded string or empty."""
    if _ser is not None and _ser.is_open:
        try:
            raw = _ser.readline()
            if raw:
                line = raw.strip()
                if isinstance(line, bytes):
                    return line.decode("utf-8", errors="ignore")
                return line
        except Exception as e:
            logger.debug("readline error: %s", e)
    return ""


def ser_getc():
    """Read single byte from serial. Returns bytes or b''."""
    if _ser is not None and _ser.is_open:
        try:
            return _ser.read(1)
        except Exception:
            pass
    return b""


def ser_putc(data):
    """Write bytes to serial."""
    if _ser is not None and _ser.is_open:
        try:
            _ser.write(data)
        except Exception as e:
            logger.debug("ser_putc error: %s", e)


def ser_flush():
    """Flush serial buffers."""
    if _ser is not None and _ser.is_open:
        try:
            _ser.flushInput()
        except Exception as e:
            logger.debug("ser_flush error: %s", e)


# ═══════════════════════════════════════════════════════════
# Callback registration
# ═══════════════════════════════════════════════════════════

def SetComReadBack(callback):
    """Register callback for serial data."""
    global _com_readback
    _com_readback = callback


# ═══════════════════════════════════════════════════════════
# Shutdown
# ═══════════════════════════════════════════════════════════

def planToShutdown(delay=0):
    """Initiate shutdown sequence.

    Sets _shutdown_flag and sends shutdown command to GD32.
    Optional delay parameter (from .so __defaults__).
    """
    global _shutdown_flag
    _shutdown_flag = True
    _ser_write("plan2shutdown")
    logger.info("Shutdown planned")


def shutdowning():
    """Send shutdown acknowledgment to GD32 and return shutdown flag.

    Sends "shutdowning" to GD32 (H3→GD32 direction).
    Note: "SHUTDOWN H3!" is the GD32→H3 command, NOT what H3 sends.
            logic analyser trace: < shutdowning\\r\\n
    """
    _ser_write("shutdowning")
    return _shutdown_flag


# ═══════════════════════════════════════════════════════════
# Internal helper
# ═══════════════════════════════════════════════════════════

def _set_com(cmd):
    """Send command to GD32 MCU via serial.

    Used by TimeSyncActivity for RTC sync: 'TIME:YYYY-MM-DD HH:MM:SS'.
    """
    _ser_write(cmd)


def _ser_write(cmd):
    """Write command string to serial port with \\r\\n terminator.

    No-op when _ser is None (emulation/test mode).
    """
    if _ser is None:
        logger.debug("[emu] %s", cmd)
        return
    try:
        if _ser.is_open:
            data = cmd.encode("utf-8") + b"\r\n"
            _ser.write(data)
            _ser.flush()
    except Exception as e:
        logger.debug("Serial write error: %s", e)


# ═══════════════════════════════════════════════════════════
# Test helper (not in original .so — for QEMU/test injection)
# ═══════════════════════════════════════════════════════════

def inject_key(key_str):
    """Inject a key event for testing (bypasses serial).

    Calls _serial_key_handle directly so key dispatch works
    without real hardware.
    """
    _serial_key_handle(key_str)
