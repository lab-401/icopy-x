#!/bin/bash
# Erase MF1 1K — keys found but wrbl fails (access bits deny writes)
# Trace source: trace_erase_flow_20260330.txt lines 688-706
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="erase_mf1_wrbl_fail"
BOOT_TIMEOUT=600
ERASE_TRIGGER_WAIT=400
source "${PROJECT}/tests/flows/erase/includes/erase_common.sh"
run_erase_scenario 0 3 "toast:Unknown error"
