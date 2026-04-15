#!/bin/bash
# Read scenario: mf1k_all_default_keys
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="read_mf1k_all_default_keys"
source "${PROJECT}/tests/flows/read/includes/read_common.sh"
# Happy path: OK → scan → read → M1="Reread", M2="Write"
run_read_scenario 3 "toast:File saved"
