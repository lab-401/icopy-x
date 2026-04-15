#!/bin/bash
# Backlight: start at Low(0), DOWN×1 to Middle(1), M2 save
# Tests single-step save (partial traversal)
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="backlight_save_low_to_mid"
BOOT_TIMEOUT=300
source "${PROJECT}/tests/flows/backlight/includes/backlight_common.sh"
run_backlight_scenario 0 "DOWN" "OK" 2 1
