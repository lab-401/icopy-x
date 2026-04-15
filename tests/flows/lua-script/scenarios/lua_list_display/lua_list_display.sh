#!/bin/bash
# LUA Script: verify file list display — title, content, no visible buttons
# Validation: title contains "LUA Script", content has first script name, M1/M2 invisible
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="lua_list_display"
BOOT_TIMEOUT=120
source "${PROJECT}/tests/flows/lua-script/includes/lua_common.sh"
run_lua_list_display_scenario
