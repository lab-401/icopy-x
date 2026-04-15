#!/bin/bash
# Dump Files scenario: dump_detail_t55xx
# Tag Info for T5577 (parseInfoByT55xxInfoFileName, regex R2 6-group)
# Seed: T55xx_000880E8_00000000_00000000_1.bin — 4-field format exercises regex R2
# Ground truth: regex (\S+)_(\S+)_(\S+)_(\S+)_(\d+).*\.(.*) (L21404),
#               T55xx/Unknown (L21676), real files in /tmp/device_dumps/dump/t55xx/
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="dump_detail_t55xx"
source "${PROJECT}/tests/flows/dump_files/includes/dump_common.sh"
run_dump_scenario "detail" 3 "t55xx" 17 "title:Tag Info"
