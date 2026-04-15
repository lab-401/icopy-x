#!/bin/bash
# Corrupt install.so → path_import fails → error 0x03 in background thread.
# QEMU limitation: background thread toasts invisible. Verify READY state + process alive.
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="install_install_exception"
source "${PROJECT}/tests/flows/install/includes/install_common.sh"
run_install_scenario "corrupt_install.ipk" "title:Update|M2:Start|KEY:M2|SLEEP:10|toast:Install failed" 4
