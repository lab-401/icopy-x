#!/bin/bash
# Backlight: start at Low(0), DOWN×2 to High(2), M2 save
# Trace source: real device trace session 1 (20260330)
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="backlight_save_low_to_high"
BOOT_TIMEOUT=300
source "${PROJECT}/tests/flows/backlight/includes/backlight_common.sh"
run_backlight_scenario 0 "DOWN DOWN" "OK" 3 2
