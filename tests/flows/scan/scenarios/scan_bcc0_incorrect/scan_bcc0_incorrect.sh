#!/bin/bash
# Scan scenario: bcc0_incorrect
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="scan_bcc0_incorrect"
source "${PROJECT}/tests/flows/scan/includes/scan_common.sh"
run_scan_scenario 3
