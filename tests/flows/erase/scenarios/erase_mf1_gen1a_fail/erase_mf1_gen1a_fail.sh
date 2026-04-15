#!/bin/bash
# Erase MF1 Gen1a magic card — cwipe timeout/fail
# Source: .so binary analysis (cwipe returns -1)
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="erase_mf1_gen1a_fail"
source "${PROJECT}/tests/flows/erase/includes/erase_common.sh"
run_erase_scenario 0 3 "toast:Unknown error"
