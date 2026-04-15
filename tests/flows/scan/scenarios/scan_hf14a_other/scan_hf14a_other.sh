#!/bin/bash
# Scan scenario: hf14a_other
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="scan_hf14a_other"
source "${PROJECT}/tests/flows/scan/includes/scan_common.sh"
run_scan_scenario 3
