#!/bin/bash
# Dump Files scenario: dump_delete_last_file
# Delete the only file in a category, return to type list
# Only one MF1 file seeded. After deleting it, the category becomes empty and should return to Type List (showing "Dump Files" title without file list softkeys).
# Ground truth: docs/UI_Mapping/03_dump_files/README.md §5
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="dump_delete_last_file"
source "${PROJECT}/tests/flows/dump_files/includes/dump_common.sh"
run_dump_scenario "delete_last" 4 "mf1" 4 "title:Dump Files"
