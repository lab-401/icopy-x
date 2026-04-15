#!/bin/bash
# Dump Files scenario: dump_types_multi
# Multiple type categories visible
# Ground truth: docs/UI_Mapping/03_dump_files/README.md
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="dump_types_multi"
source "${PROJECT}/tests/flows/dump_files/includes/dump_common.sh"
run_dump_scenario "types_multi" 1 "mf1,em410x,hid,t55xx" 0 "title:Dump Files"
