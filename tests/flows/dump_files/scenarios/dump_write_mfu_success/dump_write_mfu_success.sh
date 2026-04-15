#!/bin/bash
# Dump Files scenario: dump_write_mfu_success
# MFU (Ultralight) write via write_file_base — hf mfu restore path
# Ground truth: trace_dump_files_20260403.txt lines 194-212
#   PM3 commands: hf mfu restore → hf 14a info → hf mf cgetblk 0 → hf mfu info
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="dump_write_mfu_success"
source "${PROJECT}/tests/flows/dump_files/includes/dump_common.sh"
run_dump_scenario "write_success" 7 "mfu" 1 "toast:Write successful"
