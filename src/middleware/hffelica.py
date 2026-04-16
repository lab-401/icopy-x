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

"""hffelica -- FeliCa tag parser.

Reimplemented from hffelica.so (iCopy-X v1.0.90, Cython 0.29.21, ARM 32-bit).

Ground truth:
    Strings:    docs/v1090_strings/hffelica_strings.txt
    Decompiled: decompiled/hffelica_ghidra_raw.txt

API:
    parser() -> dict
"""

# Module-level constants (from audit: V1090_MODULE_AUDIT.txt)
CMD = 'hf felica reader'    # STR@hffelica_strings.txt
TIMEOUT = 10000              # __pyx_int_10000

# Detection keywords (from binary string table)
_KW_FOUND = 'FeliCa tag info'
_KW_TIMEOUT = 'card timeout'

# Regex for IDm extraction (from binary: '.*IDm(.*)')
_RE_IDM = r'.*IDm(.*)'


def parser():
    """Parse hf felica reader output from executor cache.

    Returns:
        {'found': True, 'idm': '<idm_hex>'}  -- FeliCa tag detected
        {'found': False}                      -- no FeliCa / timeout
    """
    try:
        import executor
    except ImportError:
        try:
            from . import executor
        except ImportError:
            return {'found': False}

    # Timeout or no tag
    if executor.hasKeyword(_KW_TIMEOUT):
        return {'found': False}

    # FeliCa detected
    if executor.hasKeyword(_KW_FOUND):
        idm_raw = executor.getContentFromRegex(_RE_IDM)
        idm = ''
        if idm_raw:
            # The regex captures everything after 'IDm', including ': 01 FE ...'
            # Strip whitespace but keep ':' prefix, remove internal spaces
            # Ground truth: scan_cache idm = ':01FE010203040506'
            # PM3 output: 'IDm: 01 FE 01 02 03 04 05 06'
            # Captured by regex: ': 01 FE 01 02 03 04 05 06'
            # After strip().replace(' ',''): ':01FE010203040506'
            idm = idm_raw.strip().replace(' ', '')
        return {'found': True, 'idm': idm}

    return {'found': False}
