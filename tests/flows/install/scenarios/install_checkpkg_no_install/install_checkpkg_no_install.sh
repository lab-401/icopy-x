#!/bin/bash
# IPK missing main/install.so → checkPkg should fail (error 0x05) in background thread.
# QEMU limitation: background thread toasts invisible. Verify READY state + process alive.
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="install_checkpkg_no_install"
source "${PROJECT}/tests/flows/install/includes/install_common.sh"
run_install_scenario "no_install.ipk" "title:Update|M2:Start|KEY:M2|SLEEP:10|toast:Install failed" 4
