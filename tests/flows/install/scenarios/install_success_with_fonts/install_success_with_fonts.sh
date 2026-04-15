#!/bin/bash
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="install_success_with_fonts"
INSTALL_BOOT_TIMEOUT=240
source "${PROJECT}/tests/flows/install/includes/install_common.sh"
# M2:Start gate verifies the button is rendered (onCreate complete, can_click=True)
# before sending OK to start the install.
run_install_scenario "valid_with_fonts.ipk" "title:Update|M2:Start|KEY:M2|SLEEP:45" 4
