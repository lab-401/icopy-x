#!/bin/bash
# Write scenario: write_mf_plus_2k_success
# MIFARE Plus 2K (SAK 08, SL1 mode) — scan_cache.type is 1 (M1_S50_1K_4B).
# Real device trace: Plus 2K in SL1 mode reports "MIFARE Classic 1K / Classic 1K CL2"
# so scan.so classifies it as type 1. TAG_TYPE=26 is for ReadListActivity navigation only.
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="write_mf_plus_2k_success"
BOOT_TIMEOUT=600
READ_TRIGGER_WAIT=200
WRITE_TRIGGER_WAIT=300
VERIFY_TRIGGER_WAIT=120
source "${PROJECT}/tests/flows/write/includes/write_common.sh"
run_write_scenario 5 "toast:Verification successful" "" "toast:Write successful!"
RC=$?

# Post-run validation: scan_cache type must be 1 (M1_S50_1K_4B).
# Real device trace: Plus 2K in SL1 mode has "MIFARE Classic 1K" in hf 14a info,
# so scan.so returns type=1 (same as Classic 1K). TAG_TYPE=26 is navigation only.
if [ "$RC" -eq 0 ]; then
    STATES_JSON="${SCENARIO_DIR}/scenario_states.json"
    if [ -f "$STATES_JSON" ]; then
        python3 -c "
import json, sys
with open('${STATES_JSON}') as f: data = json.load(f)
for s in data.get('states', []):
    sc = s.get('scan_cache')
    if sc and sc.get('type'):
        t = str(sc['type'])
        if t in ('1', '43'):
            sys.exit(0)  # scan.so returns 43 (MF_POSSIBLE) for bare "MIFARE Classic" or 1 for "MIFARE Classic 1K"
        elif t == '25':
            print('FAIL: scan_cache type=25 (Mini) — expected type=43 or 1 (Plus 2K SL1)')
            sys.exit(1)
        else:
            print('FAIL: scan_cache type=%s — expected type=43 or 1 (Plus 2K SL1)' % t)
            sys.exit(1)
print('FAIL: no scan_cache type found in states')
sys.exit(1)
" 2>/dev/null
        if [ $? -ne 0 ]; then
            # Overwrite result.txt with the failure
            echo "FAIL: scan_cache type validation failed (expected type=43 or 1, Plus 2K SL1)" > "${SCENARIO_DIR}/result.txt"
            exit 1
        fi
    fi
fi

exit $RC
