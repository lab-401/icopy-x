#!/bin/bash
# Dump Files scenario: dump_types_empty
# No dump files anywhere, verify empty state message
# Ground truth: docs/UI_Mapping/03_dump_files/README.md
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="dump_types_empty"
source "${PROJECT}/tests/flows/dump_files/includes/dump_common.sh"
run_dump_scenario "types_empty" 1 "none" 0 "title:Dump Files"
