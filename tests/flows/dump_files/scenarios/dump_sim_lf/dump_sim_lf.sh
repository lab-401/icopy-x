#!/bin/bash
# Dump Files scenario: dump_sim_lf
# Simulate EM410x from Dump Files (LF type -> sim UI)
# Ground truth: docs/UI_Mapping/03_dump_files/README.md §6
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="dump_sim_lf"
source "${PROJECT}/tests/flows/dump_files/includes/dump_common.sh"
run_dump_scenario "simulate" 4 "em410x" 19 "title:Simulation"
