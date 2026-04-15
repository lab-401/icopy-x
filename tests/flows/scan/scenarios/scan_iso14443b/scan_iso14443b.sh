#!/bin/bash
# Scan scenario: iso14443b
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="scan_iso14443b"
source "${PROJECT}/tests/flows/scan/includes/scan_common.sh"
run_scan_scenario 3
