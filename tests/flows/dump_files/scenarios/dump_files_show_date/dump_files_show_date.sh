#!/bin/bash
# Dump Files scenario: dump_files_show_date
# M1 ("Details") in File List toggles is_dump_show_date — re-renders list with dates
# Ground truth: is_dump_show_date (L21389), get_ctime (L22076), date_format (L21842),
#               %Y-%m-%d %H:%M:%S (L21674), Screenshot A.3 (dates displayed)
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="dump_files_show_date"
source "${PROJECT}/tests/flows/dump_files/includes/dump_common.sh"
run_dump_scenario "files_show_date" 4 "mf1" 4 ""
