#!/bin/bash
# Dump Files scenario: dump_pwr_data_ready
# PWR from data ready returns to tag info
# Ground truth: docs/UI_Mapping/03_dump_files/README.md
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="dump_pwr_data_ready"
source "${PROJECT}/tests/flows/dump_files/includes/dump_common.sh"
run_dump_scenario "pwr_data_ready" 5 "mf1" 4 ""
