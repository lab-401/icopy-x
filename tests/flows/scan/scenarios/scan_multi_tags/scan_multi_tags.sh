#!/bin/bash
# Scan scenario: multi_tags
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="scan_multi_tags"
source "${PROJECT}/tests/flows/scan/includes/scan_common.sh"
run_scan_scenario 3
