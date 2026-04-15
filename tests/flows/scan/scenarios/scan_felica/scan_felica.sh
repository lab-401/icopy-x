#!/bin/bash
# Scan scenario: felica
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="scan_felica"
source "${PROJECT}/tests/flows/scan/includes/scan_common.sh"
run_scan_scenario 3
