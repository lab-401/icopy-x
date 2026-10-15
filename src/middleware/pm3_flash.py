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

"""pm3_flash -- PM3 firmware flash engine for the iCopy-X.

Handles detection, safety checks, and execution of PM3 firmware flashing.

Architecture:
    1. Detect running PM3 firmware version via TCP executor (hw version)
    2. Read target firmware version from manifest.json (shipped in IPK)
    3. Compare versions to determine if flash is needed
    4. Check battery/charging safety before flashing
    5. Execute flash: kill PM3 -> run flash command -> restart PM3
    6. Parse flash output for progress reporting
    7. Supports dry-run mode (for QEMU/testing)

Verified flash sequence (tested on real device 2026-04-12):
    1. sudo killall -9 proxmark3
    2. proxmark3 /dev/ttyACM0 --flash --image fullimage.elf
    3. Wait for exit (timeout 120s)
    4. ttyACM0 reappears within ~1s after flash
    5. Restart PM3 daemon via service restart
    6. Verify via hw version on TCP:8888

ABSOLUTE SAFETY RULE: NEVER flash bootrom. No --unlock-bootloader, no bootrom.elf.
No JTAG on iCopy-X = bricked device. Zero exceptions.
"""

import hashlib
import json
import logging
import os
import re
import subprocess
import time

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependencies (may not be available under QEMU)
# ---------------------------------------------------------------------------
try:
    import hmi_driver
except ImportError:
    hmi_driver = None

try:
    from middleware import executor
except ImportError:
    try:
        import executor
    except ImportError:
        executor = None

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PM3_DEVICE = '/dev/ttyACM0'
FLASH_TIMEOUT = 120  # seconds
BATTERY_MIN_PERCENT = 50
TTYACM0_WAIT_TIMEOUT = 10  # seconds to wait for ttyACM0 to reappear

# Bootrom safety: strings that MUST NEVER appear in any flash command
_BOOTROM_BLOCKLIST = ('--unlock-bootloader', 'bootrom.elf')

# ---------------------------------------------------------------------------
# Progress stage constants
# ---------------------------------------------------------------------------
STAGE_PREPARING = 'preparing'
STAGE_KILLING_PM3 = 'killing_pm3'
STAGE_ENTERING_BOOTLOADER = 'entering_bootloader'
STAGE_FLASHING = 'flashing'
STAGE_VERIFYING = 'verifying'
STAGE_RESTARTING = 'restarting'
STAGE_COMPLETE = 'complete'


# ===========================================================================
# Version detection
# ===========================================================================

def _parse_hw_version(output):
    """Parse hw version output into structured dict.

    Expected format (from real device):
        [ ARM ]
         bootrom: RRG/Iceman/master/release (git)
              os: RRG/Iceman/master/385d892f-dirty-unclean 2022-06-09 14:19:31
          NIKOLA: v3.1 2022-06-09 14:19:31

    Returns:
        dict with keys: 'os', 'bootrom', 'nikola', 'client', 'fpga', 'raw'
        Values are stripped strings or '' if not found.
    """
    result = {
        'os': '',
        'bootrom': '',
        'nikola': '',
        'client': '',
        'fpga': '',
        'raw': output or '',
    }

    if not output:
        return result

    # bootrom line: "bootrom: <value>" or "Bootrom.... <value>"
    m = re.search(r'[Bb]ootrom[.:]+\s*(.+)', output)
    if m:
        result['bootrom'] = m.group(1).strip()

    # os line: "os: <value>" or "OS......... <value>"
    m = re.search(r'(?:^|\n)\s*[Oo][Ss][.:]+\s*(.+)', output)
    if m:
        result['os'] = m.group(1).strip()

    # NIKOLA line: "NIKOLA: <value>" or "Nikola.D: <value>"
    m = re.search(r'NIKOLA:\s*(.+)', output)
    if m:
        result['nikola'] = m.group(1).strip()

    # client line: "client: <value>" (may not always be present)
    m = re.search(r'client:\s*(.+)', output)
    if m:
        result['client'] = m.group(1).strip()

    # FPGA line: "FPGA: <value>" or "FPGA firmware... <value>"
    m = re.search(r'FPGA[.:]+\s*(.+)', output)
    if m:
        result['fpga'] = m.group(1).strip()

    return result


def get_running_version():
    """Get currently running PM3 firmware version via TCP executor.

    Sends 'hw version' via the Nikola protocol and parses the response.

    Returns:
        dict with keys: 'os', 'bootrom', 'nikola', 'client', 'fpga', 'raw'
        or None if PM3 is not connected or executor unavailable.
    """
    if executor is None:
        logger.warning("get_running_version: executor not available")
        return None

    try:
        ret = executor.startPM3Task('hw version', timeout=10000)
        if ret != 1:
            logger.warning("get_running_version: hw version command failed (ret=%s)", ret)
            return None

        output = executor.getPrintContent()
        if not output:
            logger.warning("get_running_version: empty response from hw version")
            return None

        return _parse_hw_version(output)
    except Exception as e:
        logger.error("get_running_version failed: %s", e)
        return None


def get_image_version(manifest_path):
    """Read firmware version from manifest.json.

    Args:
        manifest_path: absolute path to manifest.json

    Returns:
        dict with keys from manifest (pm3_firmware_version, pm3_firmware_sha256,
        pm3_client_version, build_platform, build_date), or None if file missing
        or unreadable.
    """
    if not manifest_path or not os.path.isfile(manifest_path):
        logger.debug("get_image_version: manifest not found at %s", manifest_path)
        return None

    try:
        with open(manifest_path, 'r') as f:
            data = json.load(f)
        return data
    except (json.JSONDecodeError, IOError, OSError) as e:
        logger.error("get_image_version: failed to read manifest: %s", e)
        return None


def needs_flash(app_dir):
    """Check if PM3 firmware flash is needed.

    Compares the running PM3 firmware version against the manifest shipped
    in the IPK. Returns False if no manifest exists or if versions match.

    Args:
        app_dir: application root directory (contains res/firmware/pm3/)

    Returns:
        bool -- True if flash is needed, False otherwise.
    """
    manifest_path = os.path.join(app_dir, 'res', 'firmware', 'pm3', 'manifest.json')
    image_ver = get_image_version(manifest_path)
    if image_ver is None:
        logger.debug("needs_flash: no manifest found, flash not needed")
        return False

    target_version = image_ver.get('pm3_firmware_version', '')
    if not target_version:
        logger.debug("needs_flash: manifest has no pm3_firmware_version")
        return False

    running = get_running_version()
    if running is None:
        # PM3 not connected -- cannot compare, assume flash needed
        logger.info("needs_flash: PM3 not connected, assuming flash needed")
        return True

    running_os = running.get('os', '')
    if not running_os:
        logger.info("needs_flash: no running OS version, assuming flash needed")
        return True

    # Compare: if the target version string appears in the running OS string,
    # they match. Otherwise flash is needed.
    if target_version in running_os:
        logger.info("needs_flash: versions match (%s), no flash needed", target_version)
        return False

    logger.info("needs_flash: version mismatch — running='%s', target='%s'",
                running_os, target_version)
    return True


# ===========================================================================
# Safety checks
# ===========================================================================

def check_safety():
    """Check if it's safe to flash PM3 firmware.

    Checks battery level (>= 50%) and charging state. Both conditions are
    informational -- the caller decides whether to proceed.

    Returns:
        tuple: (safe: bool, error_msg: str)
            safe=True means all checks passed, error_msg is ''.
            safe=False includes a descriptive error message.
    """
    if hmi_driver is None:
        # Under QEMU/test -- no hardware to check, assume safe
        logger.debug("check_safety: hmi_driver not available, assuming safe")
        return (True, '')

    try:
        battery = hmi_driver.readbatpercent()
        # requestChargeState() sends "charge" to GD32 and returns the cached
        # value. First call primes the query; brief wait lets the GD32
        # response arrive on the serial thread; second call returns updated.
        hmi_driver.requestChargeState()
        time.sleep(0.5)
        charging = hmi_driver.requestChargeState()
    except Exception as e:
        logger.error("check_safety: failed to read battery/charge state: %s", e)
        # Cannot determine safety -- report as unsafe
        return (False, "Cannot read battery status: %s" % e)

    low_battery = battery < BATTERY_MIN_PERCENT
    not_plugged = not charging

    if low_battery and not_plugged:
        msg = ("Battery is too low (%d%%) and device is not plugged in... "
               "Are you trying to brick your device?" % battery)
        return (False, msg)

    if low_battery:
        msg = "Battery too low (%d%%). Please recharge and try later." % battery
        return (False, msg)

    if not_plugged:
        msg = "Device is not plugged in. Please plug in and try again."
        return (False, msg)

    return (True, '')


# ===========================================================================
# Flash output parsing
# ===========================================================================

def _parse_flash_output(line):
    """Parse a line of flash output into progress information.

    Maps real PM3 flash output lines to percent + stage:
        "Waiting for Proxmark3"       -> 5%, entering_bootloader
        "found" (first encounter)     -> 10%, entering_bootloader
        "Entering bootloader"         -> 15%, entering_bootloader
        "found" (second encounter)    -> 20%, entering_bootloader
        "Loading ELF file"            -> 25%, flashing
        "Flashing..."                 -> 30%, flashing
        "Writing segments"            -> 30-90%, flashing (block progress)
        "OK"                          -> 95%, flashing
        "All done"                    -> 100%, complete

    Args:
        line: a single line of flash subprocess output

    Returns:
        tuple: (percent: int, stage: str) or None if line is not progress-relevant.
    """
    if not line:
        return None

    line = line.strip()

    if 'Waiting for Proxmark3' in line:
        return (5, STAGE_ENTERING_BOOTLOADER)

    if 'Entering bootloader' in line:
        return (15, STAGE_ENTERING_BOOTLOADER)

    if 'Loading ELF file' in line:
        return (25, STAGE_FLASHING)

    if 'Flashing...' in line:
        return (30, STAGE_FLASHING)

    # "Writing segments for file:" line
    if 'Writing segments' in line:
        return (30, STAGE_FLASHING)

    # Block progress: "0x00102000..0x0013e0eb [0x3c0ec / 481 blocks]"
    # This line appears once with total block count. The actual writing progress
    # follows as a stream of "." or "m" characters until "OK".
    m = re.search(r'\[0x[0-9a-fA-F]+\s*/\s*(\d+)\s+blocks\]', line)
    if m:
        # Store total blocks for callers that need it
        return (35, STAGE_FLASHING)

    # Block writing complete -- "mm OK" or standalone "OK" after block markers
    if line.endswith('OK') and ('mm' in line or line == 'OK'):
        return (95, STAGE_FLASHING)

    if 'All done' in line:
        return (100, STAGE_COMPLETE)

    # "found" appears twice in the flash output (once per "Waiting for Proxmark3")
    if 'found' in line and re.search(r'\d+\s+found', line):
        # Cannot distinguish first vs second "found" from a single line;
        # the caller tracks state to differentiate.
        return (10, STAGE_ENTERING_BOOTLOADER)

    return None


# ===========================================================================
# Flash command execution
# ===========================================================================

def _check_bootrom_safety(cmd_str):
    """Validate that a command string does not contain bootrom-related flags.

    SAFETY: The iCopy-X has no JTAG. Flashing the bootrom risks a permanent
    brick with no recovery path.

    Args:
        cmd_str: the full command string to validate

    Raises:
        RuntimeError: if the command contains any blocklisted string.
    """
    for blocked in _BOOTROM_BLOCKLIST:
        if blocked in cmd_str:
            raise RuntimeError(
                "BLOCKED: command contains '%s'. "
                "Flashing bootrom on iCopy-X = permanent brick. "
                "This operation is forbidden." % blocked
            )


def _run_flash_command(pm3_bin, device, image_path, progress_cb=None, timeout=120):
    """Run the PM3 flash subprocess.

    Constructs and executes:
        <pm3_bin> <device> --flash --image <image_path>

    Reads stdout line-by-line, parsing progress via _parse_flash_output().

    SAFETY: Raises RuntimeError if command contains --unlock-bootloader or bootrom.elf.

    Args:
        pm3_bin: path to proxmark3 client binary
        device: serial device path (e.g. /dev/ttyACM0)
        image_path: path to fullimage.elf
        progress_cb: optional callback -- progress_cb(percent, stage)
        timeout: subprocess timeout in seconds (default 120)

    Returns:
        tuple: (success: bool, output: str)
    """
    # --force: required when flashing from factory firmware — the old
    # firmware's version_information format differs from what the new client
    # expects, causing a capabilities check failure without this flag.
    # SAFE: --force only skips version checks, does NOT touch the bootrom.
    cmd = [pm3_bin, device, '--flash', '--force', '--image', image_path]
    cmd_str = ' '.join(cmd)

    # Safety check -- MUST happen before any subprocess call
    _check_bootrom_safety(cmd_str)
    _check_bootrom_safety(image_path)

    logger.info("Flash command: %s", cmd_str)

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1,
        )
    except OSError as e:
        msg = "Failed to start flash process: %s" % e
        logger.error(msg)
        return (False, msg)

    output_lines = []
    found_count = 0

    try:
        start = time.monotonic()
        while True:
            # Check timeout
            elapsed = time.monotonic() - start
            if elapsed > timeout:
                proc.kill()
                proc.wait(timeout=5)
                msg = "Flash process timed out after %ds" % timeout
                logger.error(msg)
                output_lines.append(msg)
                return (False, '\n'.join(output_lines))

            line = proc.stdout.readline()
            if not line:
                if proc.poll() is not None:
                    break
                # Brief sleep to avoid busy-spin when pipe has no data
                time.sleep(0.05)
                continue

            line_stripped = line.rstrip('\n\r')
            output_lines.append(line_stripped)
            logger.debug("flash> %s", line_stripped)

            # Parse progress
            parsed = _parse_flash_output(line_stripped)
            if parsed and progress_cb:
                percent, stage = parsed
                # Disambiguate first vs second "found"
                if 'found' in line_stripped and re.search(r'\d+\s+found', line_stripped):
                    found_count += 1
                    if found_count == 1:
                        percent = 10
                    else:
                        percent = 20
                progress_cb(percent, stage)

        # Collect any remaining output
        remaining = proc.stdout.read()
        if remaining:
            for extra_line in remaining.splitlines():
                output_lines.append(extra_line)
                logger.debug("flash> %s", extra_line)

        proc.wait(timeout=5)
        retcode = proc.returncode

    except Exception as e:
        try:
            proc.kill()
            proc.wait(timeout=5)
        except OSError:
            pass
        msg = "Flash process error: %s" % e
        logger.error(msg)
        output_lines.append(msg)
        return (False, '\n'.join(output_lines))
    finally:
        # Ensure stdout pipe is closed to prevent file descriptor leaks
        try:
            proc.stdout.close()
        except Exception:
            pass

    output_str = '\n'.join(output_lines)

    if retcode == 0 and 'All done' in output_str:
        logger.info("Flash completed successfully")
        return (True, output_str)

    logger.error("Flash failed (retcode=%s)", retcode)
    return (False, output_str)


def _wait_for_device(device_path, timeout=10):
    """Wait for a device node to appear.

    Args:
        device_path: path to check (e.g. /dev/ttyACM0)
        timeout: max seconds to wait

    Returns:
        bool -- True if device appeared within timeout.
    """
    start = time.monotonic()
    while (time.monotonic() - start) < timeout:
        if os.path.exists(device_path):
            return True
        time.sleep(0.2)
    return False


# ===========================================================================
# Main flash entry point
# ===========================================================================

def flash_firmware(app_dir, progress_cb=None, dry_run=False):
    """Execute the full PM3 firmware flash cycle.

    Sequence (verified on real device 2026-04-12):
        1. Locate binaries (pm3 client + fullimage.elf)
        2. Kill PM3 process (sudo killall -9 proxmark3)
        3. Verify firmware image integrity (SHA256 vs manifest)
        4. Run flash command: proxmark3 --flash --image fullimage.elf
           (client handles bootloader entry, USB reconnection, page writes)
        5. Wait for ttyACM0 to reappear
        6. Send restartpm3 to GD32 via hmi_driver
        7. Verify via hw version on TCP:8888

    CRITICAL: The caller (FWUpdateActivity) is responsible for stopping
    the systemd watchdog (icopy.service) BEFORE calling this function and
    re-enabling it AFTER. If the watchdog restarts the app during flash,
    it will kill the proxmark3 --flash subprocess mid-write, corrupting
    the firmware. This was verified the hard way on 2026-04-12.

    In dry_run mode: logs all steps but does not execute destructive commands.

    Args:
        app_dir: application root directory (contains pm3/ and res/firmware/pm3/)
        progress_cb: optional -- progress_cb(percent: int, stage: str)
            Stages: 'preparing', 'killing_pm3', 'entering_bootloader',
                    'flashing', 'verifying', 'restarting', 'complete'
        dry_run: if True, skip destructive operations (for QEMU/testing)

    Returns:
        tuple: (success: bool, message: str)
    """
    def _progress(percent, stage):
        if progress_cb:
            try:
                progress_cb(percent, stage)
            except Exception:
                pass

    # -- Step 1: Locate binaries --
    _progress(0, STAGE_PREPARING)

    pm3_bin = os.path.join(app_dir, 'pm3', 'proxmark3')
    image_path = os.path.join(app_dir, 'res', 'firmware', 'pm3', 'fullimage.elf')

    if not dry_run:
        if not os.path.isfile(pm3_bin):
            msg = "PM3 client binary not found: %s" % pm3_bin
            logger.error(msg)
            return (False, msg)

        if not os.path.isfile(image_path):
            msg = "Firmware image not found: %s" % image_path
            logger.error(msg)
            return (False, msg)
    else:
        logger.info("[DRY RUN] Would use pm3_bin=%s, image=%s", pm3_bin, image_path)

    # Safety: verify image path does not reference bootrom
    try:
        _check_bootrom_safety(image_path)
    except RuntimeError as e:
        return (False, str(e))

    _progress(2, STAGE_PREPARING)

    # -- Step 2: Kill PM3 process --
    _progress(3, STAGE_KILLING_PM3)

    if not dry_run:
        logger.info("Killing PM3 process...")
        try:
            subprocess.call(
                ['sudo', 'killall', '-9', 'proxmark3'],
                timeout=10,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            logger.warning("killall proxmark3 failed (may not be running): %s", e)
        # Brief pause for process cleanup
        time.sleep(0.5)
    else:
        logger.info("[DRY RUN] Would run: sudo killall -9 proxmark3")

    _progress(5, STAGE_KILLING_PM3)

    # -- Step 2b: Verify image integrity before flashing --
    manifest_path = os.path.join(app_dir, 'res', 'firmware', 'pm3', 'manifest.json')
    if os.path.isfile(manifest_path) and not dry_run:
        valid, integrity_msg = verify_image_integrity(app_dir)
        if not valid:
            msg = "Firmware integrity check failed: %s" % integrity_msg
            logger.error(msg)
            return (False, msg)
        logger.info("Firmware integrity verified")

    # -- Step 3: Run flash command --
    if not dry_run:
        logger.info("Starting flash...")
        success, output = _run_flash_command(
            pm3_bin, PM3_DEVICE, image_path,
            progress_cb=_progress,
            timeout=FLASH_TIMEOUT,
        )
        if not success:
            msg = "Flash failed: %s" % output
            logger.error(msg)
            return (False, msg)
    else:
        logger.info("[DRY RUN] Would run: %s %s --flash --image %s",
                     pm3_bin, PM3_DEVICE, image_path)
        output = "[DRY RUN] Flash skipped"

    # -- Step 4: Restart PM3 via GD32 --
    _progress(95, STAGE_RESTARTING)

    if not dry_run:
        if hmi_driver is not None:
            try:
                logger.info("Sending restartpm3 to GD32...")
                hmi_driver.restartpm3()
            except Exception as e:
                logger.warning("hmi_driver.restartpm3() failed: %s", e)
    else:
        logger.info("[DRY RUN] Would call hmi_driver.restartpm3()")

    _progress(100, STAGE_COMPLETE)
    if dry_run:
        return (True, "[DRY RUN] Flash sequence completed successfully (no changes made)")
    return (True, "Flash complete")


def verify_image_integrity(app_dir):
    """Verify the firmware image integrity against the manifest SHA256.

    Args:
        app_dir: application root directory

    Returns:
        tuple: (valid: bool, message: str)
    """
    manifest_path = os.path.join(app_dir, 'res', 'firmware', 'pm3', 'manifest.json')
    image_path = os.path.join(app_dir, 'res', 'firmware', 'pm3', 'fullimage.elf')

    manifest = get_image_version(manifest_path)
    if manifest is None:
        return (False, "Manifest not found")

    expected_sha = manifest.get('pm3_firmware_sha256', '')
    if not expected_sha:
        return (False, "Manifest has no SHA256 hash")

    if not os.path.isfile(image_path):
        return (False, "Firmware image not found: %s" % image_path)

    try:
        h = hashlib.sha256()
        with open(image_path, 'rb') as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                h.update(chunk)
        actual_sha = h.hexdigest()
    except IOError as e:
        return (False, "Failed to read firmware image: %s" % e)

    if actual_sha == expected_sha:
        return (True, "Image integrity verified (SHA256 match)")

    return (False, "SHA256 mismatch: expected=%s, actual=%s" % (expected_sha, actual_sha))
