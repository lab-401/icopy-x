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

"""Firmware update management — IPK search, validation, and installation.

OSS reimplementation of update functions called by AboutActivity._check_update().
Binary source: activity_update.so (search, checkPkg, unpkg, install methods)
Archive reference: /home/qx/archive/ui/activities/update.py

The AboutActivity calls these module-level functions:
  update.search(path)     — find .ipk files
  update.checkPkg()       — validate found package
  update.unpkg()          — extract to temp dir
  update.install(callback) — run installer

Also provides firmware check functions from update.so:
  check_all(), check_flash(), check_pm3(), check_linux(), check_stm32()
"""

import os
import shutil
import logging
import zipfile

logger = logging.getLogger(__name__)

# Paths matching original firmware
_UPAN_PATH = '/mnt/upan/'
_FW_PATH = '/mnt/upan/fw/'
_TMP_OUT_DIR = '/tmp/.ipk/unpkg'
_IPK_EXTENSION = '.ipk'

# Required files in IPK.
# The original firmware required lib/version.so and main/install.so (ARM .so).
# Our OSS firmware accepts .py equivalents too.
_REQUIRED_FILES = ['app.py']
_REQUIRED_EITHER = [
    ('lib/version.so', 'lib/version.py'),
    ('main/install.so', 'main/install.py'),
]

# Module state — set by search(), used by checkPkg/unpkg/install
_found_ipk = None


def search(path):
    """Search for .ipk firmware files in the given directory.

    Called by AboutActivity._check_update() as: update.search('/mnt/upan/')

    Args:
        path: directory to search (e.g. '/mnt/upan/')

    Returns:
        str path to first .ipk found, or None if none found
    """
    global _found_ipk
    _found_ipk = None

    if not os.path.isdir(path):
        logger.debug("update.search: path %s does not exist", path)
        return None

    try:
        for entry in sorted(os.listdir(path)):
            if entry.lower().endswith(_IPK_EXTENSION):
                full_path = os.path.join(path, entry)
                if os.path.isfile(full_path):
                    _found_ipk = full_path
                    logger.info("update.search: found %s", full_path)
                    return full_path
    except OSError as e:
        logger.error("update.search error: %s", e)

    logger.debug("update.search: no .ipk found in %s", path)
    return None


def checkPkg():
    """Validate the found IPK package structure.

    Checks that the ZIP contains app.py and at least one of each pair:
    (lib/version.so OR lib/version.py), (main/install.so OR main/install.py).

    Returns:
        True if valid, False otherwise

    Raises:
        RuntimeError: if no IPK was found by search()
    """
    if not _found_ipk:
        raise RuntimeError("No IPK found — call search() first")

    try:
        if not zipfile.is_zipfile(_found_ipk):
            logger.error("checkPkg: not a valid ZIP: %s", _found_ipk)
            return False

        with zipfile.ZipFile(_found_ipk, 'r') as zf:
            names = zf.namelist()
            for required in _REQUIRED_FILES:
                if required not in names:
                    logger.error("checkPkg: missing %s in IPK", required)
                    return False
            for either_a, either_b in _REQUIRED_EITHER:
                if either_a not in names and either_b not in names:
                    logger.error("checkPkg: need %s or %s in IPK",
                                 either_a, either_b)
                    return False

        logger.info("checkPkg: package valid")
        return True
    except Exception as e:
        logger.error("checkPkg failed: %s", e)
        return False


def unpkg():
    """Extract the found IPK to a temporary directory.

    Extracts to /tmp/.ipk/unpkg.

    Returns:
        True if successful, False otherwise
    """
    if not _found_ipk:
        raise RuntimeError("No IPK found — call search() first")

    try:
        if os.path.exists(_TMP_OUT_DIR):
            shutil.rmtree(_TMP_OUT_DIR)
        os.makedirs(_TMP_OUT_DIR, exist_ok=True)

        with zipfile.ZipFile(_found_ipk, 'r') as zf:
            zf.extractall(_TMP_OUT_DIR)

        # Make extracted files executable
        os.system('chmod -R 777 %s' % _TMP_OUT_DIR)

        logger.info("unpkg: extracted to %s", _TMP_OUT_DIR)
        return True
    except Exception as e:
        logger.error("unpkg failed: %s", e)
        return False


def install(callback=None):
    """Install the extracted firmware.

    Tries installers in order:
      1. main/install.py  (OSS Python installer)
      2. main/install.so  (original ARM binary)
      3. Fallback file copy

    Args:
        callback: progress callback — signature: callback(name, progress)

    Returns:
        True if successful, False otherwise
    """
    cb = callback or (lambda n, p: None)

    # 1. Try OSS install.py
    install_py = os.path.join(_TMP_OUT_DIR, 'main', 'install.py')
    if os.path.exists(install_py):
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location('install', install_py)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if hasattr(mod, 'install'):
                logger.info("Running install.py")
                mod.install(_TMP_OUT_DIR, cb)
                return True
        except Exception as e:
            logger.warning("install.py failed: %s", e)

    # 2. Try genuine install.so
    install_so = os.path.join(_TMP_OUT_DIR, 'main', 'install.so')
    if os.path.exists(install_so):
        try:
            import importlib.machinery
            loader = importlib.machinery.ExtensionFileLoader('install', install_so)
            spec = importlib.util.spec_from_file_location('install', install_so,
                                                           loader=loader)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if hasattr(mod, 'install'):
                logger.info("Running install.so")
                mod.install(_TMP_OUT_DIR, cb)
                return True
        except Exception as e:
            logger.warning("install.so failed: %s — using fallback", e)

    # 3. Fallback: simple file-copy
    return _fallback_install(callback)


def _fallback_install(callback=None):
    """Fallback installer when install.so is not available.

    Copies extracted files to the new app directory. The device's
    ipk_starter.py will swap ipk_app_new → ipk_app_main on next boot.

    Ground truth: archive/ui/activities/update.py _fallbackInstall()
    """
    dest_unpkg = '/home/pi/unpkg'
    dest_new = '/home/pi/ipk_app_new'

    try:
        if os.path.exists(dest_unpkg):
            shutil.rmtree(dest_unpkg)
        if os.path.exists(dest_new):
            shutil.rmtree(dest_new)

        shutil.move(_TMP_OUT_DIR, dest_unpkg)
        os.rename(dest_unpkg, dest_new)

        logger.info("Fallback install: files placed at %s", dest_new)
        if callback:
            callback('install', 100)
        return True
    except Exception as e:
        logger.error("Fallback install failed: %s", e)
        return False


# =====================================================================
# Firmware component check functions (from original update.so)
# Ground truth: V1090_MODULE_AUDIT.txt lines 2916+
# =====================================================================

def check_all():
    """Check if any firmware update is available."""
    return (bool(check_flash()) or bool(check_pm3()) or
            bool(check_linux()) or bool(check_stm32()))


def check_flash():
    """Check for flash firmware update files."""
    return _scan_fw_dir('flash', '.bin')


def check_pm3():
    """Check for PM3 firmware update files."""
    return _scan_fw_dir('pm3', '.bin')


def check_linux():
    """Check for Linux OS update files."""
    return _scan_fw_dir(None, '.ipk')


def check_stm32():
    """Check for STM32/GD32 firmware update files."""
    results = _scan_fw_dir('stm32', '.bin')
    results += _scan_fw_dir('hmi', '.bin')
    return results


def check_hmi_update():
    """Check if HMI update is available."""
    return bool(check_stm32())


def check_pm3_update():
    """Check if PM3 update is available."""
    return bool(check_pm3())


def _scan_fw_dir(keyword, extension):
    """Scan firmware directory for files matching keyword + extension."""
    results = []
    try:
        if os.path.exists(_FW_PATH):
            for f in os.listdir(_FW_PATH):
                if f.endswith(extension):
                    if keyword is None or keyword in f.lower():
                        results.append(os.path.join(_FW_PATH, f))
    except Exception:
        pass
    return results


def delete_fw_if_no_update():
    """Delete firmware files if no valid update found."""
    try:
        if os.path.exists(_FW_PATH) and not check_all():
            shutil.rmtree(_FW_PATH, ignore_errors=True)
    except Exception:
        pass
