#!/usr/bin/env python3

##########################################################################
# Required Notice: Copyright ETOILE401 SAS (http://www.lab401.com)
#
# Copyright (c) 2026: ETOILE401 SAS & https://github.com/quantum-x/
#
# This software is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this software for commercial purposes.
#
# A copy of the license is available at:
# https://polyformproject.org/licenses/noncommercial/1.0.0
#
# This entire header "Required Notice" must remain in place.
##########################################################################

"""Generate write flow test fixtures and scenario scripts.

Each write scenario = read happy-path fixture + write-specific PM3 responses.
This script merges them and writes:
  - tests/flows/write/scenarios/<name>/fixture.py
  - tests/flows/write/scenarios/<name>/write_<name>.sh

Usage:
    python3 tools/generate_write_fixtures.py
"""

import os
import sys
import stat

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT, 'tools'))

from pm3_fixtures import ALL_WRITE_SCENARIOS

# ---------------------------------------------------------------------------
# Scenario Map: every write scenario with its inputs
# ---------------------------------------------------------------------------
# Keys:
#   read_fixture: path to the read happy-path fixture.py (relative to PROJECT)
#   write_keys:   list of keys from ALL_WRITE_SCENARIOS to overlay
#   tag_type:     TAG_TYPE for fixture.py
#   default_ret:  DEFAULT_RETURN (1=continue, -1=timeout)
#   min_unique:   minimum unique states for PASS
#   final_trigger: expected end-state trigger string
#   skip_verify:  "no_verify" to skip verify phase
#   timing:       dict of timing overrides {BOOT_TIMEOUT, READ_TRIGGER_WAIT, ...}

SCENARIO_MAP = {
    # =======================================================================
    # 4.1 MIFARE Classic — hfmfwrite.so
    # =======================================================================
    'write_mf1k_standard_success': {
        'read_fixture': 'tests/flows/read/scenarios/read_mf1k_all_default_keys/fixture.py',
        'write_keys': ['standard_success'],
        'tag_type': 1, 'default_ret': 1,
        'min_unique': 5, 'final_trigger': 'toast:Verification successful',
    },
    'write_mf1k_standard_fail': {
        'read_fixture': 'tests/flows/read/scenarios/read_mf1k_all_default_keys/fixture.py',
        'write_keys': ['standard_fail'],
        'tag_type': 1, 'default_ret': 1,
        'min_unique': 4, 'final_trigger': 'toast:Write failed', 'skip_verify': 'no_verify',
    },
    'write_mf1k_standard_partial': {
        'read_fixture': 'tests/flows/read/scenarios/read_mf1k_all_default_keys/fixture.py',
        'write_keys': ['standard_partial'],
        'tag_type': 1, 'default_ret': 1,
        'min_unique': 4, 'final_trigger': 'toast:Write failed', 'skip_verify': 'no_verify',
    },
    'write_mf1k_standard_verify_fail': {
        'read_fixture': 'tests/flows/read/scenarios/read_mf1k_all_default_keys/fixture.py',
        'write_keys': ['verify_fail'],
        'tag_type': 1, 'default_ret': 1,
        'min_unique': 5, 'final_trigger': 'toast:Verification failed',
    },
    'write_mf1k_gen1a_success': {
        'read_fixture': 'tests/flows/read/scenarios/read_mf1k_gen1a_csave_success/fixture.py',
        'write_keys': ['gen1a_cload'],
        'tag_type': 1, 'default_ret': 1,
        'min_unique': 5, 'final_trigger': 'toast:Verification successful',
        'timing': {'BOOT_TIMEOUT': 200, 'READ_TRIGGER_WAIT': 60, 'WRITE_TRIGGER_WAIT': 60},
    },
    'write_mf1k_gen1a_fail': {
        'read_fixture': 'tests/flows/read/scenarios/read_mf1k_gen1a_csave_success/fixture.py',
        'write_keys': ['gen1a_cload_fail'],
        'tag_type': 1, 'default_ret': 1,
        'min_unique': 4, 'final_trigger': 'toast:Write failed', 'skip_verify': 'no_verify',
        'timing': {'BOOT_TIMEOUT': 200, 'READ_TRIGGER_WAIT': 60, 'WRITE_TRIGGER_WAIT': 60},
    },
    'write_mf1k_gen1a_uid_only': {
        'read_fixture': 'tests/flows/read/scenarios/read_mf1k_gen1a_csave_success/fixture.py',
        'write_keys': ['gen1a_uid'],
        'tag_type': 1, 'default_ret': 1,
        'min_unique': 5, 'final_trigger': 'toast:Verification successful',
        'timing': {'BOOT_TIMEOUT': 200, 'READ_TRIGGER_WAIT': 60, 'WRITE_TRIGGER_WAIT': 60},
    },
    'write_mf4k_standard_success': {
        'read_fixture': 'tests/flows/read/scenarios/read_mf4k_all_keys/fixture.py',
        'write_keys': ['standard_success'],
        'tag_type': 0, 'default_ret': 1,
        'min_unique': 5, 'final_trigger': 'toast:Verification successful',
        'timing': {'BOOT_TIMEOUT': 900, 'READ_TRIGGER_WAIT': 200, 'WRITE_TRIGGER_WAIT': 640},
    },
    'write_mf4k_standard_fail': {
        'read_fixture': 'tests/flows/read/scenarios/read_mf4k_all_keys/fixture.py',
        'write_keys': ['standard_fail'],
        'tag_type': 0, 'default_ret': 1,
        'min_unique': 4, 'final_trigger': 'toast:Write failed', 'skip_verify': 'no_verify',
        'timing': {'BOOT_TIMEOUT': 900, 'READ_TRIGGER_WAIT': 200, 'WRITE_TRIGGER_WAIT': 640},
    },
    'write_mf4k_gen1a_success': {
        'read_fixture': 'tests/flows/read/scenarios/read_mf4k_gen1a_csave_success/fixture.py',
        'write_keys': ['gen1a_cload'],
        'tag_type': 0, 'default_ret': 1,
        'min_unique': 5, 'final_trigger': 'toast:Verification successful',
        'timing': {'BOOT_TIMEOUT': 200, 'READ_TRIGGER_WAIT': 60, 'WRITE_TRIGGER_WAIT': 60},
    },
    'write_mf1k_7b_standard_success': {
        'read_fixture': 'tests/flows/read/scenarios/read_mf1k_7b_all_keys/fixture.py',
        'write_keys': ['standard_success'],
        'tag_type': 42, 'default_ret': 1,
        'min_unique': 5, 'final_trigger': 'toast:Verification successful',
    },
    'write_mf4k_7b_standard_success': {
        'read_fixture': 'tests/flows/read/scenarios/read_mf4k_7b_all_keys/fixture.py',
        'write_keys': ['standard_success'],
        'tag_type': 41, 'default_ret': 1,
        'min_unique': 5, 'final_trigger': 'toast:Verification successful',
        'timing': {'BOOT_TIMEOUT': 900, 'READ_TRIGGER_WAIT': 200, 'WRITE_TRIGGER_WAIT': 640},
    },
    'write_mf_mini_success': {
        'read_fixture': 'tests/flows/read/scenarios/read_mf_mini_all_keys/fixture.py',
        'write_keys': ['standard_success'],
        'tag_type': 25, 'default_ret': 1,
        'min_unique': 5, 'final_trigger': 'toast:Verification successful',
    },
    'write_mf_possible_4b_success': {
        'read_fixture': 'tests/flows/read/scenarios/read_mf_plus_2k_all_keys/fixture.py',
        'write_keys': ['standard_success'],
        'tag_type': 43, 'default_ret': 1,
        'min_unique': 5, 'final_trigger': 'toast:Verification successful',
    },

    # =======================================================================
    # 4.2 Ultralight/NTAG — hfmfuwrite.so
    # =======================================================================
    'write_ultralight_success': {
        'read_fixture': 'tests/flows/read/scenarios/read_ultralight_success/fixture.py',
        'write_keys': ['ultralight_success'],
        'tag_type': 2, 'default_ret': 1,
        'min_unique': 5, 'final_trigger': 'toast:Verification successful',
        'timing': {'BOOT_TIMEOUT': 120, 'READ_TRIGGER_WAIT': 60, 'WRITE_TRIGGER_WAIT': 90, 'VERIFY_TRIGGER_WAIT': 60},
    },
    'write_ultralight_fail': {
        'read_fixture': 'tests/flows/read/scenarios/read_ultralight_success/fixture.py',
        'write_keys': ['ultralight_fail'],
        'tag_type': 2, 'default_ret': 1,
        'min_unique': 4, 'final_trigger': 'toast:Write failed', 'skip_verify': 'no_verify',
        'timing': {'BOOT_TIMEOUT': 120, 'READ_TRIGGER_WAIT': 60, 'WRITE_TRIGGER_WAIT': 30},
    },
    'write_ultralight_cant_select': {
        'read_fixture': 'tests/flows/read/scenarios/read_ultralight_success/fixture.py',
        'write_keys': ['ultralight_cant_select'],
        'tag_type': 2, 'default_ret': 1,
        'min_unique': 4, 'final_trigger': 'toast:Write failed', 'skip_verify': 'no_verify',
        'timing': {'BOOT_TIMEOUT': 120, 'READ_TRIGGER_WAIT': 60, 'WRITE_TRIGGER_WAIT': 30},
    },
    'write_ultralight_verify_fail': {
        'read_fixture': 'tests/flows/read/scenarios/read_ultralight_success/fixture.py',
        'write_keys': ['ultralight_success'],  # write succeeds, but verify sees mismatch
        'tag_type': 2, 'default_ret': 1,
        'min_unique': 5, 'final_trigger': 'toast:Verification failed',
        'timing': {'BOOT_TIMEOUT': 120, 'READ_TRIGGER_WAIT': 60, 'WRITE_TRIGGER_WAIT': 90, 'VERIFY_TRIGGER_WAIT': 60},
    },
    'write_ultralight_c_success': {
        'read_fixture': 'tests/flows/read/scenarios/read_ultralight_c_success/fixture.py',
        'write_keys': ['ultralight_success'],
        'tag_type': 3, 'default_ret': 1,
        'min_unique': 5, 'final_trigger': 'toast:Verification successful',
        'timing': {'BOOT_TIMEOUT': 120, 'READ_TRIGGER_WAIT': 60, 'WRITE_TRIGGER_WAIT': 90, 'VERIFY_TRIGGER_WAIT': 60},
    },
    'write_ultralight_ev1_success': {
        'read_fixture': 'tests/flows/read/scenarios/read_ultralight_ev1_success/fixture.py',
        'write_keys': ['ultralight_success'],
        'tag_type': 4, 'default_ret': 1,
        'min_unique': 5, 'final_trigger': 'toast:Verification successful',
        'timing': {'BOOT_TIMEOUT': 120, 'READ_TRIGGER_WAIT': 60, 'WRITE_TRIGGER_WAIT': 90, 'VERIFY_TRIGGER_WAIT': 60},
    },
    'write_ntag213_success': {
        'read_fixture': 'tests/flows/read/scenarios/read_ntag213_success/fixture.py',
        'write_keys': ['ultralight_success'],
        'tag_type': 5, 'default_ret': 1,
        'min_unique': 5, 'final_trigger': 'toast:Verification successful',
        'timing': {'BOOT_TIMEOUT': 120, 'READ_TRIGGER_WAIT': 60, 'WRITE_TRIGGER_WAIT': 90, 'VERIFY_TRIGGER_WAIT': 60},
    },
    'write_ntag215_success': {
        'read_fixture': 'tests/flows/read/scenarios/read_ntag215_success/fixture.py',
        'write_keys': ['ultralight_success'],
        'tag_type': 6, 'default_ret': 1,
        'min_unique': 5, 'final_trigger': 'toast:Verification successful',
        'timing': {'BOOT_TIMEOUT': 120, 'READ_TRIGGER_WAIT': 60, 'WRITE_TRIGGER_WAIT': 90, 'VERIFY_TRIGGER_WAIT': 60},
    },
    'write_ntag216_success': {
        'read_fixture': 'tests/flows/read/scenarios/read_ntag216_success/fixture.py',
        'write_keys': ['ultralight_success'],
        'tag_type': 7, 'default_ret': 1,
        'min_unique': 5, 'final_trigger': 'toast:Verification successful',
        'timing': {'BOOT_TIMEOUT': 120, 'READ_TRIGGER_WAIT': 60, 'WRITE_TRIGGER_WAIT': 90, 'VERIFY_TRIGGER_WAIT': 60},
    },

    # =======================================================================
    # 4.3 iCLASS — iclasswrite.so
    # =======================================================================
    'write_iclass_legacy_success': {
        'read_fixture': 'tests/flows/read/scenarios/read_iclass_legacy/fixture.py',
        'write_keys': ['iclass_success'],
        'tag_type': 17, 'default_ret': 1,
        'min_unique': 5, 'final_trigger': 'toast:Verification successful',
        'timing': {'BOOT_TIMEOUT': 150, 'READ_TRIGGER_WAIT': 80, 'WRITE_TRIGGER_WAIT': 40, 'VERIFY_TRIGGER_WAIT': 30},
    },
    'write_iclass_legacy_fail': {
        'read_fixture': 'tests/flows/read/scenarios/read_iclass_legacy/fixture.py',
        'write_keys': ['iclass_fail'],
        'tag_type': 17, 'default_ret': 1,
        'min_unique': 4, 'final_trigger': 'toast:Write failed', 'skip_verify': 'no_verify',
        'timing': {'BOOT_TIMEOUT': 150, 'READ_TRIGGER_WAIT': 80, 'WRITE_TRIGGER_WAIT': 40},
    },
    'write_iclass_tag_select_fail': {
        'read_fixture': 'tests/flows/read/scenarios/read_iclass_legacy/fixture.py',
        'write_keys': ['iclass_tag_select_fail'],
        'tag_type': 17, 'default_ret': 1,
        'min_unique': 4, 'final_trigger': 'toast:Write failed', 'skip_verify': 'no_verify',
        'timing': {'BOOT_TIMEOUT': 150, 'READ_TRIGGER_WAIT': 80, 'WRITE_TRIGGER_WAIT': 40},
    },
    'write_iclass_key_calc_success': {
        'read_fixture': 'tests/flows/read/scenarios/read_iclass_legacy/fixture.py',
        'write_keys': ['iclass_key_calc'],
        'tag_type': 17, 'default_ret': 1,
        'min_unique': 5, 'final_trigger': 'toast:Verification successful',
        'timing': {'BOOT_TIMEOUT': 150, 'READ_TRIGGER_WAIT': 80, 'WRITE_TRIGGER_WAIT': 40, 'VERIFY_TRIGGER_WAIT': 30},
    },
    'write_iclass_key_calc_fail': {
        'read_fixture': 'tests/flows/read/scenarios/read_iclass_legacy/fixture.py',
        'write_keys': ['iclass_key_calc_fail'],
        'tag_type': 17, 'default_ret': 1,
        'min_unique': 4, 'final_trigger': 'toast:Write failed', 'skip_verify': 'no_verify',
        'timing': {'BOOT_TIMEOUT': 150, 'READ_TRIGGER_WAIT': 80, 'WRITE_TRIGGER_WAIT': 40},
    },
    'write_iclass_elite_success': {
        'read_fixture': 'tests/flows/read/scenarios/read_iclass_elite/fixture.py',
        'write_keys': ['iclass_success'],
        'tag_type': 18, 'default_ret': 1,
        'min_unique': 5, 'final_trigger': 'toast:Verification successful',
        'timing': {'BOOT_TIMEOUT': 150, 'READ_TRIGGER_WAIT': 80, 'WRITE_TRIGGER_WAIT': 40, 'VERIFY_TRIGGER_WAIT': 30},
    },

    # =======================================================================
    # 4.4 ISO15693 — hf15write.so
    # =======================================================================
    'write_iso15693_success': {
        'read_fixture': 'tests/flows/read/scenarios/read_iso15693/fixture.py',
        'write_keys': ['iso15693_success'],
        'tag_type': 19, 'default_ret': 1,
        'min_unique': 5, 'final_trigger': 'toast:Verification successful',
        'timing': {'BOOT_TIMEOUT': 120, 'READ_TRIGGER_WAIT': 60, 'WRITE_TRIGGER_WAIT': 90, 'VERIFY_TRIGGER_WAIT': 60},
    },
    'write_iso15693_restore_fail': {
        'read_fixture': 'tests/flows/read/scenarios/read_iso15693/fixture.py',
        'write_keys': ['iso15693_fail'],
        'tag_type': 19, 'default_ret': 1,
        'min_unique': 4, 'final_trigger': 'toast:Write failed', 'skip_verify': 'no_verify',
        'timing': {'BOOT_TIMEOUT': 120, 'READ_TRIGGER_WAIT': 60, 'WRITE_TRIGGER_WAIT': 30},
    },
    'write_iso15693_uid_fail': {
        'read_fixture': 'tests/flows/read/scenarios/read_iso15693/fixture.py',
        'write_keys': ['iso15693_uid_fail'],
        'tag_type': 19, 'default_ret': 1,
        'min_unique': 4, 'final_trigger': 'toast:Write failed', 'skip_verify': 'no_verify',
        'timing': {'BOOT_TIMEOUT': 120, 'READ_TRIGGER_WAIT': 60, 'WRITE_TRIGGER_WAIT': 30},
    },
    'write_iso15693_verify_fail': {
        'read_fixture': 'tests/flows/read/scenarios/read_iso15693/fixture.py',
        'write_keys': ['iso15693_success'],
        'tag_type': 19, 'default_ret': 1,
        'min_unique': 5, 'final_trigger': 'toast:Verification failed',
        'timing': {'BOOT_TIMEOUT': 120, 'READ_TRIGGER_WAIT': 60, 'WRITE_TRIGGER_WAIT': 90, 'VERIFY_TRIGGER_WAIT': 60},
    },

    # =======================================================================
    # 4.5 LF Types — lfwrite.so
    # =======================================================================
    # Special handlers
    'write_lf_em410x_success': {
        'read_fixture': 'tests/flows/read/scenarios/read_lf_em410x/fixture.py',
        'write_keys': ['lf_em410x'],
        'tag_type': 8, 'default_ret': 1,
        'min_unique': 5, 'final_trigger': 'toast:Verification successful',
        'timing': {'BOOT_TIMEOUT': 150, 'READ_TRIGGER_WAIT': 60, 'WRITE_TRIGGER_WAIT': 90, 'VERIFY_TRIGGER_WAIT': 60},
    },
    'write_lf_hid_success': {
        'read_fixture': 'tests/flows/read/scenarios/read_lf_hid/fixture.py',
        'write_keys': ['lf_hid_clone'],
        'tag_type': 9, 'default_ret': 1,
        'min_unique': 5, 'final_trigger': 'toast:Verification successful',
        'timing': {'BOOT_TIMEOUT': 150, 'READ_TRIGGER_WAIT': 60, 'WRITE_TRIGGER_WAIT': 90, 'VERIFY_TRIGGER_WAIT': 60},
    },
    'write_lf_indala_success': {
        'read_fixture': 'tests/flows/read/scenarios/read_lf_indala/fixture.py',
        'write_keys': ['lf_indala'],
        'tag_type': 10, 'default_ret': 1,
        'min_unique': 5, 'final_trigger': 'toast:Verification successful',
        'timing': {'BOOT_TIMEOUT': 150, 'READ_TRIGGER_WAIT': 60, 'WRITE_TRIGGER_WAIT': 90, 'VERIFY_TRIGGER_WAIT': 60},
    },
    # B0_WRITE types
    'write_lf_awid_success': {
        'read_fixture': 'tests/flows/read/scenarios/read_lf_awid/fixture.py',
        'write_keys': ['lf_awid'],
        'tag_type': 11, 'default_ret': 1,
        'min_unique': 5, 'final_trigger': 'toast:Verification successful',
        'timing': {'BOOT_TIMEOUT': 150, 'READ_TRIGGER_WAIT': 60, 'WRITE_TRIGGER_WAIT': 90, 'VERIFY_TRIGGER_WAIT': 60},
    },
    'write_lf_io_success': {
        'read_fixture': 'tests/flows/read/scenarios/read_lf_io/fixture.py',
        'write_keys': ['lf_io'],
        'tag_type': 12, 'default_ret': 1,
        'min_unique': 5, 'final_trigger': 'toast:Verification successful',
        'timing': {'BOOT_TIMEOUT': 150, 'READ_TRIGGER_WAIT': 60, 'WRITE_TRIGGER_WAIT': 90, 'VERIFY_TRIGGER_WAIT': 60},
    },
    'write_lf_viking_success': {
        'read_fixture': 'tests/flows/read/scenarios/read_lf_viking/fixture.py',
        'write_keys': ['lf_viking'],
        'tag_type': 15, 'default_ret': 1,
        'min_unique': 5, 'final_trigger': 'toast:Verification successful',
        'timing': {'BOOT_TIMEOUT': 150, 'READ_TRIGGER_WAIT': 60, 'WRITE_TRIGGER_WAIT': 90, 'VERIFY_TRIGGER_WAIT': 60},
    },
    'write_lf_pyramid_success': {
        'read_fixture': 'tests/flows/read/scenarios/read_lf_pyramid/fixture.py',
        'write_keys': ['lf_pyramid'],
        'tag_type': 16, 'default_ret': 1,
        'min_unique': 5, 'final_trigger': 'toast:Verification successful',
        'timing': {'BOOT_TIMEOUT': 150, 'READ_TRIGGER_WAIT': 60, 'WRITE_TRIGGER_WAIT': 90, 'VERIFY_TRIGGER_WAIT': 60},
    },
    'write_lf_jablotron_success': {
        'read_fixture': 'tests/flows/read/scenarios/read_lf_jablotron/fixture.py',
        'write_keys': ['lf_jablotron'],
        'tag_type': 30, 'default_ret': 1,
        'min_unique': 5, 'final_trigger': 'toast:Verification successful',
        'timing': {'BOOT_TIMEOUT': 150, 'READ_TRIGGER_WAIT': 60, 'WRITE_TRIGGER_WAIT': 90, 'VERIFY_TRIGGER_WAIT': 60},
    },
    'write_lf_keri_success': {
        'read_fixture': 'tests/flows/read/scenarios/read_lf_keri/fixture.py',
        'write_keys': ['lf_keri'],
        'tag_type': 31, 'default_ret': 1,
        'min_unique': 5, 'final_trigger': 'toast:Verification successful',
        'timing': {'BOOT_TIMEOUT': 150, 'READ_TRIGGER_WAIT': 60, 'WRITE_TRIGGER_WAIT': 90, 'VERIFY_TRIGGER_WAIT': 60},
    },
    'write_lf_noralsy_success': {
        'read_fixture': 'tests/flows/read/scenarios/read_lf_noralsy/fixture.py',
        'write_keys': ['lf_noralsy'],
        'tag_type': 33, 'default_ret': 1,
        'min_unique': 5, 'final_trigger': 'toast:Verification successful',
        'timing': {'BOOT_TIMEOUT': 150, 'READ_TRIGGER_WAIT': 60, 'WRITE_TRIGGER_WAIT': 90, 'VERIFY_TRIGGER_WAIT': 60},
    },
    'write_lf_presco_success': {
        'read_fixture': 'tests/flows/read/scenarios/read_lf_presco/fixture.py',
        'write_keys': ['lf_presco'],
        'tag_type': 36, 'default_ret': 1,
        'min_unique': 5, 'final_trigger': 'toast:Verification successful',
        'timing': {'BOOT_TIMEOUT': 150, 'READ_TRIGGER_WAIT': 60, 'WRITE_TRIGGER_WAIT': 90, 'VERIFY_TRIGGER_WAIT': 60},
    },
    'write_lf_visa2000_success': {
        'read_fixture': 'tests/flows/read/scenarios/read_lf_visa2000/fixture.py',
        'write_keys': ['lf_visa2000'],
        'tag_type': 37, 'default_ret': 1,
        'min_unique': 5, 'final_trigger': 'toast:Verification successful',
        'timing': {'BOOT_TIMEOUT': 150, 'READ_TRIGGER_WAIT': 60, 'WRITE_TRIGGER_WAIT': 90, 'VERIFY_TRIGGER_WAIT': 60},
    },
    # RAW_CLONE types
    'write_lf_securakey_success': {
        'read_fixture': 'tests/flows/read/scenarios/read_lf_securakey/fixture.py',
        'write_keys': ['lf_securakey'],
        'tag_type': 14, 'default_ret': 1,
        'min_unique': 5, 'final_trigger': 'toast:Verification successful',
        'timing': {'BOOT_TIMEOUT': 150, 'READ_TRIGGER_WAIT': 60, 'WRITE_TRIGGER_WAIT': 90, 'VERIFY_TRIGGER_WAIT': 60},
    },
    'write_lf_gallagher_success': {
        'read_fixture': 'tests/flows/read/scenarios/read_lf_gallagher/fixture.py',
        'write_keys': ['lf_gallagher'],
        'tag_type': 29, 'default_ret': 1,
        'min_unique': 5, 'final_trigger': 'toast:Verification successful',
        'timing': {'BOOT_TIMEOUT': 150, 'READ_TRIGGER_WAIT': 60, 'WRITE_TRIGGER_WAIT': 90, 'VERIFY_TRIGGER_WAIT': 60},
    },
    'write_lf_pac_success': {
        'read_fixture': 'tests/flows/read/scenarios/read_lf_pac/fixture.py',
        'write_keys': ['lf_pac'],
        'tag_type': 34, 'default_ret': 1,
        'min_unique': 5, 'final_trigger': 'toast:Verification successful',
        'timing': {'BOOT_TIMEOUT': 150, 'READ_TRIGGER_WAIT': 60, 'WRITE_TRIGGER_WAIT': 90, 'VERIFY_TRIGGER_WAIT': 60},
    },
    'write_lf_paradox_success': {
        'read_fixture': 'tests/flows/read/scenarios/read_lf_paradox/fixture.py',
        'write_keys': ['lf_paradox'],
        'tag_type': 35, 'default_ret': 1,
        'min_unique': 5, 'final_trigger': 'toast:Verification successful',
        'timing': {'BOOT_TIMEOUT': 150, 'READ_TRIGGER_WAIT': 60, 'WRITE_TRIGGER_WAIT': 90, 'VERIFY_TRIGGER_WAIT': 60},
    },
    'write_lf_nexwatch_success': {
        'read_fixture': 'tests/flows/read/scenarios/read_lf_nexwatch/fixture.py',
        'write_keys': ['lf_nexwatch'],
        'tag_type': 45, 'default_ret': 1,
        'min_unique': 5, 'final_trigger': 'toast:Verification successful',
        'timing': {'BOOT_TIMEOUT': 150, 'READ_TRIGGER_WAIT': 60, 'WRITE_TRIGGER_WAIT': 90, 'VERIFY_TRIGGER_WAIT': 60},
    },
    # PAR_CLONE + special
    'write_lf_fdxb_success': {
        'read_fixture': 'tests/flows/read/scenarios/read_lf_fdxb/fixture.py',
        'write_keys': ['lf_fdxb'],
        'tag_type': 28, 'default_ret': 1,
        'min_unique': 5, 'final_trigger': 'toast:Verification successful',
        'timing': {'BOOT_TIMEOUT': 150, 'READ_TRIGGER_WAIT': 60, 'WRITE_TRIGGER_WAIT': 90, 'VERIFY_TRIGGER_WAIT': 60},
    },
    'write_lf_nedap_success': {
        'read_fixture': 'tests/flows/read/scenarios/read_lf_nedap/fixture.py',
        'write_keys': ['lf_nedap'],
        'tag_type': 32, 'default_ret': 1,
        'min_unique': 5, 'final_trigger': 'toast:Verification successful',
        'timing': {'BOOT_TIMEOUT': 150, 'READ_TRIGGER_WAIT': 60, 'WRITE_TRIGGER_WAIT': 90, 'VERIFY_TRIGGER_WAIT': 60},
    },
    # LF fail
    'write_lf_fail': {
        'read_fixture': 'tests/flows/read/scenarios/read_lf_em410x/fixture.py',
        'write_keys': ['lf_write_fail'],
        'tag_type': 8, 'default_ret': 1,
        'min_unique': 4, 'final_trigger': 'toast:Write failed', 'skip_verify': 'no_verify',
        'timing': {'BOOT_TIMEOUT': 150, 'READ_TRIGGER_WAIT': 60, 'WRITE_TRIGGER_WAIT': 30},
    },

    # =======================================================================
    # 4.6 T55XX — lft55xx.so (type 23) — 5 scenarios
    # =======================================================================
    'write_t55xx_restore_success': {
        'read_fixture': 'tests/flows/read/scenarios/read_lf_t55xx/fixture.py',
        'write_keys': ['lf_t55xx_restore'],
        'tag_type': 23, 'default_ret': 1,
        'min_unique': 5, 'final_trigger': 'toast:Verification successful',
        'timing': {'BOOT_TIMEOUT': 150, 'READ_TRIGGER_WAIT': 60, 'WRITE_TRIGGER_WAIT': 90, 'VERIFY_TRIGGER_WAIT': 60},
    },
    'write_t55xx_restore_fail': {
        'read_fixture': 'tests/flows/read/scenarios/read_lf_t55xx/fixture.py',
        'write_keys': ['lf_t55xx_restore_fail'],
        'tag_type': 23, 'default_ret': 1,
        'min_unique': 4, 'final_trigger': 'toast:Write failed', 'skip_verify': 'no_verify',
        'timing': {'BOOT_TIMEOUT': 150, 'READ_TRIGGER_WAIT': 60, 'WRITE_TRIGGER_WAIT': 30},
    },
    'write_t55xx_block_success': {
        'read_fixture': 'tests/flows/read/scenarios/read_lf_t55xx/fixture.py',
        'write_keys': ['lf_t55xx_block'],
        'tag_type': 23, 'default_ret': 1,
        'min_unique': 5, 'final_trigger': 'toast:Verification successful',
        'timing': {'BOOT_TIMEOUT': 150, 'READ_TRIGGER_WAIT': 60, 'WRITE_TRIGGER_WAIT': 90, 'VERIFY_TRIGGER_WAIT': 60},
    },
    'write_t55xx_block_fail': {
        'read_fixture': 'tests/flows/read/scenarios/read_lf_t55xx/fixture.py',
        'write_keys': ['lf_t55xx_block_fail'],
        'tag_type': 23, 'default_ret': 1,
        'min_unique': 4, 'final_trigger': 'toast:Write failed', 'skip_verify': 'no_verify',
        'timing': {'BOOT_TIMEOUT': 150, 'READ_TRIGGER_WAIT': 60, 'WRITE_TRIGGER_WAIT': 30},
    },
    'write_t55xx_password_write': {
        'read_fixture': 'tests/flows/read/scenarios/read_lf_t55xx_with_password/fixture.py',
        'write_keys': ['lf_t55xx_password_write'],
        'tag_type': 23, 'default_ret': 1,
        'min_unique': 5, 'final_trigger': 'toast:Verification successful',
        'timing': {'BOOT_TIMEOUT': 150, 'READ_TRIGGER_WAIT': 60, 'WRITE_TRIGGER_WAIT': 90, 'VERIFY_TRIGGER_WAIT': 60},
    },

    # =======================================================================
    # 4.7 EM4305 — lfwrite.so write_dump_em4x05() (type 24) — 2 scenarios
    # =======================================================================
    'write_em4305_dump_success': {
        'read_fixture': 'tests/flows/read/scenarios/read_lf_em4305_success/fixture.py',
        'write_keys': ['lf_em4305_dump'],
        'tag_type': 24, 'default_ret': 1,
        'min_unique': 5, 'final_trigger': 'toast:Verification successful',
        'timing': {'BOOT_TIMEOUT': 150, 'READ_TRIGGER_WAIT': 60, 'WRITE_TRIGGER_WAIT': 90, 'VERIFY_TRIGGER_WAIT': 60},
    },
    'write_em4305_dump_fail': {
        'read_fixture': 'tests/flows/read/scenarios/read_lf_em4305_success/fixture.py',
        'write_keys': ['lf_em4305_fail'],
        'tag_type': 24, 'default_ret': 1,
        'min_unique': 4, 'final_trigger': 'toast:Write failed', 'skip_verify': 'no_verify',
        'timing': {'BOOT_TIMEOUT': 150, 'READ_TRIGGER_WAIT': 60, 'WRITE_TRIGGER_WAIT': 30},
    },

    # =======================================================================
    # 4.8 GProx II — lfwrite.so write_raw_clone() (type 13) — 1 scenario
    # =======================================================================
    'write_lf_gprox_success': {
        'read_fixture': 'tests/flows/read/scenarios/read_lf_gprox/fixture.py',
        'write_keys': ['lf_gprox'],
        'tag_type': 13, 'default_ret': 1,
        'min_unique': 5, 'final_trigger': 'toast:Verification successful',
        'timing': {'BOOT_TIMEOUT': 150, 'READ_TRIGGER_WAIT': 60, 'WRITE_TRIGGER_WAIT': 90, 'VERIFY_TRIGGER_WAIT': 60},
    },

    # =======================================================================
    # 4.9 ISO15693 ST SA — hf15write.so (type 46) — 1 scenario
    # =======================================================================
    'write_iso15693_st_success': {
        'read_fixture': 'tests/flows/read/scenarios/read_iso15693_st/fixture.py',
        'write_keys': ['iso15693_success'],
        'tag_type': 46, 'default_ret': 1,
        'min_unique': 5, 'final_trigger': 'toast:Verification successful',
        'timing': {'BOOT_TIMEOUT': 120, 'READ_TRIGGER_WAIT': 60, 'WRITE_TRIGGER_WAIT': 90, 'VERIFY_TRIGGER_WAIT': 60},
    },

    # =======================================================================
    # 4.10 Additional MFC variants — hfmfwrite.so
    # =======================================================================
    # M1 Plus 2K (type 26) — same write path as MFC standard
    'write_mf_plus_2k_success': {
        'read_fixture': 'tests/flows/read/scenarios/read_mf_plus_2k_all_keys/fixture.py',
        'write_keys': ['standard_success'],
        'tag_type': 26, 'default_ret': 1,
        'min_unique': 5, 'final_trigger': 'toast:Verification successful',
    },
    # M1 POSSIBLE 7B (type 44) — same write path as type 43, uses MFC standard
    'write_mf_possible_7b_success': {
        'read_fixture': 'tests/flows/read/scenarios/read_mf_plus_2k_all_keys/fixture.py',
        'write_keys': ['standard_success'],
        'tag_type': 44, 'default_ret': 1,
        'min_unique': 5, 'final_trigger': 'toast:Verification successful',
    },

    # =======================================================================
    # 4.11 LF verify-fail — lfwrite.so verify mismatch
    # =======================================================================
    'write_lf_em410x_verify_fail': {
        'read_fixture': 'tests/flows/read/scenarios/read_lf_em410x/fixture.py',
        'write_keys': ['lf_em410x_verify_fail'],
        'tag_type': 8, 'default_ret': 1,
        'min_unique': 5, 'final_trigger': 'toast:Verification failed',
        'timing': {'BOOT_TIMEOUT': 150, 'READ_TRIGGER_WAIT': 60, 'WRITE_TRIGGER_WAIT': 90, 'VERIFY_TRIGGER_WAIT': 60},
    },
}


def load_read_fixture(fixture_path):
    """Load a read fixture.py and return its SCENARIO_RESPONSES dict."""
    full_path = os.path.join(PROJECT, fixture_path)
    if not os.path.exists(full_path):
        print(f"  WARNING: read fixture not found: {full_path}")
        return {}, 1, 1
    ns = {}
    with open(full_path) as f:
        exec(f.read(), ns)
    responses = ns.get('SCENARIO_RESPONSES', {})
    default_ret = ns.get('DEFAULT_RETURN', 1)
    tag_type = ns.get('TAG_TYPE', 1)
    return responses, default_ret, tag_type


def merge_fixtures(read_responses, write_keys, default_ret, tag_type=1):
    """Merge read responses with write fixture(s) from ALL_WRITE_SCENARIOS.

    For MFC types: splits the generic 'hf mf rdsc' into sector-0-specific
    and generic responses. Sector 0 returns UID in block 0; sectors 1-15
    return empty data blocks. This prevents the dump file from having
    duplicated UID data in every sector (which the write module rejects).
    """
    merged = dict(read_responses)
    for wk in write_keys:
        wfix = ALL_WRITE_SCENARIOS.get(wk, {})
        for k, v in wfix.items():
            if k.startswith('_'):
                continue
            merged[k] = v
        if '_default_return' in wfix:
            default_ret = wfix['_default_return']

    # MFC sector-specific rdsc fix: if 'hf mf rdsc' exists (generic),
    # add a sector-0-specific key that returns UID data, and make the
    # generic key return non-UID data for sectors 1-15.
    mfc_types = {0, 1, 25, 41, 42, 43, 44}
    if tag_type in mfc_types and 'hf mf rdsc' in merged:
        original_rdsc = merged['hf mf rdsc']
        if isinstance(original_rdsc, tuple):
            ret_code, rdsc_text = original_rdsc
            # Sector 0 keeps the original (with UID in block 0)
            # Trailing space prevents matching sector 10, 20, etc.
            merged['hf mf rdsc 0 '] = original_rdsc

            # Generic rdsc for sectors 1-15: replace block 0 line (UID) with zeros
            generic_text = rdsc_text
            # The UID line looks like: "  0 | 2C AD C2 72 ..." — replace with zeros
            import re
            generic_text = re.sub(
                r'(  0 \|) [0-9A-Fa-f ]{47}',
                r'\1 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00',
                generic_text
            )
            merged['hf mf rdsc'] = (ret_code, generic_text)

    return merged, default_ret


def write_fixture_py(scenario_name, merged, tag_type, default_ret, out_dir):
    """Write the merged fixture.py file.

    Keys are sorted by length DESCENDING so that the PM3 mock's substring
    matching checks more-specific patterns before shorter generic ones.
    Example: 'lf em 410x_write' must be checked before 'lf em 410x'
    to avoid the read key stealing the write command's match.
    """
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, 'fixture.py')
    lines = [f'# Write scenario: {scenario_name}']
    lines.append('SCENARIO_RESPONSES = {')
    # Sort keys: longest first to prevent substring collision
    for k in sorted(merged.keys(), key=len, reverse=True):
        v = merged[k]
        if isinstance(v, tuple):
            ret_code, text = v
            # Escape triple quotes in text
            safe_text = text.replace("'''", "\\'\\'\\'")
            lines.append(f"    '{k}': ({ret_code}, '''{safe_text}'''),")
        else:
            lines.append(f"    '{k}': {v!r},")
    lines.append('}')
    lines.append(f'DEFAULT_RETURN = {default_ret}')
    lines.append(f'TAG_TYPE = {tag_type}')
    lines.append('')
    with open(path, 'w') as f:
        f.write('\n'.join(lines))
    return path


def write_scenario_sh(scenario_name, spec, out_dir):
    """Write the scenario .sh script."""
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f'{scenario_name}.sh')

    timing = spec.get('timing', {})
    min_unique = spec.get('min_unique', 5)
    final_trigger = spec.get('final_trigger', 'toast:Verification successful')
    skip_verify = spec.get('skip_verify', '')

    lines = ['#!/bin/bash']
    lines.append(f'# Write scenario: {scenario_name}')
    lines.append(f'PROJECT="${{PROJECT:-/home/qx/icopy-x-reimpl}}"')
    lines.append(f'SCENARIO="{scenario_name}"')

    # Timing overrides
    if 'BOOT_TIMEOUT' in timing:
        lines.append(f'BOOT_TIMEOUT={timing["BOOT_TIMEOUT"]}')
    if 'READ_TRIGGER_WAIT' in timing:
        lines.append(f'READ_TRIGGER_WAIT={timing["READ_TRIGGER_WAIT"]}')
    if 'WRITE_TRIGGER_WAIT' in timing:
        lines.append(f'WRITE_TRIGGER_WAIT={timing["WRITE_TRIGGER_WAIT"]}')
    if 'VERIFY_TRIGGER_WAIT' in timing:
        lines.append(f'VERIFY_TRIGGER_WAIT={timing["VERIFY_TRIGGER_WAIT"]}')

    lines.append('source "${PROJECT}/tests/flows/write/includes/write_common.sh"')

    # Build run_write_scenario args
    if skip_verify:
        lines.append(f'run_write_scenario {min_unique} "{final_trigger}" "{skip_verify}"')
    else:
        lines.append(f'run_write_scenario {min_unique} "{final_trigger}"')

    lines.append('')

    with open(path, 'w') as f:
        f.write('\n'.join(lines))

    # Make executable
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return path


def main():
    scenarios_dir = os.path.join(PROJECT, 'tests', 'flows', 'write', 'scenarios')
    total = len(SCENARIO_MAP)
    created = 0
    skipped = 0

    print(f"Generating {total} write scenarios...")
    print(f"  Output: {scenarios_dir}/")
    print()

    for name, spec in sorted(SCENARIO_MAP.items()):
        out_dir = os.path.join(scenarios_dir, name)

        # Load read fixture
        read_responses, read_default, read_type = load_read_fixture(spec['read_fixture'])
        if not read_responses:
            print(f"  SKIP {name}: no read fixture at {spec['read_fixture']}")
            skipped += 1
            continue

        # Override tag_type and default_ret from scenario spec
        tag_type = spec.get('tag_type', read_type)
        default_ret = spec.get('default_ret', read_default)

        # Merge read + write fixtures
        merged, default_ret = merge_fixtures(read_responses, spec['write_keys'], default_ret, tag_type)

        # Write fixture.py
        write_fixture_py(name, merged, tag_type, default_ret, out_dir)

        # Write scenario .sh
        write_scenario_sh(name, spec, out_dir)

        created += 1

    print(f"\nDone: {created} created, {skipped} skipped")
    print(f"  Fixture files: {created}")
    print(f"  Script files:  {created}")


if __name__ == '__main__':
    main()
