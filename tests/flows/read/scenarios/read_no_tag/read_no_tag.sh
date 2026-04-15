#!/bin/bash
# Read scenario: no tag present — scan finds nothing
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="read_no_tag"
source "${PROJECT}/tests/flows/read/includes/read_common.sh"
run_read_scenario 3 "toast:Wrong type"
