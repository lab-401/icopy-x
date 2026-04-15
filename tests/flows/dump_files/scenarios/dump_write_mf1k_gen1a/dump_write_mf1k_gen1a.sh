#!/bin/bash
# Dump Files scenario: dump_write_mf1k_gen1a
# MF1K Gen1a magic card write via write_file_base — hf mf cload path
# Ground truth: trace_dump_files_20260403.txt lines 218-265
#   PM3 commands: hf 14a info (detects Gen1a) → hf mf cload → raw BCC fix ×6 → verify
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="dump_write_mf1k_gen1a"
source "${PROJECT}/tests/flows/dump_files/includes/dump_common.sh"
run_dump_scenario "write_success" 7 "mf1" 4 "toast:Write successful"
