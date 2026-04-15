#!/bin/bash
# Dump Files scenario: dump_pwr_type_list
# PWR from type list exits to main menu
# Ground truth: docs/UI_Mapping/03_dump_files/README.md
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="dump_pwr_type_list"
source "${PROJECT}/tests/flows/dump_files/includes/dump_common.sh"
run_dump_scenario "pwr_type_list" 1 "mf1" 0 ""
