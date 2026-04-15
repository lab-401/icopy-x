#!/bin/bash
# Read scenario: mf1k_nested_timeout
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="read_mf1k_nested_timeout"
source "${PROJECT}/tests/flows/read/includes/read_common.sh"
BOOT_TIMEOUT=600
TRIGGER_WAIT=360
run_read_scenario 3 "toast:Read Failed"
