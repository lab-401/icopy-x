#!/bin/bash
# Dump Files scenario: dump_sim_hf
# Simulate MF1K from Dump Files (HF type -> trace view)
# Ground truth: docs/UI_Mapping/03_dump_files/README.md §6
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="dump_sim_hf"
source "${PROJECT}/tests/flows/dump_files/includes/dump_common.sh"
run_dump_scenario "simulate" 4 "mf1" 4 "title:Simulation"
