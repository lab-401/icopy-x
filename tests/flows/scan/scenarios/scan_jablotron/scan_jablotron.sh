#!/bin/bash
# Scan scenario: jablotron
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="scan_jablotron"
source "${PROJECT}/tests/flows/scan/includes/scan_common.sh"
run_scan_scenario 3
