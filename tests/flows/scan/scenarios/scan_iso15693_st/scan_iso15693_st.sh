#!/bin/bash
# Scan scenario: iso15693_st
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="scan_iso15693_st"
source "${PROJECT}/tests/flows/scan/includes/scan_common.sh"
run_scan_scenario 3
