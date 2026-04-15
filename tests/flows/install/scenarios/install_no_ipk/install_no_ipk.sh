#!/bin/bash
# No .ipk on USB → original firmware shows "Install failed, code = 0x03" inline at About.
# Ground truth: sequential QEMU run 2026-04-10 confirmed this behavior with clean /mnt/upan/.
# The original firmware's checkUpdate() path under QEMU produces 0x03 when no IPK is found,
# NOT the "No update available" toast that the decompiled source suggests.
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="install_no_ipk"
source "${PROJECT}/tests/flows/install/includes/install_common.sh"
run_install_scenario "NONE" "toast:Install failed" 2
