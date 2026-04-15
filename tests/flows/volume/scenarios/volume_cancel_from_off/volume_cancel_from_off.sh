#!/bin/bash
# Volume: start at Off(0), DOWN×1 to Low(1), PWR exit
# PWR exits WITHOUT recovery — conf.ini still has volume=0
# Verifies no-recovery from Off starting point
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="volume_cancel_from_off"
source "${PROJECT}/tests/flows/volume/includes/volume_common.sh"
run_volume_scenario 0 "DOWN" "PWR" 2 0
