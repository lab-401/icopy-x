#!/bin/bash
# Dump Files scenario: dump_delete_confirm_no
# Cancel delete with No button
# After pressing No, should return to file list.
# Ground truth: docs/UI_Mapping/03_dump_files/README.md §5
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="dump_delete_confirm_no"
source "${PROJECT}/tests/flows/dump_files/includes/dump_common.sh"
run_dump_scenario "delete_no" 4 "mf1" 4 "M1:Details"
