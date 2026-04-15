#!/bin/bash
# LUA Script: verify console has no title bar
# Validation: console state dump does not show LUA Script title
# Source: lua_console_*.png — NO title bar, full-screen console
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="lua_console_no_title"
BOOT_TIMEOUT=120
LUA_CONSOLE_WAIT=60
source "${PROJECT}/tests/flows/lua-script/includes/lua_common.sh"
run_lua_console_no_title_scenario
