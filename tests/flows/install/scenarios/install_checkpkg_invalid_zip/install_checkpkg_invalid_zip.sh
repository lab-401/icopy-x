#!/bin/bash
# Invalid ZIP file → checkPkg should fail (error 0x05) in background thread.
# QEMU limitation: original .so background thread UI updates are invisible (Tk not thread-safe).
# Verify: IPK found → UpdateActivity launched → READY state → OK starts install → process alive.
# Full error toast verification: --target=current only.
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="install_checkpkg_invalid_zip"
source "${PROJECT}/tests/flows/install/includes/install_common.sh"
run_install_scenario "invalid_zip.ipk" "title:Update|M2:Start|KEY:M2|SLEEP:10|toast:Install failed" 4
