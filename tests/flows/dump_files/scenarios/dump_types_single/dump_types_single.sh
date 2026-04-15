#!/bin/bash
# Dump Files scenario: dump_types_single
# One type category visible (Mifare Classic)
# Ground truth: docs/UI_Mapping/03_dump_files/README.md
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="dump_types_single"
source "${PROJECT}/tests/flows/dump_files/includes/dump_common.sh"
run_dump_scenario "types_single" 1 "mf1" 0 "title:Dump Files"
