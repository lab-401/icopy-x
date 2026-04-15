"""Tests for pm3_flash -- PM3 firmware flash engine.

Covers:
  - _parse_hw_version: empty, full, partial, os-only, NIKOLA-only
  - get_running_version: executor None, task fail, empty output, valid, exception
  - get_image_version: None path, missing path, invalid JSON, valid, IOError
  - needs_flash: no manifest, no version, PM3 not connected, no OS, match, mismatch
  - check_safety: hmi_driver None, battery/charging combos, exception
  - _check_bootrom_safety: clean cmd, --unlock-bootloader, bootrom.elf
  - _parse_flash_output: all recognized lines, block info, unrecognized, empty
  - _run_flash_command: bootrom block, OSError, timeout, success, fail, progress_cb
  - flash_firmware: pm3 not found, image not found, bootrom.elf path, integrity fail,
                    dry run, full success, flash fail
  - verify_image_integrity: no manifest, no SHA, image not found, mismatch, match

All tests run headless.  External dependencies (hmi_driver, executor, subprocess)
are fully mocked.
"""

import hashlib
import json
import os
import sys
import tempfile
import time

import pytest
from unittest import mock
from unittest.mock import MagicMock, patch, PropertyMock, call

import pm3_flash
from pm3_flash import (
    _parse_hw_version,
    get_running_version,
    get_image_version,
    needs_flash,
    check_safety,
    _check_bootrom_safety,
    _parse_flash_output,
    _run_flash_command,
    _wait_for_device,
    flash_firmware,
    verify_image_integrity,
    STAGE_ENTERING_BOOTLOADER,
    STAGE_FLASHING,
    STAGE_COMPLETE,
    STAGE_PREPARING,
    STAGE_KILLING_PM3,
    STAGE_RESTARTING,
    STAGE_VERIFYING,
    BATTERY_MIN_PERCENT,
    PM3_DEVICE,
    FLASH_TIMEOUT,
)


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture
def app_dir(tmp_path):
    """Create a minimal app_dir with firmware directory structure."""
    fw_dir = tmp_path / 'res' / 'firmware' / 'pm3'
    fw_dir.mkdir(parents=True)
    pm3_dir = tmp_path / 'pm3'
    pm3_dir.mkdir()
    return str(tmp_path)


@pytest.fixture
def manifest_file(app_dir):
    """Write a valid manifest.json and matching fullimage.elf. Returns (app_dir, sha)."""
    fw_dir = os.path.join(app_dir, 'res', 'firmware', 'pm3')
    image_path = os.path.join(fw_dir, 'fullimage.elf')

    # Write a dummy image
    image_content = b'fake elf binary content for testing'
    with open(image_path, 'wb') as f:
        f.write(image_content)

    # Compute its SHA
    sha = hashlib.sha256(image_content).hexdigest()

    manifest_path = os.path.join(fw_dir, 'manifest.json')
    manifest_data = {
        'pm3_firmware_version': 'RRG/Iceman/master/abc1234',
        'pm3_firmware_sha256': sha,
        'pm3_client_version': '4.17768',
        'build_platform': 'PM3ICOPYX',
        'build_date': '2026-04-12',
    }
    with open(manifest_path, 'w') as f:
        json.dump(manifest_data, f)

    return app_dir, sha


@pytest.fixture
def pm3_binary(app_dir):
    """Create a fake proxmark3 binary file."""
    pm3_bin = os.path.join(app_dir, 'pm3', 'proxmark3')
    with open(pm3_bin, 'w') as f:
        f.write('#!/bin/sh\n')
    os.chmod(pm3_bin, 0o755)
    return pm3_bin


# =====================================================================
# HW version line constants for test reuse
# =====================================================================

HW_VERSION_FULL = """\
 [ ARM ]
  bootrom: RRG/Iceman/master/release (git)
       os: RRG/Iceman/master/385d892f-dirty-unclean 2022-06-09 14:19:31
   NIKOLA: v3.1 2022-06-09 14:19:31
   client: RRG/Iceman/master/release (git)
     FPGA: v0.10"""

HW_VERSION_OS_ONLY = """\
       os: RRG/Iceman/master/385d892f 2022-06-09 14:19:31"""

HW_VERSION_NIKOLA_ONLY = """\
   NIKOLA: v3.1 2022-06-09 14:19:31"""

HW_VERSION_PARTIAL = """\
 [ ARM ]
  bootrom: RRG/Iceman/master/release (git)
       os: RRG/Iceman/master/abc1234 2022-06-09 14:19:31"""


# =====================================================================
# TestParseHwVersion
# =====================================================================

class TestParseHwVersion:
    """Tests for _parse_hw_version()."""

    def test_empty_input_returns_empty_fields(self):
        """Empty string returns dict with all empty string values."""
        result = _parse_hw_version('')
        assert result['os'] == ''
        assert result['bootrom'] == ''
        assert result['nikola'] == ''
        assert result['client'] == ''
        assert result['fpga'] == ''
        assert result['raw'] == ''

    def test_none_input_returns_empty_fields(self):
        """None returns dict with all empty string values."""
        result = _parse_hw_version(None)
        assert result['os'] == ''
        assert result['bootrom'] == ''
        assert result['raw'] == ''

    def test_full_hw_version_all_fields_parsed(self):
        """Full hw version output has all fields populated."""
        result = _parse_hw_version(HW_VERSION_FULL)
        assert 'RRG/Iceman/master/release' in result['bootrom']
        assert '385d892f-dirty-unclean' in result['os']
        assert 'v3.1' in result['nikola']
        assert 'RRG/Iceman/master/release' in result['client']
        assert 'v0.10' in result['fpga']
        assert result['raw'] == HW_VERSION_FULL

    def test_partial_output_missing_fields_empty(self):
        """Partial output: present fields populated, missing fields empty."""
        result = _parse_hw_version(HW_VERSION_PARTIAL)
        assert 'RRG/Iceman/master/release' in result['bootrom']
        assert 'abc1234' in result['os']
        assert result['nikola'] == ''
        assert result['client'] == ''
        assert result['fpga'] == ''

    def test_os_only_output(self):
        """Output with only os: line."""
        result = _parse_hw_version(HW_VERSION_OS_ONLY)
        assert '385d892f' in result['os']
        assert result['bootrom'] == ''
        assert result['nikola'] == ''

    def test_nikola_only_output(self):
        """Output with only NIKOLA line."""
        result = _parse_hw_version(HW_VERSION_NIKOLA_ONLY)
        assert result['os'] == ''
        assert result['bootrom'] == ''
        assert 'v3.1' in result['nikola']


# =====================================================================
# TestGetRunningVersion
# =====================================================================

class TestGetRunningVersion:
    """Tests for get_running_version()."""

    def test_executor_none_returns_none(self):
        """When executor is None, returns None."""
        with patch.object(pm3_flash, 'executor', None):
            result = get_running_version()
            assert result is None

    def test_startpm3task_not_1_returns_none(self):
        """When startPM3Task returns != 1, returns None."""
        mock_exec = MagicMock()
        mock_exec.startPM3Task.return_value = -1
        with patch.object(pm3_flash, 'executor', mock_exec):
            result = get_running_version()
            assert result is None

    def test_getprintcontent_empty_returns_none(self):
        """When getPrintContent returns empty string, returns None."""
        mock_exec = MagicMock()
        mock_exec.startPM3Task.return_value = 1
        mock_exec.getPrintContent.return_value = ''
        with patch.object(pm3_flash, 'executor', mock_exec):
            result = get_running_version()
            assert result is None

    def test_getprintcontent_none_returns_none(self):
        """When getPrintContent returns None, returns None."""
        mock_exec = MagicMock()
        mock_exec.startPM3Task.return_value = 1
        mock_exec.getPrintContent.return_value = None
        with patch.object(pm3_flash, 'executor', mock_exec):
            result = get_running_version()
            assert result is None

    def test_valid_output_returns_parsed_dict(self):
        """Valid hw version output returns a populated dict."""
        mock_exec = MagicMock()
        mock_exec.startPM3Task.return_value = 1
        mock_exec.getPrintContent.return_value = HW_VERSION_FULL
        with patch.object(pm3_flash, 'executor', mock_exec):
            result = get_running_version()
            assert result is not None
            assert '385d892f-dirty-unclean' in result['os']
            assert 'v3.1' in result['nikola']

    def test_exception_returns_none(self):
        """Exception during execution returns None."""
        mock_exec = MagicMock()
        mock_exec.startPM3Task.side_effect = ConnectionError("TCP refused")
        with patch.object(pm3_flash, 'executor', mock_exec):
            result = get_running_version()
            assert result is None


# =====================================================================
# TestGetImageVersion
# =====================================================================

class TestGetImageVersion:
    """Tests for get_image_version()."""

    def test_none_path_returns_none(self):
        """None manifest_path returns None."""
        result = get_image_version(None)
        assert result is None

    def test_empty_string_path_returns_none(self):
        """Empty string manifest_path returns None."""
        result = get_image_version('')
        assert result is None

    def test_nonexistent_path_returns_none(self):
        """Path that does not exist returns None."""
        result = get_image_version('/nonexistent/manifest.json')
        assert result is None

    def test_invalid_json_returns_none(self, tmp_path):
        """Manifest file with invalid JSON returns None."""
        p = tmp_path / 'manifest.json'
        p.write_text('{bad json content', encoding='utf-8')
        result = get_image_version(str(p))
        assert result is None

    def test_valid_json_returns_dict(self, tmp_path):
        """Valid manifest.json returns the parsed dict."""
        data = {
            'pm3_firmware_version': 'RRG/Iceman/master/abc1234',
            'pm3_firmware_sha256': 'deadbeef' * 8,
            'build_date': '2026-04-12',
        }
        p = tmp_path / 'manifest.json'
        p.write_text(json.dumps(data), encoding='utf-8')
        result = get_image_version(str(p))
        assert result is not None
        assert result['pm3_firmware_version'] == 'RRG/Iceman/master/abc1234'
        assert result['build_date'] == '2026-04-12'

    def test_ioerror_returns_none(self, tmp_path):
        """IOError when reading manifest returns None."""
        p = tmp_path / 'manifest.json'
        p.write_text('{}', encoding='utf-8')
        with patch('builtins.open', side_effect=IOError("disk error")):
            result = get_image_version(str(p))
            assert result is None


# =====================================================================
# TestNeedsFlash
# =====================================================================

class TestNeedsFlash:
    """Tests for needs_flash()."""

    def test_no_manifest_returns_false(self, app_dir):
        """No manifest.json means no flash needed."""
        result = needs_flash(app_dir)
        assert result is False

    def test_manifest_no_version_returns_false(self, app_dir):
        """Manifest with no pm3_firmware_version returns False."""
        fw_dir = os.path.join(app_dir, 'res', 'firmware', 'pm3')
        manifest_path = os.path.join(fw_dir, 'manifest.json')
        with open(manifest_path, 'w') as f:
            json.dump({'build_date': '2026-04-12'}, f)

        result = needs_flash(app_dir)
        assert result is False

    def test_manifest_empty_version_returns_false(self, app_dir):
        """Manifest with empty pm3_firmware_version returns False."""
        fw_dir = os.path.join(app_dir, 'res', 'firmware', 'pm3')
        manifest_path = os.path.join(fw_dir, 'manifest.json')
        with open(manifest_path, 'w') as f:
            json.dump({'pm3_firmware_version': ''}, f)

        result = needs_flash(app_dir)
        assert result is False

    def test_pm3_not_connected_returns_true(self, app_dir):
        """PM3 not connected (get_running_version returns None) -> True."""
        fw_dir = os.path.join(app_dir, 'res', 'firmware', 'pm3')
        manifest_path = os.path.join(fw_dir, 'manifest.json')
        with open(manifest_path, 'w') as f:
            json.dump({'pm3_firmware_version': 'abc1234'}, f)

        with patch('pm3_flash.get_running_version', return_value=None):
            result = needs_flash(app_dir)
            assert result is True

    def test_running_no_os_returns_true(self, app_dir):
        """Running version has no os string -> True."""
        fw_dir = os.path.join(app_dir, 'res', 'firmware', 'pm3')
        manifest_path = os.path.join(fw_dir, 'manifest.json')
        with open(manifest_path, 'w') as f:
            json.dump({'pm3_firmware_version': 'abc1234'}, f)

        running = {'os': '', 'bootrom': 'something', 'nikola': '', 'client': '', 'fpga': '', 'raw': ''}
        with patch('pm3_flash.get_running_version', return_value=running):
            result = needs_flash(app_dir)
            assert result is True

    def test_version_match_returns_false(self, app_dir):
        """Target version substring in running OS -> False (no flash needed)."""
        fw_dir = os.path.join(app_dir, 'res', 'firmware', 'pm3')
        manifest_path = os.path.join(fw_dir, 'manifest.json')
        with open(manifest_path, 'w') as f:
            json.dump({'pm3_firmware_version': 'abc1234'}, f)

        running = {
            'os': 'RRG/Iceman/master/abc1234-dirty 2022-06-09',
            'bootrom': '', 'nikola': '', 'client': '', 'fpga': '', 'raw': '',
        }
        with patch('pm3_flash.get_running_version', return_value=running):
            result = needs_flash(app_dir)
            assert result is False

    def test_version_mismatch_returns_true(self, app_dir):
        """Target version not in running OS -> True (flash needed)."""
        fw_dir = os.path.join(app_dir, 'res', 'firmware', 'pm3')
        manifest_path = os.path.join(fw_dir, 'manifest.json')
        with open(manifest_path, 'w') as f:
            json.dump({'pm3_firmware_version': 'new_version_xyz'}, f)

        running = {
            'os': 'RRG/Iceman/master/old_version_123 2022-06-09',
            'bootrom': '', 'nikola': '', 'client': '', 'fpga': '', 'raw': '',
        }
        with patch('pm3_flash.get_running_version', return_value=running):
            result = needs_flash(app_dir)
            assert result is True


# =====================================================================
# TestCheckSafety
# =====================================================================

class TestCheckSafety:
    """Tests for check_safety()."""

    def test_hmi_driver_none_returns_safe(self):
        """When hmi_driver is None, assume safe (QEMU/test environment)."""
        with patch.object(pm3_flash, 'hmi_driver', None):
            safe, msg = check_safety()
            assert safe is True
            assert msg == ''

    def test_battery_high_and_charging_returns_safe(self):
        """Battery >= 50% and charging -> safe."""
        mock_hmi = MagicMock()
        mock_hmi.readbatpercent.return_value = 80
        mock_hmi.requestChargeState.return_value = True
        with patch.object(pm3_flash, 'hmi_driver', mock_hmi):
            safe, msg = check_safety()
            assert safe is True
            assert msg == ''

    def test_battery_exactly_50_and_charging_returns_safe(self):
        """Battery exactly 50% and charging -> safe (boundary check)."""
        mock_hmi = MagicMock()
        mock_hmi.readbatpercent.return_value = 50
        mock_hmi.requestChargeState.return_value = True
        with patch.object(pm3_flash, 'hmi_driver', mock_hmi):
            safe, msg = check_safety()
            assert safe is True
            assert msg == ''

    def test_battery_low_and_charging_returns_unsafe(self):
        """Battery < 50% and charging -> unsafe with recharge message."""
        mock_hmi = MagicMock()
        mock_hmi.readbatpercent.return_value = 30
        mock_hmi.requestChargeState.return_value = True
        with patch.object(pm3_flash, 'hmi_driver', mock_hmi):
            safe, msg = check_safety()
            assert safe is False
            assert 'Battery too low' in msg
            assert '30%' in msg

    def test_battery_high_and_not_charging_returns_unsafe(self):
        """Battery >= 50% and not charging -> unsafe with plug-in message."""
        mock_hmi = MagicMock()
        mock_hmi.readbatpercent.return_value = 80
        mock_hmi.requestChargeState.return_value = False
        with patch.object(pm3_flash, 'hmi_driver', mock_hmi):
            safe, msg = check_safety()
            assert safe is False
            assert 'not plugged in' in msg

    def test_battery_low_and_not_charging_returns_unsafe_brick_warning(self):
        """Battery < 50% and not charging -> unsafe with brick warning."""
        mock_hmi = MagicMock()
        mock_hmi.readbatpercent.return_value = 10
        mock_hmi.requestChargeState.return_value = False
        with patch.object(pm3_flash, 'hmi_driver', mock_hmi):
            safe, msg = check_safety()
            assert safe is False
            assert 'brick' in msg.lower() or 'too low' in msg.lower()
            assert '10%' in msg

    def test_battery_49_not_charging_hits_both_low_and_unplugged(self):
        """Battery 49% and not charging -> hits the combined (low+unplugged) branch."""
        mock_hmi = MagicMock()
        mock_hmi.readbatpercent.return_value = 49
        mock_hmi.requestChargeState.return_value = False
        with patch.object(pm3_flash, 'hmi_driver', mock_hmi):
            safe, msg = check_safety()
            assert safe is False
            # This should hit the "low battery AND not plugged in" branch
            assert 'brick' in msg.lower()

    def test_exception_reading_battery_returns_unsafe(self):
        """Exception from hmi_driver returns unsafe with error message."""
        mock_hmi = MagicMock()
        mock_hmi.readbatpercent.side_effect = RuntimeError("I2C read error")
        with patch.object(pm3_flash, 'hmi_driver', mock_hmi):
            safe, msg = check_safety()
            assert safe is False
            assert 'Cannot read' in msg

    def test_exception_reading_charge_state_returns_unsafe(self):
        """Exception from requestChargeState returns unsafe."""
        mock_hmi = MagicMock()
        mock_hmi.readbatpercent.return_value = 80
        mock_hmi.requestChargeState.side_effect = OSError("GPIO error")
        with patch.object(pm3_flash, 'hmi_driver', mock_hmi):
            safe, msg = check_safety()
            assert safe is False
            assert 'Cannot read' in msg


# =====================================================================
# TestCheckBootromSafety
# =====================================================================

class TestCheckBootromSafety:
    """Tests for _check_bootrom_safety()."""

    def test_clean_command_no_exception(self):
        """A clean command with no bootrom references passes."""
        _check_bootrom_safety('proxmark3 /dev/ttyACM0 --flash --image fullimage.elf')

    def test_unlock_bootloader_raises(self):
        """Command containing --unlock-bootloader raises RuntimeError."""
        with pytest.raises(RuntimeError, match='--unlock-bootloader'):
            _check_bootrom_safety(
                'proxmark3 /dev/ttyACM0 --flash --unlock-bootloader --image bootrom.elf'
            )

    def test_bootrom_elf_raises(self):
        """Command containing bootrom.elf raises RuntimeError."""
        with pytest.raises(RuntimeError, match='bootrom.elf'):
            _check_bootrom_safety(
                'proxmark3 /dev/ttyACM0 --flash --image bootrom.elf'
            )

    def test_both_blocklisted_raises_on_first(self):
        """Command with both blocked strings raises on the first match."""
        with pytest.raises(RuntimeError):
            _check_bootrom_safety(
                'proxmark3 --unlock-bootloader --image bootrom.elf'
            )

    def test_empty_string_no_exception(self):
        """Empty command string passes without error."""
        _check_bootrom_safety('')


# =====================================================================
# TestParseFlashOutput
# =====================================================================

class TestParseFlashOutput:
    """Tests for _parse_flash_output()."""

    def test_empty_line_returns_none(self):
        """Empty string returns None."""
        assert _parse_flash_output('') is None

    def test_none_returns_none(self):
        """None input returns None."""
        assert _parse_flash_output(None) is None

    def test_whitespace_only_returns_none(self):
        """Whitespace-only line returns None (after stripping, no match)."""
        assert _parse_flash_output('   ') is None

    def test_waiting_for_proxmark3(self):
        """'Waiting for Proxmark3' -> (5, entering_bootloader)."""
        result = _parse_flash_output('Waiting for Proxmark3 to appear on /dev/ttyACM0')
        assert result == (5, STAGE_ENTERING_BOOTLOADER)

    def test_entering_bootloader(self):
        """'Entering bootloader' -> (15, entering_bootloader)."""
        result = _parse_flash_output(' Entering bootloader...')
        assert result == (15, STAGE_ENTERING_BOOTLOADER)

    def test_loading_elf_file(self):
        """'Loading ELF file' -> (25, flashing)."""
        result = _parse_flash_output('Loading ELF file fullimage.elf')
        assert result == (25, STAGE_FLASHING)

    def test_flashing_dots(self):
        """'Flashing...' -> (30, flashing)."""
        result = _parse_flash_output('Flashing...')
        assert result == (30, STAGE_FLASHING)

    def test_writing_segments(self):
        """'Writing segments' -> (30, flashing)."""
        result = _parse_flash_output('Writing segments for file: fullimage.elf')
        assert result == (30, STAGE_FLASHING)

    def test_block_info_line(self):
        """Block info with hex addresses and block count -> (35, flashing)."""
        result = _parse_flash_output(
            '0x00102000..0x0013e0eb [0x3c0ec / 481 blocks]'
        )
        assert result == (35, STAGE_FLASHING)

    def test_mm_ok(self):
        """'mm OK' at end of line -> (95, flashing)."""
        result = _parse_flash_output('mmmmmmmmmmmmmmmmmm OK')
        assert result == (95, STAGE_FLASHING)

    def test_standalone_ok(self):
        """Standalone 'OK' -> (95, flashing)."""
        result = _parse_flash_output('OK')
        assert result == (95, STAGE_FLASHING)

    def test_all_done(self):
        """'All done' -> (100, complete)."""
        result = _parse_flash_output('All done. Have a nice day!')
        assert result == (100, STAGE_COMPLETE)

    def test_found_with_number(self):
        """'1 found' line -> (10, entering_bootloader)."""
        result = _parse_flash_output('  1 found on /dev/ttyACM0')
        assert result == (10, STAGE_ENTERING_BOOTLOADER)

    def test_unrecognized_line_returns_none(self):
        """Unrecognized line returns None."""
        assert _parse_flash_output('Some random debug output here') is None

    def test_found_without_number_returns_none(self):
        """'found' without a preceding number returns None."""
        assert _parse_flash_output('Device not found') is None


# =====================================================================
# TestRunFlashCommand
# =====================================================================

class TestRunFlashCommand:
    """Tests for _run_flash_command()."""

    def test_bootrom_safety_blocks_command(self):
        """Command with bootrom.elf in image_path raises RuntimeError."""
        with pytest.raises(RuntimeError, match='bootrom.elf'):
            _run_flash_command(
                '/usr/bin/proxmark3', '/dev/ttyACM0',
                '/path/to/bootrom.elf'
            )

    def test_bootrom_safety_blocks_unlock_in_binary_path(self):
        """Binary path containing --unlock-bootloader raises RuntimeError."""
        with pytest.raises(RuntimeError, match='--unlock-bootloader'):
            _run_flash_command(
                '/usr/bin/proxmark3 --unlock-bootloader', '/dev/ttyACM0',
                '/path/to/fullimage.elf'
            )

    def test_popen_oserror_returns_failure(self):
        """OSError when starting process returns (False, message)."""
        with patch('subprocess.Popen', side_effect=OSError("No such binary")):
            success, output = _run_flash_command(
                '/nonexistent/proxmark3', '/dev/ttyACM0',
                '/path/to/fullimage.elf'
            )
            assert success is False
            assert 'Failed to start' in output

    def test_process_timeout_returns_failure(self):
        """Process exceeding timeout returns (False, 'timed out')."""
        mock_proc = MagicMock()
        mock_proc.stdout.readline.return_value = ''
        mock_proc.poll.return_value = None  # still running
        mock_proc.kill.return_value = None
        mock_proc.wait.return_value = None
        mock_proc.stdout.read.return_value = ''
        mock_proc.stdout.close.return_value = None

        # Make monotonic advance past timeout on the check
        start_time = 1000.0
        call_count = [0]

        def fake_monotonic():
            call_count[0] += 1
            if call_count[0] <= 1:
                return start_time
            # Second call: way past timeout
            return start_time + 200

        with patch('subprocess.Popen', return_value=mock_proc), \
             patch('time.monotonic', side_effect=fake_monotonic), \
             patch('time.sleep'):
            success, output = _run_flash_command(
                '/usr/bin/proxmark3', '/dev/ttyACM0',
                '/path/to/fullimage.elf',
                timeout=120,
            )
            assert success is False
            assert 'timed out' in output
            mock_proc.kill.assert_called_once()

    def test_process_success_all_done(self):
        """Process completes with 'All done' and retcode 0 -> (True, output)."""
        flash_lines = [
            'Waiting for Proxmark3 to appear on /dev/ttyACM0\n',
            'Entering bootloader...\n',
            'Loading ELF file fullimage.elf\n',
            'Flashing...\n',
            'Writing segments for file: fullimage.elf\n',
            'mmmmmmmm OK\n',
            'All done. Have a nice day!\n',
            '',  # EOF signal
        ]
        line_idx = [0]

        def fake_readline():
            if line_idx[0] < len(flash_lines):
                line = flash_lines[line_idx[0]]
                line_idx[0] += 1
                return line
            return ''

        mock_proc = MagicMock()
        mock_proc.stdout.readline = fake_readline
        mock_proc.stdout.read.return_value = ''
        mock_proc.stdout.close.return_value = None
        mock_proc.returncode = 0

        # poll returns None while lines remain, then 0
        def fake_poll():
            if line_idx[0] < len(flash_lines):
                return None
            return 0

        mock_proc.poll = fake_poll
        mock_proc.wait.return_value = None

        base_time = [1000.0]

        def fake_monotonic():
            base_time[0] += 0.1
            return base_time[0]

        with patch('subprocess.Popen', return_value=mock_proc), \
             patch('time.monotonic', side_effect=fake_monotonic), \
             patch('time.sleep'):
            success, output = _run_flash_command(
                '/usr/bin/proxmark3', '/dev/ttyACM0',
                '/path/to/fullimage.elf',
            )
            assert success is True
            assert 'All done' in output

    def test_process_nonzero_exit_returns_failure(self):
        """Non-zero exit without 'All done' -> (False, output)."""
        mock_proc = MagicMock()
        mock_proc.stdout.readline.side_effect = ['Some error output\n', '']
        mock_proc.stdout.read.return_value = ''
        mock_proc.stdout.close.return_value = None
        mock_proc.returncode = 1
        mock_proc.poll.side_effect = [None, 1]
        mock_proc.wait.return_value = None

        base_time = [1000.0]

        def fake_monotonic():
            base_time[0] += 0.1
            return base_time[0]

        with patch('subprocess.Popen', return_value=mock_proc), \
             patch('time.monotonic', side_effect=fake_monotonic), \
             patch('time.sleep'):
            success, output = _run_flash_command(
                '/usr/bin/proxmark3', '/dev/ttyACM0',
                '/path/to/fullimage.elf',
            )
            assert success is False
            assert 'Some error output' in output

    def test_progress_callback_called(self):
        """Progress callback receives parsed percent and stage values."""
        flash_lines = [
            'Waiting for Proxmark3 to appear on /dev/ttyACM0\n',
            'All done. Have a nice day!\n',
            '',
        ]
        line_idx = [0]

        def fake_readline():
            if line_idx[0] < len(flash_lines):
                line = flash_lines[line_idx[0]]
                line_idx[0] += 1
                return line
            return ''

        mock_proc = MagicMock()
        mock_proc.stdout.readline = fake_readline
        mock_proc.stdout.read.return_value = ''
        mock_proc.stdout.close.return_value = None
        mock_proc.returncode = 0
        mock_proc.poll.side_effect = [None, None, 0]
        mock_proc.wait.return_value = None

        base_time = [1000.0]

        def fake_monotonic():
            base_time[0] += 0.1
            return base_time[0]

        progress_calls = []

        def track_progress(percent, stage):
            progress_calls.append((percent, stage))

        with patch('subprocess.Popen', return_value=mock_proc), \
             patch('time.monotonic', side_effect=fake_monotonic), \
             patch('time.sleep'):
            _run_flash_command(
                '/usr/bin/proxmark3', '/dev/ttyACM0',
                '/path/to/fullimage.elf',
                progress_cb=track_progress,
            )

        assert len(progress_calls) >= 2
        # First progress: "Waiting for Proxmark3" -> 5%
        assert progress_calls[0] == (5, STAGE_ENTERING_BOOTLOADER)
        # Last progress: "All done" -> 100%
        assert progress_calls[-1] == (100, STAGE_COMPLETE)

    def test_found_count_disambiguated_in_progress(self):
        """First 'found' sends 10%, second 'found' sends 20%."""
        flash_lines = [
            '  1 found on /dev/ttyACM0\n',
            '  1 found on /dev/ttyACM0\n',
            'All done. Have a nice day!\n',
            '',
        ]
        line_idx = [0]

        def fake_readline():
            if line_idx[0] < len(flash_lines):
                line = flash_lines[line_idx[0]]
                line_idx[0] += 1
                return line
            return ''

        mock_proc = MagicMock()
        mock_proc.stdout.readline = fake_readline
        mock_proc.stdout.read.return_value = ''
        mock_proc.stdout.close.return_value = None
        mock_proc.returncode = 0
        mock_proc.poll.side_effect = [None, None, None, 0]
        mock_proc.wait.return_value = None

        base_time = [1000.0]

        def fake_monotonic():
            base_time[0] += 0.1
            return base_time[0]

        progress_calls = []

        def track_progress(percent, stage):
            progress_calls.append((percent, stage))

        with patch('subprocess.Popen', return_value=mock_proc), \
             patch('time.monotonic', side_effect=fake_monotonic), \
             patch('time.sleep'):
            _run_flash_command(
                '/usr/bin/proxmark3', '/dev/ttyACM0',
                '/path/to/fullimage.elf',
                progress_cb=track_progress,
            )

        found_calls = [(p, s) for p, s in progress_calls
                        if s == STAGE_ENTERING_BOOTLOADER]
        assert (10, STAGE_ENTERING_BOOTLOADER) in found_calls
        assert (20, STAGE_ENTERING_BOOTLOADER) in found_calls

    def test_process_exception_during_read_returns_failure(self):
        """Exception during line reading kills proc and returns failure."""
        mock_proc = MagicMock()
        mock_proc.stdout.readline.side_effect = IOError("broken pipe")
        mock_proc.stdout.read.return_value = ''
        mock_proc.stdout.close.return_value = None
        mock_proc.kill.return_value = None
        mock_proc.wait.return_value = None

        base_time = [1000.0]

        def fake_monotonic():
            base_time[0] += 0.1
            return base_time[0]

        with patch('subprocess.Popen', return_value=mock_proc), \
             patch('time.monotonic', side_effect=fake_monotonic), \
             patch('time.sleep'):
            success, output = _run_flash_command(
                '/usr/bin/proxmark3', '/dev/ttyACM0',
                '/path/to/fullimage.elf',
            )
            assert success is False
            assert 'error' in output.lower()
            mock_proc.kill.assert_called()

    def test_remaining_output_collected_after_loop(self):
        """Remaining output after readline loop is collected."""
        flash_lines = [
            'All done. Have a nice day!\n',
            '',  # EOF
        ]
        line_idx = [0]

        def fake_readline():
            if line_idx[0] < len(flash_lines):
                line = flash_lines[line_idx[0]]
                line_idx[0] += 1
                return line
            return ''

        mock_proc = MagicMock()
        mock_proc.stdout.readline = fake_readline
        # Remaining output AFTER the readline loop ends
        mock_proc.stdout.read.return_value = 'Extra trailing line\nAnother line'
        mock_proc.stdout.close.return_value = None
        mock_proc.returncode = 0
        mock_proc.poll.side_effect = [None, 0]
        mock_proc.wait.return_value = None

        base_time = [1000.0]

        def fake_monotonic():
            base_time[0] += 0.1
            return base_time[0]

        with patch('subprocess.Popen', return_value=mock_proc), \
             patch('time.monotonic', side_effect=fake_monotonic), \
             patch('time.sleep'):
            success, output = _run_flash_command(
                '/usr/bin/proxmark3', '/dev/ttyACM0',
                '/path/to/fullimage.elf',
            )
            assert success is True
            assert 'Extra trailing line' in output
            assert 'Another line' in output

    def test_exception_kill_raises_oserror_swallowed(self):
        """When proc.kill() raises OSError in exception handler, it is swallowed."""
        mock_proc = MagicMock()
        mock_proc.stdout.readline.side_effect = RuntimeError("unexpected error")
        mock_proc.stdout.read.return_value = ''
        mock_proc.stdout.close.return_value = None
        # kill() raises OSError (process already dead)
        mock_proc.kill.side_effect = OSError("No such process")

        base_time = [1000.0]

        def fake_monotonic():
            base_time[0] += 0.1
            return base_time[0]

        with patch('subprocess.Popen', return_value=mock_proc), \
             patch('time.monotonic', side_effect=fake_monotonic), \
             patch('time.sleep'):
            success, output = _run_flash_command(
                '/usr/bin/proxmark3', '/dev/ttyACM0',
                '/path/to/fullimage.elf',
            )
            assert success is False
            assert 'error' in output.lower()

    def test_stdout_close_exception_swallowed(self):
        """Exception in proc.stdout.close() in finally block is swallowed."""
        flash_lines = [
            'All done. Have a nice day!\n',
            '',
        ]
        line_idx = [0]

        def fake_readline():
            if line_idx[0] < len(flash_lines):
                line = flash_lines[line_idx[0]]
                line_idx[0] += 1
                return line
            return ''

        mock_proc = MagicMock()
        mock_proc.stdout.readline = fake_readline
        mock_proc.stdout.read.return_value = ''
        # close() raises in finally block
        mock_proc.stdout.close.side_effect = OSError("fd already closed")
        mock_proc.returncode = 0
        mock_proc.poll.side_effect = [None, 0]
        mock_proc.wait.return_value = None

        base_time = [1000.0]

        def fake_monotonic():
            base_time[0] += 0.1
            return base_time[0]

        with patch('subprocess.Popen', return_value=mock_proc), \
             patch('time.monotonic', side_effect=fake_monotonic), \
             patch('time.sleep'):
            success, output = _run_flash_command(
                '/usr/bin/proxmark3', '/dev/ttyACM0',
                '/path/to/fullimage.elf',
            )
            # Should still succeed despite close() error
            assert success is True
            assert 'All done' in output

    def test_retcode_zero_no_all_done_returns_failure(self):
        """retcode 0 but no 'All done' in output -> (False, output)."""
        flash_lines = [
            'Some partial output\n',
            '',  # EOF
        ]
        line_idx = [0]

        def fake_readline():
            if line_idx[0] < len(flash_lines):
                line = flash_lines[line_idx[0]]
                line_idx[0] += 1
                return line
            return ''

        mock_proc = MagicMock()
        mock_proc.stdout.readline = fake_readline
        mock_proc.stdout.read.return_value = ''
        mock_proc.stdout.close.return_value = None
        mock_proc.returncode = 0  # retcode 0, but no "All done"
        mock_proc.poll.side_effect = [None, 0]
        mock_proc.wait.return_value = None

        base_time = [1000.0]

        def fake_monotonic():
            base_time[0] += 0.1
            return base_time[0]

        with patch('subprocess.Popen', return_value=mock_proc), \
             patch('time.monotonic', side_effect=fake_monotonic), \
             patch('time.sleep'):
            success, output = _run_flash_command(
                '/usr/bin/proxmark3', '/dev/ttyACM0',
                '/path/to/fullimage.elf',
            )
            assert success is False
            assert 'Some partial output' in output


# =====================================================================
# TestWaitForDevice
# =====================================================================

class TestWaitForDevice:
    """Tests for _wait_for_device()."""

    def test_device_exists_immediately(self):
        """Device exists right away -> returns True instantly."""
        with patch('os.path.exists', return_value=True):
            result = _wait_for_device('/dev/ttyACM0', timeout=5)
            assert result is True

    def test_device_never_appears(self):
        """Device never appears -> returns False after timeout."""
        call_count = [0]
        start = time.monotonic()

        def fake_exists(path):
            return False

        def fake_monotonic():
            # Advance time rapidly past timeout
            call_count[0] += 1
            return start + (call_count[0] * 5)

        with patch('os.path.exists', side_effect=fake_exists), \
             patch('time.monotonic', side_effect=fake_monotonic), \
             patch('time.sleep'):
            result = _wait_for_device('/dev/ttyACM0', timeout=5)
            assert result is False

    def test_device_appears_after_delay(self):
        """Device appears after a few checks -> returns True."""
        calls = [0]

        def fake_exists(path):
            calls[0] += 1
            return calls[0] >= 3

        start = time.monotonic()
        tick = [0]

        def fake_monotonic():
            tick[0] += 1
            return start + tick[0] * 0.3

        with patch('os.path.exists', side_effect=fake_exists), \
             patch('time.monotonic', side_effect=fake_monotonic), \
             patch('time.sleep'):
            result = _wait_for_device('/dev/ttyACM0', timeout=10)
            assert result is True


# =====================================================================
# TestFlashFirmware
# =====================================================================

class TestFlashFirmware:
    """Tests for flash_firmware()."""

    def test_pm3_binary_not_found(self, app_dir):
        """PM3 binary missing -> (False, 'not found')."""
        # Create image so it passes that check
        image_path = os.path.join(app_dir, 'res', 'firmware', 'pm3', 'fullimage.elf')
        with open(image_path, 'wb') as f:
            f.write(b'fake')

        success, msg = flash_firmware(app_dir)
        assert success is False
        assert 'not found' in msg

    def test_image_not_found(self, app_dir, pm3_binary):
        """Firmware image missing -> (False, 'not found')."""
        # pm3_binary exists but no fullimage.elf
        success, msg = flash_firmware(app_dir)
        assert success is False
        assert 'not found' in msg

    def test_bootrom_elf_in_image_path_blocked(self, tmp_path):
        """Image path containing bootrom.elf -> (False, blocked message)."""
        # Construct a special app_dir where image resolves to a bootrom path
        fw_dir = tmp_path / 'res' / 'firmware' / 'pm3'
        fw_dir.mkdir(parents=True)
        pm3_dir = tmp_path / 'pm3'
        pm3_dir.mkdir()

        # Create pm3 binary
        pm3_bin = pm3_dir / 'proxmark3'
        pm3_bin.write_text('#!/bin/sh\n')
        pm3_bin.chmod(0o755)

        # The fullimage.elf is the legitimate name; test bootrom blocking via
        # a direct call that resolves to bootrom.elf in the path.
        # Since flash_firmware builds the path from app_dir, we need the
        # file to actually be named fullimage.elf -- the bootrom check is on
        # the path string. We can test this by patching os.path.join to return
        # a bootrom path, but it is cleaner to test _check_bootrom_safety
        # directly (already covered above) and test via the image_path check.
        # Instead, patch the image_path after construction.
        image_path = fw_dir / 'fullimage.elf'
        image_path.write_bytes(b'fake')

        # Patch _check_bootrom_safety to raise for the image path
        with patch('pm3_flash._check_bootrom_safety',
                   side_effect=[RuntimeError("BLOCKED: bootrom.elf")]):
            success, msg = flash_firmware(str(tmp_path))
            assert success is False
            assert 'BLOCKED' in msg

    def test_integrity_check_fails(self, manifest_file, pm3_binary):
        """Integrity check failure -> (False, 'integrity check failed')."""
        app_dir, sha = manifest_file

        # Corrupt the image so SHA mismatches
        image_path = os.path.join(app_dir, 'res', 'firmware', 'pm3', 'fullimage.elf')
        with open(image_path, 'wb') as f:
            f.write(b'corrupted content that does not match SHA')

        with patch('subprocess.call'):  # mock killall
            success, msg = flash_firmware(app_dir)
            assert success is False
            assert 'integrity check failed' in msg.lower() or 'SHA256 mismatch' in msg

    def test_dry_run_skips_everything(self, app_dir):
        """Dry run mode returns success without executing any destructive ops."""
        progress_calls = []

        def track_progress(percent, stage):
            progress_calls.append((percent, stage))

        success, msg = flash_firmware(app_dir, progress_cb=track_progress, dry_run=True)
        assert success is True
        assert 'DRY RUN' in msg

        # Progress callbacks should have been called
        assert len(progress_calls) > 0
        # Should reach completion
        stages = [s for _, s in progress_calls]
        assert STAGE_COMPLETE in stages

    def test_flash_command_fails(self, manifest_file, pm3_binary):
        """Flash command failure -> (False, 'Flash failed')."""
        app_dir, sha = manifest_file

        with patch('subprocess.call'), \
             patch('time.sleep'), \
             patch('pm3_flash._run_flash_command',
                   return_value=(False, 'Flash process error: some error')):
            success, msg = flash_firmware(app_dir)
            assert success is False
            assert 'Flash failed' in msg or 'error' in msg.lower()

    def test_full_success_path(self, manifest_file, pm3_binary):
        """Full success: kill -> flash -> restart -> verify."""
        app_dir, sha = manifest_file
        progress_calls = []

        def track_progress(percent, stage):
            progress_calls.append((percent, stage))

        mock_exec = MagicMock()
        mock_exec.startPM3Task.return_value = 1
        mock_exec.getPrintContent.return_value = HW_VERSION_FULL
        mock_exec.connect2PM3.return_value = None

        mock_hmi = MagicMock()
        mock_hmi.restartpm3.return_value = None

        with patch('subprocess.call'), \
             patch('time.sleep'), \
             patch('pm3_flash._run_flash_command',
                   return_value=(True, 'All done. Have a nice day!')), \
             patch('pm3_flash._wait_for_device', return_value=True), \
             patch.object(pm3_flash, 'executor', mock_exec), \
             patch.object(pm3_flash, 'hmi_driver', mock_hmi):
            success, msg = flash_firmware(app_dir, progress_cb=track_progress)
            assert success is True
            assert 'Flash complete' in msg or 'version' in msg.lower()

        # Verify progress reached key stages
        stages = [s for _, s in progress_calls]
        assert STAGE_PREPARING in stages
        assert STAGE_KILLING_PM3 in stages

    def test_full_success_with_hmi(self, manifest_file, pm3_binary):
        """Flash succeeds and restartpm3 is sent to GD32."""
        app_dir, sha = manifest_file

        mock_hmi = MagicMock()

        with patch('subprocess.call'), \
             patch('time.sleep'), \
             patch('pm3_flash._run_flash_command',
                   return_value=(True, 'All done. Have a nice day!')), \
             patch.object(pm3_flash, 'hmi_driver', mock_hmi):
            success, msg = flash_firmware(app_dir)
            assert success is True
            mock_hmi.restartpm3.assert_called_once()

    def test_full_success_no_hmi_driver(self, manifest_file, pm3_binary):
        """Flash without hmi_driver skips GD32 restart."""
        app_dir, sha = manifest_file

        mock_exec = MagicMock()
        mock_exec.startPM3Task.return_value = 1
        mock_exec.getPrintContent.return_value = HW_VERSION_FULL
        mock_exec.connect2PM3.return_value = None

        with patch('subprocess.call'), \
             patch('time.sleep'), \
             patch('pm3_flash._run_flash_command',
                   return_value=(True, 'All done. Have a nice day!')), \
             patch('pm3_flash._wait_for_device', return_value=True), \
             patch.object(pm3_flash, 'executor', mock_exec), \
             patch.object(pm3_flash, 'hmi_driver', None):
            success, msg = flash_firmware(app_dir)
            assert success is True

    def test_full_success_no_executor(self, manifest_file, pm3_binary):
        """Flash without executor still succeeds."""
        app_dir, sha = manifest_file

        mock_hmi = MagicMock()

        with patch('subprocess.call'), \
             patch('time.sleep'), \
             patch('pm3_flash._run_flash_command',
                   return_value=(True, 'All done. Have a nice day!')), \
             patch.object(pm3_flash, 'executor', None), \
             patch.object(pm3_flash, 'hmi_driver', mock_hmi):
            success, msg = flash_firmware(app_dir)
            assert success is True

    def test_device_does_not_reappear_still_succeeds(self, manifest_file, pm3_binary):
        """ttyACM0 not reappearing is non-fatal -- flash still succeeds."""
        app_dir, sha = manifest_file

        mock_exec = MagicMock()
        mock_exec.startPM3Task.return_value = 1
        mock_exec.getPrintContent.return_value = HW_VERSION_FULL
        mock_exec.connect2PM3.return_value = None

        with patch('subprocess.call'), \
             patch('time.sleep'), \
             patch('pm3_flash._run_flash_command',
                   return_value=(True, 'All done. Have a nice day!')), \
             patch('pm3_flash._wait_for_device', return_value=False), \
             patch.object(pm3_flash, 'executor', mock_exec), \
             patch.object(pm3_flash, 'hmi_driver', None):
            success, msg = flash_firmware(app_dir)
            assert success is True

    def test_progress_cb_exception_swallowed(self, app_dir):
        """Exception in progress_cb does not crash flash_firmware."""
        def bad_progress(percent, stage):
            raise ValueError("callback error")

        success, msg = flash_firmware(app_dir, progress_cb=bad_progress, dry_run=True)
        assert success is True

    def test_killall_failure_non_fatal(self, manifest_file, pm3_binary):
        """killall failing (PM3 not running) does not block flash."""
        app_dir, sha = manifest_file

        mock_exec = MagicMock()
        mock_exec.startPM3Task.return_value = 1
        mock_exec.getPrintContent.return_value = HW_VERSION_FULL
        mock_exec.connect2PM3.return_value = None

        def side_effect_call(cmd, **kwargs):
            if 'killall' in cmd:
                raise subprocess.TimeoutExpired(cmd, 10)
            return 0

        with patch('subprocess.call', side_effect=side_effect_call), \
             patch('time.sleep'), \
             patch('pm3_flash._run_flash_command',
                   return_value=(True, 'All done. Have a nice day!')), \
             patch('pm3_flash._wait_for_device', return_value=True), \
             patch.object(pm3_flash, 'executor', mock_exec), \
             patch.object(pm3_flash, 'hmi_driver', None):
            success, msg = flash_firmware(app_dir)
            assert success is True

    def test_service_restart_failure_non_fatal(self, manifest_file, pm3_binary):
        """Service restart failing does not block overall success."""
        app_dir, sha = manifest_file

        mock_exec = MagicMock()
        mock_exec.startPM3Task.return_value = 1
        mock_exec.getPrintContent.return_value = HW_VERSION_FULL
        mock_exec.connect2PM3.return_value = None

        call_count = [0]

        def side_effect_call(cmd, **kwargs):
            call_count[0] += 1
            if 'icopy' in cmd:
                raise OSError("service not found")
            return 0

        with patch('subprocess.call', side_effect=side_effect_call), \
             patch('time.sleep'), \
             patch('pm3_flash._run_flash_command',
                   return_value=(True, 'All done. Have a nice day!')), \
             patch('pm3_flash._wait_for_device', return_value=True), \
             patch.object(pm3_flash, 'executor', mock_exec), \
             patch.object(pm3_flash, 'hmi_driver', None):
            success, msg = flash_firmware(app_dir)
            assert success is True

    def test_connect2pm3_exception_non_fatal(self, manifest_file, pm3_binary):
        """executor.connect2PM3 failure does not block flash."""
        app_dir, sha = manifest_file

        mock_exec = MagicMock()
        mock_exec.connect2PM3.side_effect = ConnectionError("TCP refused")
        mock_exec.startPM3Task.return_value = -1  # verify fails too

        with patch('subprocess.call'), \
             patch('time.sleep'), \
             patch('pm3_flash._run_flash_command',
                   return_value=(True, 'All done. Have a nice day!')), \
             patch('pm3_flash._wait_for_device', return_value=True), \
             patch.object(pm3_flash, 'executor', mock_exec), \
             patch.object(pm3_flash, 'hmi_driver', None):
            success, msg = flash_firmware(app_dir)
            assert success is True

    def test_hmi_restartpm3_exception_non_fatal(self, manifest_file, pm3_binary):
        """hmi_driver.restartpm3 failure does not block flash."""
        app_dir, sha = manifest_file

        mock_exec = MagicMock()
        mock_exec.startPM3Task.return_value = 1
        mock_exec.getPrintContent.return_value = HW_VERSION_FULL
        mock_exec.connect2PM3.return_value = None

        mock_hmi = MagicMock()
        mock_hmi.restartpm3.side_effect = RuntimeError("GD32 comm error")

        with patch('subprocess.call'), \
             patch('time.sleep'), \
             patch('pm3_flash._run_flash_command',
                   return_value=(True, 'All done. Have a nice day!')), \
             patch('pm3_flash._wait_for_device', return_value=True), \
             patch.object(pm3_flash, 'executor', mock_exec), \
             patch.object(pm3_flash, 'hmi_driver', mock_hmi):
            success, msg = flash_firmware(app_dir)
            assert success is True

    def test_no_manifest_skips_integrity_check(self, app_dir, pm3_binary):
        """Without manifest.json, integrity check is skipped entirely."""
        # Create image but NO manifest
        image_path = os.path.join(app_dir, 'res', 'firmware', 'pm3', 'fullimage.elf')
        with open(image_path, 'wb') as f:
            f.write(b'fake elf')

        mock_exec = MagicMock()
        mock_exec.startPM3Task.return_value = 1
        mock_exec.getPrintContent.return_value = HW_VERSION_FULL
        mock_exec.connect2PM3.return_value = None

        with patch('subprocess.call'), \
             patch('time.sleep'), \
             patch('pm3_flash._run_flash_command',
                   return_value=(True, 'All done. Have a nice day!')), \
             patch('pm3_flash._wait_for_device', return_value=True), \
             patch.object(pm3_flash, 'executor', mock_exec), \
             patch.object(pm3_flash, 'hmi_driver', None):
            success, msg = flash_firmware(app_dir)
            assert success is True


# =====================================================================
# TestVerifyImageIntegrity
# =====================================================================

class TestVerifyImageIntegrity:
    """Tests for verify_image_integrity()."""

    def test_no_manifest_returns_false(self, app_dir):
        """No manifest.json -> (False, 'Manifest not found')."""
        valid, msg = verify_image_integrity(app_dir)
        assert valid is False
        assert 'Manifest not found' in msg

    def test_manifest_without_sha_returns_false(self, app_dir):
        """Manifest without pm3_firmware_sha256 -> (False, 'no SHA256 hash')."""
        manifest_path = os.path.join(app_dir, 'res', 'firmware', 'pm3', 'manifest.json')
        with open(manifest_path, 'w') as f:
            json.dump({'pm3_firmware_version': 'abc'}, f)

        valid, msg = verify_image_integrity(app_dir)
        assert valid is False
        assert 'no SHA256 hash' in msg

    def test_manifest_with_empty_sha_returns_false(self, app_dir):
        """Manifest with empty SHA string -> (False, 'no SHA256 hash')."""
        manifest_path = os.path.join(app_dir, 'res', 'firmware', 'pm3', 'manifest.json')
        with open(manifest_path, 'w') as f:
            json.dump({'pm3_firmware_sha256': ''}, f)

        valid, msg = verify_image_integrity(app_dir)
        assert valid is False
        assert 'no SHA256 hash' in msg

    def test_image_not_found_returns_false(self, app_dir):
        """Image file does not exist -> (False, 'not found')."""
        manifest_path = os.path.join(app_dir, 'res', 'firmware', 'pm3', 'manifest.json')
        with open(manifest_path, 'w') as f:
            json.dump({'pm3_firmware_sha256': 'deadbeef' * 8}, f)

        valid, msg = verify_image_integrity(app_dir)
        assert valid is False
        assert 'not found' in msg

    def test_sha_mismatch_returns_false(self, app_dir):
        """SHA256 mismatch between manifest and image -> (False, 'mismatch')."""
        manifest_path = os.path.join(app_dir, 'res', 'firmware', 'pm3', 'manifest.json')
        image_path = os.path.join(app_dir, 'res', 'firmware', 'pm3', 'fullimage.elf')

        with open(image_path, 'wb') as f:
            f.write(b'some binary content')

        with open(manifest_path, 'w') as f:
            json.dump({'pm3_firmware_sha256': 'wrong_hash_value'}, f)

        valid, msg = verify_image_integrity(app_dir)
        assert valid is False
        assert 'SHA256 mismatch' in msg

    def test_sha_match_returns_true(self, app_dir):
        """SHA256 matches -> (True, 'verified')."""
        manifest_path = os.path.join(app_dir, 'res', 'firmware', 'pm3', 'manifest.json')
        image_path = os.path.join(app_dir, 'res', 'firmware', 'pm3', 'fullimage.elf')

        content = b'real firmware binary content for hash test'
        with open(image_path, 'wb') as f:
            f.write(content)

        sha = hashlib.sha256(content).hexdigest()
        with open(manifest_path, 'w') as f:
            json.dump({'pm3_firmware_sha256': sha}, f)

        valid, msg = verify_image_integrity(app_dir)
        assert valid is True
        assert 'verified' in msg.lower()

    def test_ioerror_reading_image_returns_false(self, app_dir):
        """IOError when reading firmware image -> (False, 'Failed to read')."""
        manifest_path = os.path.join(app_dir, 'res', 'firmware', 'pm3', 'manifest.json')
        image_path = os.path.join(app_dir, 'res', 'firmware', 'pm3', 'fullimage.elf')

        # Create the image so isfile passes
        with open(image_path, 'wb') as f:
            f.write(b'content')

        sha = hashlib.sha256(b'content').hexdigest()
        with open(manifest_path, 'w') as f:
            json.dump({'pm3_firmware_sha256': sha}, f)

        # Patch open to raise IOError only for the image file (not the manifest)
        original_open = open

        def patched_open(path, *args, **kwargs):
            if 'fullimage.elf' in str(path) and 'b' in (args[0] if args else ''):
                raise IOError("disk read error")
            return original_open(path, *args, **kwargs)

        with patch('builtins.open', side_effect=patched_open):
            valid, msg = verify_image_integrity(app_dir)
            assert valid is False
            assert 'Failed to read' in msg


# =====================================================================
# TestModuleConstants
# =====================================================================

class TestModuleConstants:
    """Verify module-level constants are set correctly."""

    def test_pm3_device(self):
        assert PM3_DEVICE == '/dev/ttyACM0'

    def test_flash_timeout(self):
        assert FLASH_TIMEOUT == 120

    def test_battery_min_percent(self):
        assert BATTERY_MIN_PERCENT == 50

    def test_stage_constants(self):
        assert STAGE_PREPARING == 'preparing'
        assert STAGE_KILLING_PM3 == 'killing_pm3'
        assert STAGE_ENTERING_BOOTLOADER == 'entering_bootloader'
        assert STAGE_FLASHING == 'flashing'
        assert STAGE_VERIFYING == 'verifying'
        assert STAGE_RESTARTING == 'restarting'
        assert STAGE_COMPLETE == 'complete'

    def test_bootrom_blocklist(self):
        from pm3_flash import _BOOTROM_BLOCKLIST
        assert '--unlock-bootloader' in _BOOTROM_BLOCKLIST
        assert 'bootrom.elf' in _BOOTROM_BLOCKLIST
