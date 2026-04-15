#!/bin/bash
# LUA Script: hf_read with MF Classic 1K card — script detects card successfully
# Source: real device trace session 2 (20260330)
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="lua_hf_read_mf1k"
BOOT_TIMEOUT=120
LUA_CONSOLE_WAIT=60
source "${PROJECT}/tests/flows/lua-script/includes/lua_common.sh"
run_lua_scenario 3 "yes" 3 0
