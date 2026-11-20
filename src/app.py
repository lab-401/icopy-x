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

Application launcher with the staged-update fallback introduced in PR #14.

Boot chain:
    ipk_starter.py -> app.py -> main.main() -> application.startApp()

On each boot, this script checks for a staged firmware update in
    /home/pi/ipk_app_new. If present, it swaps it into /home/pi/ipk_app_main
    (the live application directory), then launches the app.

Staged files are checked before activation and a failed rename or exec
attempt restores the previous application when possible. The backup is
retained after exec; this is not a boot-health or power-loss recovery system.
USB accessory discovery belongs to ics_decoder, not this installation step.
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

    Rollback covers activation and exec failures, not failures after the
    new interpreter starts. A failed rollback raises rather than continuing
    with an inconsistent installation.

    Returns:
        False if no staged firmware found or swap failed (normal boot).
        Does NOT return if swap succeeds (process is replaced via execv).
    """
    if not os.path.isdir(APP_NEW):
        return False

    print("[app] Staged firmware found, validating...")

    # Step 1: Pre-swap validation
    try:
        is_valid, error_msg = _validate_staged_firmware()
    except OSError as error:
        is_valid, error_msg = False, str(error)
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
    original_cwd = os.getcwd()

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
                raise RuntimeError("Application activation rollback failed") from rollback_error
        else:
            print("[app] No backup to restore or directory unchanged")

        return False

    # Step 4: Restart from new location via os.execv()
    # This replaces the current process cleanly, avoiding self-modification
    new_app = os.path.join(APP_DIR, 'app.py')
    print("[app] Restarting from %s" % new_app)
    try:
        # rename() preserves a process's working-directory inode on Linux.
        # Explicitly enter the new tree before app.py resolves main/lib.
        os.chdir(APP_DIR)
        os.execv(sys.executable, [sys.executable, new_app])
    except OSError as error:
        print("[app] Restart FAILED: %s" % error)
        try:
            # Leave the failed update staged for diagnosis; never delete it.
            # Move out of APP_DIR first (also required for Windows tests).
            os.chdir(os.path.dirname(APP_DIR))
            os.rename(APP_DIR, APP_NEW)
            if backup_created:
                os.rename(APP_OLD, APP_DIR)
            os.chdir(original_cwd)
        except OSError as rollback_error:
            raise RuntimeError("Application restart rollback failed") from rollback_error
        if not backup_created:
            raise RuntimeError("Application restart failed; no previous application") from error
        return False



def _disable_universal_version():
    """Disable only the temporary Universal version.so before app imports.

    The original device-specific Lab401 version.so must never be renamed.
    This runs after any staged firmware swap (including the execv restart).
    """
    lib_dir = os.path.join(APP_DIR, 'lib')
    candidate = os.path.join(lib_dir, 'version.so')
    python_version = os.path.join(lib_dir, 'version.py')
    backup = candidate + '.bak'

    if not os.path.isfile(candidate) or not os.path.isfile(python_version):
        return

    try:
        # The exact group of fallback strings identifies our Universal shim.
        # Never rename an unknown or factory version.so.
        with open(candidate, 'rb') as f:
            binary = f.read(1024 * 1024 + 1)
        if len(binary) > 1024 * 1024:
            print('[app] version.so too large to identify; leaving unchanged')
            return
        signatures = (b'2.0.0', b'1.10', b'1.0.2', b'1.0', b'00000000')
        if not all(marker in binary for marker in signatures):
            print('[app] version.so is not recognized Universal; leaving unchanged')
            return

        if os.path.lexists(backup):
            # Preserve an existing backup, without allowing the shim to shadow
            # the real version.py on a subsequent firmware installation.
            os.remove(candidate)
            print('[app] Removed redundant Universal version.so; backup retained')
        else:
            os.rename(candidate, backup)
            print('[app] Disabled Universal version.so -> version.so.bak')
    except OSError as error:
        print('[app] Could not disable Universal version.so: %s' % error)


if __name__ == '__main__':
    # Swap staged firmware if present before launching app
    swap_firmware()
    _disable_universal_version()
    print("[app] Launching current application")

    sys.path.append("main")
    sys.path.append("lib")
    try:
        from main import main
        main.main()
    except Exception as e:
        print("\u542f\u52a8\u811a\u672c\u65e0\u6cd5\u542f\u52a8\u7a0b\u5e8f\uff0c\u51fa\u73b0\u5f02\u5e38: ", e)
        exit(44)
