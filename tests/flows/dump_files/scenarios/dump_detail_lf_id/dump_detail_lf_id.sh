#!/bin/bash
# Dump Files scenario: dump_detail_lf_id
# Tag Info for LF ID card (parseInfoByIDFileName, using EM410x)
# Ground truth: docs/UI_Mapping/03_dump_files/README.md
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="dump_detail_lf_id"
source "${PROJECT}/tests/flows/dump_files/includes/dump_common.sh"
run_dump_scenario "detail" 4 "em410x" 19 "content:EM410x"
