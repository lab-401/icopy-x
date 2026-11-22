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

"""USB gadget kernel module management.

OSS reimplementation of gadget_linux.so.
Binary source: gadget_linux.so (Cython, os + subprocess)
Ground truth: V1090_MODULE_AUDIT.txt lines 1029-1044
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

# Always-on configfs RNDIS gadget (see tools/rndis/README.md).  Optional: the
# directory does not exist on a stock image, only once rndis.service has run.
_RNDIS_GADGET = '/sys/kernel/config/usb_gadget/icopy'


def get_upan_partition():
    """Get the USB mass storage partition device path.

    Returns:
        str: '/dev/mmcblk0p4' (hardcoded, same as original .so)
    """
    return _UPAN_PARTITION


def usb_mass_storage():
    """Enable USB mass storage gadget mode.

    Loads g_mass_storage kernel module with the UPAN partition.
    Ground truth: V1090_SO_STRINGS_RAW.txt — "sudo modprobe g_mass_storage"
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

    Ground truth: V1090_SO_STRINGS_RAW.txt — "sudo modprobe g_serial"
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


def release_rndis_udc():
    """Detach the always-on configfs RNDIS gadget, freeing the UDC.

    The UDC can host exactly one gadget driver.  While the RNDIS gadget from
    ``tools/rndis/rndis.sh`` is bound, a modprobe'd gadget is parked in
    "udc-core: couldn't find an available UDC - added [...] to list of pending
    drivers" and never enumerates — PC mode and screen mirroring silently do
    nothing.

    configfs ignores a zero-length store, so the unbind must write a newline
    (the equivalent of the shell's ``echo "" > UDC``).

    Returns:
        bool: True when a bound gadget was released, False when this system has
        no RNDIS gadget or the write failed.
    """
    udc = os.path.join(_RNDIS_GADGET, 'UDC')
    if not os.path.exists(udc):
        return False
    try:
        with open(udc, 'w') as f:
            f.write('\n')
        logger.debug("gadget_linux: released configfs UDC")
        return True
    except OSError as e:
        logger.warning("gadget_linux: UDC release failed: %s", e)
        return False


def restore_rndis():
    """Rebuild the always-on RNDIS gadget after the UDC was handed to g_serial.

    rndis.sh tears the gadget down, reloads the RNDIS function, puts the
    addresses back on the recreated usb0 and restarts rndis-dhcp — without that
    last step dnsmasq stays bound to the destroyed netdev and the host falls
    back to an APIPA (169.254.x) address.

    Returns:
        bool: True when rndis.service was restarted, False when the RNDIS
        gadget is not installed on this system.
    """
    if not os.path.isdir(_RNDIS_GADGET):
        return False
    try:
        os.system('sudo systemctl restart rndis.service >/dev/null 2>&1')
        logger.debug("gadget_linux: rndis.service restarted")
        return True
    except Exception as e:
        logger.warning("gadget_linux: rndis restore failed: %s", e)
        return False


def upan_and_serial():
    """Enable both USB mass storage and serial gadget modes.

    Loads g_acm_ms composite gadget (ACM serial + mass storage).
    This is the main function called by PCModeActivity.startPCMode().

    Ground truth: gadget_linux.so string table (STR@0x0001d50c " file=",
    STR@0x0001d2d0 " removable=1 stall=0") + live device confirmation
    (/sys/module/g_acm_ms/parameters/: file=/dev/mmcblk0p4, removable=Y, stall=N)
    See: docs/Real_Hardware_Intel/pcmode_live_audit_20260411.txt §2

    UDC pre-flight: the USB Device Controller can host only ONE gadget
    driver at a time. If a prior gadget (g_mass_storage boot-default, or
    g_serial from our post-PC-mode teardown) is still bound, g_acm_ms
    gets queued pending and never enumerates — the PC sees no ttyGS0
    and PC-mode silently fails. Confirmed live 2026-04-17 via dmesg:
    "udc-core: couldn't find an available UDC - added [g_acm_ms] to list
    of pending drivers" while g_mass_storage remained bound. Unload
    every possible prior gadget before loading g_acm_ms.

    The optional configfs RNDIS gadget (tools/rndis) holds the UDC the same
    way and must be detached first — see release_rndis_udc().
    """
    logger.debug("gadget_linux: upan_and_serial()")
    release_rndis_udc()
    try:
        # Free the UDC. modprobe -r on an unloaded module is a no-op.
        for mod in ('g_serial', 'g_mass_storage', 'g_ether', 'g_acm_ms'):
            os.system('sudo modprobe -r %s 2>/dev/null' % mod)
        umount_upan_partition()
        partition = get_upan_partition()
        os.system('sudo modprobe g_acm_ms file=%s removable=1 stall=0 iManufacturer="proxmark.org"' % partition)
    except Exception:
        pass


def upan_or_both(mod=None):
    """Enable USB mass storage or composite gadget mode.

    Args:
        mod: module name override (unused in practice)
    """
    usb_mass_storage()


def kill_all_module(auto_remount=True):
    """Remove all USB gadget kernel modules, then restore the baseline gadget.

    Args:
        auto_remount: if True, remount UPAN partition after cleanup (default True)

    This is the main teardown function called by PCModeActivity.stopPCMode().

    Factory audit ground truth
      docs/Real_Hardware_Intel/pcmode_live_audit_20260411.txt
        §4 dmesg: "[1891] g_serial gadget: g_serial ready (loaded during cleanup)"
        §5 POST-STOP STATE: "Kernel module: g_serial (NOT g_acm_ms)"

    Factory's teardown UNLOADS the composite g_acm_ms and then LOADS g_serial
    as the baseline gadget. Leaving the USB-C in a no-gadget state (our prior
    behaviour) breaks the USB controller until the device reboots — user-
    reported symptom 2026-04-17: "USB-C hub no longer works after PC-mode
    until I reboot". Restoring g_serial re-initialises the USB gadget layer
    cleanly.
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
    # Factory: reload g_serial as baseline gadget so USB controller is not
    # left orphaned. See audit §4/§5 cited above.
    try:
        os.system('sudo modprobe g_serial')
    except Exception:
        pass
    restore_rndis()
    if auto_remount:
        auto_ms_remount()


def mount_upan_partition():
    """Mount the UPAN partition at /mnt/upan/.

    Ground truth: V1090_SO_STRINGS_RAW.txt — "sudo mount -o rw "
    """
    logger.debug("gadget_linux: mount %s → %s", _UPAN_PARTITION, _MOUNT_POINT)
    try:
        os.system('sudo mkdir -p %s' % _MOUNT_POINT)
        os.system('sudo mount -o rw %s %s' % (_UPAN_PARTITION, _MOUNT_POINT))
    except Exception:
        pass


def umount_upan_partition():
    """Unmount the UPAN partition.

    Ground truth: V1090_SO_STRINGS_RAW.txt — "sudo umount "
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
