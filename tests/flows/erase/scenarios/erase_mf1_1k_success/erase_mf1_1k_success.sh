#!/bin/bash
# Erase MF1 1K standard card — all default keys, all blocks written
# Trace source: trace_erase_flow_20260330.txt lines 539-677
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="erase_mf1_1k_success"
BOOT_TIMEOUT=600
ERASE_TRIGGER_WAIT=400
source "${PROJECT}/tests/flows/erase/includes/erase_common.sh"
run_erase_scenario 0 3 "toast:Erase successful"
