#!/bin/bash
# Read scenario: mf1k_gen1a_csave_fail
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="read_mf1k_gen1a_csave_fail"
source "${PROJECT}/tests/flows/read/includes/read_common.sh"
BOOT_TIMEOUT=600
TRIGGER_WAIT=360
run_read_scenario 3 "toast:Read Failed"
