#!/bin/bash
# Erase T5577 — wipe succeeds but detect fails, all strategies exhausted
# Trace source: trace_erase_flow_20260330.txt lines 714-722
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="erase_t5577_fail"
ERASE_TRIGGER_WAIT=180
source "${PROJECT}/tests/flows/erase/includes/erase_common.sh"
run_erase_scenario 1 3 "toast:Erase failed" "t5577"
