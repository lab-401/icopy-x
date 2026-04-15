#!/bin/bash
# UpdateActivity READY → PWR → back to About
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="install_ready_pwr"
source "${PROJECT}/tests/flows/install/includes/install_common.sh"
run_install_scenario "valid_minimal.ipk" "title:Update|M2:Start|KEY:PWR|SLEEP:3|title:About" 3
