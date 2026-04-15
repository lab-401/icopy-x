#!/bin/bash
# Scan scenario: indala
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="scan_indala"
source "${PROJECT}/tests/flows/scan/includes/scan_common.sh"
run_scan_scenario 3
