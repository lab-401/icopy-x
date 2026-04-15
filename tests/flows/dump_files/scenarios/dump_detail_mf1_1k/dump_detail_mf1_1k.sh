#!/bin/bash
# Dump Files scenario: dump_detail_mf1_1k
# Tag Info for Mifare Classic 1K (parseInfoByM1FileName, regex R1, size="1K")
# Seed: M1-1K-4B_DAEFB416_1.bin → display "1K-4B-DAEFB416(1)"
# Ground truth: Screenshot 090-Dump-Types-Files-Info.png, regex L21251,
#               trace L5: START(ReadFromHistoryActivity, '.../M1-1K-4B_B7785E50_11.eml')
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="dump_detail_mf1_1k"
source "${PROJECT}/tests/flows/dump_files/includes/dump_common.sh"
run_dump_scenario "detail" 4 "mf1" 4 "title:Tag Info"
