"""Tests for hmi_driver.py — serial protocol, PM3 control, battery, shutdown.

All tests mock serial.Serial since there is no hardware in CI.
FakeSerial records written data and returns canned responses.
"""

import threading
import time
import sys
import os
import types

import pytest

# ---------------------------------------------------------------------------
# Ensure src/ is on path so 'lib.hmi_driver' imports work
# ---------------------------------------------------------------------------
SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, os.path.abspath(SRC_DIR))


# ---------------------------------------------------------------------------
# FakeSerial — records writes, feeds canned reads
# ---------------------------------------------------------------------------

class FakeSerial:
    """Mock serial.Serial that records writes and returns canned read data."""

    def __init__(self, port=None, baudrate=57600, timeout=None, **kwargs):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.is_open = True
        self._written = []         # list of bytes written
        self._read_lines = []      # list of bytes lines to return from readline()
        self._read_bytes = b""     # raw bytes for read(n)
        self._lock = threading.Lock()

    def write(self, data):
        with self._lock:
            self._written.append(data)

    def flush(self):
        pass

    def flushInput(self):
        pass

    def readline(self):
        with self._lock:
            if self._read_lines:
                return self._read_lines.pop(0)
        # Block briefly to simulate timeout
        time.sleep(0.01)
        return b""

    def read(self, n=1):
        with self._lock:
            result = self._read_bytes[:n]
            self._read_bytes = self._read_bytes[n:]
            return result

    def close(self):
        self.is_open = False

    def enqueue_line(self, line_str):
        """Enqueue a line for readline() to return (adds \\r\\n)."""
        with self._lock:
            self._read_lines.append((line_str + "\r\n").encode("utf-8"))

    def enqueue_bytes(self, raw):
        """Enqueue raw bytes for read() to return."""
        with self._lock:
            self._read_bytes += raw

    def get_written_strings(self):
        """Return all written data as decoded strings."""
        with self._lock:
            return [d.decode("utf-8", errors="ignore") for d in self._written]

    def clear_written(self):
        """Clear the write log."""
        with self._lock:
            self._written.clear()

    @property
    def in_waiting(self):
        with self._lock:
            return len(self._read_lines) + len(self._read_bytes)


# ---------------------------------------------------------------------------
# Fixture: fresh hmi_driver module state for each test
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_hmi_state():
    """Reset hmi_driver module globals before each test."""
    from lib import hmi_driver as hd
    # Ensure read loop is stopped
    hd._running = False
    if hd._read_thread is not None:
        hd._read_thread.join(timeout=1)

    # Reset all module state
    hd._ser = None
    hd._read_thread = None
    hd._running = False
    hd._key_callback = None
    hd._status_callback = None
    hd._charging = False
    hd._bat_percent = 100
    hd._bat_vol = 0.0
    hd._vcc_vol = 0.0
    hd._shutdown_flag = False
    hd._hmi_version = ""
    hd._stid = ""
    hd._com_readback = None

    yield

    # Teardown: stop any running threads
    hd._running = False
    if hd._read_thread is not None:
        hd._read_thread.join(timeout=1)
    hd._ser = None
    hd._read_thread = None


@pytest.fixture
def fake_serial():
    """Provide a FakeSerial and install it as hmi_driver._ser."""
    from lib import hmi_driver as hd
    fs = FakeSerial(port="/dev/ttyS0", baudrate=57600)
    hd._ser = fs
    return fs


# ===========================================================================
# TestSerialProtocol
# ===========================================================================

class TestSerialProtocol:
    """Verify serial command formats and event parsing."""

    def test_boot_sequence_commands(self, fake_serial, monkeypatch):
        """starthmi() sends only restartpm3 (h3start/givemelcd sent by bootstrap)."""
        from lib import hmi_driver as hd

        # Prevent DOpenPort from overwriting our fake serial
        monkeypatch.setattr(hd, "DOpenPort", lambda *a, **kw: None)
        # Prevent DOpenReadThread from starting a real thread
        monkeypatch.setattr(hd, "DOpenReadThread", lambda: None)

        hd.starthmi()

        cmds = fake_serial.get_written_strings()
        assert len(cmds) == 1
        assert cmds[0] == "restartpm3\r\n"

    def test_key_event_parsing_dispatches_to_keymap(self, monkeypatch):
        """KEYOK_PRES! dispatches to keymap.key.onKey."""
        from lib import hmi_driver as hd
        from lib import keymap as real_keymap

        received = []

        # Patch the real keymap.key.onKey to capture dispatched events
        mock_key = types.SimpleNamespace(onKey=lambda ev: received.append(ev))
        monkeypatch.setattr(real_keymap, "key", mock_key)

        hd._serial_key_handle("KEYOK_PRES!")

        assert received == ["KEYOK_PRES!"]

    def test_key_event_legacy_format(self, monkeypatch):
        """OK_PRES! (legacy format) also dispatches to keymap."""
        from lib import hmi_driver as hd
        from lib import keymap as real_keymap

        received = []
        mock_key = types.SimpleNamespace(onKey=lambda ev: received.append(ev))
        monkeypatch.setattr(real_keymap, "key", mock_key)

        hd._serial_key_handle("OK_PRES!")
        assert received == ["OK_PRES!"]

    def test_battery_query_response(self):
        """#batpct:75 updates _bat_percent to 75."""
        from lib import hmi_driver as hd

        hd._serial_key_handle("#batpct:75")
        assert hd._bat_percent == 75

    def test_backlight_command_format(self, fake_serial):
        """setbaklight sends 'setbaklight' + 'B<byte>A' + '\\r\\n' (3 writes).

        Ground truth (strace of original firmware, 2026-04-10):
          write(8, "setbaklight", 11)
          write(8, "BdA", 3)            # B + chr(100) + A for High
          write(8, "\\r\\n", 2)
        """
        from lib import hmi_driver as hd

        hd.setbaklight(100)
        cmds = fake_serial.get_written_strings()
        assert cmds == ["setbaklight", "BdA", "\r\n"]

    def test_heartbeat_response(self, fake_serial):
        """ARE YOU OK? triggers 'i'm alive' response."""
        from lib import hmi_driver as hd

        hd._serial_key_handle("ARE YOU OK?")
        cmds = fake_serial.get_written_strings()
        assert cmds == ["i'm alive\r\n"]


# ===========================================================================
# TestPM3Control
# ===========================================================================

class TestPM3Control:
    """Verify PM3 hardware control commands."""

    def test_restartpm3_sends_command(self, fake_serial):
        """restartpm3() sends 'restartpm3\\r\\n'."""
        from lib import hmi_driver as hd

        hd.restartpm3()
        cmds = fake_serial.get_written_strings()
        assert cmds == ["restartpm3\r\n"]

    def test_turnonpm3(self, fake_serial):
        """turnonpm3() sends 'turnonpm3\\r\\n'."""
        from lib import hmi_driver as hd

        hd.turnonpm3()
        cmds = fake_serial.get_written_strings()
        assert cmds == ["turnonpm3\r\n"]

    def test_turnoffpm3(self, fake_serial):
        """turnoffpm3() sends 'turnoffpm3\\r\\n'."""
        from lib import hmi_driver as hd

        hd.turnoffpm3()
        cmds = fake_serial.get_written_strings()
        assert cmds == ["turnoffpm3\r\n"]


# ===========================================================================
# TestBattery
# ===========================================================================

class TestBattery:
    """Verify battery monitoring functions."""

    def test_readbatpercent_default(self):
        """readbatpercent() returns 100 by default (no hardware)."""
        from lib import hmi_driver as hd

        result = hd.readbatpercent()
        assert result == 100

    def test_readbatpercent_after_update(self):
        """readbatpercent() returns updated value after parsing response."""
        from lib import hmi_driver as hd

        hd._serial_key_handle("#batpct:42")
        result = hd.readbatpercent()
        assert result == 42

    def test_request_charge_state_default(self):
        """requestChargeState() returns False by default."""
        from lib import hmi_driver as hd

        result = hd.requestChargeState()
        assert result is False

    def test_charge_state_after_charging_event(self):
        """Charging state updates after CHARGING! event."""
        from lib import hmi_driver as hd

        hd._serial_key_handle("CHARGING!")
        assert hd._charging is True
        result = hd.requestChargeState()
        assert result is True

    def test_charge_state_after_response(self):
        """#charge:1 sets charging to True."""
        from lib import hmi_driver as hd

        hd._serial_key_handle("#charge:1")
        assert hd._charging is True

        hd._serial_key_handle("#charge:0")
        assert hd._charging is False


# ===========================================================================
# TestGracefulDegradation
# ===========================================================================

class TestGracefulDegradation:
    """Verify the driver works without serial hardware."""

    def test_no_serial_no_crash(self):
        """All serial commands are no-ops when _ser is None."""
        from lib import hmi_driver as hd

        assert hd._ser is None

        # These should all complete without error
        hd.restartpm3()
        hd.turnonpm3()
        hd.turnoffpm3()
        hd.presspm3()
        hd.ledpm3()
        hd.setbaklight(2)
        hd.startscreen()
        hd.stopscreen()
        hd.gotobl()
        hd.ser_byte_mode()
        hd.ser_cmd_mode()
        hd.ser_flush()
        hd.ser_putc(b"\x00")

        assert hd.readline() == ""
        assert hd.ser_getc() == b""

    def test_inject_key_for_testing(self, monkeypatch):
        """inject_key() dispatches key events without serial."""
        from lib import hmi_driver as hd
        from lib import keymap as real_keymap

        received = []
        mock_key = types.SimpleNamespace(onKey=lambda ev: received.append(ev))
        monkeypatch.setattr(real_keymap, "key", mock_key)

        hd.inject_key("KEYDOWN_PRES!")
        assert received == ["KEYDOWN_PRES!"]

    def test_setbaklight_no_serial(self):
        """setbaklight() does not crash when _ser is None."""
        from lib import hmi_driver as hd

        assert hd._ser is None
        # Should not raise
        hd.setbaklight(3)

    def test_starthmi_no_serial(self, monkeypatch):
        """starthmi() returns without error when serial is unavailable."""
        from lib import hmi_driver as hd

        # Make sure serial import fails inside DOpenPort
        real_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

        def fake_import(name, *args, **kwargs):
            if name == "serial":
                raise ImportError("no serial module")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", fake_import)

        # DOpenReadThread will start a thread — we need to stop it after
        hd.starthmi()
        # Should not have crashed
        assert hd._ser is None
        # Clean up the thread
        hd._running = False
        if hd._read_thread is not None:
            hd._read_thread.join(timeout=1)


# ===========================================================================
# TestShutdown
# ===========================================================================

class TestShutdown:
    """Verify shutdown sequence."""

    def test_plan_to_shutdown(self, fake_serial):
        """planToShutdown() sets flag and sends command."""
        from lib import hmi_driver as hd

        assert hd._shutdown_flag is False
        hd.planToShutdown()
        assert hd._shutdown_flag is True
        cmds = fake_serial.get_written_strings()
        assert "plan2shutdown\r\n" in cmds

    def test_shutdowning_flag(self, fake_serial):
        """shutdowning() returns current shutdown flag."""
        from lib import hmi_driver as hd

        assert hd.shutdowning() is False
        hd._shutdown_flag = True
        assert hd.shutdowning() is True


# ===========================================================================
# TestSerialIO
# ===========================================================================

class TestSerialIO:
    """Verify low-level serial I/O primitives."""

    def test_readline_returns_decoded_string(self, fake_serial):
        """readline() returns a decoded stripped string."""
        from lib import hmi_driver as hd

        fake_serial.enqueue_line("hello world")
        result = hd.readline()
        assert result == "hello world"

    def test_ser_getc_returns_byte(self, fake_serial):
        """ser_getc() returns a single byte."""
        from lib import hmi_driver as hd

        fake_serial.enqueue_bytes(b"\xAB")
        result = hd.ser_getc()
        assert result == b"\xAB"

    def test_ser_putc_writes_bytes(self, fake_serial):
        """ser_putc() writes raw bytes to serial."""
        from lib import hmi_driver as hd

        hd.ser_putc(b"\x01\x02")
        assert fake_serial._written == [b"\x01\x02"]

    def test_set_com_read_back(self):
        """SetComReadBack() registers a callback."""
        from lib import hmi_driver as hd

        received = []
        hd.SetComReadBack(lambda data: received.append(data))

        # Unrecognized data should go to the callback
        hd._serial_key_handle("custom_data_123")
        assert received == ["custom_data_123"]

    def test_dopen_dclose_port(self, monkeypatch):
        """DOpenPort / DClosePort lifecycle with FakeSerial."""
        from lib import hmi_driver as hd

        # Patch serial.Serial to return our fake
        fake_serial_mod = types.ModuleType("serial")
        fake_serial_mod.Serial = FakeSerial
        monkeypatch.setitem(sys.modules, "serial", fake_serial_mod)

        hd.DOpenPort("/dev/ttyS0", 57600)
        assert hd._ser is not None
        assert hd._ser.is_open is True

        hd.DClosePort()
        assert hd._ser is None
