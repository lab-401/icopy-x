#!/bin/bash
# Read scenario: mf1k_tag_lost
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="read_mf1k_tag_lost"
source "${PROJECT}/tests/flows/read/includes/read_common.sh"
run_read_scenario 3 "toast:Read Failed"
