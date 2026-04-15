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

"""hfsearch -- HF tag search parser.

Reimplements hfsearch.so (iCopy-X v1.0.90) parser() function.
All constants, detection keywords, regex patterns, priority order,
and return value shapes are  .


Binary: hfsearch.so (Cython 0.29.23, ARM:LE:32:v7)
    Source: C:\\Users\\ADMINI~1\\AppData\\Local\\Temp\\1\\tmprriqzsry\\hfsearch.py
    Entry: __pyx_pw_8hfsearch_1parser @0x000138c8

Imports (from binary): executor, hffelica
Does NOT import tagtypes — all type integers are hardcoded.

API:
    CMD     = 'hf sea'
    TIMEOUT = 10000
    parser() -> dict
"""

# ---------------------------------------------------------------------------
# Module-level constants — EXACT from binary
# ---------------------------------------------------------------------------
CMD = 'hf sea'
TIMEOUT = 10000

# ---------------------------------------------------------------------------
# Detection keywords — EXACT from binary string extraction (§2.3)
# ---------------------------------------------------------------------------
_KW_NO_KNOWN = 'No known/supported 13.56 MHz tags found'   # STR@0x00016610
_KW_ICLASS = 'Valid iCLASS tag'                             # STR@0x00016674
_KW_ISO15693 = 'Valid ISO15693'                             # STR@0x0001668c
_KW_ST_MICRO = 'ST Microelectronics SA France'              # STR@0x000166a0
_KW_LEGIC = 'Valid LEGIC Prime'                             # STR@0x000166d8
_KW_FELICA = 'Valid ISO18092 / FeliCa'                      # STR@0x000166f0
_KW_ISO14443B = 'Valid ISO14443-B'                          # STR@0x00016714
_KW_MIFARE = 'MIFARE'                                      # STR@0x00016730
_KW_TOPAZ = 'Valid Topaz'                                   # STR@0x00016748

# ---------------------------------------------------------------------------
# Regex patterns — EXACT from binary string extraction (§2.4)
# ---------------------------------------------------------------------------
_RE_UID = r'.*UID:\s(.*)'           # ISO15693 UID
_RE_UID_ALT = r'.*UID.*:(.*)'       # ISO14443-B / Topaz UID
_RE_MSN = r'.*MSN:\s(.*)'           # LEGIC MSN
_RE_MCD = r'.*MCD:\s(.*)'           # LEGIC MCD
_RE_ATQB = r'.*ATQB.*:(.*)'         # ISO14443-B ATQB
_RE_ATQA = r'.*ATQA.*:(.*)'         # Topaz ATQA

# ---------------------------------------------------------------------------
# Hardcoded integer type constants (§2.5)
# NOT from tagtypes — hardcoded in binary as hex literals
# ---------------------------------------------------------------------------
_TYPE_ISO15693_ICODE = 19   # 0x13
_TYPE_ISO15693_ST_SA = 46   # 0x2e
_TYPE_LEGIC_MIM256 = 20     # __pyx_int_20
_TYPE_ISO14443B = 22        # __pyx_int_22
_TYPE_TOPAZ = 27            # __pyx_int_27


def parser():
    """Parse hf search output from executor cache.

    Reads from executor.CONTENT_OUT_IN__TXT_CACHE (populated by prior
    startPM3Task('hf sea', 10000)).

    Detection priority order:
        1. No known tag       -> {'found': False}
        2. iCLASS             -> {'found': True, 'isIclass': True}
        3. ISO15693           -> {'found': True, 'uid': ..., 'type': 19|46}
        4. LEGIC Prime        -> {'found': True, 'mcd': ..., 'msn': ..., 'type': 20}
        5. ISO14443-B         -> {'found': True, 'uid': ..., 'atqb': ..., 'type': 22}
        6. MIFARE (14443-A)   -> {'found': True, 'isMifare': True}
        7. Topaz              -> {'found': True, 'uid': ..., 'atqa': ..., 'type': 27}
        8. FeliCa             -> {'found': False}  (handled by scan.so separately)
        9. Default            -> {'found': False}
    """
    try:
        from . import executor
    except ImportError:
        import executor

    # ------------------------------------------------------------------
    # Check 1: No known/supported tag
    # ------------------------------------------------------------------
    if executor.hasKeyword(_KW_NO_KNOWN):
        return {'found': False}

    # ------------------------------------------------------------------
    # Check 2: iCLASS
    # ------------------------------------------------------------------
    if executor.hasKeyword(_KW_ICLASS):
        return {'found': True, 'isIclass': True}

    # ------------------------------------------------------------------
    # Check 3: ISO15693
    # ------------------------------------------------------------------
    if executor.hasKeyword(_KW_ISO15693):
        uid_raw = executor.getContentFromRegexG(_RE_UID, 1)
        uid = uid_raw.strip().replace(' ', '') if uid_raw else ''
        if executor.hasKeyword(_KW_ST_MICRO):
            typ = _TYPE_ISO15693_ST_SA   # 46
        else:
            typ = _TYPE_ISO15693_ICODE   # 19
        return {'found': True, 'uid': uid, 'type': typ}

    # ------------------------------------------------------------------
    # Check 4: LEGIC Prime
    # ------------------------------------------------------------------
    if executor.hasKeyword(_KW_LEGIC):
        mcd_raw = executor.getContentFromRegexG(_RE_MCD, 1)
        msn_raw = executor.getContentFromRegexG(_RE_MSN, 1)
        mcd = mcd_raw.strip().replace(' ', '') if mcd_raw else ''
        msn = msn_raw.strip().replace(' ', '') if msn_raw else ''
        return {'found': True, 'mcd': mcd, 'msn': msn, 'type': _TYPE_LEGIC_MIM256}

    # ------------------------------------------------------------------
    # Check 5: ISO14443-B
    # ------------------------------------------------------------------
    if executor.hasKeyword(_KW_ISO14443B):
        uid_raw = executor.getContentFromRegexG(_RE_UID_ALT, 1)
        atqb_raw = executor.getContentFromRegexG(_RE_ATQB, 1)
        uid = uid_raw.strip().replace(' ', '') if uid_raw else ''
        atqb = atqb_raw.strip().replace(' ', '') if atqb_raw else ''
        return {'found': True, 'uid': uid, 'atqb': atqb, 'type': _TYPE_ISO14443B}

    # ------------------------------------------------------------------
    # Check 6: MIFARE (ISO14443-A with MIFARE keyword)
    # ------------------------------------------------------------------
    if executor.hasKeyword(_KW_MIFARE):
        return {'found': True, 'isMifare': True}

    # ------------------------------------------------------------------
    # Check 7: Topaz
    # ------------------------------------------------------------------
    if executor.hasKeyword(_KW_TOPAZ):
        uid_raw = executor.getContentFromRegexG(_RE_UID_ALT, 1)
        atqa_raw = executor.getContentFromRegexG(_RE_ATQA, 1)
        uid = uid_raw.strip().replace(' ', '') if uid_raw else ''
        atqa = atqa_raw.strip().replace(' ', '') if atqa_raw else ''
        return {'found': True, 'uid': uid, 'atqa': atqa, 'type': _TYPE_TOPAZ}

    # ------------------------------------------------------------------
    # Check 8: FeliCa — returns found=False (actual FeliCa handled by
    # scan.so calling hffelica.parser() directly)
    # ------------------------------------------------------------------
    if executor.hasKeyword(_KW_FELICA):
        return {'found': False}

    # ------------------------------------------------------------------
    # Default: no tag found
    # ------------------------------------------------------------------
    return {'found': False}
