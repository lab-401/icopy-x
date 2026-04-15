#!/bin/bash
# Volume: start at Low(1), DOWN×1 to Middle(2), M2 save
# Tests non-Off to non-Off save (setKeyAudioEnable stays true)
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="volume_save_low_to_mid"
source "${PROJECT}/tests/flows/volume/includes/volume_common.sh"
run_volume_scenario 1 "DOWN" "OK" 2 2
