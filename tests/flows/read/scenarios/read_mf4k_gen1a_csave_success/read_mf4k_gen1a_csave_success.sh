#!/bin/bash
# Read scenario: mf4k_gen1a_csave_success
# Real device trace 2026-03-28: Gen1b 4K magic card, csave dumps 256 blocks
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="read_mf4k_gen1a_csave_success"
source "${PROJECT}/tests/flows/read/includes/read_common.sh"
BOOT_TIMEOUT=600
TRIGGER_WAIT=360
run_read_scenario 3 "toast:File saved"
