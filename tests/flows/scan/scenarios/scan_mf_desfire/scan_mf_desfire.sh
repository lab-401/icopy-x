#!/bin/bash
# Scan scenario: mf_desfire
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="scan_mf_desfire"
source "${PROJECT}/tests/flows/scan/includes/scan_common.sh"
run_scan_scenario 3
