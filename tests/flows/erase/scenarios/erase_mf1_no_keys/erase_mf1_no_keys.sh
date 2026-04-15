#!/bin/bash
# Erase MF1 — fchk finds 0 keys (NTAG/non-MFC card)
# Trace source: trace_erase_flow_20260330.txt lines 678-687
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="erase_mf1_no_keys"
source "${PROJECT}/tests/flows/erase/includes/erase_common.sh"
run_erase_scenario 0 3 "toast:No valid keys" "no_keys"
