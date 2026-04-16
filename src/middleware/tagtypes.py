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

"""tagtypes -- Tag type registry with DRM bypass.

Reimplemented from tagtypes.so (iCopy-X v1.0.90).
DRM (AES license verification) is BYPASSED — all types always readable.

Ground truth:
    Strings:  docs/v1090_strings/tagtypes_strings.txt
    Audit:    docs/V1090_MODULE_AUDIT.txt (lines 805-881)
    Launcher: tools/launcher_current.py (lines 233-260, DRM bypass fallback)

API:
    types               — dict: type_id → (name, can_read, can_write)
    getReadable()       — list of readable type IDs (DRM bypassed)
    isTagCanRead(typ)   — bool
    isTagCanWrite(typ)  — bool
    getName(typ)        — str
    getUnreadable()     — list of non-readable type IDs
    getM1Types(), getULTypes(), getiClassTypes(), etc.
"""

# ---------------------------------------------------------------------------
# Type ID constants
# ---------------------------------------------------------------------------
M1_S70_4K_4B = 0
M1_S50_1K_4B = 1
ULTRALIGHT = 2
ULTRALIGHT_C = 3
ULTRALIGHT_EV1 = 4
NTAG213_144B = 5
NTAG215_504B = 6
NTAG216_888B = 7
EM410X_ID = 8
HID_PROX_ID = 9
INDALA_ID = 10
AWID_ID = 11
IO_PROX_ID = 12
GPROX_II_ID = 13
SECURAKEY_ID = 14
VIKING_ID = 15
PYRAMID_ID = 16
ICLASS_LEGACY = 17
ICLASS_ELITE = 18
ISO15693_ICODE = 19
LEGIC_MIM256 = 20
FELICA = 21
ISO14443B = 22
T55X7_ID = 23
EM4305_ID = 24
M1_MINI = 25
M1_PLUS_2K = 26
TOPAZ = 27
FDXB_ID = 28
GALLAGHER_ID = 29
JABLOTRON_ID = 30
KERI_ID = 31
NEDAP_ID = 32
NORALSY_ID = 33
PAC_ID = 34
PARADOX_ID = 35
PRESCO_ID = 36
VISA2000_ID = 37
HITAG2_ID = 38
MIFARE_DESFIRE = 39
HF14A_OTHER = 40
M1_S70_4K_7B = 41
M1_S50_1K_7B = 42
M1_POSSIBLE_4B = 43
M1_POSSIBLE_7B = 44
NEXWATCH_ID = 45
ISO15693_ST_SA = 46
ICLASS_SE = 47
UNSUPPORTED = -1

# ---------------------------------------------------------------------------
# Type registry: type_id → (display_name, can_read, can_write)
# ---------------------------------------------------------------------------
types = {
    -1:  ('Unsupported', False, False),
    0:   ('M1 S70 4K 4B', True, True),
    1:   ('M1 S50 1K 4B', True, True),
    2:   ('Ultralight', True, True),
    3:   ('Ultralight C', True, True),
    4:   ('Ultralight EV1', True, True),
    5:   ('NTAG213 144b', True, True),
    6:   ('NTAG215 504b', True, True),
    7:   ('NTAG216 888b', True, True),
    8:   ('EM410x ID', True, True),
    9:   ('HID Prox ID', True, True),
    10:  ('Indala ID', True, True),
    11:  ('AWID ID', True, True),
    12:  ('IO Prox ID', True, True),
    13:  ('GProx II ID', True, True),
    14:  ('Securakey ID', True, True),
    15:  ('Viking ID', True, True),
    16:  ('Pyramid ID', True, True),
    17:  ('iClass Legacy', True, True),
    18:  ('iClass Elite', True, True),
    19:  ('ISO15693 ICODE', True, True),
    20:  ('Legic MIM256', True, False),
    21:  ('Felica', True, True),
    22:  ('ISO14443B', True, False),
    23:  ('T5577', True, True),
    24:  ('EM4305', True, True),
    25:  ('M1 Mini', True, True),
    26:  ('M1 Plus 2K', True, True),
    27:  ('Topaz', True, False),
    28:  ('FDXB ID', True, True),
    29:  ('Gallagher ID', True, True),
    30:  ('Jablotron ID', True, True),
    31:  ('KERI ID', True, True),
    32:  ('NEDAP ID', True, True),
    33:  ('Noralsy ID', True, True),
    34:  ('PAC ID', True, True),
    35:  ('Paradox ID', True, True),
    36:  ('Presco ID', True, True),
    37:  ('Visa2000 ID', True, True),
    38:  ('Hitag2 ID', True, False),
    39:  ('MIFARE DESFire', True, False),
    40:  ('HF14A Other', True, False),
    41:  ('M1 S70 4K 7B', True, True),
    42:  ('M1 S50 1K 7B', True, True),
    43:  ('M1 POSSIBLE 4B', True, True),
    44:  ('M1 POSSIBLE 7B', True, True),
    45:  ('NexWatch ID', True, True),
    46:  ('ISO15693 ST SA', True, True),
    47:  ('iClass SE', True, True),
}


# ---------------------------------------------------------------------------
# DRM bypass — getReadable always returns full list
# Original uses AES decryption of cpuinfo serial.
# Open-source: all readable types returned unconditionally.
# ---------------------------------------------------------------------------
def getReadable():
    """Return list of all readable type IDs. DRM BYPASSED."""
    return [tid for tid, (_, can_read, _) in types.items() if can_read and tid >= 0]


def getUnreadable():
    """Return list of non-readable type IDs."""
    readable = set(getReadable())
    return [tid for tid in types if tid >= 0 and tid not in readable]


def isTagCanRead(typ, infos=None):
    """Return True if tag type can be read."""
    return types.get(typ, ('', False, False))[1]


def isTagCanWrite(typ, infos=None):
    """Return True if tag type can be written."""
    return types.get(typ, ('', False, False))[2]


def getName(typ):
    """Return display name for a tag type."""
    return types.get(typ, ('Unsupported', False, False))[0]


# ---------------------------------------------------------------------------
# Type group queries
# ---------------------------------------------------------------------------
def getM1Types():
    return [0, 1, 25, 26, 41, 42, 43, 44]

def getM11KTypes():
    return [1, 42, 43, 44]

def getM12KTypes():
    return [26]

def getM14KTypes():
    return [0, 41]

def getM17BTypes():
    return [41, 42, 44]

def getM14BTypes():
    return [0, 1, 25, 26, 43]

def getM1MiniTypes():
    return [25]

def getULTypes():
    return [2, 3, 4, 5, 6, 7]

def getiClassTypes():
    return [17, 18, 47]

def getHfOtherTypes():
    return [19, 20, 21, 22, 39, 40, 46]

def getAllHigh():
    return [0, 1, 2, 3, 4, 5, 6, 7, 17, 18, 19, 20, 21, 22, 25, 26,
            39, 40, 41, 42, 43, 44, 46, 47]

def getAllLow():
    return [8, 9, 10, 11, 12, 13, 14, 15, 16, 23, 24, 27,
            28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 45]

def getAllLowCanDump():
    return [23, 24]

def getAllLowNoDump():
    return [t for t in getAllLow() if t not in (23, 24)]


# ---------------------------------------------------------------------------
# DRM internals — bypassed, stubs for API compatibility
# ---------------------------------------------------------------------------
def _get_name(serial_hex=None):
    """DRM decryption. BYPASSED — returns readable list."""
    return getReadable()
