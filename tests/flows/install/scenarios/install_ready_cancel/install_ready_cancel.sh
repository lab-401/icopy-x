#!/bin/bash
# UpdateActivity READY → M1 (Cancel) → back to About
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="install_ready_cancel"
source "${PROJECT}/tests/flows/install/includes/install_common.sh"
run_install_scenario "valid_minimal.ipk" "title:Update|M2:Start|KEY:M1|title:About" 3
