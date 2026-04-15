#!/bin/bash
# Read scenario: mf1k_hardnested_fail
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="read_mf1k_hardnested_fail"
source "${PROJECT}/tests/flows/read/includes/read_common.sh"
# No keys → darkside(key) → nested(not vulnerable) → Missing keys warning
BOOT_TIMEOUT=600
TRIGGER_WAIT=360
run_read_scenario 3 "M1:Sniff"
