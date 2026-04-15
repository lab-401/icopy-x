#!/bin/bash
# Dump Files scenario: dump_files_empty_type
# Type with no supported files shows empty message
# Ground truth: docs/UI_Mapping/03_dump_files/README.md
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="dump_files_empty_type"
source "${PROJECT}/tests/flows/dump_files/includes/dump_common.sh"
run_dump_scenario "types_single" 1 "mf1" 0 "title:Dump Files"
