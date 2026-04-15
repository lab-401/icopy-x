#!/bin/bash
# Erase T5577 DRM-locked tag — wipe with password 20206666 succeeds
# Trace source: trace_erase_flow_20260330.txt lines 707-713
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="erase_t5577_drm_success"
source "${PROJECT}/tests/flows/erase/includes/erase_common.sh"
run_erase_scenario 1 3 "toast:Erase successful" "t5577"
