#!/bin/bash
# LUA Script: empty scripts directory — verify "No scripts found" toast
# Validation: toast contains "No scripts"
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="lua_no_scripts"
BOOT_TIMEOUT=120
source "${PROJECT}/tests/flows/lua-script/includes/lua_common.sh"
run_lua_no_scripts_scenario
