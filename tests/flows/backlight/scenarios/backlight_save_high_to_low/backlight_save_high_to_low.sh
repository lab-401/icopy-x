#!/bin/bash
# Backlight: start at High(2), UP×2 to Low(0), M2 save
# Inverse of session 1 trace
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="backlight_save_high_to_low"
BOOT_TIMEOUT=300
source "${PROJECT}/tests/flows/backlight/includes/backlight_common.sh"
run_backlight_scenario 2 "UP UP" "OK" 3 0
