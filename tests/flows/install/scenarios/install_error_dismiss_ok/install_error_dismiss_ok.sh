#!/bin/bash
# Error dismiss via OK key. Uses corrupt install.so → error 0x03.
# QEMU original: background thread toast invisible. Verifies error path + process alive.
# Full dismiss test (OK on error toast → return to About): --target=current only.
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="install_error_dismiss_ok"
source "${PROJECT}/tests/flows/install/includes/install_common.sh"
# Error dismiss via M1 (Cancel). M2 re-triggers the install in ERROR state.
# On the real device, M1/PWR/arrow keys all dismiss. OK→M2 mapping re-installs.
run_install_scenario "corrupt_install.ipk" "title:Update|M2:Start|KEY:M2|SLEEP:10|toast:Install failed|KEY:M1|SLEEP:3|title:About" 5
