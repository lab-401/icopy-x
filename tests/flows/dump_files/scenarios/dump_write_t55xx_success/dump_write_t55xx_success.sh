#!/bin/bash
# Dump Files scenario: dump_write_t55xx_success
# T55xx raw dump write via write_lf_dump — restore succeeds, verify matches
# Ground truth: trace_dump_files_em410x_t55xx_write_20260405.txt lines 103-136
#   Seed block 0 = 00148040, fixture read-back = 00148040 → match → success
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="dump_write_t55xx_success"
source "${PROJECT}/tests/flows/dump_files/includes/dump_common.sh"
run_dump_scenario "write_success" 7 "t55xx" 17 "toast:Write successful"
