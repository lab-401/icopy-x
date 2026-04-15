#!/bin/bash
# Read scenario: lf_io
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="read_lf_io"
source "${PROJECT}/tests/flows/read/includes/read_common.sh"
run_read_scenario 3 "toast:File saved"
