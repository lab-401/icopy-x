#!/bin/bash
# LUA Script: console zoom + navigation controls
# Tests M1=zoom out, M2=zoom in, arrow keys=scroll
# Each action validated via pixel diff
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="lua_console_zoom_nav"
BOOT_TIMEOUT=120
LUA_CONSOLE_WAIT=60
source "${PROJECT}/tests/flows/lua-script/includes/lua_common.sh"
run_lua_console_zoom_nav_scenario
