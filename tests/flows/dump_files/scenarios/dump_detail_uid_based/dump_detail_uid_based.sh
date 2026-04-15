#!/bin/bash
# Dump Files scenario: dump_detail_uid_based
# Tag Info for UID-based HF tag (parseInfoByUIDInfoFileName, using MFU)
# Ground truth: docs/UI_Mapping/03_dump_files/README.md
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="dump_detail_uid_based"
source "${PROJECT}/tests/flows/dump_files/includes/dump_common.sh"
run_dump_scenario "detail" 3 "mfu" 1 "title:Tag Info"
