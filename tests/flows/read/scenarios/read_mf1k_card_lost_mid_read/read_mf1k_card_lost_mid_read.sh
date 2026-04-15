#!/bin/bash
# Read scenario: mf1k_card_lost_mid_read
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="read_mf1k_card_lost_mid_read"
source "${PROJECT}/tests/flows/read/includes/read_common.sh"
run_read_scenario 3 "toast:Read Failed"
