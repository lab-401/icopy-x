#!/bin/bash
# Dump Files scenario: dump_pwr_file_list
# PWR from file list returns to type list
# Ground truth: docs/UI_Mapping/03_dump_files/README.md
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="dump_pwr_file_list"
source "${PROJECT}/tests/flows/dump_files/includes/dump_common.sh"
run_dump_scenario "pwr_file_list" 2 "mf1" 4 ""
