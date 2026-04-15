#!/bin/bash
# Erase T5577 plain tag — wipe without password succeeds
# Source: .so binary analysis
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="erase_t5577_no_password_success"
source "${PROJECT}/tests/flows/erase/includes/erase_common.sh"
run_erase_scenario 1 3 "toast:Erase successful" "t5577"
