#!/bin/bash
# Scan scenario: ioprx
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="scan_ioprx"
source "${PROJECT}/tests/flows/scan/includes/scan_common.sh"
run_scan_scenario 3
