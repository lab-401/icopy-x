#!/bin/bash
# Read scenario: Force Read after darkside+nested both fail
# Warning screen appears → DOWN → M1 (Force) → reads with partial keys → Partial data
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="read_mf1k_force_from_darkside_fail"
source "${PROJECT}/tests/flows/read/includes/read_common.sh"
TRIGGER_WAIT=300
run_read_force_scenario 3 "toast:Partial data"
