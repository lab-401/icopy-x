#!/bin/bash
# Scan scenario: presco
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="scan_presco"
source "${PROJECT}/tests/flows/scan/includes/scan_common.sh"
run_scan_scenario 3
