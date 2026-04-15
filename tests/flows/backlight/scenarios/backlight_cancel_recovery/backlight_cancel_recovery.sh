#!/bin/bash
# Backlight: start at Low(0), DOWN to Middle(1), PWR cancel — recovers to Low
# Tests recovery_backlight() restoring original level
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="backlight_cancel_recovery"
BOOT_TIMEOUT=300
source "${PROJECT}/tests/flows/backlight/includes/backlight_common.sh"
run_backlight_scenario 0 "DOWN" "PWR" 2 0
