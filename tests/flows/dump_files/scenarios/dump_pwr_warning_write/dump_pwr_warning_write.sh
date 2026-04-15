#!/bin/bash
# Dump Files scenario: dump_pwr_warning_write
# PWR from WarningWriteActivity cancels
# Ground truth: docs/UI_Mapping/03_dump_files/README.md
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="dump_pwr_warning_write"
source "${PROJECT}/tests/flows/dump_files/includes/dump_common.sh"
run_dump_scenario "pwr_warning_write" 6 "mf1" 4 ""
