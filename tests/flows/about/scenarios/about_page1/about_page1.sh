#!/bin/bash
# About — verify Page 1 displays version info with page indicator 1/2
# Ground truth: QEMU frames 2-5 show content:iCopy-XS, content:HW, content:SN, content:1/2
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="about_page1"
source "${PROJECT}/tests/flows/about/includes/about_common.sh"
run_about_scenario "" 2 "title:About|content:1/2|content:iCopy-XS|content:SN"
