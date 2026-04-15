#!/bin/bash
# Backlight: start at High(2), UP×2 to Low(0), PWR cancel — recovers to High
# Tests recovery_backlight() restoring High (non-Low starting point)
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="backlight_cancel_from_high"
BOOT_TIMEOUT=300
source "${PROJECT}/tests/flows/backlight/includes/backlight_common.sh"
run_backlight_scenario 2 "UP UP" "PWR" 2 2
