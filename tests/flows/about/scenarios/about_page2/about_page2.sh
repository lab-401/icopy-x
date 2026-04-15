#!/bin/bash
# About — verify Page 2 displays firmware update instructions with indicator 2/2
# Ground truth: QEMU frame 6 shows content:Firmware update, content:2/2 after DOWN
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="about_page2"
source "${PROJECT}/tests/flows/about/includes/about_common.sh"
run_about_scenario "" 2 "title:About|content:1/2|KEY:DOWN|content:2/2|content:Firmware update"
