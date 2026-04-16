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

"""hf14ainfo -- HF 14443A tag identification parser.

Reimplemented from hf14ainfo.so (iCopy-X v1.0.90, Cython 0.29.21, ARM:LE:32:v7).
All constants, function signatures, return values, and edge-case behaviors match
the original binary as documented in the spec.

Ground truth:
    Spec:        docs/middleware-integration/2-hf14ainfo_hfsearch_lfsearch_spec.md (section 1)
    Strings:     docs/v1090_strings/hf14ainfo_strings.txt

API:
    CMD = 'hf 14a info'
    TIMEOUT = 5000
    parser() -> dict
    has_static_nonce() -> bool
    has_prng_level() -> bool
    is_gen1a_magic() -> bool
    is_maybe_mifare() -> bool
    get_uid() -> str
    get_sak() -> str
    get_atqa() -> str
    get_ats() -> str
    get_uid_length() -> int
    get_prng_level() -> str
    get_manufacturer() -> str

Functions read from executor.CONTENT_OUT_IN__TXT_CACHE.
"""

# ---------------------------------------------------------------------------
# Module-level constants -- from original binary
# ---------------------------------------------------------------------------
# STR@0x0001de26: 'hf 14a info'
CMD = 'hf 14a info'
# __pyx_int_5000 (STR@0x00001085)
TIMEOUT = 5000

# ---------------------------------------------------------------------------
# Regex patterns -- EXACT from binary string extraction
# ---------------------------------------------------------------------------
# STR@0x0001df68: '.*UID:(.*)\n'
_RE_UID = r'.*UID:(.*)\n'
# STR@0x0001df78: '.*ATQA:(.*)\n'
_RE_ATQA = r'.*ATQA:(.*)\n'
# STR@0x0001df88: '.*SAK:(.*)\[.*\n'
_RE_SAK = r'.*SAK:(.*)\[.*\n'
# STR@0x0001dc88: '.*Prng detection: (.*)\n'
_RE_PRNG = r'.*Prng detection: (.*)\n'
# STR@0x0001dfa0: '.*ATS:(.*)'
_RE_ATS = r'.*ATS:(.*)'
# STR@0x0001dde4: '.*MANUFACTURER:(.*)'
_RE_MANUFACTURER = r'.*MANUFACTURER:(.*)'

# ---------------------------------------------------------------------------
# Detection keyword strings -- EXACT from binary string extraction
# ---------------------------------------------------------------------------
# STR@0x0001dc38
_KW_MIFARE_CLASSIC_1K = 'MIFARE Classic 1K'
# STR@0x0001dc24
_KW_MIFARE_CLASSIC_4K = 'MIFARE Classic 4K'
# STR@0x0001dd64
_KW_MIFARE_CLASSIC = 'MIFARE Classic'
# STR@0x0001de5c
_KW_MIFARE_MINI = 'MIFARE Mini'
# STR@0x0001de50
_KW_MIFARE_PLUS = 'MIFARE Plus'
# STR@0x0001dd34
_KW_MIFARE_PLUS_4K = 'MIFARE Plus 4K'
# STR@0x0001dc10
_KW_MIFARE_ULTRALIGHT = 'MIFARE Ultralight'
# STR@0x0001dd44
_KW_MIFARE_DESFIRE = 'MIFARE DESFire'
# STR@0x0001df9c
_KW_NTAG = 'NTAG'
# STR@0x0001db94
_KW_GEN1A = 'Magic capabilities : Gen 1a'
# STR@0x0001db70
_KW_GEN2_CUID = 'Magic capabilities : Gen 2 / CUID'
# STR@0x0001dc74
_KW_STATIC_NONCE = 'Static nonce: yes'
# STR@0x0001dbcc
_KW_MULTIPLE_TAGS = 'Multiple tags detected'
# STR@0x0001daf8
_KW_ANTICOLLISION = "Card doesn't support standard iso14443-3 anticollision"
# hf14ainfo_strings.txt line 614
_KW_BCC0_INCORRECT = 'BCC0 incorrect'
# STR@0x0001dd24
_KW_PRNG_DETECTION = 'Prng detection'

def has_static_nonce():
    """Check if the cached output indicates a static nonce card.

    Binary citation: references __pyx_kp_u_Static_nonce_yes and hasKeyword
    Behavior: executor.hasKeyword('Static nonce: yes')
    Returns: True if keyword found, False otherwise
    """
    import executor
    return executor.hasKeyword(_KW_STATIC_NONCE)

def has_prng_level():
    """Check if the cached output has a PRNG detection result.

    Binary citation: __pyx_pw_9hf14ainfo_3has_prng_level @0x000149c4
    Behavior: executor.hasKeyword('Prng detection')
    Note: checks bare string, not the regex pattern
    Returns: True if keyword found, False otherwise
    """
    import executor
    return executor.hasKeyword(_KW_PRNG_DETECTION)

def is_gen1a_magic():
    """Check if the tag is a Gen 1a magic card.

    Binary citation: __pyx_pw_9hf14ainfo_5is_gen1a_magic @0x00018220
    References: startPM3Task, getPrintContent, isEmptyContent,
                CONTENT_OUT_IN__TXT_CACHE, 'data:', 'fail'
    PM3 command: 'hf mf cgetblk 0' (STR@0x0001dcb4)

    Behavior:
      1. Save executor.CONTENT_OUT_IN__TXT_CACHE
      2. Run 'hf mf cgetblk 0' (Gen1a backdoor read)
      3. If task succeeded: check getPrintContent() for 'data:' and NOT 'fail'
      4. Restore original cache
      5. Fall back to hasKeyword('Magic capabilities : Gen 1a')
    Returns: True if Gen1a magic card detected, False otherwise
    """
    import executor

    # Save cache before PM3 probe (startPM3Task clobbers CONTENT_OUT_IN__TXT_CACHE)
    # Binary: references __pyx_k_CONTENT_OUT_IN__TXT_CACHE
    saved_cache = executor.CONTENT_OUT_IN__TXT_CACHE

    # Active probe via Gen1a backdoor command
    # Binary: STR@0x0001dcb4 'hf mf cgetblk 0'
    ret = executor.startPM3Task('hf mf cgetblk 0', 5000)

    if ret != executor.CODE_PM3_TASK_ERROR:
        # Binary: references getPrintContent, isEmptyContent, 'data:', 'fail'
        if not executor.isEmptyContent():
            content = executor.getPrintContent()
            if content and 'data:' in content and 'fail' not in content:
                # Restore cache before returning
                executor.CONTENT_OUT_IN__TXT_CACHE = saved_cache
                return True

    # Restore cache so hasKeyword checks the original hf 14a info output
    executor.CONTENT_OUT_IN__TXT_CACHE = saved_cache
    return executor.hasKeyword(_KW_GEN1A)

def get_prng_level():
    """Get the PRNG detection level string.

    Binary citation: __pyx_pw_9hf14ainfo_9get_prng_level @0x00014c14
    Behavior: executor.getContentFromRegexG('.*Prng detection: (.*)\\n'), .strip()
    Returns: PRNG level string (e.g. 'weak', 'hard')
    """
    import executor
    # STR@0x0001dbe4: getContentFromRegexG
    return executor.getContentFromRegexG(_RE_PRNG, 0).strip()

def get_manufacturer():
    """Get the MANUFACTURER field string.

    Binary citation: __pyx_pw_9hf14ainfo_19get_manufacturer @0x00015064
    Behavior: executor.getContentFromRegexG('.*MANUFACTURER:(.*)'), .strip()
    Returns: Manufacturer string
    """
    import executor
    return executor.getContentFromRegexG(_RE_MANUFACTURER, 0).strip()

def get_uid():
    """Get the UID hex string with spaces removed.

    Binary citation: __pyx_pw_9hf14ainfo_11get_uid @0x00015624
    Behavior: executor.getContentFromRegexG('.*UID:(.*)\\n'), .strip().replace(' ', '')
    Returns: UID hex string (e.g. 'AABBCCDD')
    """
    import executor
    return executor.getContentFromRegexG(_RE_UID, 0).strip().replace(' ', '')

def get_atqa():
    """Get the ATQA hex string with spaces removed.

    Binary citation: __pyx_pw_9hf14ainfo_15get_atqa @0x00016204
    Behavior: executor.getContentFromRegexG('.*ATQA:(.*)\\n'), .strip().replace(' ', '')
    Returns: ATQA hex string (e.g. '0004')
    """
    import executor
    return executor.getContentFromRegexG(_RE_ATQA, 0).strip().replace(' ', '')

def get_ats():
    """Get the ATS hex string with spaces removed.

    Binary citation: __pyx_pw_9hf14ainfo_17get_ats @0x00016658
    Behavior: executor.getContentFromRegexG('.*ATS:(.*)'), .strip().replace(' ', '')
    Returns: ATS hex string
    """
    import executor
    return executor.getContentFromRegexG(_RE_ATS, 0).strip().replace(' ', '')

def get_sak():
    """Get the SAK hex string with spaces removed.

    Binary citation: __pyx_pw_9hf14ainfo_13get_sak @0x00017dcc
    Behavior: executor.getContentFromRegexG('.*SAK:(.*)\\[.*\\n'), .strip().replace(' ', '')
    Returns: SAK hex string (e.g. '08')
    """
    import executor
    return executor.getContentFromRegexG(_RE_SAK, 0).strip().replace(' ', '')

def get_uid_length():
    """Get the UID length in bytes.

    Binary citation: __pyx_pw_9hf14ainfo_21get_uid_length @0x0001715c
    Behavior: len(get_uid()) // 2
    Returns: UID length in bytes (4 or 7 typically)
    """
    uid = get_uid()
    return len(uid) // 2

def is_maybe_mifare():
    """Check if the cached output indicates a potential MIFARE tag.

    Binary citation: __pyx_pw_9hf14ainfo_7is_maybe_mifare @0x00017800
    References: getM1Types, is_mifare, tagtypes
    Behavior: Runs parser(), checks if result type is in tagtypes.getM1Types()
    Returns: True if tag type is a MIFARE Classic variant, False otherwise
    """
    import tagtypes

    result = parser()
    if not result.get('found'):
        return False
    tag_type = result.get('type')
    if tag_type is None:
        return False
    return tag_type in tagtypes.getM1Types()

def parser():
    """Parse hf 14a info output from executor cache.

    Binary citation: __pyx_pw_9hf14ainfo_23parser @0x0001925c
    Reads from executor.CONTENT_OUT_IN__TXT_CACHE (populated by prior
    startPM3Task('hf 14a info', 5000)).

    Return value shapes (spec section 1.7):

    Case 1 - Multiple tags detected:
        {'found': True, 'hasMulti': True}

    Case 2 - Anticollision failure:
        {'found': False}

    Case 3 - BCC0 error:
        {'found': True, 'uid': 'BCC0 incorrect', 'len': 0,
         'sak': 'no', 'atqa': 'no', 'bbcErr': True,
         'static': <bool>, 'gen1a': <bool>, 'type': <int>}

    Case 4 - MIFARE DESFire (without Classic 1K/4K):
        {'found': True, 'uid': ..., 'len': ..., 'sak': ..., 'atqa': ...,
         'bbcErr': False, 'ats': ..., 'type': tagtypes.MIFARE_DESFIRE}

    Case 5 - MIFARE Ultralight / NTAG:
        {'found': True, 'isUL': True}

    Case 6 - Standard MIFARE classification:
        {'found': True, 'uid': ..., 'len': ..., 'sak': ..., 'atqa': ...,
         'bbcErr': False, 'static': ..., 'gen1a': ..., 'type': ...,
         'manufacturer': ...}  # manufacturer optional, only for M1_POSSIBLE
    """
    import executor
    import tagtypes

    # -------------------------------------------------------------------
    # Case 1: "Multiple tags detected" -- highest priority
    # Binary: STR@0x0001dbcc
    # -------------------------------------------------------------------
    if executor.hasKeyword(_KW_MULTIPLE_TAGS):
        return {'found': True, 'hasMulti': True}

    # -------------------------------------------------------------------
    # Case 2: Anticollision failure
    # Binary: STR@0x0001daf8
    # -------------------------------------------------------------------
    if executor.hasKeyword(_KW_ANTICOLLISION):
        return {'found': False}

    # -------------------------------------------------------------------
    # Extract raw fields via regex
    # Binary: references getContentFromRegex (archive) / getContentFromRegexG
    # -------------------------------------------------------------------
    uid_raw = executor.getContentFromRegex(_RE_UID)
    atqa_raw = executor.getContentFromRegex(_RE_ATQA)
    sak_raw = executor.getContentFromRegex(_RE_SAK)

    # -------------------------------------------------------------------
    # Case 3: BCC0 error
    # Binary: hf14ainfo_strings.txt line 614
    # -------------------------------------------------------------------
    b_bcc_err = executor.hasKeyword(_KW_BCC0_INCORRECT)
    if b_bcc_err:
        # BCC0 error overrides UID/SAK/ATQA with special values
        uid = 'BCC0 incorrect'
        sak = 'no'
        atqa = 'no'
        uid_len = 0
    else:
        # Process UID: strip whitespace and remove spaces
        uid = uid_raw.strip().replace(' ', '')
        # Process ATQA: strip whitespace and remove spaces
        atqa = atqa_raw.strip().replace(' ', '')
        # Process SAK: strip whitespace and remove spaces
        sak = sak_raw.strip().replace(' ', '')
        # UID length in bytes = number of hex chars / 2
        uid_len = len(uid) // 2

    # -------------------------------------------------------------------
    # Case 4: DESFire -- checked BEFORE Ultralight/NTAG because DESFire
    # output may contain "NTAG424DNA" which would incorrectly trigger UL
    # Binary: STR@0x0001dd44 'MIFARE DESFire'
    # -------------------------------------------------------------------
    if executor.hasKeyword(_KW_MIFARE_DESFIRE):
        # DESFire is only classified as DESFire when Classic 1K/4K
        # are NOT present in the output
        if not executor.hasKeyword(_KW_MIFARE_CLASSIC_1K) and \
           not executor.hasKeyword(_KW_MIFARE_CLASSIC_4K):
            result = {
                'found': True,
                'uid': uid,
                'len': uid_len,
                'sak': sak,
                'atqa': atqa,
                'bbcErr': b_bcc_err,
            }
            # Check for ATS
            # Binary: STR@0x0001dfa0 '.*ATS:(.*)'
            ats_raw = executor.getContentFromRegex(_RE_ATS)
            if ats_raw:
                result['ats'] = ats_raw.strip().replace(' ', '')
            # Binary: __pyx_k_MIFARE_DESFIRE -> tagtypes.MIFARE_DESFIRE (= 39)
            result['type'] = tagtypes.MIFARE_DESFIRE
            return result

    # -------------------------------------------------------------------
    # Case 5: Ultralight / NTAG -- checked after DESFire
    # Binary: STR@0x0001dc10 'MIFARE Ultralight', STR@0x0001df9c 'NTAG'
    # -------------------------------------------------------------------
    if executor.hasKeyword(_KW_MIFARE_ULTRALIGHT) or executor.hasKeyword(_KW_NTAG):
        # Early return with only found+isUL, no UID/SAK/ATQA parsing
        return {'found': True, 'isUL': True}

    # -------------------------------------------------------------------
    # Guard: If no UID was extracted and no BCC error, there's no 14A tag
    # Binary behavior: when hf 14a info returns empty/whitespace, the
    # regex for UID finds nothing → uid_raw is ''.  A valid 14A response
    # always contains UID (or triggers BCC/multi/anticollision above).
    # -------------------------------------------------------------------
    if not b_bcc_err and not uid_raw.strip():
        return {'found': False}

    # -------------------------------------------------------------------
    # Case 6: Standard MIFARE classification
    # -------------------------------------------------------------------
    b_static = has_static_nonce()
    b_prng = has_prng_level()
    b_gen1a = is_gen1a_magic()

    # Classification logic -- priority order from spec section 1.8
    tag_type = None
    manufacturer = None

    # Priority 1: MIFARE Mini
    # Binary: STR@0x0001de5c 'MIFARE Mini'
    # Checked first because Mini output also contains "MIFARE Classic 1K"
    if executor.hasKeyword(_KW_MIFARE_MINI):
        # Binary: __pyx_k_M1_MINI -> tagtypes.M1_MINI (= 25)
        tag_type = tagtypes.M1_MINI

    # Priority 2: MIFARE Classic 4K
    # Binary: STR@0x0001dc24 'MIFARE Classic 4K'
    elif executor.hasKeyword(_KW_MIFARE_CLASSIC_4K):
        if uid_len == 7:
            # Binary: __pyx_k_M1_S70_4K_7B -> tagtypes.M1_S70_4K_7B (= 41)
            tag_type = tagtypes.M1_S70_4K_7B
        else:
            # Binary: __pyx_k_M1_S70_4K_4B -> tagtypes.M1_S70_4K_4B (= 0)
            tag_type = tagtypes.M1_S70_4K_4B

    # Priority 3: MIFARE Plus 4K
    # Binary: STR@0x0001dd34 'MIFARE Plus 4K'
    elif executor.hasKeyword(_KW_MIFARE_PLUS_4K):
        if uid_len == 7:
            tag_type = tagtypes.M1_S70_4K_7B
        else:
            tag_type = tagtypes.M1_S70_4K_4B

    # Priority 4: MIFARE Classic 1K
    # Binary: STR@0x0001dc38 'MIFARE Classic 1K'
    elif executor.hasKeyword(_KW_MIFARE_CLASSIC_1K):
        if uid_len == 7:
            # Binary: __pyx_k_M1_S50_1K_7B -> tagtypes.M1_S50_1K_7B (= 42)
            tag_type = tagtypes.M1_S50_1K_7B
        else:
            # Binary: __pyx_k_M1_S50_1K_4B -> tagtypes.M1_S50_1K_4B (= 1)
            tag_type = tagtypes.M1_S50_1K_4B

    # Priority 5: Has PRNG or static nonce
    elif b_prng or b_static:
        if executor.hasKeyword(_KW_MIFARE_CLASSIC) or \
           executor.hasKeyword(_KW_MIFARE_PLUS):
            # "MIFARE Classic" (bare) or "MIFARE Plus" (bare) -> POSSIBLE type
            # Binary: __pyx_k_M1_POSSIBLE_4B / __pyx_k_M1_POSSIBLE_7B
            if uid_len == 7:
                tag_type = tagtypes.M1_POSSIBLE_7B
            else:
                tag_type = tagtypes.M1_POSSIBLE_4B
            # Set manufacturer from MANUFACTURER field or default
            # Binary: STR@0x0001dde4 '.*MANUFACTURER:(.*)'
            mfr_raw = executor.getContentFromRegex(_RE_MANUFACTURER)
            if mfr_raw and mfr_raw.strip():
                manufacturer = mfr_raw.strip()
            else:
                manufacturer = 'Default 1K (4B)'
        else:
            # Has PRNG but no MIFARE Classic/Plus keyword -> standard Classic 1K
            if uid_len == 7:
                tag_type = tagtypes.M1_S50_1K_7B
            else:
                tag_type = tagtypes.M1_S50_1K_4B

    # Priority 6: No PRNG, no static nonce
    else:
        if executor.hasKeyword(_KW_MIFARE_CLASSIC) or \
           executor.hasKeyword(_KW_MIFARE_PLUS):
            # POSSIBLE type
            if uid_len == 7:
                tag_type = tagtypes.M1_POSSIBLE_7B
            else:
                tag_type = tagtypes.M1_POSSIBLE_4B
            mfr_raw = executor.getContentFromRegex(_RE_MANUFACTURER)
            if mfr_raw and mfr_raw.strip():
                manufacturer = mfr_raw.strip()
            else:
                manufacturer = 'Default 1K (4B)'
        else:
            # No type identified -> HF14A_OTHER
            # Binary: __pyx_k_HF14A_OTHER -> tagtypes.HF14A_OTHER (= 40)
            tag_type = tagtypes.HF14A_OTHER

    # -------------------------------------------------------------------
    # Build result dict
    # -------------------------------------------------------------------
    result = {
        'found': True,
        'uid': uid,
        'len': uid_len,
        'sak': sak,
        'atqa': atqa,
        'bbcErr': b_bcc_err,
    }

    # 'static' and 'gen1a' keys present for all types except HF14A_OTHER
    if tag_type != tagtypes.HF14A_OTHER:
        result['static'] = b_static
        result['gen1a'] = b_gen1a

    result['type'] = tag_type

    if manufacturer is not None:
        result['manufacturer'] = manufacturer

    return result
