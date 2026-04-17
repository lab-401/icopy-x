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

"""lfread -- LF tag reading for 20+ card types.

Reimplemented from lfread.so (iCopy-X v1.0.90).
Ground truth: archive/lib_transliterated/lfread.py

Iceman-native command forms (P3.5 refactor, 2026-04-17):
  - Every per-tag dispatcher uses iceman `lf <tag> reader` spelling
    (matrix L1213-1237 consolidated 19-row section).  Iceman source:
    /tmp/rrg-pm3/client/src/cmdlf<tag>.c dispatch tables — each entry
    `{"reader", Cmd<Tag>Reader, IfPm3Lf, ...}`.  Matrix verifies:
      - lf em 410x reader   cmdlfem410x.c:891    (matrix L1075)
      - lf hid reader       cmdlfhid.c:723       (matrix L1160)
      - lf indala reader    cmdlfindala.c:1102   (matrix L1225)
      - lf awid reader      cmdlfawid.c:605      (matrix L998)
      - lf io reader        cmdlfio.c:373        (matrix L1226)
      - lf gproxii reader   cmdlfguard.c:417     (matrix L1227)
      - lf securakey reader cmdlfsecurakey.c:300 (matrix L1228)
      - lf viking reader    cmdlfviking.c:248    (matrix L1229)
      - lf pyramid reader   cmdlfpyramid.c:451   (matrix L1230)
      - lf fdxb reader      cmdlffdxb.c:908      (matrix L1110)
      - lf gallagher reader cmdlfgallagher.c:386 (matrix L1144)
      - lf jablotron reader cmdlfjablotron.c:317 (matrix L1223)
      - lf keri reader      cmdlfkeri.c:375      (matrix L1231)
      - lf nedap reader     cmdlfnedap.c:569     (matrix L1232)
      - lf noralsy reader   cmdlfnoralsy.c:291   (matrix L1224)
      - lf pac reader       cmdlfpac.c:401       (matrix L1233)
      - lf paradox reader   cmdlfparadox.c:477   (matrix L1234)
      - lf presco reader    cmdlfpresco.c:363    (matrix L1235)
      - lf visa2000 reader  cmdlfvisa2000.c:306  (matrix L1236)
      - lf nexwatch reader  cmdlfnexwatch.c:585  (matrix L1237)
  - Parsers consume `lfsearch.REGEX_*` (refactored to iceman-native in
    P3.1; see lfsearch.py header) via the shared `read()` / `readCardIdAndRaw`
    / `readFCCNAndRaw` helpers.
  - Per-tag FC/CN shape caveats (iceman-native Raw: always present,
    FC/CN sometimes omitted — matrix L1213): Gallagher emits
    `Facility: %u Card No.: %u` not `FC: %u Card: %u` (cmdlfgallagher.c:88),
    KERI emits `Internal ID: %u, Raw:` not `Card:` (cmdlfkeri.c:176),
    NEDAP emits `ID: %05u subtype: %1u customer code:` (cmdlfnedap.c:146),
    Presco emits `Site code:/User code:` (cmdlfpresco.c:114), NexWatch
    emits only `" Raw : <hex>"` with a space before the colon
    (cmdlfnexwatch.c:247).  `lfsearch.REGEX_RAW` now uses `\\s*:` to
    tolerate both the tight `Raw:` and the NexWatch space-before-colon
    form, so raw capture works for every per-tag demod.  Callers accept
    empty FC/CN; fallback to `Raw:` via `lfsearch.REGEX_RAW` keeps
    success status truthy when a raw field is present.  See gap log
    P3.5.
"""

try:
    import executor
except ImportError:
    try:
        from . import executor
    except ImportError:
        executor = None

try:
    import lfsearch
except ImportError:
    try:
        from . import lfsearch
    except ImportError:
        lfsearch = None

try:
    import lft55xx
except ImportError:
    try:
        from . import lft55xx
    except ImportError:
        lft55xx = None

try:
    import lfem4x05
except ImportError:
    try:
        from . import lfem4x05
    except ImportError:
        lfem4x05 = None

TIMEOUT = 10000


def createRetObj(uid, raw, ret):
    return {'return': ret, 'data': uid, 'raw': raw}


def read(cmd, uid_regex, raw_regex, uid_index=0, raw_index=0):
    """Generic LF per-tag reader driver.

    Sends `cmd` (an iceman-native `lf <tag> reader` string; see module
    docstring citations), parses cached PM3 response with the shared
    iceman-native regex patterns in lfsearch.

    Regex patterns imported via `lfsearch.REGEX_*` are iceman-native as of
    P3.1 refactor (see lfsearch.py module header):
      REGEX_RAW     r'(?:Raw|raw)\\s*:\\s*([xX0-9a-fA-F ]+)' matches iceman
                    `, Raw: <hex>` (cmdlf*.c demod emission), NexWatch's
                    `" Raw : <hex>"` space-before-colon form
                    (cmdlfnexwatch.c:247), and iceman HID lowercase
                    `raw: <hex>` (cmdlfhid.c:235).
      REGEX_CARD_ID r'(?:Card|ID|UID)[\\s:]+([xX0-9a-fA-F ]+)' matches
                    iceman `Card: %u` (Jablotron/Noralsy/Paradox/PAC),
                    `Card %X` (Viking, space-no-colon), `ID: %u` (Paradox
                    Internal ID), `UID... %s` (Indala).
      REGEX_EM410X  r'EM 410x(?:\\s+XL)?\\s+ID\\s+([0-9A-Fa-f]+)' matches
                    iceman `EM 410x ID %010llX` (cmdlfem410x.c:115) and
                    XL variant at :118.
      REGEX_HID     r'raw:\\s+([0-9A-Fa-f]+)' matches iceman
                    `raw: %08x%08x%08x` (cmdlfhid.c:235).
      REGEX_ANIMAL  r'Animal ID\\.+\\s+([0-9\\-]+)' matches iceman
                    `Animal ID........... %03u-%012llu` (cmdlffdxb.c:572/578).
    """
    ret = executor.startPM3Task(cmd, TIMEOUT)
    if ret == -1:
        return createRetObj(None, None, -1)
    content = executor.getPrintContent()
    if not content or executor.isEmptyContent():
        return createRetObj(None, None, -1)
    uid_group = uid_index if uid_index else 0
    raw_group = raw_index if raw_index else 0
    uid = executor.getContentFromRegexG(uid_regex, uid_group)
    raw = executor.getContentFromRegexG(raw_regex, raw_group)
    if uid:
        uid = lfsearch.cleanHexStr(uid.strip())
    if raw:
        raw = lfsearch.cleanHexStr(raw.strip())
    if uid or raw:
        return createRetObj(uid, raw, 1)
    return createRetObj(None, None, -1)


def readCardIdAndRaw(cmd, uid_index=0, raw_index=0):
    """Iceman-native per-tag: parse `Card|ID|UID` + `Raw:` from cache.

    Used by: Viking, ProxIO, Jablotron, Nedap, Noralsy, PAC, Presco,
    Visa2000, NexWatch.  Shape spec: lfsearch.REGEX_CARD_ID /
    REGEX_RAW (iceman-native, see lfsearch.py module header).
    """
    return read(cmd, lfsearch.REGEX_CARD_ID, lfsearch.REGEX_RAW,
                uid_index=uid_index, raw_index=raw_index)


def readFCCNAndRaw(cmd, uid_index=0, raw_index=0):
    """Iceman-native per-tag: parse `FC: %d Card: %u` + `Raw:` from cache.

    Used by: AWID (cmdlfawid.c:248), GProx-II (cmdlfguard.c:186),
    Securakey (cmdlfsecurakey.c:113), Pyramid (cmdlfpyramid.c:161),
    Keri (cmdlfkeri.c:176 — `Internal ID:` only, no FC/CN),
    Gallagher (cmdlfgallagher.c:88 — `Facility:`/`Card No.:` not
    `FC:`/`Card:`), Paradox (cmdlfparadox.c:224).

    Iceman-native FC/CN regex lives in lfsearch.py:
      _RE_FC = r'FC:\\s+([xX0-9a-fA-F]+)'
      _RE_CN = r'(CN|Card(?:\\s+No\\.)?)[\\s:]+(\\d+)'

    Per matrix L1213 + iceman source audit: Keri/Gallagher/Nedap/Presco/
    NexWatch emit alternative field labels; lfsearch._RE_FC won't match
    `Facility:` (Gallagher) and `_RE_CN` won't match `Internal ID:`
    (Keri) or `ID:` alone (Nedap, plus subtype/customer).
    `getFCCN()` falls back to `'FC,CN: X,X'` sentinel when regex misses,
    keeping `uid` truthy so caller's `if uid or raw:` still returns
    success when Raw: is present. See gap log P3.5.
    """
    ret = executor.startPM3Task(cmd, TIMEOUT)
    if ret == -1:
        return createRetObj(None, None, -1)
    content = executor.getPrintContent()
    if not content or executor.isEmptyContent():
        return createRetObj(None, None, -1)
    uid = lfsearch.getFCCN()
    raw = executor.getContentFromRegexG(lfsearch.REGEX_RAW, 1)
    if raw:
        raw = lfsearch.cleanHexStr(raw.strip())
    if uid or raw:
        return createRetObj(uid, raw, 1)
    return createRetObj(None, None, -1)


def readEM410X(listener=None, infos=None):
    return read('lf em 410x reader', lfsearch.REGEX_EM410X, lfsearch.REGEX_RAW,
                uid_index=1, raw_index=0)


def readHID(listener=None, infos=None):
    return read('lf hid reader', lfsearch.REGEX_HID, lfsearch.REGEX_RAW,
                uid_index=1, raw_index=0)


def readIndala(listener=None, infos=None):
    return read('lf indala reader', lfsearch.REGEX_RAW, lfsearch.REGEX_RAW,
                uid_index=1, raw_index=1)


def readAWID(listener=None, infos=None):
    return readFCCNAndRaw('lf awid reader')


def readProxIO(listener=None, infos=None):
    return readCardIdAndRaw('lf io reader')


def readGProx2(listener=None, infos=None):
    return readFCCNAndRaw('lf gproxii reader')


def readSecurakey(listener=None, infos=None):
    return readFCCNAndRaw('lf securakey reader')


def readViking(listener=None, infos=None):
    return readCardIdAndRaw('lf viking reader')


def readPyramid(listener=None, infos=None):
    return readFCCNAndRaw('lf pyramid reader')


def readT55XX(listener=None, infos=None):
    """Read T55XX — detect + chk + dump, return dict for read.so success path."""
    if lft55xx is None:
        return createRetObj(None, None, -1)
    result = lft55xx.chkAndDumpT55xx(listener)
    if isinstance(result, dict):
        return result
    return createRetObj(None, None, -1)


def readEM4X05(listener=None, infos=None):
    """Read EM4X05 — info + dump, return dict for read.so success path."""
    if lfem4x05 is None:
        return createRetObj(None, None, -1)
    return lfem4x05.infoAndDumpEM4x05ByKey()


def readFDX(listener=None, infos=None):
    return read('lf fdxb reader', lfsearch.REGEX_ANIMAL, lfsearch.REGEX_RAW,
                uid_index=1, raw_index=0)


def readGALLAGHER(listener=None, infos=None):
    return readFCCNAndRaw('lf gallagher reader')


def readJablotron(listener=None, infos=None):
    return readCardIdAndRaw('lf jablotron reader')


def readKeri(listener=None, infos=None):
    return readFCCNAndRaw('lf keri reader')


def readNedap(listener=None, infos=None):
    return readCardIdAndRaw('lf nedap reader')


def readNoralsy(listener=None, infos=None):
    return readCardIdAndRaw('lf noralsy reader')


def readPAC(listener=None, infos=None):
    return readCardIdAndRaw('lf pac reader')


def readParadox(listener=None, infos=None):
    return readFCCNAndRaw('lf paradox reader')


def readPresco(listener=None, infos=None):
    return readCardIdAndRaw('lf presco reader')


def readVisa2000(listener=None, infos=None):
    return readCardIdAndRaw('lf visa2000 reader')


def readNexWatch(listener=None, infos=None):
    return readCardIdAndRaw('lf nexwatch reader')


READ = {
    8: readEM410X,
    9: readHID,
    10: readIndala,
    11: readAWID,
    12: readProxIO,
    13: readGProx2,
    14: readSecurakey,
    15: readViking,
    16: readPyramid,
    23: readT55XX,
    24: readEM4X05,
    28: readFDX,
    29: readGALLAGHER,
    30: readJablotron,
    31: readKeri,
    32: readNedap,
    33: readNoralsy,
    34: readPAC,
    35: readParadox,
    36: readPresco,
    37: readVisa2000,
    45: readNexWatch,
}
