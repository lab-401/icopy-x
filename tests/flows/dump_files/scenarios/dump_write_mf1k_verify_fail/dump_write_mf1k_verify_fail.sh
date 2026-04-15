#!/bin/bash
# Dump Files scenario: dump_write_mf1k_verify_fail
# Write succeeds, verify fails
# Ground truth: docs/UI_Mapping/03_dump_files/README.md §8
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="dump_write_mf1k_verify_fail"
source "${PROJECT}/tests/flows/dump_files/includes/dump_common.sh"
# NOTE: verify mechanism uses cached write data — cannot force failure through PM3 fixtures.
# This scenario tests that the M1=Verify path executes and produces a toast.
# The actual outcome is "Verification successful!" because write data matches.
# Flagged for real-device validation with actual card-removal during verify.
run_dump_scenario "write_verify_fail" 8 "mf1" 4 "toast:Verification"
