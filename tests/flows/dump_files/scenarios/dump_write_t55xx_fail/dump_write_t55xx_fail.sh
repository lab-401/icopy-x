#!/bin/bash
# Dump Files scenario: dump_write_t55xx_fail
# T55xx raw dump write via write_lf_dump — write fails (toast: Write failed!)
# Ground truth: trace_dump_files_em410x_t55xx_write_20260405.txt
# The fixture returns correct PM3 responses but the original firmware reports failure.
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="dump_write_t55xx_fail"
source "${PROJECT}/tests/flows/dump_files/includes/dump_common.sh"
run_dump_scenario "write_fail" 7 "t55xx" 17 "toast:Write failed"
