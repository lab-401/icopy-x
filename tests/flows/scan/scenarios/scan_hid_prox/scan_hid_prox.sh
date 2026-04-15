#!/bin/bash
# Scan scenario: hid_prox
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="scan_hid_prox"
source "${PROJECT}/tests/flows/scan/includes/scan_common.sh"
run_scan_scenario 3
