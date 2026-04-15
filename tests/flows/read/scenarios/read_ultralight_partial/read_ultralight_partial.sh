#!/bin/bash
# Read scenario: ultralight_partial
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="read_ultralight_partial"
source "${PROJECT}/tests/flows/read/includes/read_common.sh"
run_read_scenario 3 "toast:Read Failed"
