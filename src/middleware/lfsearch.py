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
# Public regex patterns -- from binary string extraction (spec section 3.3)
# ---------------------------------------------------------------------------
REGEX_ANIMAL = r'.*ID\s+([xX0-9A-Fa-f\-]{2,})'
REGEX_CARD_ID = r'(?:Card|ID|id|CARD|ID|UID|uid|Uid)\s*:*\s*([xX0-9a-fA-F ]+)'
REGEX_EM410X = r'EM TAG ID\s+:[\s]+([xX0-9a-fA-F]+)'
REGEX_HID = r'HID Prox - ([xX0-9a-fA-F]+)'
REGEX_PROX_ID_XSF = r'(XSF\(.*?\).*?:[xX0-9a-fA-F]+)'
REGEX_RAW = r'.*(?:Raw|RAW|raw|hex|HEX|Hex)\s*:*\s*([xX0-9a-fA-F ]+)'

# ---------------------------------------------------------------------------
# Internal regex patterns -- from binary string extraction (spec section 3.4)
# ---------------------------------------------------------------------------
_RE_FC = r'FC:*\s+([xX0-9a-fA-F]+)'
_RE_CN = r'(CN|Card|Card ID):*\s+(\d+)'
_RE_LEN = r'(len|Len|LEN|format|Format):*\s+(\d+)'
_RE_CHIPSET = r'Chipset detection:\s(.*)'
_RE_SUBTYPE = r'subtype:*\s+(\d+)'
_RE_CUSTOMER_CODE = r'customer code:*\s+(\d+)'

# ---------------------------------------------------------------------------
# Detection keywords -- from binary string extraction (spec section 3.5)
# ---------------------------------------------------------------------------
_KW_NO_KNOWN = 'No known 125/134 kHz tags found!'
_KW_NO_DATA = 'No data found!'
_KW_CHIPSET_DETECTION = 'Chipset detection'
_KW_CHIPSET_EM4X05 = 'Chipset detection: EM4x05 / EM4x69'


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
    """Extract len/format from cached output.

    Spec section 3.7 (parseLen):
        executor.getContentFromRegexG(_RE_LEN, 2), then .strip()

    Binary citation: __pyx_pw_8lfsearch_19parseLen @0x0001a0bc
    """
    result = executor.getContentFromRegexG(_RE_LEN, 2)
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
