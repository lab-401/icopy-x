#!/bin/bash
# Dump Files scenario: dump_write_cancel
# Cancel write at WarningWriteActivity
# Ground truth: docs/UI_Mapping/03_dump_files/README.md §8
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="dump_write_cancel"
source "${PROJECT}/tests/flows/dump_files/includes/dump_common.sh"
run_dump_scenario "write_cancel" 6 "mf1" 4 ""
