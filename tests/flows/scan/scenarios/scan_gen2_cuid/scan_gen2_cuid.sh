#!/bin/bash
# Scan scenario: gen2_cuid
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="scan_gen2_cuid"
source "${PROJECT}/tests/flows/scan/includes/scan_common.sh"
run_scan_scenario 3
