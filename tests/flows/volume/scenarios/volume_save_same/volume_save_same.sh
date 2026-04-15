#!/bin/bash
# Volume: start at Low(1), no navigation, M2 to save same level
# Tests the no-change save path.
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="volume_save_same"
source "${PROJECT}/tests/flows/volume/includes/volume_common.sh"
run_volume_scenario 1 "" "OK" 1 1
