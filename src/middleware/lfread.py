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

"""lfread -- LF tag reading for 20+ card types.

Reimplemented from lfread.so (iCopy-X v1.0.90).
Ground truth: archive/lib_transliterated/lfread.py
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
    return read(cmd, lfsearch.REGEX_CARD_ID, lfsearch.REGEX_RAW,
                uid_index=uid_index, raw_index=raw_index)


def readFCCNAndRaw(cmd, uid_index=0, raw_index=0):
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
    return read('lf em 410x_read', lfsearch.REGEX_EM410X, lfsearch.REGEX_RAW,
                uid_index=1, raw_index=0)


def readHID(listener=None, infos=None):
    return read('lf hid read', lfsearch.REGEX_HID, lfsearch.REGEX_RAW,
                uid_index=1, raw_index=0)


def readIndala(listener=None, infos=None):
    return read('lf indala read', lfsearch.REGEX_RAW, lfsearch.REGEX_RAW,
                uid_index=1, raw_index=1)


def readAWID(listener=None, infos=None):
    return readFCCNAndRaw('lf awid read')


def readProxIO(listener=None, infos=None):
    return readCardIdAndRaw('lf io read')


def readGProx2(listener=None, infos=None):
    return readFCCNAndRaw('lf gproxii read')


def readSecurakey(listener=None, infos=None):
    return readFCCNAndRaw('lf securakey read')


def readViking(listener=None, infos=None):
    return readCardIdAndRaw('lf viking read')


def readPyramid(listener=None, infos=None):
    return readFCCNAndRaw('lf pyramid read')


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
    return read('lf fdx read', lfsearch.REGEX_ANIMAL, lfsearch.REGEX_RAW,
                uid_index=1, raw_index=0)


def readGALLAGHER(listener=None, infos=None):
    return readFCCNAndRaw('lf gallagher read')


def readJablotron(listener=None, infos=None):
    return readCardIdAndRaw('lf jablotron read')


def readKeri(listener=None, infos=None):
    return readFCCNAndRaw('lf keri read')


def readNedap(listener=None, infos=None):
    return readCardIdAndRaw('lf nedap read')


def readNoralsy(listener=None, infos=None):
    return readCardIdAndRaw('lf noralsy read')


def readPAC(listener=None, infos=None):
    return readCardIdAndRaw('lf pac read')


def readParadox(listener=None, infos=None):
    return readFCCNAndRaw('lf paradox read')


def readPresco(listener=None, infos=None):
    return readCardIdAndRaw('lf presco read')


def readVisa2000(listener=None, infos=None):
    return readCardIdAndRaw('lf visa2000 read')


def readNexWatch(listener=None, infos=None):
    return readCardIdAndRaw('lf nexwatch read')


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
