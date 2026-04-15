#!/bin/bash
# About — PWR from page 2 exits to main menu
# Ground truth: PWR from page 2 returns to MainMenu
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="about_pwr_exit_page2"
source "${PROJECT}/tests/flows/about/includes/about_common.sh"
run_about_scenario "PWR" 2 "title:About|content:1/2|KEY:DOWN|content:2/2"
