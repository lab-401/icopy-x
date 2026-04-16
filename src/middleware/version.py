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

"""Device version information.

OSS reimplementation of version.so.
Binary source: version.so (Cython)
Ground truth: V1090_MODULE_AUDIT.txt, device_so/version_universal.py

Provides device identification: type, hardware, HMI, OS, PM3, serial number.

Original version.so behavior:
    getTYP()          — static: "ICopy-XS"
    getHW()           — static: compiled-in hardware version
    getHMI()          — DYNAMIC: calls hmi_driver.readhmiversion() → GD32 "#version:X.Y"
    getOS()           — static: compiled-in OS version
    getPM()           — static default, overridden by getPM3_Dynamic()
    getPM3_Dynamic()  — DYNAMIC: parses "NIKOLA: vX.Y" from hw version output
    getHMI_Dynamic()  — DYNAMIC: calls hmi_driver.readhmiversion()
    getSN()           — static: compiled-in serial number

OSS implementation:
    getTYP()  — "iCopy-XS Open"
    getHW()   — removed (not reliably available without original version.so)
    getHMI()  — dynamic from GD32 via hmi_driver.readhmiversion()
    getOS()   — build-stamped version (YYMMDD-H.M-Int for local, release tag for CI)
    getPM()   — dynamic from PM3 via pm3_flash.get_running_version()
    getSN()   — extracted from backup version.so binary on device
"""

import os
import re
import logging

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════
# Build version — stamped at build time by build_ipk.py
# Default is the internal dev format. CI overrides via _BUILD_VERSION file.
# ═══════════════════════════════════════════════════════════
_DEFAULT_VERSION = "dev"

def _read_build_version():
    """Read build version from _BUILD_VERSION file (stamped by build_ipk.py).

    Returns the version string, or _DEFAULT_VERSION if not found.
    """
    # Check next to this file (inside the installed app)
    here = os.path.dirname(os.path.abspath(__file__))
    for candidate in [
        os.path.join(here, '_BUILD_VERSION'),
        os.path.join(here, '..', '_BUILD_VERSION'),
    ]:
        try:
            with open(candidate, 'r') as f:
                ver = f.read().strip()
                if ver:
                    return ver
        except (IOError, OSError):
            pass
    return _DEFAULT_VERSION

VERSION_STR = _read_build_version()

# ═══════════════════════════════════════════════════════════
# Serial number — not used in OSS version
# ═══════════════════════════════════════════════════════════
SERIAL_NUMBER = ""

# ═══════════════════════════════════════════════════════════
# Cached dynamic values (populated on first call)
# ═══════════════════════════════════════════════════════════
_pm3_version_cache = None
_hmi_version_cache = None


# ═══════════════════════════════════════════════════════════
# Public API — matches original version.so exports
# ═══════════════════════════════════════════════════════════

def getTYP():
    """Get device type name.

    Original: "ICopy-XS"
    OSS: "iCopy-XS Open"
    """
    return "iCopy-XS Open"


def getHW():
    """Get hardware version.

    Not reliably available without the original device-specific version.so.
    Returns empty string — the About screen should omit this field.
    """
    return ""


def getHMI():
    """Get HMI (GD32 MCU) firmware version — DYNAMIC.

    Queries the GD32 via hmi_driver.readhmiversion().
    GD32 responds with "#version:X.Y" which hmi_driver parses.
    Caches the result after first successful query.

    Original: getHMI_Dynamic() did this via readhmiversion + mcu_fw_version.
    """
    global _hmi_version_cache
    if _hmi_version_cache is not None:
        return _hmi_version_cache

    try:
        import hmi_driver
        hmi_driver.readhmiversion()
        # readhmiversion sends the query; the serial read thread parses
        # the "#version:X.Y" response into hmi_driver._hmi_version.
        # Brief wait for the async response.
        import time
        time.sleep(0.3)
        ver = getattr(hmi_driver, '_hmi_version', '')
        if ver:
            _hmi_version_cache = ver
            return ver
    except ImportError:
        pass
    except Exception as e:
        logger.debug("getHMI failed: %s", e)
    return "?"


def getOS():
    """Get OS/application version.

    Returns the build-stamped version string.
    Local builds: "YYMMDD-H.M-Int" (e.g. "260413-11.22-Int")
    CI builds: release tag (e.g. "v0.6.1")
    """
    return VERSION_STR


def getPM():
    """Get Proxmark3 firmware version — DYNAMIC.

    Queries the PM3 via hw version and parses the response.
    On iCopy-X factory firmware: returns NIKOLA version (e.g. "3.1")
    On RRG/Iceman firmware: returns OS version (e.g. "v4.21128")
    Caches the result after first successful query.

    Original: getPM3_Dynamic() parsed "NIKOLA: vX.Y" from hw version output.
    """
    global _pm3_version_cache
    if _pm3_version_cache is not None:
        return _pm3_version_cache

    try:
        try:
            from middleware import pm3_flash
        except ImportError:
            import pm3_flash
        ver = pm3_flash.get_running_version()
        if ver is None:
            return "?"

        # iCopy-X factory firmware: NIKOLA line present
        nikola = ver.get('nikola', '')
        if nikola:
            # Extract version number: "v3.1 2022-06-09 14:19:31" → "3.1"
            m = re.match(r'v?([\d.]+)', nikola)
            if m:
                _pm3_version_cache = m.group(1)
                return _pm3_version_cache

        # RRG/Iceman firmware: os line
        os_ver = ver.get('os', '')
        if os_ver:
            # Extract version: "Iceman/master/v4.21128..." → "v4.21128"
            m = re.search(r'(v[\d.]+)', os_ver)
            if m:
                _pm3_version_cache = m.group(1)
                return _pm3_version_cache
            # Fallback: return the whole os string truncated
            _pm3_version_cache = os_ver[:20]
            return _pm3_version_cache

    except ImportError:
        pass
    except Exception as e:
        logger.debug("getPM failed: %s", e)
    return "?"


def getSN():
    """Get device serial number.

    Extracted from the backup version.so binary on device.
    """
    return SERIAL_NUMBER


# ═══════════════════════════════════════════════════════════
# Dynamic aliases (match original version.so exports)
# ═══════════════════════════════════════════════════════════

def getHMI_Dynamic():
    """Alias for getHMI() — dynamic HMI version."""
    return getHMI()


def getPM3_Dynamic():
    """Alias for getPM() — dynamic PM3 version."""
    return getPM()
