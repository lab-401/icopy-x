#!/bin/bash
# Dump Files scenario: dump_types_scroll
# Scroll through type list with UP/DOWN
# Ground truth: docs/UI_Mapping/03_dump_files/README.md
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="dump_types_scroll"
source "${PROJECT}/tests/flows/dump_files/includes/dump_common.sh"
run_dump_scenario "types_scroll" 2 "mf1,em410x,hid,t55xx,awid,viking" 0 ""
