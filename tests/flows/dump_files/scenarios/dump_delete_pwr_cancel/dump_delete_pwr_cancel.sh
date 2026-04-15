#!/bin/bash
# Dump Files scenario: dump_delete_pwr_cancel
# Cancel delete with PWR key
# PWR during Delete confirmation should cancel and return to file list.
# Ground truth: docs/UI_Mapping/03_dump_files/README.md §5
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="dump_delete_pwr_cancel"
source "${PROJECT}/tests/flows/dump_files/includes/dump_common.sh"
run_dump_scenario "delete_pwr" 4 "mf1" 4 "title:Dump Files"
