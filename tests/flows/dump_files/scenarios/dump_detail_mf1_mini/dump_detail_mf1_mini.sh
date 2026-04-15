#!/bin/bash
# Dump Files scenario: dump_detail_mf1_mini
# Tag Info for Mifare Mini (parseInfoByM1FileName, regex R1, size="Mini")
# Seed: M1-Mini-4B_8800E177_1.bin → display "Mini-4B-8800E177(1)"
# Ground truth: Screenshot 090-Dump-Types-Files.png "Mini-4B-8800E177", regex L21251
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="dump_detail_mf1_mini"
source "${PROJECT}/tests/flows/dump_files/includes/dump_common.sh"
run_dump_scenario "detail" 4 "mf1_mini" 4 "title:Tag Info"
