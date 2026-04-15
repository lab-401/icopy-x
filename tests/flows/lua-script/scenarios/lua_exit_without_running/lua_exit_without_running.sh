#!/bin/bash
# LUA Script: enter file list, press PWR to exit without running any script
# Flow: GOTO:13 → capture LUA Script list → PWR → back to main menu
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="lua_exit_without_running"
BOOT_TIMEOUT=120
source "${PROJECT}/tests/flows/lua-script/includes/lua_common.sh"
run_lua_exit_scenario 1
