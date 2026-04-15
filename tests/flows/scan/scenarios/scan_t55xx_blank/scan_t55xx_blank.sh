#!/bin/bash
# Scan scenario: t55xx_blank
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="scan_t55xx_blank"
source "${PROJECT}/tests/flows/scan/includes/scan_common.sh"
run_scan_scenario 3
