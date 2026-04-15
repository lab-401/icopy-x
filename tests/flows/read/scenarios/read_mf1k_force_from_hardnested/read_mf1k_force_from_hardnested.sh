#!/bin/bash
# Read scenario: Force Read after hardnested path (nested not vulnerable)
# Warning screen appears → DOWN → M1 (Force) → reads with partial keys → Partial data
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="read_mf1k_force_from_hardnested"
source "${PROJECT}/tests/flows/read/includes/read_common.sh"
TRIGGER_WAIT=300
run_read_force_scenario 3 "toast:Partial data"
