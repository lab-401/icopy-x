#!/bin/bash
# DRM serial mismatch (wrong_serial.ipk has serial 99999999, device has 02150004).
# Under QEMU, checkVer runs in background thread → error toast invisible.
# Sequential run 2026-04-10 confirmed: IPK reaches Update (stack=3), not inline fail.
# Verify: UpdateActivity READY reached → OK starts install → process alive.
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="install_checkver_fail"
source "${PROJECT}/tests/flows/install/includes/install_common.sh"
run_install_scenario "wrong_serial.ipk" "title:Update|M2:Start|KEY:M2|SLEEP:10|toast:Install failed" 4
