#!/bin/bash
# Dump Files scenario: dump_write_lf_success
# LF write via write_id — EM410x clone (T55xx-based) success path
# Ground truth: trace_dump_files_20260403.txt lines 172-189 (FDX clone, same mechanism)
#               write_id method (L22126)
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="dump_write_lf_success"
source "${PROJECT}/tests/flows/dump_files/includes/dump_common.sh"
run_dump_scenario "write_success" 7 "em410x" 19 "toast:Write successful"
