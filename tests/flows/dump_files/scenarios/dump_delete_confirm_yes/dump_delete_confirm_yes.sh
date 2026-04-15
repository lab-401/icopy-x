#!/bin/bash
# Dump Files scenario: dump_delete_confirm_yes
# Delete file with Yes confirmation
# Seeds multiple MF1 files so list still has items after delete. After confirming delete, should return to file list with M1:Details visible.
# Ground truth: docs/UI_Mapping/03_dump_files/README.md §5
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="dump_delete_confirm_yes"
source "${PROJECT}/tests/flows/dump_files/includes/dump_common.sh"
run_dump_scenario "delete_yes" 4 "mf1" 4 "M1:Details" "multi:mf1:3"
