#!/bin/bash
# Read scenario: read_iso15693_st
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="read_iso15693_st"
source "${PROJECT}/tests/flows/read/includes/read_common.sh"
run_read_scenario 3 "toast:File saved"
