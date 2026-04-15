#!/bin/bash
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="install_success_minimal"
INSTALL_BOOT_TIMEOUT=240
source "${PROJECT}/tests/flows/install/includes/install_common.sh"
# "Update finish" toast appears too briefly for state dumps to capture reliably.
# Gate on SLEEP after M2 press: install pipeline completes in ~30s (extract, chmod,
# install_app, restart_app). The expected.json validates Update title + Start button.
run_install_scenario "valid_minimal.ipk" "title:Update|M2:Start|KEY:M2|SLEEP:45" 4
