#!/bin/bash
# LUA Script: scroll — UP/DOWN within page, verify selection highlight changes
# Validation: screen visually changes after DOWN key
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="lua_list_scroll"
BOOT_TIMEOUT=120
source "${PROJECT}/tests/flows/lua-script/includes/lua_common.sh"
run_lua_scroll_scenario
