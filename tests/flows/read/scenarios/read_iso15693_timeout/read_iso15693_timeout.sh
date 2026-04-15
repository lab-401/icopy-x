#!/bin/bash
# Read scenario: iso15693_timeout
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="read_iso15693_timeout"
source "${PROJECT}/tests/flows/read/includes/read_common.sh"
run_read_scenario 3 "toast:Read Failed"
