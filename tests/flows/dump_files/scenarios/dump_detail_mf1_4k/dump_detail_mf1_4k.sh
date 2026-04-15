#!/bin/bash
# Dump Files scenario: dump_detail_mf1_4k
# Tag Info for Mifare Classic 4K (parseInfoByM1FileName, regex R1, size="4K")
# Seed: M1-4K-4B_E93C5221_1.bin → display "4K-4B-E93C5221(1)"
# Ground truth: M1_S70_4K_4B (L21765), regex M1-(\S+)-(\S+)_([A-Fa-f\d]+)_(\d+).*\.(.*) (L21251)
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="dump_detail_mf1_4k"
source "${PROJECT}/tests/flows/dump_files/includes/dump_common.sh"
run_dump_scenario "detail" 4 "mf1_4k" 4 "title:Tag Info"
