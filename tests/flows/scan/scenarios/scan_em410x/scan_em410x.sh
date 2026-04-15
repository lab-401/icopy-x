#!/bin/bash
# Scan scenario: em410x
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="scan_em410x"
source "${PROJECT}/tests/flows/scan/includes/scan_common.sh"
run_scan_scenario 3
