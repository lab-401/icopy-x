#!/bin/bash
# LUA Script: PWR cancel during execution — task cancelled, returns to list
# Source: real device trace session 1 (20260330) — PM3-CTRL> stop, ret=-1
# Uses PM3_DELAY=10 to keep task running long enough for PWR cancel
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="lua_run_pwr_cancel"
BOOT_TIMEOUT=120
PM3_DELAY=10
source "${PROJECT}/tests/flows/lua-script/includes/lua_common.sh"
run_lua_pwr_cancel_scenario
