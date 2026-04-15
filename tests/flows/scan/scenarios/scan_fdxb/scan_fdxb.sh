#!/bin/bash
# Scan scenario: fdxb
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="scan_fdxb"
source "${PROJECT}/tests/flows/scan/includes/scan_common.sh"
run_scan_scenario 3
