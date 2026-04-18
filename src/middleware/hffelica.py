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

"""hffelica -- FeliCa tag parser.

Reimplemented from hffelica.so (iCopy-X v1.0.90, Cython 0.29.21, ARM 32-bit).

Post compat-flip (Phase 3) — iceman-native sentinels.

Ground truth:
    Strings:    docs/v1090_strings/hffelica_strings.txt
    Source:     /tmp/rrg-pm3/client/src/cmdhffelica.c

Iceman emissions (hf felica reader):
    Success: cmdhffelica.c:1183 `PrintAndLogEx(SUCCESS, "IDm: " _GREEN_("%s"),
             sprint_hex_inrow(card.IDm, sizeof(card.IDm)))`
        → single line `"IDm: XX XX XX XX XX XX XX XX"`
        The legacy header `"FeliCa tag info"` is NOT emitted under iceman
        (legacy fork cmdhffelica.c:1835 `readFelicaUid` emitted it; iceman
        replaced that with `read_felica_uid` @ L1144 which only emits `IDm:`).
    Timeout: cmdhffelica.c:1431 `PrintAndLogEx(WARNING, "card timeout")`.

API:
    parser() -> dict
"""

# Module-level constants (from audit: V1090_MODULE_AUDIT.txt)
CMD = 'hf felica reader'
TIMEOUT = 10000

# ── Iceman-native sentinels ───────────────────────────────────────────
# Success: iceman emits `"IDm: %s"` (cmdhffelica.c:1183).
#   Include the trailing colon in the keyword so we don't false-positive on
#   other IDm mentions (e.g., argument help strings emitted in error paths).
#   Match is case-sensitive (hasKeyword → re.search); iceman capitalises
#   `IDm` consistently.
_KW_FOUND = r'IDm:\s'
# Timeout: iceman emits `"card timeout"` at cmdhffelica.c:1431. The full
#   trace often includes a status code `(-N)` but `card timeout` is a
#   stable substring under both iceman and legacy.
_KW_TIMEOUT = 'card timeout'

# IDm extraction: iceman `IDm: XX XX XX XX XX XX XX XX` (8 hex bytes,
# space-separated) emitted by sprint_hex_inrow. Capture the tail after
# `IDm`; strip whitespace & spaces to yield `:01FE010203040506` matching
# the pre-existing scan-cache shape documented in template.py:684.
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

    # Timeout or no tag (iceman cmdhffelica.c:1431).
    if executor.hasKeyword(_KW_TIMEOUT):
        return {'found': False}

    # FeliCa detected via iceman `IDm: ...` emission (cmdhffelica.c:1183).
    if executor.hasKeyword(_KW_FOUND):
        idm_raw = executor.getContentFromRegex(_RE_IDM)
        idm = ''
        if idm_raw:
            # The regex captures everything after 'IDm', including
            # ': 01 FE 01 02 03 04 05 06'. Strip whitespace, remove
            # internal spaces → ':01FE010203040506'. Leading colon is
            # preserved on purpose — it acts as a sentinel for downstream
            # scan-cache consumers (template.py:684).
            idm = idm_raw.strip().replace(' ', '')
        return {'found': True, 'idm': idm}

    return {'found': False}
