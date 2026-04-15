#!/bin/bash
# About — DOWN from page 1 navigates to page 2
# Ground truth: QEMU frame 5→6 shows 1/2→2/2 after DOWN
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="about_page_nav_down"
source "${PROJECT}/tests/flows/about/includes/about_common.sh"
run_about_scenario "" 2 "content:1/2|KEY:DOWN|content:2/2"
