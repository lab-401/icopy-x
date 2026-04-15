#!/bin/bash
# Volume: start at Off(0), no navigation, PWR to exit immediately
# Tests the minimal path through VolumeActivity.
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="volume_exit_immediate"
source "${PROJECT}/tests/flows/volume/includes/volume_common.sh"
run_volume_scenario 0 "" "PWR" 1 0
