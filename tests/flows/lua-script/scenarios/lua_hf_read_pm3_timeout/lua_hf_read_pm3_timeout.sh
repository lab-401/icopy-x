#!/bin/bash
# LUA Script: hf_read with PM3 connection failure — startPM3Task returns -1
# Source: real device trace session 1 (20260330) — first attempt, PM3 error
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="lua_hf_read_pm3_timeout"
BOOT_TIMEOUT=120
LUA_CONSOLE_WAIT=30
source "${PROJECT}/tests/flows/lua-script/includes/lua_common.sh"
# PM3 returns -1 with no output — console may not show anything visible
run_lua_scenario 2 "no" 3 0
