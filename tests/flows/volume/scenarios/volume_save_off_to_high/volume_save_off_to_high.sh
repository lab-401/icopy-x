#!/bin/bash
# Volume: start at Off(0), DOWN×3 to High(3), M2 to save
# Trace source: real device Session 1 (start=Low, save=High)
# This scenario starts at Off and navigates full range down to High.
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="volume_save_off_to_high"
source "${PROJECT}/tests/flows/volume/includes/volume_common.sh"
run_volume_scenario 0 "DOWN DOWN DOWN" "OK" 2 3
