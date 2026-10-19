"""Tests for 4 ICS bug fixes (GitHub Issues #58-#61 on lab-401/icopy-x).

Covers:
1. Issue 58: _KW_WRBL_SUCCESS accepts both legacy 'successful' (any case) and
   iceman '( ok )' with variable spacing
2. Issue 59: writeDataBlock() calls executor.stopPM3Task() on PM3 task error
   and on no success keyword
3. Issue 60: _decoder_port_devices() filters by USB VID:PID
4. Issue 61: parse_block() logs full block 7 key without truncation

Follows upstream test patterns (PhantomPlanetDev/icopy-x):
- monkeypatch.setitem(sys.modules, 'executor', types.ModuleType)
- pytest.mark.parametrize for data-driven cases
- Shared MockCanvas from tests/ui/conftest.py
"""

import re
import sys
import types
from types import SimpleNamespace

import pytest


# ===========================================================================
# Issue 58: _KW_WRBL_SUCCESS regex tolerance
# ===========================================================================

class TestWrblSuccessKeyword:
    """Test _KW_WRBL_SUCCESS matches legacy and iceman success formats."""

    @pytest.mark.parametrize('text', [
        "Wrote block 07 successful",
        "Wrote block 10 SUCCESSFUL",
        "Wrote block 07 Successful",
        "WRITE SUCCESSFUL",
    ])
    def test_matches_successful_any_case(self, text):
        import iclasswrite
        pattern = iclasswrite._KW_WRBL_SUCCESS
        assert re.search(pattern, text) is not None

    @pytest.mark.parametrize('text', [
        "Wrote block 6 / 0x06 ( ok )",
        "Wrote block 6 / 0x06 (ok)",
        "Wrote block 6 / 0x06 (  ok  )",
    ])
    def test_matches_iceman_ok(self, text):
        import iclasswrite
        pattern = iclasswrite._KW_WRBL_SUCCESS
        assert re.search(pattern, text) is not None

    @pytest.mark.parametrize('text', [
        "Wrote block 07 failed",
        "Error: invalid block",
        "Wrote block 07 error",
    ])
    def test_does_not_match_error(self, text):
        import iclasswrite
        pattern = iclasswrite._KW_WRBL_SUCCESS
        assert re.search(pattern, text) is None


# ===========================================================================
# Issue 59: stopPM3Task cleanup on write failure
# ===========================================================================

def _make_executor(start_ret=0, has_keyword=True):
    """Create a types.ModuleType-based mock executor matching upstream pattern."""
    executor = types.ModuleType('executor')
    executor._calls = []

    def startPM3Task(cmd, timeout=10000):
        executor._calls.append(('start', cmd))
        return start_ret

    def hasKeyword(keywords, line=None):
        executor._calls.append(('keyword', keywords))
        return has_keyword_ret[0]

    def stopPM3Task(listener=None, wait=True):
        executor._calls.append(('stop',))

    def getPrintContent():
        return ''

    has_keyword_ret = [has_keyword]
    executor.startPM3Task = startPM3Task
    executor.hasKeyword = hasKeyword
    executor.stopPM3Task = stopPM3Task
    executor.getPrintContent = getPrintContent
    return executor


class TestStopPM3TaskCleanup:
    """Test writeDataBlock() calls stopPM3Task on failure paths."""

    def test_stopPM3_called_on_task_error(self, monkeypatch):
        import iclasswrite
        executor = _make_executor(start_ret=-1)
        monkeypatch.setitem(sys.modules, 'executor', executor)
        monkeypatch.setitem(sys.modules, 'hficlass', None)
        import importlib
        importlib.reload(iclasswrite)

        iclasswrite.writeDataBlock(17, 7, "0011223344556677", "2020666666668888")
        stop_calls = [c for c in executor._calls if c[0] == 'stop']
        assert len(stop_calls) == 1

    def test_stopPM3_called_on_no_keyword(self, monkeypatch):
        import iclasswrite
        executor = _make_executor(start_ret=0, has_keyword=False)
        monkeypatch.setitem(sys.modules, 'executor', executor)
        monkeypatch.setitem(sys.modules, 'hficlass', None)
        import importlib
        importlib.reload(iclasswrite)

        iclasswrite.writeDataBlock(17, 7, "0011223344556677", "2020666666668888")
        stop_calls = [c for c in executor._calls if c[0] == 'stop']
        assert len(stop_calls) == 1

    def test_stopPM3_not_called_on_success(self, monkeypatch):
        import iclasswrite
        executor = _make_executor(start_ret=0, has_keyword=True)
        monkeypatch.setitem(sys.modules, 'executor', executor)
        monkeypatch.setitem(sys.modules, 'hficlass', None)
        import importlib
        importlib.reload(iclasswrite)

        result = iclasswrite.writeDataBlock(17, 7, "0011223344556677", "2020666666668888")
        assert result == 0
        stop_calls = [c for c in executor._calls if c[0] == 'stop']
        assert len(stop_calls) == 0


# ===========================================================================
# Issue 60: _decoder_port_devices() VID:PID filtering
# ===========================================================================

class TestDecoderPortDevices:
    """Test _decoder_port_devices filters by USB VID:PID."""

    @pytest.mark.parametrize('vid,pid,should_match', [
        (0x2341, 0x0043, True),   # SparkFun Pro Micro
        (0x2A03, 0x0043, True),   # Arduino/Genuino Micro (clone)
        (0x1B4F, 0x9206, True),   # Adafruit Feather 32U4
        (0x0403, 0x6001, False),  # FTDI adapter (should not match)
        (None, None, False),      # No VID/PID (should not match)
    ])
    def test_vid_pid_filtering(self, monkeypatch, vid, pid, should_match):
        import ics_decoder
        fake_port = SimpleNamespace(device='/dev/ttyACM0', vid=vid, pid=pid)
        monkeypatch.setattr(ics_decoder, '_comports',
                            lambda: [fake_port])
        result = ics_decoder._decoder_port_devices()
        if should_match:
            assert '/dev/ttyACM0' in result
        else:
            assert result == set()

    def test_multiple_ports_mixed(self, monkeypatch):
        import ics_decoder
        ports = [
            SimpleNamespace(device='/dev/ttyACM0', vid=0x2341, pid=0x0043),
            SimpleNamespace(device='/dev/ttyACM1', vid=0x0403, pid=0x6001),
            SimpleNamespace(device='/dev/ttyACM2', vid=0x2A03, pid=0x0043),
        ]
        monkeypatch.setattr(ics_decoder, '_comports', lambda: ports)
        result = ics_decoder._decoder_port_devices()
        assert '/dev/ttyACM0' in result
        assert '/dev/ttyACM1' not in result
        assert '/dev/ttyACM2' in result

    def test_comports_none_returns_empty(self, monkeypatch):
        import ics_decoder
        monkeypatch.setattr(ics_decoder, '_comports', None)
        result = ics_decoder._decoder_port_devices()
        assert result == set()


# ===========================================================================
# Issue 61: parse_block() full key logging
# ===========================================================================

class TestKeyLogging:
    """Test parse_block logs full block 7 key without truncation."""

    @pytest.mark.parametrize('blk7_hex', [
        "0011223344556677",
        "AABBCCDDEEFF0011",
        "DEADBEEFCAFEBABE",
    ])
    def test_logs_full_blk7_key(self, monkeypatch, blk7_hex):
        import ics_decoder
        logged = []
        monkeypatch.setattr(ics_decoder, '_log', lambda msg: logged.append(msg))

        frame = "$A_CARD_START$\nBlk7#:{}\n$A_CARD_STOP$".format(blk7_hex)
        ics_decoder.parse_block(frame, frame.encode('utf-8'))

        key_log = [m for m in logged if 'Key#:' in m]
        assert len(key_log) == 1
        assert key_log[0] == 'Key#: {}'.format(blk7_hex.upper())

    def test_no_key_log_when_blk7_absent(self, monkeypatch):
        import ics_decoder
        logged = []
        monkeypatch.setattr(ics_decoder, '_log', lambda msg: logged.append(msg))

        frame = "$A_CARD_START$\nwiedata#:000001FF\n$A_CARD_STOP$"
        ics_decoder.parse_block(frame, frame.encode('utf-8'))

        key_logs = [m for m in logged if 'Key#:' in m]
        assert len(key_logs) == 0

    def test_key_not_truncated(self, monkeypatch):
        import ics_decoder
        logged = []
        monkeypatch.setattr(ics_decoder, '_log', lambda msg: logged.append(msg))

        full_key = "AABBCCDDEEFF001122334455667788"
        frame = "$A_CARD_START$\nBlk7#:{}\n$A_CARD_STOP$".format(full_key)
        ics_decoder.parse_block(frame, frame.encode('utf-8'))

        key_log = [m for m in logged if 'Key#:' in m][0]
        # Verify the full key is present — not truncated to 2 chars
        assert full_key.upper() in key_log
        assert len(key_log) > 10
