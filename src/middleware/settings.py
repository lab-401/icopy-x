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

"""Typed settings accessors wrapping config module.

OSS reimplementation of settings.so.
Binary source: settings.so (Cython)
Ground truth: V1090_MODULE_AUDIT.txt lines 329-343

Functions:
    getBacklight() / setBacklight(value)   — 0=Low, 1=Middle, 2=High
    getVolume() / setVolume(value)          — 0=Off, 1=Low, 2=Middle, 3=High
    getSleepTime() / setSleepTime(value)
    fromLevelGetBacklight(level)            — UI level → HW value
    fromLevelGetVolume(level)               — UI level → audio param
    fromLevelGetSleepTime(level)            — UI level → seconds
"""

import config


def getBacklight():
    """Get current backlight level (0-2).

    Returns:
        int: 0=Low, 1=Middle, 2=High (default 2)
    """
    val = config.getValue('backlight', '2')
    try:
        return int(val)
    except (TypeError, ValueError):
        return 2


def setBacklight(value):
    """Set backlight level (0-2) and apply to hardware.

    Ground truth (trace_original_backlight_volume_20260410.txt):
    The original settings.so persists AND applies the hardware change.
    Every UP/DOWN navigation calls setBacklight() which both saves
    to conf.ini and sends the HMI serial command.

    Args:
        value: int 0=Low, 1=Middle, 2=High
    """
    config.setKeyValue('backlight', value)
    # Apply to hardware — original .so does this internally
    hw_val = int(fromLevelGetBacklight(value))
    try:
        import hmi_driver
        hmi_driver.setbaklight(hw_val)
    except Exception:
        pass


def getVolume():
    """Get current volume level (0-3).

    Returns:
        int: 0=Off, 1=Low, 2=Middle, 3=High (default 2)
    """
    val = config.getValue('volume', '2')
    try:
        return int(val)
    except (TypeError, ValueError):
        return 2


def setVolume(value):
    """Set volume level (0-3).

    Args:
        value: int 0=Off, 1=Low, 2=Middle, 3=High
    """
    config.setKeyValue('volume', value)


def getSleepTime():
    """Get current sleep timeout.

    Returns:
        int: sleep time value (default 1)
    """
    val = config.getValue('sleep_time', '1')
    try:
        return int(val)
    except (TypeError, ValueError):
        return 1


def setSleepTime(value):
    """Set sleep timeout.

    Args:
        value: int sleep time value
    """
    config.setKeyValue('sleep_time', value)


def fromLevelGetBacklight(level):
    """Convert UI backlight level to hardware brightness byte.

    Ground truth (strace of original firmware, 2026-04-10):
    setbaklight sends B + chr(brightness) + A over serial.
    Observed: Low=B\\x14A (20), Middle=B2A (50), High=BdA (100).

    Level 0 (Low) → 20, Level 1 (Middle) → 50, Level 2 (High) → 100

    Args:
        level: int 0-2

    Returns:
        int: hardware brightness value (raw byte, 1-100)
    """
    mapping = {0: 20, 1: 50, 2: 100}
    return mapping.get(level, 100)


def fromLevelGetVolume(level):
    """Convert UI volume level to audio parameter.

    Ground truth (trace_original_backlight_volume_20260410.txt):
    Level 0→0, Level 1→20, Level 2→50, Level 3→100
    Confirmed: playVolumeExam(20), setVolume(20) for level 1, etc.

    Args:
        level: int 0-3

    Returns:
        int: volume parameter
    """
    mapping = {0: 0, 1: 20, 2: 50, 3: 100}
    return mapping.get(level, 50)


def fromLevelGetSleepTime(level):
    """Convert UI sleep level to timeout in seconds.

    Args:
        level: int

    Returns:
        int: timeout in seconds
    """
    mapping = {0: 30, 1: 60, 2: 120, 3: 300, 4: 0}
    return mapping.get(level, 60)


def getScreenMirror():
    """Get screen mirror enabled state.

    Returns:
        int: 0=disabled, 1=enabled (default 0)
    """
    val = config.getValue('screen_mirror', '0')
    try:
        return int(val)
    except (TypeError, ValueError):
        return 0


def setScreenMirror(value):
    """Set screen mirror setting.

    The mirror service starts/stops on next app restart, not immediately.
    This avoids USB gadget conflicts during live operation.

    Args:
        value: int 0=disabled, 1=enabled
    """
    config.setKeyValue('screen_mirror', str(int(value)))
