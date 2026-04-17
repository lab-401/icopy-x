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

"""lfsearch -- LF tag search parser.

Reimplemented from lfsearch.so (iCopy-X v1.0.90, Cython 0.29.21, ARM 32-bit).

Ground truth:
    Spec:       docs/middleware-integration/2-hf14ainfo_hfsearch_lfsearch_spec.md (section 3)
    Strings:    docs/v1090_strings/lfsearch_strings.txt
    Archive:    archive/lib_transliterated/lfsearch.py (structural reference only)

API:
    CMD = 'lf sea'
    TIMEOUT = 10000
    COUNT = 0

    parser() -> dict
    cleanHexStr(hexStr) -> str
    getFCCN() -> str
    getXsf() -> str or None
    hasFCCN() -> bool
    parseFC() -> str
    parseCN() -> str
    parseLen() -> str
    setUID(seaObj, regex=REGEX_CARD_ID, group=0) -> None
    setRAW(seaObj) -> None
    setUID2FCCN(seaObj) -> None
    setUID2Raw(seaObj) -> None
    setRAWForRegex(seaObj, regex, group) -> None
    cleanAndSetRaw(seaObj, hexStr) -> None
    hasFCCN() -> bool

Functions read from executor.CONTENT_OUT_IN__TXT_CACHE.
"""

import re

try:
    from . import executor
except ImportError:
    import executor

try:
    from . import tagtypes
except ImportError:
    import tagtypes

# ---------------------------------------------------------------------------
# Module-level constants -- from binary (spec section 3.2)
# ---------------------------------------------------------------------------
CMD = 'lf sea'
TIMEOUT = 10000
COUNT = 0

# ---------------------------------------------------------------------------
# Public regex patterns -- iceman-native shapes
# Source: /tmp/rrg-pm3/client/src/cmdlf*.c per-protocol demod output.
# Matrix section: `lf search` (divergence_matrix.md L958-988).
# ---------------------------------------------------------------------------
# Iceman FDX-B demodFDXB @ cmdlffdxb.c:572/578 emits dotted form
#   "Animal ID........... <country>-<national>" (decimal, 9-11 dots).
# Matrix L980; source_strings.md "lf fdxb" sections.
REGEX_ANIMAL = r'Animal ID\.+\s+([0-9\-]+)'

# Iceman per-tag demod labels: Viking "Card <hex>" (cmdlfviking.c:57, no colon),
# Jablotron/Noralsy/Paradox "Card: <u>" or "ID: <hex>" (cmdlfjablotron.c:98,
# cmdlfparadox.c:224). Tolerant to both `Card `/`Card:` within iceman native forms.
# Matrix L988; source_strings.md lf viking/jablotron/noralsy/paradox.
REGEX_CARD_ID = r'(?:Card|ID|UID)[\s:]+([xX0-9a-fA-F ]+)'

# Iceman EM410x demodEM410x @ cmdlfem410x.c:115 emits "EM 410x ID <hex>" —
# iceman dropped the legacy "EM TAG ID :" label entirely.
# Matrix L977; source_strings.md "lf em 410x" section.
REGEX_EM410X = r'EM 410x(?:\s+XL)?\s+ID\s+([0-9A-Fa-f]+)'

# Iceman HID demodHID @ cmdlfhid.c:235 emits "raw: <hex>" (lowercase `raw`).
# Iceman removed the legacy "HID Prox - <hex>" emission entirely; grep of
# /tmp/rrg-pm3/client/src/ for "HID Prox -" yields zero results.
# Matrix L978 claim of iceman `HID Prox -` is incorrect; verified by source.
# Used only in Check 3 which first gates on 'Valid HID Prox ID' keyword, so
# bare `raw:` will be bounded to the HID demod output.
REGEX_HID = r'raw:\s+([0-9A-Fa-f]+)'

# Iceman IO Prox demodIOProx @ cmdlfio.c:156 emits
#   "IO Prox - XSF(%02d)%02x:%05d, Raw: ..."
# decimal card number after colon. Matches iceman natively.
REGEX_PROX_ID_XSF = r'(XSF\(.*?\).*?:[xX0-9a-fA-F]+)'

# Iceman per-tag demod consistently emits ", Raw: <hex>" (capital Raw+colon)
# (cmdlfjablotron.c:98, cmdlfviking.c:57, cmdlfawid.c:248, cmdlfnoralsy.c:106,
# cmdlfparadox.c:224, cmdlfsecurakey.c:113, cmdlfpresco.c:114, ...); HID demod
# uses lowercase "raw:" (cmdlfhid.c:235). Drop legacy `Hex|HEX|hex` alternates
# never emitted by iceman. Matrix L988.
REGEX_RAW = r'(?:Raw|raw):\s*([xX0-9a-fA-F ]+)'

# ---------------------------------------------------------------------------
# Internal regex patterns -- iceman-native shapes
# ---------------------------------------------------------------------------
# Iceman AWID/Pyramid/Paradox/KERI emit `FC: %d` (cmdlfawid.c:248,
# cmdlfpyramid.c:161, cmdlfparadox.c:224, cmdlfkeri.c:181); Securakey emits
# `FC: 0x%X` (cmdlfsecurakey.c:113). Colon is uniform post-iceman. Drop
# `:*` tolerance. Matrix L981-982.
_RE_FC = r'FC:\s+([xX0-9a-fA-F]+)'

# Iceman per-tag demod uses: `Card: %u` (Jablotron/Noralsy/Paradox/AWID
# cmdlfjablotron.c:98, cmdlfnoralsy.c:106, cmdlfparadox.c:224, cmdlfawid.c:248),
# `Card %X` (Viking cmdlfviking.c:57 — space, no colon), `CN: %u` (COTAG
# cmdlfcotag.c:76). Tolerant colon-or-space required for iceman natively since
# Viking is the outlier. Matrix L988.
_RE_CN = r'(CN|Card(?:\s+No\.)?|Card ID)[\s:]+(\d+)'

# Iceman AWID/Pyramid/Securakey emit `- len: %d` (cmdlfawid.c:248,
# cmdlfpyramid.c:161, cmdlfsecurakey.c:113) — lowercase only. Drop `Len|LEN|
# format|Format` alternates never emitted by iceman. Matrix L988.
_RE_LEN = r'len:\s+(\d+)'

# Iceman chipset-detection in cmdlf.c:1601-1655 emits dotted `Chipset... <name>`
# (3 dots); legacy emits `Chipset detection: <name>`. Matrix L986; compat
# adapter `_normalize_chipset_detection` handles legacy→iceman reshaping.
_RE_CHIPSET = r'Chipset\.+\s+(.*)'

# Iceman NEDAP @ cmdlfnedap.c:146/410/520 emits
#   `" subtype: %1u customer code: %u / 0x%03X"` — both colons.
_RE_SUBTYPE = r'subtype:\s+(\d+)'
_RE_CUSTOMER_CODE = r'customer code:\s+(\d+)'

# ---------------------------------------------------------------------------
# Detection keywords -- iceman-native
# ---------------------------------------------------------------------------
# Iceman cmdlf.c:2210 emits `"No known 125/134 kHz tags found!"` — IDENTICAL
# to legacy. Matrix L976 (v3 re-verification).
_KW_NO_KNOWN = 'No known 125/134 kHz tags found!'

# Legacy cmdlf.c:1441/1510 emits `"No data found!"`; iceman REMOVED this
# emission (empty response on no-tag). The compat adapter
# `_normalize_lf_no_data` synthesises this marker on iceman empty response
# so middleware can use a single keyword across both firmwares.
# TODO(Phase 4): confirm `_normalize_lf_no_data` active for `lf sea`.
# Matrix L975.
_KW_NO_DATA = 'No data found!'

# Iceman emits `Chipset...` (dotted, cmdlf.c:1601-1655); legacy emits
# `Chipset detection:`. Phase 4 compat adapter `_normalize_chipset_detection`
# (pm3_compat.py:1313) reshapes legacy to iceman form. Matrix L986.
_KW_CHIPSET_DETECTION = 'Chipset...'

# Iceman EM4x05/EM4x69 detection emits `"Chipset... EM4x05 / EM4x69"`.
# Used only as a marker for chipset classification in Check 24 logic; the
# `'EM' in chipset_str` substring match handles both cases.
_KW_CHIPSET_EM4X05 = 'Chipset... EM4x05 / EM4x69'


# ===========================================================================
# Helper functions -- spec section 3.7
# ===========================================================================

def cleanHexStr(hexStr):
    """Clean a hex string by stripping '0x'/'0X' prefix and removing spaces.

    Spec section 3.7 (cleanHexStr):
        1. If starts with '0x' or '0X', strip prefix using lstrip
        2. Remove all spaces via .replace(' ', '')

    Binary citation: __pyx_pw_8lfsearch_1cleanHexStr @0x0001976c
    """
    if not hexStr:
        return ''
    s = hexStr
    if s.startswith('0x') or s.startswith('0X'):
        s = s.lstrip('0xX')
    s = s.replace(' ', '')
    return s


def parseFC():
    """Extract FC (Facility Code) from cached output.

    Spec section 3.7 (parseFC):
        executor.getContentFromRegexG(_RE_FC, 1), then .strip()

    Binary citation: __pyx_pw_8lfsearch_15parseFC @0x0001a5b0
    """
    result = executor.getContentFromRegexG(_RE_FC, 1)
    if result:
        return result.strip()
    return ''


def parseCN():
    """Extract CN (Card Number) from cached output.

    Spec section 3.7 (parseCN):
        executor.getContentFromRegexG(_RE_CN, 2), then .strip()

    Binary citation: __pyx_pw_8lfsearch_17parseCN @0x0001aaa0
    """
    result = executor.getContentFromRegexG(_RE_CN, 2)
    if result:
        return result.strip()
    return ''


def parseLen():
    """Extract len from cached output.

    Iceman `len:` is lowercase with colon (cmdlfawid.c:248 etc.); _RE_LEN is
    `r'len:\\s+(\\d+)'` — single capture group. Group=1.
    """
    result = executor.getContentFromRegexG(_RE_LEN, 1)
    if result:
        return result.strip()
    return ''


def hasFCCN():
    """Check if FC and CN are present in cached output.

    Spec section 3.7 (hasFCCN):
        Calls parseFC(), returns bool(result)

    Binary citation: lfsearch_strings.txt: hasFCCN
    """
    fc = parseFC()
    return bool(fc)


def getFCCN():
    """Get formatted FC,CN string from cached output.

    Spec section 3.7 (getFCCN):
        Calls parseFC() and parseCN(), formats with 'FC,CN: {},{}'.format(fc, cn)
        The binary uses fill_char mechanism suggesting zero-padding:
        FC padded to 3 digits, CN padded to 5 digits.

    Binary citation: __pyx_pw_8lfsearch_21getFCCN @0x00016258
    """
    fc = parseFC()
    cn = parseCN()
    if not fc and not cn:
        return 'FC,CN: X,X'
    # Clean FC: strip 0x prefix so int() parses as decimal
    # Ground truth: original shows decimal FC values, not hex
    fc_clean = cleanHexStr(fc) if fc else ''
    try:
        fc_int = int(fc_clean)
        fc_str = '%03d' % fc_int
    except (ValueError, TypeError):
        fc_str = 'X'
    try:
        cn_int = int(cn)
        cn_str = '%05d' % cn_int
    except (ValueError, TypeError):
        cn_str = cn if cn else 'X'
    return 'FC,CN: %s,%s' % (fc_str, cn_str)


def getXsf():
    """Extract XSF format data from cached output.

    Spec section 3.7 (getXsf):
        executor.getContentFromRegexG(REGEX_PROX_ID_XSF, 1), then .strip()
        Returns None if not found.

    Binary citation: __pyx_pw_8lfsearch_23getXsf @0x0001af90
    """
    result = executor.getContentFromRegexG(REGEX_PROX_ID_XSF, 1)
    if result:
        return result.strip()
    return None


def setUID(seaObj, regex=REGEX_CARD_ID, group=0):
    """Set 'data' key in seaObj dict from regex match.

    Spec section 3.7 (setUID):
        executor.getContentFromRegexG(regex, group), clean with cleanHexStr(),
        set seaObj['data'].
        Default: regex=REGEX_CARD_ID, group=0

    Binary citation: __pyx_pw_8lfsearch_5setUID @0x000189bc
    """
    uid = executor.getContentFromRegexG(regex, group)
    if uid:
        seaObj['data'] = cleanHexStr(uid.strip())
    else:
        seaObj['data'] = ''


def setRAW(seaObj):
    """Set 'raw' key in seaObj dict from REGEX_RAW match.

    Spec section 3.7 (setRAW):
        executor.getContentFromRegexG(REGEX_RAW, 1), clean with cleanHexStr(),
        set seaObj['raw'].

    Binary citation: __pyx_pw_8lfsearch_13setRAW @0x00017320
    """
    raw = executor.getContentFromRegexG(REGEX_RAW, 1)
    if raw:
        seaObj['raw'] = cleanHexStr(raw.strip())
    else:
        seaObj['raw'] = ''


def setUID2FCCN(seaObj):
    """Set data/fc/cn/len keys in seaObj from FC/CN fields.

    Spec section 3.7 (setUID2FCCN):
        seaObj['data'] = getFCCN()
        seaObj['fc'] = parseFC()
        seaObj['cn'] = parseCN()
        seaObj['len'] = parseLen()

    Binary citation: __pyx_pw_8lfsearch_7setUID2FCCN @0x00018220
    """
    seaObj['data'] = getFCCN()
    seaObj['fc'] = parseFC()
    seaObj['cn'] = parseCN()
    seaObj['len'] = parseLen()


def setUID2Raw(seaObj):
    """Set 'raw' key to match 'data' key value.

    Spec section 3.7 (setUID2Raw):
        seaObj['raw'] = seaObj['data']

    Binary citation: __pyx_pw_8lfsearch_9setUID2Raw @0x0001592c
    """
    seaObj['raw'] = seaObj['data']


def setRAWForRegex(seaObj, regex, group):
    """Set 'raw' key from a specific regex match.

    Spec section 3.7 (setRAWForRegex):
        executor.getContentFromRegexG(regex, group), clean with cleanHexStr(),
        set seaObj['raw'].

    Binary citation: __pyx_pw_8lfsearch_11setRAWForRegex @0x0001778c
    """
    raw = executor.getContentFromRegexG(regex, group)
    if raw:
        seaObj['raw'] = cleanHexStr(raw.strip())
    else:
        seaObj['raw'] = ''


def cleanAndSetRaw(seaObj, hexStr):
    """Clean hex string and set as 'raw' in seaObj.

    Spec section 3.7 (cleanAndSetRaw):
        seaObj['raw'] = cleanHexStr(hexStr)

    Binary citation: __pyx_pw_8lfsearch_3cleanAndSetRaw @0x00019480
    """
    seaObj['raw'] = cleanHexStr(hexStr)


# ===========================================================================
# Main parser -- spec section 3.8
# ===========================================================================

def parser():
    """Parse lf search output from executor cache.

    Detection priority order (spec section 3.8):
        1. 'No data found!' -> {'found': False}
        2-22. Tag-specific 'Valid <type> ID' checks in order
        23. 'No known 125/134 kHz tags found!' -> {'found': True, 'isT55XX': True}
        24. 'Chipset detection' -> {'chipset': '<str>', 'found': False}
        25. Default fallback -> {'found': False}

    Binary citation: __pyx_pw_8lfsearch_25parser @0x0001b408
    """
    # -------------------------------------------------------------------
    # Check 1: No data found
    # -------------------------------------------------------------------
    if executor.hasKeyword(_KW_NO_DATA):
        return {'found': False}

    # -------------------------------------------------------------------
    # Checks 2-22: Tag-specific detection in order
    # -------------------------------------------------------------------

    # Check 2: EM410x
    if executor.hasKeyword('Valid EM410x ID'):
        seaObj = {}
        uid = executor.getContentFromRegexG(REGEX_EM410X, 1)
        if uid:
            seaObj['data'] = cleanHexStr(uid.strip())
        else:
            seaObj['data'] = ''
        seaObj['raw'] = seaObj['data']
        seaObj['type'] = tagtypes.EM410X_ID
        seaObj['found'] = True
        return seaObj

    # Check 3: HID Prox
    if executor.hasKeyword('Valid HID Prox ID'):
        seaObj = {}
        # Raw hex from "HID Prox - XXXX" line
        uid = executor.getContentFromRegexG(REGEX_HID, 1)
        seaObj['raw'] = cleanHexStr(uid.strip()) if uid else ''
        # Extract FC/CN from Wiegand decode block if available
        # (iceman outputs "[H10301] HID H10301 26-bit FC: 128 CN: 54641")
        fc = parseFC()
        cn = parseCN()
        if fc or cn:
            seaObj['data'] = getFCCN()
        else:
            seaObj['data'] = seaObj['raw']
        seaObj['type'] = tagtypes.HID_PROX_ID
        seaObj['found'] = True
        return seaObj

    # Check 4: AWID
    if executor.hasKeyword('Valid AWID ID'):
        seaObj = {}
        setUID2FCCN(seaObj)
        setRAW(seaObj)
        seaObj['type'] = tagtypes.AWID_ID
        seaObj['found'] = True
        return seaObj

    # Check 5: IO Prox
    if executor.hasKeyword('Valid IO Prox ID'):
        seaObj = {}
        xsf = getXsf()
        if xsf:
            seaObj['data'] = xsf
            # Decompose "XSF(VN)FC:CN" into sim-field-friendly keys so
            # scan→simulate prepopulation picks them up per-field.
            # Example: "XSF(00)00:00273" → vn=00, fc=00, cn=273
            m = re.match(r'XSF\(\s*([0-9A-Fa-f]+)\s*\)\s*([0-9A-Fa-f]+)\s*:\s*([0-9]+)', xsf)
            if m:
                seaObj['vn'] = m.group(1)
                seaObj['fc'] = m.group(2)
                seaObj['cn'] = m.group(3)
        else:
            seaObj['data'] = None
        setRAW(seaObj)
        seaObj['type'] = tagtypes.IO_PROX_ID
        seaObj['found'] = True
        return seaObj

    # Check 6: Indala
    if executor.hasKeyword('Valid Indala ID'):
        seaObj = {}
        setRAW(seaObj)
        seaObj['data'] = seaObj.get('raw', '')
        seaObj['type'] = tagtypes.INDALA_ID
        seaObj['found'] = True
        return seaObj

    # Check 7: Viking
    if executor.hasKeyword('Valid Viking ID'):
        seaObj = {}
        setUID(seaObj)
        setRAW(seaObj)
        seaObj['type'] = tagtypes.VIKING_ID
        seaObj['found'] = True
        return seaObj

    # Check 8: Pyramid
    if executor.hasKeyword('Valid Pyramid ID'):
        seaObj = {}
        setUID2FCCN(seaObj)
        setRAW(seaObj)
        seaObj['type'] = tagtypes.PYRAMID_ID
        seaObj['found'] = True
        return seaObj

    # Check 9: Jablotron
    if executor.hasKeyword('Valid Jablotron ID'):
        seaObj = {}
        setUID(seaObj)
        setRAW(seaObj)
        seaObj['type'] = tagtypes.JABLOTRON_ID
        seaObj['found'] = True
        return seaObj

    # Check 10: NEDAP
    if executor.hasKeyword('Valid NEDAP ID'):
        seaObj = {}
        setUID(seaObj)
        setRAW(seaObj)
        subtype = executor.getContentFromRegexG(_RE_SUBTYPE, 1)
        code = executor.getContentFromRegexG(_RE_CUSTOMER_CODE, 1)
        seaObj['subtype'] = subtype.strip() if subtype else ''
        seaObj['code'] = code.strip() if code else ''
        seaObj['type'] = tagtypes.NEDAP_ID
        seaObj['found'] = True
        return seaObj

    # Check 11: Guardall G-Prox II
    if executor.hasKeyword('Valid Guardall G-Prox II ID'):
        seaObj = {}
        setUID2FCCN(seaObj)
        setRAW(seaObj)
        seaObj['type'] = tagtypes.GPROX_II_ID
        seaObj['found'] = True
        return seaObj

    # Check 12: FDX-B
    if executor.hasKeyword('Valid FDX-B ID'):
        seaObj = {}
        uid = executor.getContentFromRegexG(REGEX_ANIMAL, 1)
        if uid:
            uid_clean = uid.strip()
            seaObj['raw'] = uid_clean
            # FDX-B Animal ID format: CCC-NNNNNNNNNNNN (country-national)
            # Split into country + national code for two-line display
            parts = uid_clean.split('-', 1)
            if len(parts) == 2:
                seaObj['data'] = 'Country: %s' % parts[0]
                seaObj['country'] = parts[0]
                seaObj['nc'] = parts[1]
            else:
                seaObj['data'] = uid_clean
        else:
            seaObj['data'] = ''
            seaObj['raw'] = ''
        seaObj['type'] = tagtypes.FDXB_ID
        seaObj['found'] = True
        return seaObj

    # Check 13: Securakey
    if executor.hasKeyword('Valid Securakey ID'):
        seaObj = {}
        setUID2FCCN(seaObj)
        setRAW(seaObj)
        seaObj['type'] = tagtypes.SECURAKEY_ID
        seaObj['found'] = True
        return seaObj

    # Check 14: KERI
    if executor.hasKeyword('Valid KERI ID'):
        seaObj = {}
        setUID2FCCN(seaObj)
        setRAW(seaObj)
        seaObj['type'] = tagtypes.KERI_ID
        seaObj['found'] = True
        return seaObj

    # Check 15: PAC/Stanley
    if executor.hasKeyword('Valid PAC/Stanley ID'):
        seaObj = {}
        setUID(seaObj)
        setRAW(seaObj)
        seaObj['type'] = tagtypes.PAC_ID
        seaObj['found'] = True
        return seaObj

    # Check 16: Paradox
    if executor.hasKeyword('Valid Paradox ID'):
        seaObj = {}
        setUID2FCCN(seaObj)
        setRAW(seaObj)
        seaObj['type'] = tagtypes.PARADOX_ID
        seaObj['found'] = True
        return seaObj

    # Check 17: NexWatch
    if executor.hasKeyword('Valid NexWatch ID'):
        seaObj = {}
        setUID(seaObj)
        setRAW(seaObj)
        seaObj['type'] = tagtypes.NEXWATCH_ID
        seaObj['found'] = True
        return seaObj

    # Check 18: Visa2000
    if executor.hasKeyword('Valid Visa2000 ID'):
        seaObj = {}
        setUID(seaObj)
        setRAW(seaObj)
        seaObj['type'] = tagtypes.VISA2000_ID
        seaObj['found'] = True
        return seaObj

    # Check 19: GALLAGHER
    if executor.hasKeyword('Valid GALLAGHER ID'):
        seaObj = {}
        setUID2FCCN(seaObj)
        setRAW(seaObj)
        seaObj['type'] = tagtypes.GALLAGHER_ID
        seaObj['found'] = True
        return seaObj

    # Check 20: Noralsy
    if executor.hasKeyword('Valid Noralsy ID'):
        seaObj = {}
        setUID(seaObj)
        setRAW(seaObj)
        seaObj['type'] = tagtypes.NORALSY_ID
        seaObj['found'] = True
        return seaObj

    # Check 21: Presco
    if executor.hasKeyword('Valid Presco ID'):
        seaObj = {}
        setUID(seaObj)
        seaObj['type'] = tagtypes.PRESCO_ID
        seaObj['found'] = True
        return seaObj

    # Check 22: Hitag
    if executor.hasKeyword('Valid Hitag'):
        seaObj = {}
        setUID(seaObj)
        seaObj['type'] = tagtypes.HITAG2_ID
        seaObj['found'] = True
        return seaObj

    # -------------------------------------------------------------------
    # Check 23: No known tags but signal present (T55XX)
    # -------------------------------------------------------------------
    if executor.hasKeyword(_KW_NO_KNOWN):
        return {'found': True, 'isT55XX': True}

    # -------------------------------------------------------------------
    # Check 24: Chipset detection
    # -------------------------------------------------------------------
    if executor.hasKeyword(_KW_CHIPSET_DETECTION):
        chipset_raw = executor.getContentFromRegexG(_RE_CHIPSET, 1)
        chipset = ''
        if chipset_raw:
            chipset_str = chipset_raw.strip()
            if 'EM' in chipset_str:
                chipset = 'EM4305'
            elif 'T5' in chipset_str:
                chipset = 'T5577'
            else:
                chipset = 'X'
        else:
            chipset = 'X'
        return {'chipset': chipset, 'found': False}

    # -------------------------------------------------------------------
    # Check 25: Default fallback
    # -------------------------------------------------------------------
    return {'found': False}
