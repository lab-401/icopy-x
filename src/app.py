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
# If by accident a copyright was removed from this file and is not directly deducible from the Git history, please submit a PR.
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

"""iCopy-X application entry point.

Verbatim reproduction of the original app.py from v1.0.90 firmware.
Source: docs/ORIGINAL_ANALYSIS.md Section 2 (Boot Sequence).

Boot chain:
    ipk_starter.py -> app.py -> main.main() -> application.startApp()

On each boot, this script checks for a staged firmware update in
    /home/pi/ipk_app_new. If present, it swaps it into /home/pi/ipk_app_main
    (the live application directory), then launches the app.

SAFETY MECHANISMS:
    1. Pre-swap validation: verifies required files exist and are non-zero
    2. Try/except with automatic rollback: if ANY step fails, restores backup
    3. os.execv() for clean restart after swap (no self-modification)
    4. Cleanup on success only: ipk_app_old preserved until new version runs
"""
import os
import shutil
import sys


APP_DIR = '/home/pi/ipk_app_main'
APP_NEW = '/home/pi/ipk_app_new'
APP_OLD = '/home/pi/ipk_app_old'

# Required files that must exist in ipk_app_new before we attempt swap
_REQUIRED_FILES = ['app.py', 'main/main.py', 'lib/actmain.py']


def _validate_staged_firmware():
    """Validate that staged firmware has all required files.

    Returns:
        Tuple of (is_valid, error_message).
        is_valid is True if all required files exist and are non-zero.
    """
    if not os.path.isdir(APP_NEW):
        return False, "Staged firmware directory does not exist"

    for rel_path in _REQUIRED_FILES:
        full_path = os.path.join(APP_NEW, rel_path)
        if not os.path.isfile(full_path):
            return False, "Missing required file: %s" % rel_path
        if os.path.getsize(full_path) == 0:
            return False, "Required file is empty: %s" % rel_path

    return True, None


def swap_firmware():
    """Swap staged firmware into place if present.

    SAFE SWAP PATTERN:
        1. Validate staged firmware has required files
        2. Backup current firmware to ipk_app_old
        3. Move ipk_app_new to ipk_app_main
        4. Restart via os.execv() (clean process replacement)

    AUTOMATIC ROLLBACK:
        If ANY step fails, the backup is automatically restored.
        The function returns False on failure so the current firmware runs.

    Returns:
        False if no staged firmware found or swap failed (normal boot).
        Does NOT return if swap succeeds (process is replaced via execv).
    """
    if not os.path.isdir(APP_NEW):
        return False

    print("[app] Staged firmware found, validating...")

    # Step 1: Pre-swap validation
    is_valid, error_msg = _validate_staged_firmware()
    if not is_valid:
        print("[app] Validation FAILED: %s" % error_msg)
        print("[app] Aborting swap, using current firmware")
        return False

    print("[app] Validation passed")

    # Step 2: Remove any previous backup (from failed prior attempt)
    if os.path.isdir(APP_OLD):
        try:
            shutil.rmtree(APP_OLD)
        except Exception as e:
            print("[app] Warning: could not remove old backup: %s" % e)

    # Step 3: Perform swap with automatic rollback on failure
    # The entire backup-activate sequence is wrapped so ANY exception
    # triggers automatic restoration of the backup
    backup_created = False

    try:
        # Backup current firmware
        if os.path.isdir(APP_DIR):
            os.rename(APP_DIR, APP_OLD)
            backup_created = True
            print("[app] Backed up current firmware to %s" % APP_OLD)

        # Activate staged firmware
        os.rename(APP_NEW, APP_DIR)
        print("[app] Activated staged firmware")

    except Exception as e:
        print("[app] Swap FAILED: %s" % e)
        print("[app] Attempting automatic rollback...")

        # AUTOMATIC ROLLBACK: restore backup if we created one
        if backup_created and os.path.isdir(APP_OLD) and not os.path.isdir(APP_DIR):
            try:
                os.rename(APP_OLD, APP_DIR)
                print("[app] ROLLBACK SUCCESSFUL: restored current firmware")
            except Exception as rollback_error:
                print("[app] ROLLBACK FAILED: %s" % rollback_error)
                print("[app] MANUAL RECOVERY REQUIRED")
        else:
            print("[app] No backup to restore or directory unchanged")

        return False

    # Step 4: Restart from new location via os.execv()
    # This replaces the current process cleanly, avoiding self-modification
    new_app = os.path.join(APP_DIR, 'app.py')
    print("[app] Restarting from %s" % new_app)
    os.execv(sys.executable, [sys.executable, new_app])


if __name__ == '__main__':
    # Swap staged firmware if present before launching app
    swapped = swap_firmware()
    if swapped:
        # This line is never reached because os.execv() replaces the process
        print("[app] Firmware swap complete")
    else:
        print("[app] No staged firmware, using current")

    sys.path.append("main")
    sys.path.append("lib")
    try:
        from main import main
        main.main()
    except Exception as e:
        print("\u542f\u52a8\u811a\u672c\u65e0\u6cd5\u542f\u52a8\u7a0b\u5e8f\uff0c\u51fa\u73b0\u5f02\u5e38: ", e)
        exit(44)
