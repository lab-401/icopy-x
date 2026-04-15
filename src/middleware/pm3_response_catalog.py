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

"""pm3_response_catalog -- Complete catalog of PM3 response format differences.

Enumerates every response keyword and regex pattern used by the middleware,
classified as SAFE (works with both firmware versions) or BROKEN (needs
normalization when running on RRG/Iceman firmware).

Source of truth:
    OLD: iCopy-X-Community/icopyx-community-pm3 (factory FW, RRG 385d892f)
    NEW: rfidresearchgroup/proxmark3 (RRG/Iceman latest, v4.21128+)

Architecture:
    This catalog is consumed by pm3_compat.translate_response() to
    normalize NEW firmware output to match OLD patterns expected by
    middleware modules.
"""

# ============================================================================
# BREAKING CHANGES: Patterns that FAIL on new firmware
# ============================================================================

BREAKING_CHANGES = {
    # ------------------------------------------------------------------
    # Track A: HF Scan (hf14ainfo.py, hfsearch.py, hffelica.py)
    # ------------------------------------------------------------------
    'prng_detection_separator': {
        'module': 'hf14ainfo.py',
        'old': 'Prng detection: weak',
        'new': 'Prng detection..... weak',
        'pattern': r'.*Prng detection: (.*)\n',
        'fix': 'generic_dotted_to_colon',
    },
    'static_nonce_separator': {
        'module': 'hf14ainfo.py',
        'old': 'Static nonce: yes',
        'new': 'Static nonce....... yes',
        'pattern': 'Static nonce: yes',
        'fix': 'generic_dotted_to_colon',
    },
    'magic_capabilities_separator': {
        'module': 'hf14ainfo.py',
        'old': 'Magic capabilities : Gen 1a',
        'new': 'Magic capabilities... Gen 1a',
        'pattern': 'Magic capabilities : Gen 1a',
        'fix': 'magic_capabilities_normalize',
    },
    'manufacturer_removed': {
        'module': 'hf14ainfo.py',
        'old': 'MANUFACTURER:    NXP Semiconductors',
        'new': '      NXP Semiconductors',
        'pattern': r'.*MANUFACTURER:(.*)',
        'fix': 'manufacturer_label_restore',
    },
    'uid_annotation': {
        'module': 'hf14ainfo.py',
        'old': 'UID: 5E 5B CE 4C',
        'new': 'UID: 5E 5B CE 4C   ( ONUID, re-used )',
        'pattern': r'.*UID:(.*)\n',
        'fix': 'uid_strip_annotation',
    },
    'iso15693_space': {
        'module': 'hfsearch.py',
        'old': 'Valid ISO15693',
        'new': 'Valid ISO 15693',
        'pattern': 'Valid ISO15693',
        'fix': 'iso_number_normalize',
    },
    'iso14443b_space': {
        'module': 'hfsearch.py',
        'old': 'Valid ISO14443-B',
        'new': 'Valid ISO 14443-B',
        'pattern': 'Valid ISO14443-B',
        'fix': 'iso_number_normalize',
    },
    'iso18092_space': {
        'module': 'hfsearch.py',
        'old': 'Valid ISO18092 / FeliCa',
        'new': 'Valid ISO 18092 / FeliCa',
        'pattern': 'Valid ISO18092 / FeliCa',
        'fix': 'iso_number_normalize',
    },
    'iso14443a_space': {
        'module': 'hfsearch.py',
        'old': 'Valid ISO14443-A tag',
        'new': 'Valid ISO 14443-A tag',
        'pattern': 'Valid ISO14443-A',
        'fix': 'iso_number_normalize',
    },
    'felica_tag_info_removed': {
        'module': 'hffelica.py',
        'old': 'FeliCa tag info',
        'new': '(removed)',
        'pattern': 'FeliCa tag info',
        'fix': 'felica_reader_normalize',
    },
    'felica_card_timeout': {
        'module': 'hffelica.py',
        'old': 'card timeout',
        'new': 'FeliCa card select failed',
        'pattern': 'card timeout',
        'fix': 'felica_reader_normalize',
    },

    # ------------------------------------------------------------------
    # Track B: MIFARE Classic Keys (hfmfkeys.py)
    # ------------------------------------------------------------------
    'fchk_table_format': {
        'module': 'hfmfkeys.py',
        'old': '| 000 | ffffffffffff   | 1 | ffffffffffff   | 1 |',
        'new': ' 000 | 003 | FFFFFFFFFFFF | 1 | FFFFFFFFFFFF | 1',
        'pattern': r'\|\s*(\d+)\s*\|\s*([A-Fa-f0-9-]{12})\s*\|\s*(\d+)\s*\|\s*([A-Fa-f0-9-]{12})\s*\|\s*(\d+)\s*\|',
        'fix': 'fchk_table_normalize',
    },
    'darkside_key_format': {
        'module': 'hfmfkeys.py',
        'old': 'found valid key: aabbccddeeff',
        'new': 'Found valid key [ AABBCCDDEEFF ]',
        'pattern': 'found valid key',
        'fix': 'darkside_key_normalize',
    },

    # ------------------------------------------------------------------
    # Track C: MIFARE Classic Read/Write (hfmfwrite.py, hfmfread.py, erase.py)
    # ------------------------------------------------------------------
    'wrbl_isok_success': {
        'module': 'hfmfwrite.py',
        'old': 'isOk:01',
        'new': 'Write ( ok )',
        'pattern': 'isOk:01',
        'fix': 'wrbl_response_normalize',
    },
    'wrbl_isok_failure': {
        'module': 'hfmfwrite.py',
        'old': 'isOk:00',
        'new': 'Write ( fail )',
        'pattern': 'isOk:00',
        'fix': 'wrbl_response_normalize',
    },
    'rdbl_data_format': {
        'module': 'hfmfread.py',
        'old': 'data: AA BB CC DD ...',
        'new': '  N | AA BB CC DD ... | ascii',
        'pattern': 'data:',
        'fix': 'rdbl_response_normalize',
    },
    'cgetblk_data_format': {
        'module': 'hfmfwrite.py / hf14ainfo.py',
        'old': 'data: AA BB CC DD ...',
        'new': '  N | AA BB CC DD ... | ascii',
        'pattern': 'data:',
        'fix': 'cgetblk_response_normalize',
    },
    'cload_card_loaded': {
        'module': 'hfmfwrite.py',
        'old': 'Card loaded 64 blocks from file',
        'new': 'Card loaded 64 blocks from dumpfile.bin',
        'pattern': 'Card loaded',
        'fix': None,  # SAFE: 'Card loaded' substring still present
    },
    'csetuid_format': {
        'module': 'hfmfwrite.py',
        'old': 'Old UID : XX XX',
        'new': 'Old UID... XX XX',
        'pattern': 'Old UID',
        'fix': 'generic_dotted_to_colon',
    },

    # ------------------------------------------------------------------
    # Track D: LF Search (lfsearch.py)
    # ------------------------------------------------------------------
    'no_data_found_removed': {
        'module': 'lfsearch.py',
        'old': 'No data found!',
        'new': '(removed)',
        'pattern': 'No data found!',
        'fix': 'lf_search_no_data_normalize',
    },
    'em410x_id_format': {
        'module': 'lfsearch.py / lfread.py',
        'old': 'EM TAG ID      : 0100000058',
        'new': 'EM 410x ID 0100000058',
        'pattern': r'EM TAG ID\s+:[\s]+([xX0-9a-fA-F]+)',
        'fix': 'em410x_id_normalize',
    },
    'chipset_detection_format': {
        'module': 'lfsearch.py',
        'old': 'Chipset detection: EM4x05 / EM4x69',
        'new': 'Chipset... EM4x05 / EM4x69',
        'pattern': r'Chipset detection:\s(.*)',
        'fix': 'chipset_detection_normalize',
    },
    'hid_prox_format': {
        'module': 'lfsearch.py',
        'old': 'HID Prox - 2006ec0c86',
        'new': '(format changed to wiegand decode)',
        'pattern': r'HID Prox - ([xX0-9a-fA-F]+)',
        'fix': 'hid_prox_normalize',
    },
    'hitag_removed': {
        'module': 'lfsearch.py',
        'old': 'Valid Hitag',
        'new': '(removed from lf search)',
        'pattern': 'Valid Hitag',
        'fix': None,  # Tag type still detected via chipset path
    },

    # ------------------------------------------------------------------
    # Track E: LF T55xx/EM4x05 (lft55xx.py, lfem4x05.py)
    # ------------------------------------------------------------------
    't55xx_chip_type_format': {
        'module': 'lft55xx.py',
        'old': '     Chip Type      : T55x7',
        'new': ' Chip type......... T55x7',
        'pattern': r'.*Chip Type.*:(.*)',
        'fix': 't55xx_config_normalize',
    },
    't55xx_modulation_format': {
        'module': 'lft55xx.py',
        'old': '     Modulation     : FSK2a',
        'new': ' Modulation........ FSK2a',
        'pattern': r'.*Modulation.*:(.*)',
        'fix': 't55xx_config_normalize',
    },
    't55xx_block0_format': {
        'module': 'lft55xx.py',
        'old': '     Block0         : 0x00148040',
        'new': ' Block0............ 00148040',
        'pattern': r'Block0\s+:\s+0x([A-Fa-f0-9]+)',
        'fix': 't55xx_config_normalize',
    },
    'em4x05_chip_type_format': {
        'module': 'lfem4x05.py',
        'old': ' Chip Type:   9 | EM4305',
        'new': 'Chip type..... EM4305',
        'pattern': r'.*Chip Type.*\|(.*)',
        'fix': 'em4x05_info_normalize',
    },
    'em4x05_serial_format': {
        'module': 'lfem4x05.py',
        'old': '  Serial #: 1A2B3C4D',
        'new': 'Serialno...... 1A2B3C4D',
        'pattern': r'.*Serial.*:(.*)',
        'fix': 'em4x05_info_normalize',
    },
    'saved_12_blocks': {
        'module': 'lft55xx.py',
        'old': 'saved 12 blocks to text file',
        'new': '(removed, no EML save)',
        'pattern': 'saved 12 blocks',
        'fix': 'save_message_normalize',
    },
    'saved_case_change': {
        'module': 'lft55xx.py / lfem4x05.py',
        'old': 'saved 64 bytes to binary file',
        'new': 'Saved 64 bytes to binary file',
        'pattern': 'saved',
        'fix': 'save_message_normalize',
    },

    # ------------------------------------------------------------------
    # Track F: iCLASS / ISO15693 / FeliCa (hficlass, hf15write, etc.)
    # ------------------------------------------------------------------
    'iclass_wrbl_success': {
        'module': 'iclasswrite.py',
        'old': 'Wrote block 07 successful',
        'new': 'Wrote block 7 / 0x07 ( ok )',
        'pattern': 'successful',
        'fix': 'iclass_wrbl_normalize',
    },
    'hf15_setting_uid': {
        'module': 'hf15write.py',
        'old': 'setting new UID (ok)',
        'new': 'Setting new UID ( ok )',
        'pattern': r'setting new UID \(ok\)',
        'fix': 'hf15_csetuid_normalize',
    },
    'hf15_cant_read_uid': {
        'module': 'hf15write.py',
        'old': "can't read card UID",
        'new': 'no tag found',
        'pattern': "can't read card UID",
        'fix': 'hf15_csetuid_normalize',
    },
    'hf15_done': {
        'module': 'hf15write.py',
        'old': 'done',
        'new': 'Done!',
        'pattern': 'done',
        'fix': None,  # SAFE: hasKeyword('done') matches 'Done!' via re.search
    },
}

# ============================================================================
# SAFE PATTERNS: Work with both firmware versions
# ============================================================================

SAFE_PATTERNS = [
    # hf14ainfo.py
    'Multiple tags detected',
    "Card doesn't support standard iso14443-3 anticollision",
    'BCC0 incorrect',
    'MIFARE DESFire',
    'MIFARE Classic 1K',
    'MIFARE Classic 4K',
    'MIFARE Classic',
    'MIFARE Mini',
    'MIFARE Plus',
    'MIFARE Plus 4K',
    'MIFARE Ultralight',
    'NTAG',
    # hfsearch.py
    'No known/supported 13.56 MHz tags found',
    'Valid iCLASS tag',
    'Valid LEGIC Prime',
    'MIFARE',
    'Valid Topaz',
    'ST Microelectronics SA France',
    # lfsearch.py
    'No known 125/134 kHz tags found!',
    'Valid EM410x ID',
    'Valid HID Prox ID',
    'Valid AWID ID',
    'Valid IO Prox ID',
    'Valid Indala ID',
    'Valid Viking ID',
    'Valid Pyramid ID',
    'Valid Jablotron ID',
    'Valid NEDAP ID',
    'Valid Guardall G-Prox II ID',
    'Valid FDX-B ID',
    'Valid Securakey ID',
    'Valid KERI ID',
    'Valid PAC/Stanley ID',
    'Valid Paradox ID',
    'Valid NexWatch ID',
    'Valid Visa2000 ID',
    'Valid GALLAGHER ID',
    'Valid Noralsy ID',
    'Valid Presco ID',
    # hfmfwrite.py
    "Can't set magic",
    'Card loaded',
    'wupC1 error',
    "Can't read block",
    # hfmfread.py
    'Auth error',
    # hfmfuread.py / hfmfuwrite.py
    "Can't select card",
    'Partial dump created',
    'failed to write block',
    # lft55xx.py
    'Could not detect modulation automatically',
    # lfem4x05.py
    'Chip Type',
    # hf15write.py
    'restore failed',
    'Too many retries',
    'Write OK',
    # iclassread.py
    'saving dump file',
    # hficlass.py (block read pattern)
    # r'[Bb]lock \d+ : ([a-fA-F0-9 ]+)' -- works with both
]
