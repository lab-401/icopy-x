#!/usr/bin/env python3

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

"""iCopy-X boot starter - swaps staged firmware and launches the app.

Boot chain:
    ipk_starter.py -> app.py -> main.main() -> application.startApp()

On each boot, this script checks for a staged firmware update in
/home/pi/ipk_app_new. If present, it swaps it into /home/pi/ipk_app_main
(the live application directory), then launches the app.

The swap mechanism:
    1. If /home/pi/ipk_app_new exists, it contains a complete firmware
       package staged by the installer (install.py or install.so).
    2. Rename current /home/pi/ipk_app_main to /home/pi/ipk_app_old (backup).
    3. Rename /home/pi/ipk_app_new to /home/pi/ipk_app_main (activate).
    4. Launch app.py from the new /home/pi/ipk_app_main directory.
"""

import os
import shutil
import sys


APP_DIR = '/home/pi/ipk_app_main'
APP_NEW = '/home/pi/ipk_app_new'
APP_OLD = '/home/pi/ipk_app_old'


def swap_firmware():
    """Swap staged firmware into place if present.

    Returns:
        True if a swap was performed, False if no staged firmware found.
    """
    if not os.path.isdir(APP_NEW):
        return False

    print("[ipk_starter] Staged firmware found, swapping...")

    # Remove any previous backup
    if os.path.isdir(APP_OLD):
        try:
            shutil.rmtree(APP_OLD)
            print("[ipk_starter] Removed previous backup")
        except Exception as e:
            print("[ipk_starter] Warning: could not remove old backup: %s" % e)

    # Backup current firmware
    if os.path.isdir(APP_DIR):
        try:
            os.rename(APP_DIR, APP_OLD)
            print("[ipk_starter] Backed up current firmware to %s" % APP_OLD)
        except Exception as e:
            print("[ipk_starter] Error: could not backup current firmware: %s" % e)
            return False

    # Activate staged firmware
    try:
        os.rename(APP_NEW, APP_DIR)
        print("[ipk_starter] Activated staged firmware")
    except Exception as e:
        print("[ipk_starter] Error: could not activate staged firmware: %s" % e)
        # Try to restore backup
        if os.path.isdir(APP_OLD) and not os.path.isdir(APP_DIR):
            try:
                os.rename(APP_OLD, APP_DIR)
                print("[ipk_starter] Restored backup")
            except Exception:
                pass
        return False

    return True


def main():
    """Run the boot starter."""
    print("[ipk_starter] iCopy-X boot starting...")

    # Swap staged firmware if present
    swapped = swap_firmware()
    if swapped:
        print("[ipk_starter] Firmware swap complete")
    else:
        print("[ipk_starter] No staged firmware, using current")

    # Set up paths for app launch
    app_dir = APP_DIR
    main_dir = os.path.join(app_dir, 'main')
    lib_dir = os.path.join(app_dir, 'lib')

    # Add to sys.path so imports work
    if main_dir not in sys.path:
        sys.path.insert(0, main_dir)
    if lib_dir not in sys.path:
        sys.path.insert(0, lib_dir)
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)

    # Launch the app
    print("[ipk_starter] Launching app from %s" % app_dir)
    app_py = os.path.join(app_dir, 'app.py')
    if not os.path.isfile(app_py):
        print("[ipk_starter] ERROR: app.py not found at %s" % app_py)
        sys.exit(1)

    # Execute app.py
    try:
        with open(app_py, 'r') as f:
            code = f.read()
        exec(compile(code, app_py, 'exec'))
    except Exception as e:
        print("[ipk_starter] ERROR: app.py failed: %s" % e)
        sys.exit(1)


if __name__ == '__main__':
    main()
