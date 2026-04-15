#!/bin/bash
# Backlight: start at Low(0), no navigation, PWR exit immediately
# Tests immediate exit with no changes
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="backlight_exit_immediate"
BOOT_TIMEOUT=300
source "${PROJECT}/tests/flows/backlight/includes/backlight_common.sh"
run_backlight_scenario 0 "" "PWR" 1 0
