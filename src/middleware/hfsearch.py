##########################################################################
# Required Notice: Copyright ETOILE401 SAS (http://www.lab401.com)
#
# Initial author: ETOILE401 SAS & https://github.com/quantum-x/ as of April 16, 2026
#
# Since this date, each contribution is under the copyright of its respective author.
#
# Copyright of each contribution is tracked by the Git history. See the output of git shortlog -nse for a full list or git log --pretty=short --follow <path/to/sourcefile> |git shortlog -ne to track a specific file.
#
# A mailmap is maintained to map author and committer names and email addresses to canonical names and email addresses.
# If by accident a copyright was removed from a file and is not directly deducible from the Git history, please submit a PR.
#
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
and return value shapes are from the original binary (Ghidra ARM).

Ground truth: docs/middleware-integration/2-hf14ainfo_hfsearch_lfsearch_spec.md §2

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
# Detection keywords — iceman-native shapes
# Matrix section: `hf search` (divergence_matrix.md L928-954).
# Source: /tmp/rrg-pm3/client/src/cmdhf.c:69+ (CmdHFSearch, table L621).
# ---------------------------------------------------------------------------
# Iceman cmdhf.c:242 `_RED_("No known/supported 13.56 MHz tags found")` —
# IDENTICAL to legacy cmdhf.c:193. Matrix L943.
_KW_NO_KNOWN = 'No known/supported 13.56 MHz tags found'

# Iceman cmdhf.c:208 `"Valid " _GREEN_("iCLASS tag / PicoPass tag") " found"`.
# Substring `Valid iCLASS tag` matches both iceman and legacy. Matrix L944.
_KW_ICLASS = 'Valid iCLASS tag'

# Iceman cmdhf.c:198 `"Valid " _GREEN_("ISO 15693 tag") " found"` — WITH
# space between ISO and number. Legacy cmdhf.c:127 omits the space.
# Phase 4 compat `_normalize_iso15693_manufacturer` / `_RE_ISO_SPACE`
# (pm3_compat.py:1078) strips space on legacy→iceman; keyword targets
# iceman-native form. Matrix L945.
_KW_ISO15693 = 'Valid ISO 15693'

# Iceman cmdhf.c emits `"ST Microelectronics SA France"` as ISO15693
# manufacturer sub-key. IDENTICAL in both. Matrix L951.
_KW_ST_MICRO = 'ST Microelectronics SA France'

# Iceman cmdhf.c:155 `"Valid " _GREEN_("LEGIC Prime tag") " found"`.
# Substring `Valid LEGIC Prime` matches both. Matrix (L942 grouping).
_KW_LEGIC = 'Valid LEGIC Prime'

# Iceman cmdhf.c:220 `"Valid " _GREEN_("ISO 18092 / FeliCa tag") " found"` —
# WITH space. Legacy cmdhf.c omits space. Same `_RE_ISO_SPACE` adapter
# handles reshaping on legacy→iceman path. Matrix L947.
_KW_FELICA = 'Valid ISO 18092 / FeliCa'

# Iceman cmdhf.c:186 `"Valid " _GREEN_("ISO 14443-B tag") " found"` — WITH
# space. Legacy omits. Matrix L946.
_KW_ISO14443B = 'Valid ISO 14443-B'

# Substring `MIFARE` hits iceman infoHF14A block types. IDENTICAL after
# prefix strip. Matrix L870.
_KW_MIFARE = 'MIFARE'

# Iceman cmdhf.c:106 `"Valid " _GREEN_("Topaz tag") " found"`. Substring
# `Valid Topaz` matches both.
_KW_TOPAZ = 'Valid Topaz'

# ---------------------------------------------------------------------------
# Regex patterns — iceman-native shapes
# ---------------------------------------------------------------------------
# Iceman ISO15693 UID: `"UID.... " _GREEN_("%s")` — cmdhf15.c:447 inside
# `getUID()` called by `readHF15Uid()` (cmdhf15.c:465), which is the path
# exercised by `hf sea` (cmdhf.c:197). The field separator is FOUR dots,
# NOT a colon — iceman dropped the legacy `UID: ` form for ISO15693 entirely.
# Grep of /tmp/rrg-pm3/client/src/cmdhf15.c for `UID:` within SUCCESS-level
# emissions yields zero matches; only `UID....` is emitted.
# Keep regex tolerant to 4+ dots in case downstream iceman versions vary.
# Matrix L971 (hf search ISO15693 sub-row — to be re-verified in v4).
_RE_UID = r'UID\.{3,}\s+([0-9A-Fa-f ]+)'

# Iceman ISO14443-B UID: `" UID    : %s"` (cmdhf14b.c:1269, padded spaces
# before colon). Tolerant to both padded and non-padded colon.
_RE_UID_ALT = r'UID\s*:\s+([0-9A-Fa-f ]+)'

# Iceman LEGIC: `"MCD: " _GREEN_("%02X") " MSN: " _GREEN_("%s")
# " MCC: " _GREEN_("%02X")` (cmdhflegic.c:90). MSN is
# multi-byte hex; capture non-greedy up to next `MCC` field.
_RE_MSN = r'MSN:\s+([0-9A-Fa-f][0-9A-Fa-f\s]*?)(?=\s+MCC|\n|$)'

# Iceman LEGIC MCD: single hex byte (cmdhflegic.c:90).
_RE_MCD = r'MCD:\s+([0-9A-Fa-f]{2})'

# Iceman ISO14443-B ATQB: `" ATQB   : %s"` (cmdhf14b.c:1270 — padded
# spaces before colon). Keep tolerant whitespace.
_RE_ATQB = r'ATQB\s*:\s+([0-9A-Fa-f ]+)'

# Iceman Topaz ATQA: `"ATQA: " _GREEN_("%02X %02X")` (cmdhftopaz.c:1178).
_RE_ATQA = r'ATQA\s*:\s+([0-9A-Fa-f ]+)'

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

    Detection priority order (from original binary §2.7):
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
