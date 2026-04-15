#!/bin/bash
# Read scenario: mf4k_gen1a_csave_fail
# Gen1a detected but csave fails → fall through to fchk+rdsc standard path
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="read_mf4k_gen1a_csave_fail"
source "${PROJECT}/tests/flows/read/includes/read_common.sh"
# csave fails → fchk finds all keys → rdsc 40 sectors — needs extended timeout
BOOT_TIMEOUT=600
TRIGGER_WAIT=360
run_read_scenario 3 "toast:Read Failed"
