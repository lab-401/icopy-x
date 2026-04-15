#!/bin/bash
# Dump Files scenario: dump_files_scroll
# Scroll through multi-file list with UP/DOWN
# Ground truth: docs/UI_Mapping/03_dump_files/README.md
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="dump_files_scroll"
source "${PROJECT}/tests/flows/dump_files/includes/dump_common.sh"
run_dump_scenario "files_scroll" 3 "mf1" 4 "M1:Details" "multi:mf1:5"
