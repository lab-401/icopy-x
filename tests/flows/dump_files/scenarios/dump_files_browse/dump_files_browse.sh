#!/bin/bash
# Dump Files scenario: dump_files_browse
# Browse MF1 file list, verify files shown
# Ground truth: docs/UI_Mapping/03_dump_files/README.md
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="dump_files_browse"
source "${PROJECT}/tests/flows/dump_files/includes/dump_common.sh"
run_dump_scenario "files_browse" 3 "mf1" 4 "M1:Details" ""
