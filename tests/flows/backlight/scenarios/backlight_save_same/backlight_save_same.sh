#!/bin/bash
# Backlight: start at Middle(1), no navigation, M2 save same level
# Tests save without changing selection
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="backlight_save_same"
BOOT_TIMEOUT=300
source "${PROJECT}/tests/flows/backlight/includes/backlight_common.sh"
run_backlight_scenario 1 "" "OK" 1 1
