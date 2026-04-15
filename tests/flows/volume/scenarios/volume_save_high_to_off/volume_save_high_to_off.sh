#!/bin/bash
# Volume: start at High(3), UP×3 to Off(0), M2 to save
# Tests full reverse traversal of volume levels.
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="volume_save_high_to_off"
source "${PROJECT}/tests/flows/volume/includes/volume_common.sh"
run_volume_scenario 3 "UP UP UP" "OK" 2 0
