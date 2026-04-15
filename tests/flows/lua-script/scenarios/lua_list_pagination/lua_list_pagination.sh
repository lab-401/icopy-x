#!/bin/bash
# LUA Script: pagination — RIGHT/LEFT pages, verify title updates "X/Y"
# Validation: title changes from "1/" → "2/" → "3/" → back to "2/"
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="lua_list_pagination"
BOOT_TIMEOUT=120
source "${PROJECT}/tests/flows/lua-script/includes/lua_common.sh"
run_lua_pagination_scenario
