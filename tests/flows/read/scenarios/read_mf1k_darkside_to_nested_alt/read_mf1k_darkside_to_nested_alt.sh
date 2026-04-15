#!/bin/bash
# Read scenario: mf1k_darkside_to_nested_alt
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="read_mf1k_darkside_to_nested_alt"
TRIGGER_WAIT=90
source "${PROJECT}/tests/flows/read/includes/read_common.sh"
run_read_scenario 3 "toast:File saved"
