#!/bin/bash
# Scan scenario: mf_classic_4k_7b
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="scan_mf_classic_4k_7b"
source "${PROJECT}/tests/flows/scan/includes/scan_common.sh"
run_scan_scenario 3
