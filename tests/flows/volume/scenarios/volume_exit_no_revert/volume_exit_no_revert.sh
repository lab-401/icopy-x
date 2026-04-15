#!/bin/bash
# Volume: start at Middle(2), DOWN once to High(3), PWR to exit
# PWR exits WITHOUT recovery — key difference from Backlight flow.
# The navigated-to level is NOT reverted.
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="volume_exit_no_revert"
source "${PROJECT}/tests/flows/volume/includes/volume_common.sh"
run_volume_scenario 2 "DOWN" "PWR" 2 2
