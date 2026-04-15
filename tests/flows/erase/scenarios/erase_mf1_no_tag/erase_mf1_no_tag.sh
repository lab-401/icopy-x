#!/bin/bash
# Erase MF1 — no tag present, hf 14a info times out
# Source: .so binary analysis
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="erase_mf1_no_tag"
source "${PROJECT}/tests/flows/erase/includes/erase_common.sh"
run_erase_scenario 0 3 "toast:No tag found"
