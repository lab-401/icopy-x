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

"""USB gadget kernel module management.

OSS reimplementation of gadget_linux.so.
Archive reference: /home/qx/archive/lib_transliterated/gadget_linux.py

Manages Linux USB gadget kernel modules for PC-Mode:
  g_mass_storage — USB mass storage (host sees device storage)
  g_serial       — USB serial (creates /dev/ttyGS0)
  g_acm_ms       — Composite: ACM serial + mass storage

On real hardware: loads/unloads kernel modules, mounts/unmounts partitions.
Under QEMU/test: all commands are best-effort (modprobe fails without USB HW).
"""

import os
import logging

logger = logging.getLogger(__name__)

# Device paths — hardcoded in original .so (QEMU-verified)
_UPAN_PARTITION = '/dev/mmcblk0p4'
_MOUNT_POINT = '/mnt/upan/'


def get_upan_partition():
    """Get the USB mass storage partition device path.

    Returns:
        str: '/dev/mmcblk0p4' (hardcoded, same as original .so)
    """
    return _UPAN_PARTITION


def usb_mass_storage():
    """Enable USB mass storage gadget mode.

    Loads g_mass_storage kernel module with the UPAN partition.
    with "removable=1 stall=0" parameters.
    """
    partition = get_upan_partition()
    cmd = 'sudo modprobe g_mass_storage file=%s removable=1 stall=0' % partition
    logger.debug("gadget_linux: %s", cmd)
    try:
        os.system(cmd)
    except Exception:
        pass


def serial(kill=True):
    """Manage USB serial gadget mode.

    Args:
        kill: if True, remove existing serial module first (default True)

    """
    if kill:
        try:
            os.system('sudo modprobe -r g_serial')
        except Exception:
            pass
    logger.debug("gadget_linux: modprobe g_serial")
    try:
        os.system('sudo modprobe g_serial')
    except Exception:
        pass


def upan_and_serial():
    """Enable both USB mass storage and serial gadget modes.

    Loads g_acm_ms composite gadget (ACM serial + mass storage).
    This is the main function called by PCModeActivity.startPCMode().

    STR@0x0001d2d0 " removable=1 stall=0") + live device confirmation
    (/sys/module/g_acm_ms/parameters/: file=/dev/mmcblk0p4, removable=Y, stall=N)
    See: docs/Real_Hardware_Intel/pcmode_live_audit_20260411.txt §2
    """
    logger.debug("gadget_linux: upan_and_serial()")
    try:
        umount_upan_partition()
        partition = get_upan_partition()
        os.system('sudo modprobe g_acm_ms file=%s removable=1 stall=0' % partition)
    except Exception:
        pass


def upan_or_both(mod=None):
    """Enable USB mass storage or composite gadget mode.

    Args:
        mod: module name override (unused in practice)
    """
    usb_mass_storage()


def kill_all_module(auto_remount=True):
    """Remove all USB gadget kernel modules.

    Args:
        auto_remount: if True, remount UPAN partition after cleanup (default True)

    This is the main teardown function called by PCModeActivity.stopPCMode().
    """
    logger.debug("gadget_linux: kill_all_module(auto_remount=%s)", auto_remount)
    try:
        os.system('sudo modprobe -r g_serial')
    except Exception:
        pass
    try:
        os.system('sudo modprobe -r g_mass_storage')
    except Exception:
        pass
    try:
        os.system('sudo modprobe -r g_acm_ms')
    except Exception:
        pass
    try:
        os.system('sudo modprobe -r g_ether')
    except Exception:
        pass
    if auto_remount:
        auto_ms_remount()


def mount_upan_partition():
    """Mount the UPAN partition at /mnt/upan/.

    """
    logger.debug("gadget_linux: mount %s → %s", _UPAN_PARTITION, _MOUNT_POINT)
    try:
        os.system('sudo mkdir -p %s' % _MOUNT_POINT)
        os.system('sudo mount -o rw %s %s' % (_UPAN_PARTITION, _MOUNT_POINT))
    except Exception:
        pass


def umount_upan_partition():
    """Unmount the UPAN partition.

    """
    logger.debug("gadget_linux: umount %s", _MOUNT_POINT)
    try:
        os.system('sudo umount %s' % _MOUNT_POINT)
    except Exception:
        pass


def remount_upan_partition():
    """Remount the UPAN partition (unmount then mount)."""
    umount_upan_partition()
    mount_upan_partition()


def auto_ms_remount():
    """Auto-remount mass storage after gadget teardown.

    Called by kill_all_module when auto_remount=True.
    Remounts the partition so the device can access its storage again.
    """
    logger.debug("gadget_linux: auto_ms_remount()")
    remount_upan_partition()
