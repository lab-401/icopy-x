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

# container.py — reimplementation of container.so get_public_id()
#
# The function maps (type, uid_len) → short display name shown on WarningWriteActivity.

# Mapping: type_id → display name
# len only matters for types 40 (Gen1a 4B vs 7B)
_PUBLIC_ID = {
    0: 'M4-4b',    # MF S70 4K 4B
    1: 'M1-4b',    # MF S50 1K 4B
    2: 'UL',       # Ultralight
    3: 'UL-C',     # Ultralight C
    4: 'ULEv1',    # Ultralight EV1
    5: 'Ntag',     # NTAG213
    6: 'Ntag',     # NTAG215
    7: 'Ntag',     # NTAG216
    8: 'ID1',      # EM410x
    9: 'ID1',      # HID Prox
    10: 'ID1',     # Indala
    11: 'ID1',     # AWID
    12: 'ID1',     # IO Prox
    13: 'ID1',     # GProx II
    14: 'ID1',     # Securakey
    15: 'ID1',     # Viking
    16: 'ID1',     # Pyramid
    17: 'iCL',     # iClass Legacy
    18: 'iCE',     # iClass Elite
    19: 'ICODE',   # ISO15693 ICODE
    # 20: ISO15693 ST SA — not in container.so mapping
    23: 'ID1',     # T5577
    24: 'ID2',     # EM4305
    25: 'M1-4b',   # MF Mini
    26: 'M4-4b',   # MF Plus 2K
    28: 'ID1',     # FDXB
    29: 'ID1',     # Gallagher
    30: 'ID1',     # Jablotron
    31: 'ID1',     # KERI
    32: 'ID1',     # NEDAP
    33: 'ID1',     # Noralsy
    34: 'ID1',     # PAC
    35: 'ID1',     # Paradox
    36: 'ID1',     # Presco
    37: 'ID1',     # Visa2000
    40: 'M1-4b',   # Gen1a 4B (len=4) / Gen1a 7B (len=7) — see below
    41: 'M4-7b',   # MF S70 4K 7B
    42: 'M1-7b',   # MF S50 1K 7B
    43: 'M1-4b',   # MF Plus 2K Gen2 4B
    44: 'M1-7b',   # MF Plus 2K Gen2 7B
    45: 'ID1',     # NexWatch
    46: '\u7279\u65af\u8054',  # 特斯联
}


def get_public_id(infos):
    """Return the short display name for the WarningWriteActivity TYPE: field.

    Args:
        infos: dict with at least 'type' (int) and optionally 'len' (int).

    Returns:
        str display name, e.g. 'M1-4b', 'ID1', 'UL', 'iCL'.
    """
    typ = infos.get('type', -1)
    uid_len = infos.get('len', 4)

    # Special case: type 40 (Gen1a) — len distinguishes 4B vs 7B
    if typ == 40:
        return 'M1-7b' if uid_len >= 7 else 'M1-4b'

    return _PUBLIC_ID.get(typ, '')
