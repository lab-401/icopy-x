#!/bin/bash
# Dump Files scenario: dump_write_mf1k_fail
# MF1K write failure through Dump Files
# Ground truth: docs/UI_Mapping/03_dump_files/README.md §8
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="dump_write_mf1k_fail"
source "${PROJECT}/tests/flows/dump_files/includes/dump_common.sh"
run_dump_scenario "write_fail" 6 "mf1" 4 "toast:Write failed"
