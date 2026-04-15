#!/bin/bash
# Read scenario: mf1k_darkside_nested_fail (darkside → nested "not vulnerable" → Warning screen)
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="read_mf1k_darkside_nested_fail"
source "${PROJECT}/tests/flows/read/includes/read_common.sh"
run_read_scenario 3 "M1:Sniff"
