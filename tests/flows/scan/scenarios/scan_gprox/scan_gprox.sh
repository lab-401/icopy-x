#!/bin/bash
# Scan scenario: gprox
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="scan_gprox"
source "${PROJECT}/tests/flows/scan/includes/scan_common.sh"
run_scan_scenario 3
