#!/bin/bash
# About — PWR from page 1 exits to main menu
# Ground truth: PWR from About returns to MainMenu
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="about_pwr_exit_page1"
source "${PROJECT}/tests/flows/about/includes/about_common.sh"
run_about_scenario "PWR" 2 "title:About|content:1/2"
