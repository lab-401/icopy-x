#!/bin/bash
# Dump Files scenario: dump_pwr_tag_info
# PWR from tag info returns to file list
# Ground truth: docs/UI_Mapping/03_dump_files/README.md
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="dump_pwr_tag_info"
source "${PROJECT}/tests/flows/dump_files/includes/dump_common.sh"
run_dump_scenario "pwr_tag_info" 4 "mf1" 4 ""
