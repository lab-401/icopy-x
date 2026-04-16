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

"""PM3 response fixtures for every middleware code path.

Each fixture is a dict mapping PM3 command substrings to response text.
The capture system uses these to mock PM3 behavior for specific scenarios,
triggering every UI state in the original app.

Built from exhaustive enumeration of scan.py, hf14ainfo.py, hfsearch.py,
lfsearch.py, hfmfkeys.py, hfmfread.py, hfmfwrite.py, and all tag handlers.

CRITICAL FIXTURE RULE:
  The scan pipeline STOPS when startPM3Task returns -1 (timeout).
  For tags found via hf sea / lf sea (stages 2+), the earlier stages
  must return 0 with "no tag" CONTENT, NOT -1.
  Use HF14A_NO_TAG and HFSEA_NO_TAG constants for this.
"""

# Common "no tag" responses that let the pipeline CONTINUE (return 0, not -1)
HF14A_NO_TAG = (0, """[usb] pm3 --> hf 14a info
[!] Card doesn't support standard iso14443-3 anticollision
""")

HFSEA_NO_TAG = (0, """[usb] pm3 --> hf search
[!] No known/supported 13.56 MHz tags found
""")

LFSEA_NO_TAG = (0, """[usb] pm3 --> lf search
[!] No data found!
[-] No known 125/134 kHz tags found!
""")

# ============================================================================
# SCAN OUTCOMES — Tag detection (scan.py → parsers)
# ============================================================================

# --- No tag found (all scan stages fail) ---
SCAN_NO_TAG = {
    '_default_return': -1,  # startPM3Task returns -1 = timeout = no tag
    '_description': 'No tag on reader — all scans timeout',
}

# --- HF 14443-A: MIFARE Classic 1K, 4-byte UID ---
# Gen1a check response for non-magic cards (cgetblk fails = not Gen1a)
CGETBLK_NOT_GEN1A = (0, """[-] Can't set magic card block
[-] isOk:00
""")

SCAN_MF_CLASSIC_1K_4B = {
    'hf 14a info': (0, """[usb] pm3 --> hf 14a info

[+]  UID: 2C AD C2 72
[+] ATQA: 00 04
[+]  SAK: 08 [2]
[+] Possible types:
[+]    MIFARE Classic 1K / Classic 1K CL2
[=] proprietary non iso14443-4 card found, RATS not supported
[+] Prng detection: weak
"""),
    'hf 14a reader': (0, """[usb] pm3 --> hf 14a reader

[+]  UID: 2C AD C2 72
"""),
    'hf mf cgetblk': CGETBLK_NOT_GEN1A,
    '_description': 'MIFARE Classic 1K, 4-byte UID (SAK 08)',
    '_tag_type': 1,  # M1_S50_1K_4B
}

# --- HF 14443-A: MIFARE Classic 1K, 7-byte UID ---
SCAN_MF_CLASSIC_1K_7B = {
    'hf 14a info': (0, """[usb] pm3 --> hf 14a info

[+]  UID: 04 A1 B2 C3 D4 E5 F6
[+] ATQA: 00 44
[+]  SAK: 08 [2]
[+] Possible types:
[+]    MIFARE Classic 1K / Classic 1K CL2
[=] proprietary non iso14443-4 card found, RATS not supported
[+] Prng detection: weak
"""),
    'hf mf cgetblk': CGETBLK_NOT_GEN1A,
    '_description': 'MIFARE Classic 1K, 7-byte UID (SAK 08)',
    '_tag_type': 42,  # M1_S50_1K_7B
}

# --- HF 14443-A: MIFARE Classic 4K, 4-byte UID ---
SCAN_MF_CLASSIC_4K_4B = {
    'hf 14a info': (0, """[usb] pm3 --> hf 14a info

[+]  UID: AA BB CC DD
[+] ATQA: 00 02
[+]  SAK: 18 [2]
[+] Possible types:
[+]    MIFARE Classic 4K / Classic 4K CL2
[=] proprietary non iso14443-4 card found, RATS not supported
[+] Prng detection: weak
"""),
    'hf mf cgetblk': CGETBLK_NOT_GEN1A,
    '_description': 'MIFARE Classic 4K, 4-byte UID (SAK 18)',
    '_tag_type': 0,  # M1_S70_4K_4B
}

# --- HF 14443-A: MIFARE Classic 4K, 7-byte UID ---
SCAN_MF_CLASSIC_4K_7B = {
    'hf 14a info': (0, """[usb] pm3 --> hf 14a info

[+]  UID: 04 11 22 33 44 55 66
[+] ATQA: 00 42
[+]  SAK: 18 [2]
[+] Possible types:
[+]    MIFARE Classic 4K / Classic 4K CL2
[=] proprietary non iso14443-4 card found, RATS not supported
[+] Prng detection: weak
"""),
    'hf mf cgetblk': CGETBLK_NOT_GEN1A,
    '_description': 'MIFARE Classic 4K, 7-byte UID (SAK 18)',
    '_tag_type': 41,  # M1_S70_4K_7B
}

# --- HF 14443-A: MIFARE Mini ---
SCAN_MF_MINI = {
    'hf 14a info': (0, """[usb] pm3 --> hf 14a info

[+]  UID: DE AD BE EF
[+] ATQA: 00 04
[+]  SAK: 09 [2]
[+] Possible types:
[+]    MIFARE Mini
[+]    MIFARE Classic 1K / Classic 1K CL2
[=] proprietary non iso14443-4 card found, RATS not supported
[+] Prng detection: weak
"""),
    'hf mf cgetblk': CGETBLK_NOT_GEN1A,
    '_description': 'MIFARE Mini (SAK 09)',
    '_tag_type': 25,  # M1_MINI
}

# --- HF 14443-A: MIFARE Ultralight ---
# Multi-step: hf 14a info → hf mf cgetblk 0 (Gen1a check, fails) → hf mfu info
# Traced from real scan.so under QEMU: 3 PM3 commands, TAG FOUND ✓
SCAN_MF_ULTRALIGHT = {
    'hf 14a info': (0, """[usb] pm3 --> hf 14a info

[+]  UID: 04 A1 B2 C3 D4 E5 F6
[+] ATQA: 00 44
[+]  SAK: 00 [2]
[+] Possible types:
[+]    MIFARE Ultralight
[=] proprietary non iso14443-4 card found, RATS not supported
"""),
    'hf mfu info': (0, """[usb] pm3 --> hf mfu info

[=] --- Tag Information ---------
[=]       TYPE: Ultralight (MF0ICU1)
[=]        UID: 04 A1 B2 C3 D4 E5 F6
[=]    UID LEN: 7
"""),
    '_description': 'MIFARE Ultralight',
    '_tag_type': 2,  # ULTRALIGHT
}

# --- HF 14443-A: MIFARE Ultralight C ---
SCAN_MF_ULTRALIGHT_C = {
    'hf 14a info': (0, """[usb] pm3 --> hf 14a info

[+]  UID: 04 A1 B2 C3 D4 E5 F6
[+] ATQA: 00 44
[+]  SAK: 00 [2]
[+] Possible types:
[+]    MIFARE Ultralight
[=] proprietary non iso14443-4 card found, RATS not supported
"""),
    'hf mfu info': (0, """[usb] pm3 --> hf mfu info

[=] --- Tag Information ---------
[=]       TYPE: Ultralight C (MF0ULC)
[=]        UID: 04 A1 B2 C3 D4 E5 F6
[=]    UID LEN: 7
"""),
    '_description': 'MIFARE Ultralight C',
    '_tag_type': 3,  # ULTRALIGHT_C
}

# --- HF 14443-A: MIFARE Ultralight EV1 ---
SCAN_MF_ULTRALIGHT_EV1 = {
    'hf 14a info': (0, """[usb] pm3 --> hf 14a info

[+]  UID: 04 A1 B2 C3 D4 E5 F6
[+] ATQA: 00 44
[+]  SAK: 00 [2]
[+] Possible types:
[+]    MIFARE Ultralight
[=] proprietary non iso14443-4 card found, RATS not supported
"""),
    'hf mfu info': (0, """[usb] pm3 --> hf mfu info

[=] --- Tag Information ---------
[=]       TYPE: Ultralight EV1 (MF0UL1101)
[=]        UID: 04 A1 B2 C3 D4 E5 F6
[=]    UID LEN: 7
"""),
    '_description': 'MIFARE Ultralight EV1',
    '_tag_type': 4,  # ULTRALIGHT_EV1
}

# --- HF 14443-A: NTAG215 ---
# Multi-step: hf 14a info → hf mf cgetblk 0 (Gen1a check, fails) → hf mfu info
# Traced from real scan.so under QEMU: 3 PM3 commands, TAG FOUND ✓
SCAN_NTAG215 = {
    'hf 14a info': (0, """[usb] pm3 --> hf 14a info

[+]  UID: 04 B1 C2 D3 E4 F5 A6
[+] ATQA: 00 44
[+]  SAK: 00 [2]
[+] Possible types:
[+]    NTAG215
[=] proprietary non iso14443-4 card found, RATS not supported
"""),
    'hf mfu info': (0, """[usb] pm3 --> hf mfu info

[=] --- Tag Information ---------
[=]       TYPE: NTAG 215 504bytes (NT2H1511G0DU)
[=]        UID: 04 B1 C2 D3 E4 F5 A6
[=]    UID LEN: 7
"""),
    '_description': 'NTAG215 (504 bytes)',
    '_tag_type': 6,  # NTAG215_504B
}

# --- HF 14443-A: NTAG213 ---
SCAN_NTAG213 = {
    'hf 14a info': (0, """[usb] pm3 --> hf 14a info

[+]  UID: 04 B1 C2 D3 E4 F5 A6
[+] ATQA: 00 44
[+]  SAK: 00 [2]
[+] Possible types:
[+]    NTAG213
[=] proprietary non iso14443-4 card found, RATS not supported
"""),
    'hf mfu info': (0, """[usb] pm3 --> hf mfu info

[=] --- Tag Information ---------
[=]       TYPE: NTAG 213 144bytes (NT2H1311G0DU)
[=]        UID: 04 B1 C2 D3 E4 F5 A6
[=]    UID LEN: 7
"""),
    '_description': 'NTAG213 (144 bytes)',
    '_tag_type': 5,  # NTAG213_144B
}

# --- HF 14443-A: NTAG216 ---
SCAN_NTAG216 = {
    'hf 14a info': (0, """[usb] pm3 --> hf 14a info

[+]  UID: 04 B1 C2 D3 E4 F5 A6
[+] ATQA: 00 44
[+]  SAK: 00 [2]
[+] Possible types:
[+]    NTAG216
[=] proprietary non iso14443-4 card found, RATS not supported
"""),
    'hf mfu info': (0, """[usb] pm3 --> hf mfu info

[=] --- Tag Information ---------
[=]       TYPE: NTAG 216 888bytes (NT2H1611G0DU)
[=]        UID: 04 B1 C2 D3 E4 F5 A6
[=]    UID LEN: 7
"""),
    '_description': 'NTAG216 (888 bytes)',
    '_tag_type': 7,  # NTAG216_888B
}

# --- HF 14443-A: MIFARE DESFire (with ATS) ---
SCAN_MF_DESFIRE = {
    # Route C: highTypes → scan_hfsea → "hf sea"
    # hfsearch.parser() checks hasKeyword("MIFARE") → isMifare=True
    # Then scan.so redirects to scan_14a → "hf 14a info"
    # hf14ainfo.parser() checks hasKeyword("MIFARE DESFire") → type=39
    'hf sea': (0, """[usb] pm3 --> hf search

[+] MIFARE DESFire card found
"""),
    'hf 14a info': (0, """[usb] pm3 --> hf 14a info

[+]  UID: 04 C1 D2 E3 F4 A5 B6
[+] ATQA: 03 44
[+]  SAK: 20 [2]
[+] Possible types:
[+]    MIFARE DESFire MF3ICD40
[+] ATS: 06 75 77 81 02 80
"""),
    '_description': 'MIFARE DESFire — scan_hfsea→isMifare→scan_14a→DESFire',
    '_tag_type': 39,  # MIFARE_DESFIRE
}

# --- HF 14443-A: Multiple tags ---
SCAN_MULTI_TAGS = {
    'hf 14a info': (0, """[usb] pm3 --> hf 14a info

[!] Multiple tags detected. Collision after bit 32
[!] Multiple tags detected
"""),
    '_description': 'Multiple tags detected (collision)',
    '_tag_type': None,  # hasMulti=True
}

# --- HF 14443-A: Static nonce (POSSIBLE type) ---
# For M1_POSSIBLE_4B: output has "MIFARE Classic" and "MIFARE Plus" (bare, no 1K/4K qualifier)
# The parser only reaches the POSSIBLE case when neither Classic 1K nor Classic 4K is present.
SCAN_MF_POSSIBLE_4B = {
    'hf 14a info': (0, """[usb] pm3 --> hf 14a info

[+]  UID: 01 02 03 04
[+] ATQA: 00 04
[+]  SAK: 08 [2]
[+] Possible types:
[+]    MIFARE Classic
[+]    MIFARE Plus 2K / Plus EV1 2K
[=] proprietary non iso14443-4 card found, RATS not supported
[+] Static nonce: yes
"""),
    'hf mf cgetblk': CGETBLK_NOT_GEN1A,
    '_description': 'MIFARE with static nonce (POSSIBLE 4B)',
    '_tag_type': 43,  # M1_POSSIBLE_4B — because static nonce + "MIFARE Classic" but also "MIFARE Plus"
}

# --- HF 14443-A: HF14A_OTHER (unknown 14A tag) ---
SCAN_HF14A_OTHER = {
    # Route C: highTypes → scan_hfsea → "hf sea"
    # hfsearch.parser() → hasKeyword("MIFARE") matches (14A tag) → isMifare=True
    # Redirects to scan_14a → "hf 14a info"
    # hf14ainfo.parser() → no known MIFARE type matches → fallback to HF14A_OTHER(40)
    'hf sea': (0, """[usb] pm3 --> hf search

[+] MIFARE card found
"""),
    'hf 14a info': (0, """[usb] pm3 --> hf 14a info

[+]  UID: FF EE DD CC
[+] ATQA: 00 04
[+]  SAK: 28 [2]
[=] proprietary non iso14443-4 card found, RATS not supported
"""),
    '_description': 'Unknown HF 14443-A tag — scan_hfsea→isMifare→scan_14a→no match→type 40',
    '_tag_type': 40,  # HF14A_OTHER
}

# --- HF Search: iCLASS ---
# Multi-step: hf 14a info → lf sea → hf sea → 5× hf iclass rdbl (key check)
# Traced from real scan.so under QEMU: 8 PM3 commands
# Keys tried: AFA785A7DAB33378 (×2), 2020666666668888, 6666202066668888, 2020666666668888 e
# Standard key must succeed, others must fail (return 0, not -1, to avoid pipeline stop)
SCAN_ICLASS = {
    'hf 14a info': HF14A_NO_TAG,
    'lf sea': LFSEA_NO_TAG,
    'hf sea': (0, """[usb] pm3 --> hf search

[+] Valid iCLASS tag / PicoPass tag found
"""),
    # Standard iCLASS key — MUST match before generic 'hf iclass rdbl' (dict ordering)
    'hf iclass rdbl b 01 k AFA785A7DAB33378': (0, """[usb] pm3 --> hf iclass rdbl b 01 k AFA785A7DAB33378

Block 01 : 12 FF FF FF 7F 1F FF 3C
"""),
    # Generic rdbl — catches non-standard keys (2020666666668888, 6666202066668888, elite)
    # Return 0 (not -1) so pipeline continues; content shows failure
    'hf iclass rdbl': (0, """[usb] pm3 --> hf iclass rdbl

[-] Error reading block
"""),
    'hf iclass info': (0, """[usb] pm3 --> hf iclass info

[=] CSN: 00 0B 0F FF F7 FF 12 E0
[=] CC:  D5 F8 FF FF FF FF FF FE
"""),
    '_description': 'iCLASS / PicoPass tag',
    '_tag_type': 17,  # ICLASS_LEGACY
}

# --- HF Search: iCLASS Elite ---
# Standard key FAILS, elite key (2020666666668888) SUCCEEDS → type 18
SCAN_ICLASS_ELITE = {
    # Route C: highTypes → scan_hfsea → "hf sea" → "Valid iCLASS tag" → isIclass
    # hficlass.chk_type():
    #   Step 1-3: ALL legacy rdbl key checks FAIL (AFA785, 2020666, 6666202)
    #   Step 4: chkKeys() → "hf iclass chk f {dic}" → "Found valid key" → ICLASS_ELITE
    'hf sea': (0, """[usb] pm3 --> hf search

[+] Valid iCLASS tag / PicoPass tag found
"""),
    # ALL rdbl key checks fail — no " : hex" pattern → checkKey=False for all 3 legacy keys
    'hf iclass rdbl': (0, """[-] Error reading block
"""),
    # chkKeys() dictionary check finds an elite key
    'hf iclass chk': (0, """[usb] pm3 --> hf iclass chk

[+] Found valid key ae a6 84 a6 da b2 12 32
"""),
    'hf iclass info': (0, """[usb] pm3 --> hf iclass info

[=] CSN: 00 0B 0F FF F7 FF 12 E0
[=] CC:  D5 F8 FF FF FF FF FF FE
"""),
    '_description': 'iCLASS Elite — chk_type: all legacy rdbl fail → chkKeys finds elite key → type 18',
    '_tag_type': 18,  # ICLASS_ELITE
}

# --- HF Search: iCLASS SE ---
# ALL key checks FAIL → type 47
SCAN_ICLASS_SE = {
    # Route C: highTypes → scan_hfsea → "hf sea" → "Valid iCLASS tag" → isIclass
    # hficlass.chk_type(): all legacy keys fail, chkKeys fails, SE reader not found
    # → parser() defaults to ICLASS_ELITE(18)
    # QEMU LIMITATION: iClass SE requires USB SE reader hardware, cannot be
    # distinguished from Elite under QEMU. Scan always returns type=18.
    'hf sea': (0, """[usb] pm3 --> hf search

[+] Valid iCLASS tag / PicoPass tag found
"""),
    # All rdbl key checks return error (no space-colon format → regex fails → key fails)
    'hf iclass rdbl': (0, """[-] Error reading block
"""),
    # chkKeys → hf iclass chk → no valid key found
    'hf iclass chk': (0, """[usb] pm3 --> hf iclass chk

[-] No valid key found
"""),
    'hf iclass info': (0, """[usb] pm3 --> hf iclass info

[=] CSN: 00 0B 0F FF F7 FF 12 E0
[=] CC:  D5 F8 FF FF FF FF FF FE
"""),
    '_description': 'iCLASS SE — under QEMU detects as ELITE(18), SE needs USB reader',
    '_tag_type': 18,  # Detected as ELITE under QEMU (SE requires hardware)
}

# --- HF Search: ISO15693 ICODE ---
SCAN_ISO15693_ICODE = {
    'hf 14a info': HF14A_NO_TAG,
    'lf sea': LFSEA_NO_TAG,
    'hf sea': (0, """[usb] pm3 --> hf search

[+] Valid ISO15693 tag found
[+] UID: E0 04 01 00 12 34 56 78
"""),
    '_description': 'ISO15693 ICODE',
    '_tag_type': 19,  # ISO15693_ICODE
}

# --- HF Search: ISO15693 ST Microelectronics ---
SCAN_ISO15693_ST = {
    'hf 14a info': HF14A_NO_TAG,
    'lf sea': LFSEA_NO_TAG,
    'hf sea': (0, """[usb] pm3 --> hf search

[+] Valid ISO15693 tag found
[+] UID: E0 02 08 01 12 34 56 78
[+] ST Microelectronics SA France
"""),
    '_description': 'ISO15693 ST Microelectronics SA',
    '_tag_type': 46,  # ISO15693_ST_SA
}

# --- HF Search: LEGIC Prime ---
SCAN_LEGIC = {
    'hf 14a info': HF14A_NO_TAG,
    'lf sea': LFSEA_NO_TAG,
    'hf sea': (0, """[usb] pm3 --> hf search

[+] Valid LEGIC Prime tag found
[+] MCD: 3C
[+] MSN: 01 02 03
"""),
    '_description': 'LEGIC Prime MIM256',
    '_tag_type': 20,  # LEGIC_MIM256
}

# --- HF Search: ISO14443-B ---
SCAN_ISO14443B = {
    'hf 14a info': HF14A_NO_TAG,
    'lf sea': LFSEA_NO_TAG,
    'hf sea': (0, """[usb] pm3 --> hf search

[+] Valid ISO14443-B tag found
[+] UID: AA BB CC DD
[+] ATQB: 50 00 00 00
"""),
    '_description': 'ISO14443-B tag',
    '_tag_type': 22,  # ISO14443B
}

# --- HF Search: Topaz ---
SCAN_TOPAZ = {
    'hf 14a info': HF14A_NO_TAG,
    'lf sea': LFSEA_NO_TAG,
    'hf sea': (0, """[usb] pm3 --> hf search

[+] Valid Topaz tag found
[+] UID: 11 22 33 44 55 66 77
[+] ATQA: C0 04
"""),
    '_description': 'Topaz tag',
    '_tag_type': 27,  # TOPAZ
}

# --- FeliCa ---
SCAN_FELICA = {
    'hf 14a info': HF14A_NO_TAG,
    'hf sea': HFSEA_NO_TAG,
    'lf sea': LFSEA_NO_TAG,
    'hf felica reader': (0, """[usb] pm3 --> hf felica reader

[+] FeliCa tag info
[+] IDm: 01 FE 01 02 03 04 05 06
"""),
    '_description': 'FeliCa Lite',
    '_tag_type': 21,  # FELICA
}

# --- LF: EM410x ---
SCAN_EM410X = {
    'hf 14a info': HF14A_NO_TAG,
    'hf sea': (0, """[usb] pm3 --> hf search
[!] No known/supported 13.56 MHz tags found
"""),
    'lf sea': (0, """[usb] pm3 --> lf search

[=] NOTE: some demods output possible binary
[=] if it finds something that looks like a tag
[=] False Positives ARE possible
[=]
[=] Checking for known tags...
[=]

[+] EM410x pattern found

EM TAG ID      : 0F0368568B

Possible de-scramble patterns

Unique TAG ID  : F0C016A5D1
HoneyWell IdentKey {
DEZ 8          : 06903435
DEZ 10         : 0867656267
}
Other          : 22155_003_06903435
Pattern Paxton : 1642715 [0x190F8B]

[+] Valid EM410x ID found!
"""),
    '_description': 'EM410x (125kHz LF)',
    '_tag_type': 8,  # EM410X_ID
}

# --- LF: HID Prox ---
SCAN_HID_PROX = {
    'hf 14a info': HF14A_NO_TAG,
    'hf sea': (0, '[!] No known/supported 13.56 MHz tags found\n'),
    'lf sea': (0, """[usb] pm3 --> lf search

[+] Valid HID Prox ID found!
[+] HID Prox - 200068012345
"""),
    '_description': 'HID Prox ID',
    '_tag_type': 9,  # HID_PROX_ID
}

# --- LF: Indala ---
SCAN_INDALA = {
    'hf 14a info': HF14A_NO_TAG,
    'hf sea': (0, '[!] No known/supported 13.56 MHz tags found\n'),
    'lf sea': (0, """[usb] pm3 --> lf search

[+] Valid Indala ID found!
[+] Raw: A0 00 00 00 00 12 34 56
"""),
    '_description': 'Indala ID',
    '_tag_type': 10,  # INDALA_ID
}

# --- LF: T55XX blank (signal detected but no known modulation) ---
# Multi-step traced from real scan.so under QEMU:
#   hf 14a info → lf sea → data save f /tmp/lf_trace_tmp → hf sea → hf felica reader → lf t55xx detect
# CRITICAL: Real .so sends "data save" BETWEEN lf sea and hf sea (not in transliteration!)
# Real .so order: 14a → LF → data save → HF → felica → t55xx detect
# ALL intermediate commands must return 0 (not -1) to avoid pipeline abort.
SCAN_T55XX_BLANK = {
    'hf 14a info': HF14A_NO_TAG,
    'lf sea': (0, """[usb] pm3 --> lf search

[=] NOTE: some demods output possible binary
[=] if it finds something that looks like a tag
[=] False Positives ARE possible
[=]
[=] Checking for known tags...
[=]
[-] No known 125/134 kHz tags found!
"""),
    # Real .so saves LF raw data for T55XX analysis — must return 0 to continue
    'data save': (0, """[+] saved 40000 bytes to /tmp/lf_trace_tmp
"""),
    'hf sea': (0, """[usb] pm3 --> hf search
[!] No known/supported 13.56 MHz tags found
"""),
    # Real .so checks FeliCa after HF search — must return 0 with no-tag content
    'hf felica reader': (0, """[usb] pm3 --> hf felica reader
"""),
    # After all searches fail, firmware checks isT55XX flag → runs detect
    'lf t55xx detect': (0, """[usb] pm3 --> lf t55xx detect

[=] Chip Type      : T55x7
[=] Modulation     : ASK
[=] Bit Rate       : 2 - RF/32
[=] Inverted       : No
[=] Offset         : 32
[=] Seq. Terminator: Yes
[=] Block0         : 0x00148040
[=] Downlink Mode  : default/fixed bit length
"""),
    '_description': 'T55XX blank card (LF signal but no known modulation)',
    '_tag_type': 23,  # T55X7_ID (isT55XX=True)
}

# --- T55XX Read Tag mode: full flow scan fixtures ---
# For Read Tag, scan_t55xx → lft55xx.chkAndDumpT55xx does the ENTIRE read.
# The bridge falls through to the original .so showScanToast handler.
# ALL PM3 responses must be in the SCAN fixture (no read phase switch).
# Real device trace: 2026-03-26 lf_read_trace_20260326.txt

# Scenario: detect succeeds on first try → read blocks → dump
SCAN_T55XX_READ_SUCCESS = {
    'hf 14a info': HF14A_NO_TAG,
    'lf sea': (0, """[usb] pm3 --> lf search

[-] No known 125/134 kHz tags found!
"""),
    'data save': (0, "[+] saved 40000 bytes\n"),
    'hf sea': (0, "[!] No known/supported 13.56 MHz tags found\n"),
    'hf felica reader': (0, ""),
    'lf t55xx detect': (0, """[usb] pm3 --> lf t55xx detect

[=] Chip Type      : T55x7
[=] Modulation     : ASK
[=] Bit Rate       : 2 - RF/32
[=] Inverted       : No
[=] Offset         : 32
[=] Seq. Terminator: Yes
[=] Block0         : 0x00148040
[=] Downlink Mode  : default/fixed bit length
[=] Password Set   : No
"""),
    'lf t55xx read b 0': (0, """[+] Block 0: 00148040
"""),
    'lf t55xx read b 1': (0, """[+] Block 1: 00000000
"""),
    'lf t55xx read b 2': (0, """[+] Block 2: 00000000
"""),
    'lf t55xx read b': (0, """[+] Block data
"""),
    'lf t55xx dump': (0, """[usb] pm3 --> lf t55xx dump

[+] saved 12 blocks
"""),
    '_description': 'T55XX Read Tag: detect OK → read blocks → dump → success',
    '_tag_type': 23,
}

# Scenario: detect fails without password → chk finds password → detect with password succeeds
# Key: 'lf t55xx detect p' BEFORE 'lf t55xx detect' in dict order.
# Mock substring matching: 'lf t55xx detect p' matches 'lf t55xx detect p 51243648'
# but NOT 'lf t55xx detect' (too short). Bare 'lf t55xx detect' matches only bare command.
SCAN_T55XX_READ_WITH_PASSWORD = {
    'hf 14a info': HF14A_NO_TAG,
    'lf sea': (0, """[usb] pm3 --> lf search

[-] No known 125/134 kHz tags found!
"""),
    'data save': (0, "[+] saved 40000 bytes\n"),
    'hf sea': (0, "[!] No known/supported 13.56 MHz tags found\n"),
    'hf felica reader': (0, ""),
    'lf t55xx chk': (0, """[usb] pm3 --> lf t55xx chk

[+] Found valid password: [51243648]
"""),
    # ORDERING CRITICAL: password-detect BEFORE bare-detect
    'lf t55xx detect p': (0, """[usb] pm3 --> lf t55xx detect p 51243648

[=] Chip Type      : T55x7
[=] Modulation     : ASK
[=] Block0         : 0x00148040
[=] Password Set   : Yes
"""),
    'lf t55xx detect': (0, """[!] Could not detect modulation automatically. Try setting it manually with 'lf t55xx config'
"""),
    'lf t55xx read b': (0, """[+] Block data
"""),
    'lf t55xx dump': (0, """[usb] pm3 --> lf t55xx dump

[+] saved 12 blocks
"""),
    '_description': 'T55XX Read Tag: detect fails → chk password → detect with pwd → dump',
    '_tag_type': 23,
}

# Scenario: detect always fails, no password found → Read Failed
SCAN_T55XX_READ_DETECT_FAIL = {
    'hf 14a info': HF14A_NO_TAG,
    'lf sea': (0, """[usb] pm3 --> lf search

[-] No known 125/134 kHz tags found!
"""),
    'data save': (0, "[+] saved 40000 bytes\n"),
    'hf sea': (0, "[!] No known/supported 13.56 MHz tags found\n"),
    'hf felica reader': (0, ""),
    'lf t55xx chk': (0, """[usb] pm3 --> lf t55xx chk

[-] No valid password found
"""),
    'lf t55xx detect': (0, """[!] Could not detect modulation automatically. Try setting it manually with 'lf t55xx config'
"""),
    '_description': 'T55XX Read Tag: detect fails, no password → Read Failed',
    '_tag_type': 23,
    '_default_return': -1,
}

# ============================================================================
# READ OUTCOMES — Key recovery + data read (hfmfkeys.py, hfmfread.py)
# ============================================================================

# Helper: generate fchk response with all keys found (16 sectors)
# NOTE: No Nikola.D in cache — executor strips it before caching
def _fchk_all_found_1k():
    lines = ['[usb] pm3 --> hf mf fchk 1\n']
    lines.append('[+] No key specified, trying default keys\n')
    lines.append('[+] found keys:\n')
    lines.append('[+] |-----|----------------|---|----------------|---|\n')
    lines.append('[+] | Sec | key A          |res| key B          |res|\n')
    lines.append('[+] |-----|----------------|---|----------------|---|\n')
    for s in range(16):
        lines.append('[+] | %03d | ffffffffffff   | 1 | ffffffffffff   | 1 |\n' % s)
    lines.append('[+] |-----|----------------|---|----------------|---|\n')
    lines.append('[+] ( 0:Failed / 1:Success)\n')
    return ''.join(lines)

# Helper: generate fchk response with NO keys found
# NOTE: No Nikola.D in cache — executor strips it before caching
def _fchk_no_keys_1k():
    lines = ['[usb] pm3 --> hf mf fchk 1\n']
    lines.append('[+] No key specified, trying default keys\n')
    lines.append('[+] No keys found\n')  # Branch string: triggers darkside path
    lines.append('[+] found keys:\n')
    lines.append('[+] |-----|----------------|---|----------------|---|\n')
    lines.append('[+] | Sec | key A          |res| key B          |res|\n')
    lines.append('[+] |-----|----------------|---|----------------|---|\n')
    for s in range(16):
        lines.append('[+] | %03d | ------------   | 0 | ------------   | 0 |\n' % s)
    lines.append('[+] |-----|----------------|---|----------------|---|\n')
    lines.append('[+] ( 0:Failed / 1:Success)\n')
    return ''.join(lines)

# Helper: sector read response (real device format with isOk:01)
# NOTE: No Nikola.D in cache — executor strips it before caching
# Returns 16 block lines so the response works for both small (4-block) and
# large (16-block) sectors. The .so's readAllSector uses getBlockCountInSector()
# to know how many blocks to extract from the regex matches. For small sectors
# (0-31) it reads 4; for large sectors (32-39 in 4K) it reads 16.
def _rdsc_response(sector=0, key_type='B', key='ffffffffffff'):
    base_block = sector * 4
    zero = '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00'
    trailer = 'FF FF FF FF FF FF FF 07 80 69 FF FF FF FF FF FF'
    if sector == 0:
        b0 = '2C AD C2 72 9C 4C 45 45 00 00 00 00 00 00 00 00'
    else:
        b0 = zero
    key_hex = ' '.join(key[i:i+2].upper() for i in range(0, len(key), 2))
    lines = []
    lines.append('--sector no %d, key %s - %s\n' % (sector, key_type, key_hex))
    lines.append('\n')
    lines.append('isOk:01\n')
    # 16 blocks: block 0 = data/UID, blocks 1-14 = zeros, block 15 = trailer
    lines.append('  %d | %s\n' % (base_block, b0))
    for i in range(1, 15):
        lines.append('  %d | %s\n' % (base_block + i, zero))
    lines.append('  %d | %s\n' % (base_block + 15, trailer))
    return ''.join(lines)

READ_MF1K_ALL_DEFAULT_KEYS = {
    'hf mf fchk': (0, _fchk_all_found_1k()),
    'hf mf rdsc': (0, _rdsc_response()),
    '_tag_type': 1,
    '_description': 'MF Classic 1K: all default keys, all sectors readable',
}

READ_MF1K_NO_KEYS = {
    'hf mf fchk': (0, _fchk_no_keys_1k()),
    'hf mf darkside': (0, """[usb] pm3 --> hf mf darkside

[+] found valid key: a0a1a2a3a4a5
"""),
    'hf mf nested': (0, """[usb] pm3 --> hf mf nested 1 0 A a0a1a2a3a4a5

[+] Testing known keys. Sector count 16
[+] found valid key: b0b1b2b3b4b5
"""),
    'hf mf rdsc': (0, _rdsc_response()),
    '_tag_type': 1,
    '_description': 'MF Classic 1K: no default keys, darkside + nested → read success',
}

READ_MF1K_DARKSIDE_FAIL = {
    'hf mf fchk': (0, _fchk_no_keys_1k()),
    'hf mf darkside': (0, """[usb] pm3 --> hf mf darkside

[-] This card is not vulnerable to Darkside attack
"""),
    '_tag_type': 1,
    '_description': 'MF Classic 1K: no keys, darkside fails (hardened card)',
}

# ============================================================================
# WRITE OUTCOMES — Gen1a magic vs standard (hfmfwrite.py)
# ============================================================================

WRITE_GEN1A_SUCCESS = {
    'hf 14a raw': (0, """[usb] pm3 --> hf 14a raw -p -a 43
[+] isOk:01
"""),
    'hf mf cload': (0, """[usb] pm3 --> hf mf cload b /tmp/dump.bin
[+] Card loaded 64 blocks
"""),
    '_description': 'Gen1a magic card write success',
}

WRITE_STANDARD_SUCCESS = {
    'hf 14a raw': (0, """[usb] pm3 --> hf 14a raw -p -a 43
[-] isOk:00
"""),
    'hf mf rdbl': (0, """[usb] pm3 --> hf mf rdbl 63 A ffffffffffff
--block no 63, key A - FF FF FF FF FF FF
--data: FF FF FF FF FF FF FF 07 80 69 FF FF FF FF FF FF
isOk:01
"""),
    'hf mf wrbl': (0, """[usb] pm3 --> hf mf wrbl 1 A ffffffffffff 00000000000000000000000000000000
[+] isOk:01
"""),
    '_description': 'Standard authenticated write success — with rdbl for tagChk4 trailer verification',
}

WRITE_STANDARD_FAIL = {
    'hf 14a raw': (0, '[-] isOk:00\n'),
    'hf mf wrbl': (0, """[usb] pm3 --> hf mf wrbl 1 A ffffffffffff 00000000000000000000000000000000
[-] isOk:00
"""),
    '_description': 'Standard write failure (authentication error)',
}

# ============================================================================
# DIAGNOSIS OUTCOMES
# ============================================================================

DIAGNOSIS_HW_TUNE_OK = {
    'hw tune': (0, """[usb] pm3 --> hw tune
[=] Measuring antenna characteristics, please wait...

[=] ---------- LF Antenna ----------
[+] LF antenna: 32.44 V - 125.00 kHz
[+] LF antenna: 17.03 V - 134.00 kHz
[+] LF optimal: 32.44 V - 125.00 kHz
[+] LF antenna is OK

[=] ---------- HF Antenna ----------
[+] HF antenna: 29.87 V - 13.56 MHz
[+] HF antenna is OK
"""),
    '_description': 'Hardware antenna test — both OK',
}

DIAGNOSIS_HW_TUNE_LF_FAIL = {
    'hw tune': (0, """[usb] pm3 --> hw tune
[=] Measuring antenna characteristics, please wait...

[=] ---------- LF Antenna ----------
[+] LF antenna: 0.12 V - 125.00 kHz
[!] LF antenna is NOT OK

[=] ---------- HF Antenna ----------
[+] HF antenna: 29.87 V - 13.56 MHz
[+] HF antenna is OK
"""),
    '_description': 'Hardware antenna test — LF antenna fail',
}

# ============================================================================
# Master index of ALL scenarios for capture automation
# ============================================================================

# (ALL_SCAN_SCENARIOS moved to UPDATED MASTER INDEXES section below)


# (Old indexes removed — comprehensive versions defined after all fixtures below)

# ============================================================================
# AUTO COPY FLOWS — Multi-step: scan → key recovery → read → write
# ============================================================================

AUTO_COPY_MF1K_HAPPY = {
    'hf 14a info': (0, "[usb] pm3 --> hf 14a info\n\n[+]  UID: 2C AD C2 72\n[+] ATQA: 00 04\n[+]  SAK: 08 [2]\n[+] Possible types:\n[+]    MIFARE Classic 1K / Classic 1K CL2\n[=] proprietary non iso14443-4 card found, RATS not supported\n[+] Prng detection: weak\n"),
    'hf 14a raw': (0, "[-] isOk:00\n"),
    'hf mf fchk': (0, _fchk_all_found_1k()),
    'hf mf rdsc': (0, _rdsc_response()),
    'hf mf wrbl': (0, "[+] isOk:01\n"),
    'hf mf cgetblk': (0, "[-] Can't set magic card block\n"),  # Not magic
    '_default_return': -1,
    '_description': 'Auto Copy MF1K: all default keys, read success, write success',
    '_tag_type': 1,
}

AUTO_COPY_MF1K_DARKSIDE = {
    'hf 14a info': (0, "[usb] pm3 --> hf 14a info\n\n[+]  UID: FF EE DD CC\n[+] ATQA: 00 04\n[+]  SAK: 08 [2]\n[+] Possible types:\n[+]    MIFARE Classic 1K / Classic 1K CL2\n[=] proprietary non iso14443-4 card found, RATS not supported\n[+] Prng detection: weak\n"),
    'hf 14a raw': (0, "[-] isOk:00\n"),
    'hf mf fchk': (0, _fchk_no_keys_1k()),
    'hf mf darkside': (0, "[+] found valid key: a0a1a2a3a4a5\n"),
    'hf mf nested': (0, "[+] Testing known keys. Sector count 16\n[+] found valid key: b0b1b2b3b4b5\n"),
    'hf mf rdsc': (0, _rdsc_response()),
    'hf mf wrbl': (0, "[+] isOk:01\n"),
    'hf mf cgetblk': (0, "[-] Can't set magic card block\n"),
    '_default_return': -1,
    '_description': 'Auto Copy MF1K: no default keys, darkside+nested recovery, read+write success',
    '_tag_type': 1,
}

AUTO_COPY_GEN1A = {
    'hf 14a info': (0, "[usb] pm3 --> hf 14a info\n\n[+]  UID: 11 22 33 44\n[+] ATQA: 00 04\n[+]  SAK: 08 [2]\n[+] Possible types:\n[+]    MIFARE Classic 1K / Classic 1K CL2\n[=] proprietary non iso14443-4 card found, RATS not supported\n[+] Prng detection: weak\n"),
    'hf 14a raw': (0, "[+] isOk:01\n"),
    'hf mf cgetblk': (0, "[+] Block 0: 112233449C4C4545000000000000000\n"),
    'hf mf cload': (0, "[+] Card loaded 64 blocks\n"),
    'hf mf fchk': (0, _fchk_all_found_1k()),
    'hf mf rdsc': (0, _rdsc_response()),
    '_default_return': -1,
    '_description': 'Auto Copy Gen1a: magic card detected, cload write',
    '_tag_type': 1,
}

AUTO_COPY_DARKSIDE_FAIL = {
    'hf 14a info': (0, "[usb] pm3 --> hf 14a info\n\n[+]  UID: AA BB CC DD\n[+] ATQA: 00 04\n[+]  SAK: 08 [2]\n[+] Possible types:\n[+]    MIFARE Classic 1K / Classic 1K CL2\n[=] proprietary non iso14443-4 card found, RATS not supported\n[+] Static nonce: yes\n"),
    'hf 14a raw': (0, "[-] isOk:00\n"),
    'hf mf fchk': (0, _fchk_no_keys_1k()),
    'hf mf darkside': (0, "[-] This card is not vulnerable to Darkside attack\n"),
    'hf mf cgetblk': (0, "[-] Can't set magic card block\n"),
    '_default_return': -1,
    '_description': 'Auto Copy: static nonce card, darkside fails (hardened)',
    '_tag_type': 1,
}

AUTO_COPY_WRITE_FAIL = {
    'hf 14a info': (0, "[usb] pm3 --> hf 14a info\n\n[+]  UID: 2C AD C2 72\n[+] ATQA: 00 04\n[+]  SAK: 08 [2]\n[+] Possible types:\n[+]    MIFARE Classic 1K / Classic 1K CL2\n[=] proprietary non iso14443-4 card found, RATS not supported\n[+] Prng detection: weak\n"),
    'hf 14a raw': (0, "[-] isOk:00\n"),
    'hf mf fchk': (0, _fchk_all_found_1k()),
    'hf mf rdsc': (0, _rdsc_response()),
    'hf mf wrbl': (0, "[-] isOk:00\n"),
    'hf mf cgetblk': (0, "[-] Can't set magic card block\n"),
    '_default_return': -1,
    '_description': 'Auto Copy: read success but write fails (isOk:00)',
    '_tag_type': 1,
}

# (Old autocopy index removed — comprehensive version below)

# ============================================================================
# KEY RECOVERY FIXTURES — additional branches from hfmfkeys.so patterns
# ============================================================================

# Helper: fchk with partial keys (16/32 found)
# NOTE: No Nikola.D in cache — executor strips it before caching
def _fchk_partial_1k():
    lines = ['[usb] pm3 --> hf mf fchk 1\n']
    lines.append('[+] found keys:\n')
    lines.append('[+] |-----|----------------|---|----------------|---|\n')
    lines.append('[+] | Sec | key A          |res| key B          |res|\n')
    lines.append('[+] |-----|----------------|---|----------------|---|\n')
    for s in range(16):
        if s < 8:  # First 8 sectors: keyA found, keyB not
            lines.append('[+] | %03d | ffffffffffff   | 1 | ------------   | 0 |\n' % s)
        else:  # Last 8 sectors: neither found
            lines.append('[+] | %03d | ------------   | 0 | ------------   | 0 |\n' % s)
    lines.append('[+] |-----|----------------|---|----------------|---|\n')
    return ''.join(lines)

# Helper: fchk for 2K card (32 sectors) — size flag "2"
# NOTE: No Nikola.D in cache — executor strips it before caching
def _fchk_all_found_2k():
    lines = ['[usb] pm3 --> hf mf fchk 2\n']
    lines.append('[+] No key specified, trying default keys\n')
    lines.append('[+] found keys:\n')
    lines.append('[+] |-----|----------------|---|----------------|---|\n')
    lines.append('[+] | Sec | key A          |res| key B          |res|\n')
    lines.append('[+] |-----|----------------|---|----------------|---|\n')
    for s in range(32):
        lines.append('[+] | %03d | ffffffffffff   | 1 | ffffffffffff   | 1 |\n' % s)
    lines.append('[+] |-----|----------------|---|----------------|---|\n')
    lines.append('[+] ( 0:Failed / 1:Success)\n')
    return ''.join(lines)

def _fchk_all_found_4k():
    lines = ['[usb] pm3 --> hf mf fchk 4\n']
    lines.append('[+] found keys:\n')
    lines.append('[+] |-----|----------------|---|----------------|---|\n')
    lines.append('[+] | Sec | key A          |res| key B          |res|\n')
    lines.append('[+] |-----|----------------|---|----------------|---|\n')
    for s in range(40):
        lines.append('[+] | %03d | ffffffffffff   | 1 | ffffffffffff   | 1 |\n' % s)
    lines.append('[+] |-----|----------------|---|----------------|---|\n')
    return ''.join(lines)

READ_MF1K_PARTIAL_FCHK = {
    'hf mf fchk': (0, _fchk_partial_1k()),
    'hf mf nested': (0, """[usb] pm3 --> hf mf nested 1 0 A ffffffffffff

[+] found valid key: a0a1a2a3a4a5
"""),
    'hf mf rdsc': (0, _rdsc_response()),
    '_tag_type': 1,
    '_description': 'MF Classic 1K: partial fchk (8/16 keyA), nested recovers rest',
}

READ_MF1K_NESTED_PARTIAL = {
    'hf mf fchk': (0, _fchk_partial_1k()),
    'hf mf nested': (-1, """[usb] pm3 --> hf mf nested

[-] No valid key found
"""),
    'hf mf rdsc': (0, _rdsc_response()),
    '_tag_type': 1,
    '_description': 'MF Classic 1K: partial fchk, nested fails → force read option',
}

READ_MF4K_ALL_KEYS = {
    'hf mf fchk': (0, _fchk_all_found_4k()),
    'hf mf rdsc': (0, _rdsc_response()),
    '_tag_type': 0,
    '_description': 'MF Classic 4K: all 80 keys found in fchk',
}

READ_MF1K_TAG_LOST = {
    'hf mf fchk': (0, _fchk_all_found_1k()),
    'hf mf rdsc': (-1, ''),  # PM3 error mid-read
    '_tag_type': 1,
    '_description': 'MF Classic 1K: tag lost during sector read',
    '_default_return': -1,
}

# ============================================================================
# MIFARE BRANCHES 4-27 — Complete coverage from V1090_MIFARE_BRANCH_STRINGS.md
# ============================================================================

# --- Branch 4: fchk timeout/error → abort ---
READ_MF1K_FCHK_TIMEOUT = {
    'hf mf fchk': (-1, ''),  # startPM3Task returns -1 = timeout
    '_tag_type': 1,
    '_description': 'MF Classic 1K: fchk times out (600s elapsed, no response)',
    '_default_return': -1,
}

# --- Branch 7: darkside → nested "not vulnerable" → Warning screen ---
READ_MF1K_DARKSIDE_NESTED_FAIL = {
    'hf mf fchk': (0, _fchk_no_keys_1k()),
    'hf mf darkside': (0, """[usb] pm3 --> hf mf darkside

[+] found valid key: a0a1a2a3a4a5
[-] Tag isn't vulnerable to Nested Attack
[=] Try use `hf mf staticnested`
"""),
    'hf mf nested': (0, """[usb] pm3 --> hf mf nested 1 0 A a0a1a2a3a4a5

[-] Tag isn't vulnerable to Nested Attack
"""),
    'hf mf rdsc': (0, _rdsc_response()),
    '_tag_type': 1,
    '_description': 'MF Classic 1K: no keys → darkside → nested "not vulnerable" → Warning screen',
}

# --- Branch 8: darkside → "Try use nested" (alternative output) ---
READ_MF1K_DARKSIDE_TO_NESTED_ALT = {
    'hf mf fchk': (0, _fchk_no_keys_1k()),
    'hf mf darkside': (0, """[usb] pm3 --> hf mf darkside

[+] found valid key: a0a1a2a3a4a5
[=] Try use `hf mf nested`
"""),
    'hf mf nested': (0, """[usb] pm3 --> hf mf nested 1 0 A a0a1a2a3a4a5

[+] Testing known keys. Sector count 16
[+] found valid key: b0b1b2b3b4b5
"""),
    'hf mf rdsc': (0, _rdsc_response()),
    '_tag_type': 1,
    '_description': 'MF Classic 1K: no keys → darkside → "Try nested" → nested success → read',
}

# --- Branch 9: darkside → "Can't select card (ALL)" → card lost ---
READ_MF1K_DARKSIDE_CARD_LOST = {
    'hf mf fchk': (0, _fchk_no_keys_1k()),
    'hf mf darkside': (0, """[usb] pm3 --> hf mf darkside

[-] Can't select card (ALL)
"""),
    '_tag_type': 1,
    '_description': 'MF Classic 1K: no keys → darkside → card removed → abort',
}

# --- Branch 10: darkside → timeout (no key found) ---
READ_MF1K_DARKSIDE_TIMEOUT = {
    'hf mf fchk': (0, _fchk_no_keys_1k()),
    'hf mf darkside': (-1, ''),  # PM3 timeout
    '_tag_type': 1,
    '_description': 'MF Classic 1K: no keys → darkside times out → hardnested fallback',
    '_default_return': -1,
}

# --- Branch 11: partial fchk → nested → ALL remaining keys found → full read ---
READ_MF1K_PARTIAL_NESTED_SUCCESS = {
    'hf mf fchk': (0, _fchk_partial_1k()),
    'hf mf nested': (0, """[usb] pm3 --> hf mf nested 1 0 A ffffffffffff

[+] Testing known keys. Sector count 16
[+] found valid key: a0a1a2a3a4a5
[+] found valid key: b0b1b2b3b4b5
[+] found valid key: c0c1c2c3c4c5
"""),
    'hf mf rdsc': (0, _rdsc_response()),
    '_tag_type': 1,
    '_description': 'MF Classic 1K: partial fchk → nested → all remaining keys → full read',
}

# --- Branch 12: nested → "no candidates found" → retry → eventually succeed ---
READ_MF1K_NESTED_RETRY = {
    'hf mf fchk': (0, _fchk_partial_1k()),
    'hf mf nested': (0, """[usb] pm3 --> hf mf nested 1 0 A ffffffffffff

[!] no candidates found, trying again
[+] Testing known keys. Sector count 16
[+] found valid key: a0a1a2a3a4a5
"""),
    'hf mf rdsc': (0, _rdsc_response()),
    '_tag_type': 1,
    '_description': 'MF Classic 1K: nested → no candidates → retry → success',
}

# --- Branch 13: nested → "button pressed. Aborted." → user abort ---
READ_MF1K_NESTED_ABORT = {
    'hf mf fchk': (0, _fchk_partial_1k()),
    'hf mf nested': (0, """[usb] pm3 --> hf mf nested 1 0 A ffffffffffff

[-] button pressed. Aborted.
"""),
    '_tag_type': 1,
    '_description': 'MF Classic 1K: nested → user presses button → abort',
}

# --- Branch 14: nested → timeout → partial keys only ---
READ_MF1K_NESTED_TIMEOUT = {
    'hf mf fchk': (0, _fchk_partial_1k()),
    'hf mf nested': (-1, ''),  # PM3 timeout
    'hf mf rdsc': (0, _rdsc_response()),
    '_tag_type': 1,
    '_description': 'MF Classic 1K: nested times out → read with partial keys only',
    '_default_return': -1,
}

# --- Branch 15: darkside → nested "not vulnerable" → Warning screen (variant) ---
READ_MF1K_NESTED_NOT_VULNERABLE = {
    'hf mf fchk': (0, _fchk_no_keys_1k()),
    'hf mf darkside': (0, """[usb] pm3 --> hf mf darkside

[+] found valid key: a0a1a2a3a4a5
[=] Try use `hf mf staticnested`
"""),
    'hf mf nested': (0, """[usb] pm3 --> hf mf nested 1 0 A a0a1a2a3a4a5

[-] Tag isn't vulnerable to Nested Attack
"""),
    'hf mf rdsc': (0, _rdsc_response()),
    '_tag_type': 1,
    '_description': 'MF Classic 1K: no keys → darkside → nested "not vulnerable" → Warning screen',
}

# --- Branch 16: nested "not vulnerable" → "Missing keys" warning ---
# QEMU-verified: when nested() gets "Tag isn't vulnerable to Nested Attack",
# the .so does NOT automatically send hardnested/loudong. Instead it transitions
# to the "Missing keys" WarningActivity (title="Warning", content="Missing keys",
# M1="Sniff", M2="Enter", page 1/2 with 4 options).
# Hardnested is user-initiated (Option 4: PC Mode), not automatic.
READ_MF1K_HARDNESTED_SUCCESS = {
    'hf mf fchk': (0, _fchk_partial_1k()),
    'hf mf nested': (0, """[usb] pm3 --> hf mf nested 1 0 A ffffffffffff

[-] Tag isn't vulnerable to Nested Attack
"""),
    '_tag_type': 1,
    '_description': 'MF Classic 1K: partial fchk → nested(not vulnerable) → Missing keys warning',
}

# --- Branch 17: same flow, from zero keys (darkside → nested → not vulnerable) ---
# When fchk finds NO keys, darkside finds one, then nested says "not vulnerable",
# the .so also reaches "Missing keys" warning.
READ_MF1K_HARDNESTED_FAIL = {
    'hf mf fchk': (0, _fchk_no_keys_1k()),
    'hf mf darkside': (0, """[usb] pm3 --> hf mf darkside

[+] found valid key: a0a1a2a3a4a5
"""),
    'hf mf nested': (0, """[usb] pm3 --> hf mf nested 1 0 A a0a1a2a3a4a5

[-] Tag isn't vulnerable to Nested Attack
"""),
    '_tag_type': 1,
    '_description': 'MF Classic 1K: no keys → darkside(key) → nested(not vulnerable) → Missing keys warning',
}

# --- Branch 19: readAllSector → Auth error → Read Failed ---
# NOTE: Mock returns same response for all rdsc calls. Cannot do per-sector
# partial reads. This fixture returns Auth error for every rdsc → Read Failed.
READ_MF1K_PARTIAL_READ = {
    'hf mf fchk': (0, _fchk_all_found_1k()),
    'hf mf rdsc': (0, """--sector no 0, key B - FF FF FF FF FF FF

[-] Auth error
[-] Wrong key. Can't authenticate to block 0
"""),
    '_tag_type': 1,
    '_description': 'MF Classic 1K: all keys found but Auth error on every sector → Read Failed',
}

# --- Branch 20: readAllSector → "Can't select card" → Read Failed ---
# NOTE: Mock returns same response for all rdsc calls.
# Card lost response for every rdsc → Read Failed.
READ_MF1K_CARD_LOST_MID_READ = {
    'hf mf fchk': (0, _fchk_all_found_1k()),
    'hf mf rdsc': (0, """--sector no 0, key B - FF FF FF FF FF FF

[-] Can't select card
"""),
    '_tag_type': 1,
    '_description': 'MF Classic 1K: card removed — every rdsc gets card lost → Read Failed',
}

# --- Branch 21: readAllSector → all sectors fail → Read Failed ---
READ_MF1K_ALL_SECTORS_FAIL = {
    'hf mf fchk': (0, _fchk_all_found_1k()),
    'hf mf rdsc': (0, """--sector no 0, key B - FF FF FF FF FF FF

[-] Auth error
[-] Wrong key. Can't authenticate to block 0
"""),
    '_tag_type': 1,
    '_description': 'MF Classic 1K: every rdsc gets Auth error → Read Failed',
}

# --- Branch 21b: readAllSector → hardware Read block error → retry/skip ---
READ_MF1K_READ_BLOCK_ERROR = {
    'hf mf fchk': (0, _fchk_all_found_1k()),
    'hf mf rdsc': (0, """--sector no 0, key B - FF FF FF FF FF FF

[-] Read block error
[-] Read sector 0 block 0 error
"""),
    'hf mf rdbl': (0, """isOk:01
  0 | 2C AD C2 72 9C 4C 45 45 00 00 00 00 00 00 00 00
"""),
    '_tag_type': 1,
    '_description': 'MF Classic 1K: rdsc fails with Read block error → rdbl fallback succeeds',
}

# --- Branch 22: Gen1a → csave succeeds → full dump ---
# Gen1a is detected during SCAN when hf14ainfo.is_gen1a_magic() finds
# "Magic capabilities : Gen 1a" in the hf 14a info response.
# Then cgetblk confirms by returning block 0 data.
# Read phase uses csave instead of fchk+rdsc.
SCAN_MF_CLASSIC_1K_GEN1A = {
    'hf 14a info': (0, """[usb] pm3 --> hf 14a info

[+]  UID: 11 22 33 44
[+] ATQA: 00 04
[+]  SAK: 08 [2]
[+] Possible types:
[+]    MIFARE Classic 1K / Classic 1K CL2
[+] Magic capabilities : Gen 1a
[=] proprietary non iso14443-4 card found, RATS not supported
[+] Prng detection: weak
"""),
    'hf mf cgetblk': (0, """[usb] pm3 --> hf mf cgetblk 0

[+] Block 0: 11 22 33 44 9C 4C 45 45 00 00 00 00 00 00 00 00
[+] isOk:01
"""),
    '_description': 'MIFARE Classic 1K Gen1a magic card (cgetblk succeeds)',
    '_tag_type': 1,
}

READ_MF1K_GEN1A_CSAVE_SUCCESS = {
    # Gen1a detection requires "Magic capabilities : Gen 1a" in hf 14a info response
    # (checked by hf14ainfo.is_gen1a_magic via hasKeyword). Must override the scan
    # fixture's non-Gen1a hf 14a info response.
    # Then cgetblk SUCCEEDS (block data = Gen1a confirmed).
    # This triggers readIfIsGen1a(): skip fchk, go straight to csave.
    'hf 14a info': (0, """[usb] pm3 --> hf 14a info

[+]  UID: 11 22 33 44
[+] ATQA: 00 04
[+]  SAK: 08 [2]
[+] Possible types:
[+]    MIFARE Classic 1K / Classic 1K CL2
[+] Magic capabilities : Gen 1a
[=] proprietary non iso14443-4 card found, RATS not supported
[+] Prng detection: weak
"""),
    'hf mf cgetblk': (0, """[usb] pm3 --> hf mf cgetblk 0

[+] Block 0: 11 22 33 44 9C 4C 45 45 00 00 00 00 00 00 00 00
[+] isOk:01
"""),
    'hf mf csave': (0, """[usb] pm3 --> hf mf csave 1 o /tmp/dump.bin

[+] saved 1024 bytes to binary file /tmp/dump.bin
"""),
    '_tag_type': 1,
    '_description': 'MF Classic 1K Gen1a: cgetblk succeeds → csave dumps all 64 blocks',
}

# --- Branch 23: Gen1a → csave fails → fall through to standard ---
READ_MF1K_GEN1A_CSAVE_FAIL = {
    # Gen1a detected (Magic capabilities in hf 14a info + cgetblk success),
    # but csave fails → fall through to standard fchk+rdsc path.
    'hf 14a info': (0, """[usb] pm3 --> hf 14a info

[+]  UID: 11 22 33 44
[+] ATQA: 00 04
[+]  SAK: 08 [2]
[+] Possible types:
[+]    MIFARE Classic 1K / Classic 1K CL2
[+] Magic capabilities : Gen 1a
[=] proprietary non iso14443-4 card found, RATS not supported
[+] Prng detection: weak
"""),
    'hf mf cgetblk': (0, """[usb] pm3 --> hf mf cgetblk 0

[+] Block 0: 11 22 33 44 9C 4C 45 45 00 00 00 00 00 00 00 00
[+] isOk:01
"""),
    'hf mf csave': (-1, ''),  # csave fails
    'hf mf fchk': (0, _fchk_all_found_1k()),
    'hf mf rdsc': (0, _rdsc_response()),
    '_tag_type': 1,
    '_description': 'MF Classic 1K Gen1a: csave fails → fall through to fchk+rdsc standard path',
}

# --- MIFARE Classic 4K Gen1a: csave happy path ---
# Real device trace 2026-03-28: Gen1b 4K card, hf 14a info shows
# "Magic capabilities : Gen 1b", cgetblk succeeds, csave 4 saves 4096 bytes.
# The .so treats Gen1a and Gen1b identically (cgetblk success = magic card).
READ_MF4K_GEN1A_CSAVE_SUCCESS = {
    'hf 14a info': (0, """[usb] pm3 --> hf 14a info

[+]  UID: E9 78 4E 21
[+] ATQA: 00 02
[+]  SAK: 18 [2]
[+] Possible types:
[+]    MIFARE Classic 4K / Classic 4K CL2
[+] Magic capabilities : Gen 1a
[=] proprietary non iso14443-4 card found, RATS not supported
[+] Prng detection: weak
"""),
    'hf mf cgetblk': (0, """[usb] pm3 --> hf mf cgetblk 0

data: E9 78 4E 21 FE 98 02 00 62 63 64 65 66 67 68 69
"""),
    'hf mf csave': (0, """[usb] pm3 --> hf mf csave 4 o /tmp/dump.bin

[+] Saving magic MIFARE 4K
[+] saved 4096 bytes to binary file /tmp/dump.bin
[+] saved 256 blocks to text file /tmp/dump.eml
"""),
    '_tag_type': 0,
    '_description': 'MF Classic 4K Gen1a: csave 4 dumps all 256 blocks (4096 bytes)',
}

# --- MIFARE Classic 4K Gen1a: csave fails → fall through to fchk+rdsc ---
READ_MF4K_GEN1A_CSAVE_FAIL = {
    'hf 14a info': (0, """[usb] pm3 --> hf 14a info

[+]  UID: E9 78 4E 21
[+] ATQA: 00 02
[+]  SAK: 18 [2]
[+] Possible types:
[+]    MIFARE Classic 4K / Classic 4K CL2
[+] Magic capabilities : Gen 1a
[=] proprietary non iso14443-4 card found, RATS not supported
[+] Prng detection: weak
"""),
    'hf mf cgetblk': (0, """[usb] pm3 --> hf mf cgetblk 0

data: E9 78 4E 21 FE 98 02 00 62 63 64 65 66 67 68 69
"""),
    'hf mf csave': (-1, ''),  # csave fails
    'hf mf fchk': (0, _fchk_all_found_4k()),
    'hf mf rdsc': (0, _rdsc_response()),
    '_tag_type': 0,
    '_description': 'MF Classic 4K Gen1a: csave fails → fall through to fchk+rdsc standard path',
}

# --- Branch 24-25: Wrong type detected during scan ---
# (Handled by using mismatched scan fixture in walker — no separate read fixture needed.
#  The scan fixture for type X is used but list item is type Y → showScanToast(found=False).)

# --- Branch 27: Multiple tags detected ---
# (Handled by SCAN_MULTI_TAGS scan fixture — causes "Multiple tags detected!" toast.
#  No read fixture needed — read never starts.)

# --- 4K variants of key fixtures ---
def _fchk_no_keys_4k():
    lines = ['[usb] pm3 --> hf mf fchk 4\n']
    lines.append('[+] found keys:\n')
    lines.append('[+] |-----|----------------|---|----------------|---|\n')
    lines.append('[+] | Sec | key A          |res| key B          |res|\n')
    lines.append('[+] |-----|----------------|---|----------------|---|\n')
    for s in range(40):
        lines.append('[+] | %03d | ------------   | 0 | ------------   | 0 |\n' % s)
    lines.append('[+] |-----|----------------|---|----------------|---|\n')
    return ''.join(lines)

def _fchk_partial_4k():
    lines = ['[usb] pm3 --> hf mf fchk 4\n']
    lines.append('[+] found keys:\n')
    lines.append('[+] |-----|----------------|---|----------------|---|\n')
    lines.append('[+] | Sec | key A          |res| key B          |res|\n')
    lines.append('[+] |-----|----------------|---|----------------|---|\n')
    for s in range(40):
        if s < 20:
            lines.append('[+] | %03d | ffffffffffff   | 1 | ------------   | 0 |\n' % s)
        else:
            lines.append('[+] | %03d | ------------   | 0 | ------------   | 0 |\n' % s)
    lines.append('[+] |-----|----------------|---|----------------|---|\n')
    return ''.join(lines)

READ_MF4K_NO_KEYS = {
    'hf mf fchk': (0, _fchk_no_keys_4k()),
    'hf mf darkside': (0, """[usb] pm3 --> hf mf darkside

[+] found valid key: a0a1a2a3a4a5
"""),
    'hf mf nested': (0, """[usb] pm3 --> hf mf nested 2 0 A a0a1a2a3a4a5

[+] Testing known keys. Sector count 40
[+] found valid key: b0b1b2b3b4b5
"""),
    'hf mf rdsc': (0, _rdsc_response()),
    '_tag_type': 0,
    '_description': 'MF Classic 4K: no default keys, darkside + nested → read success',
}

READ_MF4K_PARTIAL_FCHK = {
    'hf mf fchk': (0, _fchk_partial_4k()),
    'hf mf nested': (0, """[usb] pm3 --> hf mf nested 2 0 A ffffffffffff

[+] found valid key: a0a1a2a3a4a5
"""),
    'hf mf rdsc': (0, _rdsc_response()),
    '_tag_type': 0,
    '_description': 'MF Classic 4K: partial fchk, nested recovers rest',
}

READ_MF4K_DARKSIDE_FAIL = {
    'hf mf fchk': (0, _fchk_no_keys_4k()),
    'hf mf darkside': (0, """[usb] pm3 --> hf mf darkside

[-] This card is not vulnerable to Darkside attack
"""),
    '_tag_type': 0,
    '_description': 'MF Classic 4K: no keys, darkside fails',
}

# ============================================================================
# READ FIXTURES — Ultralight/NTAG, iCLASS, LF, ISO15693, LEGIC
# ============================================================================

READ_ULTRALIGHT_SUCCESS = {
    'hf mfu dump': (0, """[usb] pm3 --> hf mfu dump f /tmp/dump.bin

[=] MFU dump completed
"""),
    '_tag_type': 2,
    '_description': 'MIFARE Ultralight: full dump success',
}

READ_ULTRALIGHT_PARTIAL = {
    'hf mfu dump': (0, """[usb] pm3 --> hf mfu dump f /tmp/dump.bin

[!] Partial dump created
"""),
    '_tag_type': 2,
    '_description': 'MIFARE Ultralight: partial dump (some pages protected)',
}

READ_NTAG215_SUCCESS = {
    'hf mfu dump': (0, """[usb] pm3 --> hf mfu dump f /tmp/dump.bin

[=] NTAG dump completed
"""),
    '_tag_type': 6,
    '_description': 'NTAG215: full dump success',
}

# Ultralight/NTAG failure branches (from branch tree)
READ_ULTRALIGHT_CARD_SELECT_FAIL = {
    'hf mfu dump': (0, """[usb] pm3 --> hf mfu dump f /tmp/dump.bin

[-] iso14443a card select failed
"""),
    '_tag_type': 2,
    '_description': 'MIFARE Ultralight: card select failed → "Read Failed!"',
}

READ_ULTRALIGHT_EMPTY = {
    'hf mfu dump': (-1, ''),
    '_tag_type': 2,
    '_description': 'MIFARE Ultralight: empty response / timeout → "Read Failed!"',
    '_default_return': -1,
}

# iCLASS failure branches
READ_ICLASS_DUMP_FAIL = {
    'hf iclass chk': (0, """[usb] pm3 --> hf iclass chk

[+] Found valid key ae a6 84 a6 da b2 12 32
"""),
    'hf iclass dump': (-1, ''),
    '_tag_type': 17,
    '_description': 'iCLASS: key found but dump fails → "Read Failed!"',
    '_default_return': -1,
}

READ_ICLASS_LEGACY = {
    'hf iclass chk': (0, """[usb] pm3 --> hf iclass chk

[+] Found valid key ae a6 84 a6 da b2 12 32
"""),
    'hf iclass dump': (0, """[usb] pm3 --> hf iclass dump k aea684a6dab21232

[+] saving dump file - 19 blocks read
"""),
    '_tag_type': 17,
    '_description': 'iCLASS Legacy: key found, 19 blocks dumped',
}

READ_ICLASS_NO_KEY = {
    'hf iclass chk': (0, """[usb] pm3 --> hf iclass chk

[-] No valid key found
"""),
    '_tag_type': 17,
    '_description': 'iCLASS: no matching key found',
}

READ_LF_EM410X = {
    'lf em 410x': (0, """[usb] pm3 --> lf em 410x_read

[+] EM 410x ID 0F0368568B

EM TAG ID      : 0F0368568B

Possible de-scramble patterns

Unique TAG ID  : F0C016A5D1
"""),
    '_tag_type': 8,
    '_description': 'EM410x: read success with UID',
}

READ_LF_HID = {
    'lf hid read': (0, """[usb] pm3 --> lf hid read

[+] Valid HID Prox ID found!
[+] HID Prox - 200068012345
"""),
    '_tag_type': 9,
    '_description': 'HID Prox: read success',
}

READ_LF_T55XX = {
    'lf t55xx detect': (0, """[usb] pm3 --> lf t55xx detect

[=] Chip Type      : T55x7
[=] Modulation     : ASK
[=] Block0         : 0x00148040
"""),
    'lf t55xx dump': (0, """[usb] pm3 --> lf t55xx dump

[+] saved 12 blocks
"""),
    '_tag_type': 23,
    '_description': 'T55XX: detect + dump success',
}

READ_ISO15693 = {
    'hf 15 dump': (0, """[usb] pm3 --> hf 15 dump

[+] Block  0: E0 04 01 00 12 34 56 78
[+] Block  1: 00 00 00 00 00 00 00 00
"""),
    '_tag_type': 19,
    '_description': 'ISO15693: dump success',
}

# --- Variant types: same read path, different scan fixture + tag_type ---

READ_MF_MINI_ALL_KEYS = {
    'hf mf fchk': (0, _fchk_all_found_1k()),  # Mini has 5 sectors, but fchk format is same
    'hf mf rdsc': (0, _rdsc_response()),
    '_tag_type': 25,
    '_description': 'MIFARE Mini: all default keys, read success',
}

READ_MF_PLUS_2K_ALL_KEYS = {
    'hf mf fchk': (0, _fchk_all_found_2k()),  # Plus 2K has 32 sectors
    'hf mf rdsc': (0, _rdsc_response()),
    '_tag_type': 26,
    '_description': 'MIFARE Plus 2K: all default keys (32 sectors), read success',
}

READ_MF1K_7B_ALL_KEYS = {
    'hf mf fchk': (0, _fchk_all_found_1k()),
    'hf mf rdsc': (0, _rdsc_response()),
    '_tag_type': 42,
    '_description': 'MIFARE Classic 1K 7B: all default keys, read success',
}

READ_MF4K_7B_ALL_KEYS = {
    'hf mf fchk': (0, _fchk_all_found_4k()),
    'hf mf rdsc': (0, _rdsc_response()),
    '_tag_type': 41,
    '_description': 'MIFARE Classic 4K 7B: all default keys, read success',
}

READ_ULTRALIGHT_C_SUCCESS = {
    'hf mfu dump': (0, """[usb] pm3 --> hf mfu dump f /tmp/dump.bin

[=] MFU dump completed
"""),
    '_tag_type': 3,
    '_description': 'Ultralight C: full dump success',
}

READ_ULTRALIGHT_EV1_SUCCESS = {
    'hf mfu dump': (0, """[usb] pm3 --> hf mfu dump f /tmp/dump.bin

[=] MFU dump completed
"""),
    '_tag_type': 4,
    '_description': 'Ultralight EV1: full dump success',
}

READ_NTAG213_SUCCESS = {
    'hf mfu dump': (0, """[usb] pm3 --> hf mfu dump f /tmp/dump.bin

[=] NTAG dump completed
"""),
    '_tag_type': 5,
    '_description': 'NTAG213: full dump success',
}

READ_NTAG216_SUCCESS = {
    'hf mfu dump': (0, """[usb] pm3 --> hf mfu dump f /tmp/dump.bin

[=] NTAG dump completed
"""),
    '_tag_type': 7,
    '_description': 'NTAG216: full dump success',
}

READ_ICLASS_ELITE = {
    'hf iclass chk': (0, """[usb] pm3 --> hf iclass chk

[+] Found valid key ae a6 84 a6 da b2 12 32
"""),
    'hf iclass dump': (0, """[usb] pm3 --> hf iclass dump k aea684a6dab21232

[+] saving dump file - 19 blocks read
"""),
    '_tag_type': 18,
    '_description': 'iCLASS Elite: key found, 19 blocks dumped',
}

READ_ISO15693_ST = {
    'hf 15 dump': (0, """[usb] pm3 --> hf 15 dump

[+] Block  0: E0 04 01 00 12 34 56 78
[+] Block  1: 00 00 00 00 00 00 00 00
"""),
    '_tag_type': 46,
    '_description': 'ISO15693 ST SA: dump success',
}

READ_ISO15693_NO_TAG = {
    'hf 15 dump': (0, """[usb] pm3 --> hf 15 dump

[-] No tag found.
"""),
    '_tag_type': 19,
    '_description': 'ISO15693: no tag found during dump (period required — hf15read.so hasKeyword check)',
}

READ_ISO15693_TIMEOUT = {
    'hf 15 dump': (-1, ''),
    '_tag_type': 19,
    '_description': 'ISO15693: dump timeout',
    '_default_return': -1,
}

READ_LEGIC = {
    'hf legic dump': (0, """[usb] pm3 --> hf legic dump

[+] Dumped 256 bytes
"""),
    '_tag_type': 20,
    '_description': 'LEGIC MIM256: dump success',
}

READ_LEGIC_IDENTIFY_FAIL = {
    'hf legic dump': (0, """[usb] pm3 --> hf legic dump

[-] Failed to identify tagtype
"""),
    '_tag_type': 20,
    '_description': 'LEGIC: failed to identify tag type',
}

READ_LEGIC_CARD_SELECT_FAIL = {
    'hf legic dump': (0, """[usb] pm3 --> hf legic dump

[-] Can't select card
"""),
    '_tag_type': 20,
    '_description': 'LEGIC: card select failed',
}

# --- LF generic failure (covers all LF 125KHz types) ---
READ_LF_FAIL = {
    # No command keys — the LF read command won't match anything in this fixture,
    # so it falls through to the scan fixture's _default_return (-1) → PM3 error.
    # Do NOT set _default_return here — it would override scan responses too.
    '_tag_type': 8,
    '_description': 'LF: read command returns empty / timeout → "Read Failed!"',
}

# --- T55xx additional branches ---
READ_LF_T55XX_WITH_PASSWORD = {
    'lf t55xx chk': (0, """[usb] pm3 --> lf t55xx chk f key3

[+] Found valid password: 51243648
"""),
    'lf t55xx detect': (0, """[usb] pm3 --> lf t55xx detect p 51243648

[=] Chip Type      : T55x7
[=] Modulation     : ASK
[=] Block0         : 0x00148040
"""),
    'lf t55xx dump': (0, """[usb] pm3 --> lf t55xx dump p 51243648

[+] saved 12 blocks
"""),
    '_tag_type': 23,
    '_description': 'T55XX: password found via chk → detect+dump with password',
}

READ_LF_T55XX_DETECT_FAIL = {
    'lf t55xx chk': (0, """[usb] pm3 --> lf t55xx chk f key3

[-] No valid password found
"""),
    'lf t55xx detect': (-1, ''),
    '_tag_type': 23,
    '_description': 'T55XX: no password, detect fails → "Read Failed!"',
    '_default_return': -1,
}

# --- EM4305 branches ---
READ_LF_EM4305_SUCCESS = {
    'lf em 4x05_info': (0, """Chip Type  | EM4x05/EM4x69
ConfigWord: 600150E0 (xx)
Serial : AABBCCDD
"""),
    'lf em 4x05_dump': (0, """[usb] pm3 --> lf em 4x05_dump

[+] saved 64 bytes to binary file
"""),
    '_tag_type': 24,
    '_description': 'EM4305: info (Chip Type format) + dump success',
}

READ_LF_EM4305_FAIL = {
    'lf em 4x05_info': (-1, ''),
    '_tag_type': 24,
    '_description': 'EM4305: info fails → "Read Failed!"',
    '_default_return': -1,
}

# --- EM4305 scan fixture (uses lf em 4x05_info directly, not lf sea) ---
SCAN_EM4305 = {
    'lf em 4x05_info': (0, """Chip Type  | EM4x05/EM4x69
ConfigWord: 600150E0 (xx)
Serial : AABBCCDD
"""),
    '_description': 'EM4305/EM4469 chip (scan via info4X05)',
    '_tag_type': 24,
}

# --- FeliCa read ---
READ_FELICA_SUCCESS = {
    'hf felica litedump': (0, """[usb] pm3 --> hf felica litedump

[+] FeliCa Lite dump
[+] Block  0: 01 FE 01 02 03 04 05 06
[+] Block  1: 00 00 00 00 00 00 00 00
"""),
    '_tag_type': 21,
    '_description': 'FeliCa Lite: litedump success',
}

READ_FELICA_FAIL = {
    'hf felica litedump': (-1, ''),
    # Do NOT include 'hf felica reader' — that's used by SCAN, must succeed
    '_tag_type': 21,
    '_description': 'FeliCa: litedump timeout (scan succeeds, read fails)',
    '_default_return': -1,
}

# --- T55xx block read variants (covered by detect+dump, but listed separately in .so) ---
READ_LF_T55XX_BLOCK_READ = {
    'lf t55xx detect': (0, "[=] Chip Type      : T55x7\n[=] Block0         : 0x00148040\n"),
    'lf t55xx read b 0': (0, "[usb] pm3 --> lf t55xx read b 0\n\n[+] Block 0: 00148040\n"),
    'lf t55xx read b': (0, "[usb] pm3 --> lf t55xx read\n\n[+] Block data read\n"),
    'lf t55xx dump': (0, "[+] saved 12 blocks\n"),
    '_tag_type': 23,
    '_description': 'T55XX: detect + block reads + dump',
}

# --- EM4305 block read ---
READ_LF_EM4305_BLOCK_READ = {
    'lf em 4x05_info': (0, "Chip Type  | EM4x05/EM4x69\nConfigWord: 600150E0 (xx)\nSerial : AABBCCDD\n"),
    'lf em 4x05_read': (0, "[usb] pm3 --> lf em 4x05_read 0\n\n[+] Block 0: AABBCCDD\n"),
    'lf em 4x05_dump': (0, "[+] saved 64 bytes to binary file\n"),
    '_tag_type': 24,
    '_description': 'EM4305: info (Chip Type) + block read + dump',
}

# ============================================================================
# WRITE FIXTURES — additional branches from .so pattern analysis
# ============================================================================

WRITE_MF1K_GEN1A_CLOAD = {
    'hf mf cgetblk': (0, "[usb] pm3 --> hf mf cgetblk 0\n[+] Block 0: 2CADC2729C4C4545000000000000000\n"),
    'hf mf cload': (0, "[usb] pm3 --> hf mf cload b /tmp/dump.bin\n[+] Card loaded 64 blocks from file\n"),
    '_description': 'Gen1a: cload 64 blocks — matches "Card loaded \\d+ blocks from file"',
}

WRITE_MF1K_GEN1A_UID = {
    'hf mf cgetblk': (0, "[+] Block 0: 2CADC2729C4C4545000000000000000\n"),
    'hf mf csetuid': (0, "[usb] pm3 --> hf mf csetuid AABBCCDD 08 0004 w\n[+] New UID: AA BB CC DD\n[+] Old UID: 2C AD C2 72\n"),
    '_description': 'Gen1a: UID-only write — matches "New UID" or "Old UID"',
}

WRITE_MF1K_STANDARD_PARTIAL = {
    'hf 14a info': (0, "[usb] pm3 --> hf 14a info\n\n[+]  UID: 2C AD C2 72\n[+] ATQA: 00 04\n[+]  SAK: 08 [2]\n"),
    'hf mf cgetblk': (-1, ''),  # Not gen1a
    'hf mf wrbl': (0, "[-] isOk:00\n"),  # wrbl fails
    '_description': 'Standard write: some blocks fail (isOk:00)',
}

WRITE_MF1K_VERIFY_FAIL = {
    'hf 14a info': (0, "[usb] pm3 --> hf 14a info\n\n[+]  UID: 2C AD C2 72\n[+] ATQA: 00 04\n[+]  SAK: 08 [2]\n"),
    'hf mf cgetblk': (-1, ''),
    'hf mf wrbl': (0, "[+] isOk:01\n"),  # Write succeeds
    'hf mf rdsc': (0, _rdsc_response()),  # Read back for verify
    '_description': 'Write succeeds but verify reads different data',
}

WRITE_ULTRALIGHT_SUCCESS = {
    'hf mfu restore': (0, """[usb] pm3 --> hf mfu restore s e f /tmp/dump.bin

[=] Restoring to card...
"""),
    '_description': 'Ultralight/NTAG: restore success (no "failed to write block")',
}

WRITE_ULTRALIGHT_FAIL = {
    'hf mfu restore': (0, """[usb] pm3 --> hf mfu restore s e f /tmp/dump.bin

[!] failed to write block 4
[!] failed to write block 5
"""),
    '_description': 'Ultralight/NTAG: restore with block write failures',
}

WRITE_ULTRALIGHT_CANT_SELECT = {
    'hf mfu restore': (0, """[usb] pm3 --> hf mfu restore s e f /tmp/dump.bin

[!] Can't select card
"""),
    '_description': "Ultralight/NTAG: can't select card during restore",
}

WRITE_MF1K_GEN1A_CLOAD_FAIL = {
    'hf mf cgetblk': (0, "[usb] pm3 --> hf mf cgetblk 0\n[+] Block 0: 2CADC2729C4C4545000000000000000\n"),
    'hf mf cload': (-1, ''),
    '_description': 'Gen1a: cload timeout — write fails',
    '_default_return': -1,
}

WRITE_LF_VERIFY_MISMATCH = {
    'lf em 410x_write': (0, "[+] Success writing to tag\n"),
    # Verify re-scans but finds different UID
    'lf em 410x': (0, """[usb] pm3 --> lf em 410x_read

[+] EM 410x ID FFFFFFFFFF

EM TAG ID      : FFFFFFFFFF
"""),
    '_description': 'LF verify mismatch: write succeeds but re-read returns different UID',
}

WRITE_ICLASS_SUCCESS = {
    'hf iclass wrbl': (0, """[usb] pm3 --> hf iclass wrbl -b 6 -d 0102030405060708 -k aea684a6dab21232

[+] Write block 6 successful
"""),
    '_description': 'iCLASS: block write success — hasKeyword("successful")',
}

WRITE_ICLASS_FAIL = {
    'hf iclass wrbl': (-1, ''),
    '_description': 'iCLASS: block write timeout',
    '_default_return': -1,
}

WRITE_ICLASS_KEY_CALC = {
    'hf iclass calcnewkey': (0, """[usb] pm3 --> hf iclass calcnewkey o aea684a6dab21232 n 0102030405060708

[+] Xor div key : AB CD EF 01 23 45 67 89
"""),
    'hf iclass wrbl': (0, "[+] Write block 3 successful\n"),
    '_description': 'iCLASS: key calculation + write — hasKeyword("successful") + regex "Xor div key"',
}

WRITE_ICLASS_KEY_CALC_FAIL = {
    'hf iclass calcnewkey': (-1, ''),
    '_description': 'iCLASS: key calculation fails',
    '_default_return': -1,
}

# ============================================================================
# LF WRITE FIXTURES — derived from real device traces (2026-03-28)
#
# Real write sequence (from fdxb_t55_write_trace_20260328.txt):
#   1. lf t55xx wipe p 20206666
#   2. lf t55xx detect (after wipe — ASK, Block0: 000880E0, Password Set: No)
#   3. lf t55xx detect (second pass)
#   4. lf <type> clone ... (the actual write)
#   5. lf t55xx detect (after clone — new modulation)
#   6. lf t55xx write b 7 d 20206666 (DRM password)
#   7. lf t55xx write b 0 d <config|pwd_bit> (DRM config)
#   8. lf t55xx detect p 20206666 (verify with password)
#   9. lf sea (verify tag identity)
#  10. lf <type> read (verify data match)
#
# The mock uses substring matching, keys sorted by length DESC.
# ============================================================================

# Common wipe + detect responses used by all LF clone writes
_LF_WIPE_RESP = """[usb] pm3 --> lf t55xx wipe p 20206666

[=] Begin wiping T55x7 tag

[=] Default configation block 000880E0
[=] Writing page 0  block: 00  data: 0x000880E0 pwd: 0x20206666
[=] Writing page 0  block: 01  data: 0x00000000
[=] Writing page 0  block: 02  data: 0x00000000
[=] Writing page 0  block: 03  data: 0x00000000
[=] Writing page 0  block: 04  data: 0x00000000
[=] Writing page 0  block: 05  data: 0x00000000
[=] Writing page 0  block: 06  data: 0x00000000
"""

_LF_DETECT_AFTER_WIPE = """[usb] pm3 --> lf t55xx detect

[=]      Chip Type      : T55x7
[=]      Modulation     : ASK
[=]      Bit Rate       : 2 - RF/32
[=]      Inverted       : No
[=]      Offset         : 33
[=]      Seq. Term.     : Yes
[=]      Block0         : 0x000880E0
[=]      Downlink Mode  : default/fixed bit length
[=]      Password Set   : No
"""

# Original T55XX detect response — shows the tag's actual config before wipe
# Used during READ phase and after restore for T55XX-to-T55XX write
_LF_DETECT_ORIGINAL = """[usb] pm3 --> lf t55xx detect

[=]      Chip Type      : T55x7
[=]      Modulation     : ASK
[=]      Bit Rate       : 5 - RF/64
[=]      Inverted       : No
[=]      Offset         : 33
[=]      Seq. Term.     : Yes
[=]      Block0         : 0x00148040
[=]      Downlink Mode  : default/fixed bit length
[=]      Password Set   : No
"""

_LF_WRITE_B7_RESP = """[=] Writing page 0  block: 07  data: 0x20206666
"""

_LF_WRITE_B0_RESP = """[=] Writing page 0  block: 00  data: 0x00098090
"""

WRITE_LF_EM410X = {
    'lf t55xx wipe': (0, _LF_WIPE_RESP),
    'lf t55xx detect': (0, _LF_DETECT_AFTER_WIPE),
    'lf em 410x_write': (0, """[usb] pm3 --> lf em 410x_write 0F0368568B 1

[+] Writing T55x7 tag with UID 0x0F0368568B
[+] Blk | Data
[+] ----+------------
[+]  00 | 00148040
[+]  01 | FF8C6584
[+]  02 | 00680D1A
"""),
    'lf t55xx write b 7': (0, _LF_WRITE_B7_RESP),
    'lf t55xx write b 0': (0, _LF_WRITE_B0_RESP),
    'lf t55xx detect p': (0, _LF_DETECT_AFTER_WIPE.replace('Password Set   : No', 'Password Set   : Yes\n[=]      Password       : 20206666')),
    'lf sea': (0, """[usb] pm3 --> lf search

[+] Valid EM410x ID found!
[+] EM410x - Tag ID: 0F0368568B
"""),
    '_description': 'EM410x: wipe + detect + clone + DRM password + verify (from real trace)',
}

WRITE_LF_HID_CLONE = {
    'lf t55xx wipe': (0, _LF_WIPE_RESP),
    'lf t55xx detect': (0, _LF_DETECT_AFTER_WIPE),
    'lf hid clone': (0, """[usb] pm3 --> lf hid clone -r 200068012345

[+] Preparing to clone HID tag
[+] Blk | Data
[+] ----+------------
[+]  00 | 00107060
"""),
    'lf t55xx write b 7': (0, _LF_WRITE_B7_RESP),
    'lf t55xx write b 0': (0, _LF_WRITE_B0_RESP),
    'lf t55xx detect p': (0, _LF_DETECT_AFTER_WIPE.replace('Password Set   : No', 'Password Set   : Yes\n[=]      Password       : 20206666')),
    'lf sea': (0, """[usb] pm3 --> lf search

[+] Valid HID Prox ID found!
[+] HID Prox - 200068012345
"""),
    '_description': 'HID Prox: wipe + detect + clone + DRM + verify (from real trace)',
}

WRITE_LF_T55XX_RESTORE = {
    'lf t55xx wipe': (0, _LF_WIPE_RESP),
    # Sequential detect: original(READ) x2, wiped(after wipe) x2, original(after restore/verify)
    'lf t55xx detect': [
        (0, _LF_DETECT_ORIGINAL),
        (0, _LF_DETECT_ORIGINAL),
        (0, _LF_DETECT_AFTER_WIPE),
        (0, _LF_DETECT_AFTER_WIPE),
        (0, _LF_DETECT_ORIGINAL),
    ],
    'lf t55xx restore': (0, """[usb] pm3 --> lf t55xx restore f /mnt/upan/dump/t55xx/dump.bin

[+] loaded 48 bytes from binary file /mnt/upan/dump/t55xx/dump.bin
[=] Writing page 0  block: 01  data: 0x00000000
[=] Writing page 0  block: 02  data: 0x00000000
[=] Writing page 0  block: 03  data: 0x00000000
[=] Writing page 0  block: 04  data: 0x00000000
[=] Writing page 0  block: 05  data: 0x00000000
[=] Writing page 0  block: 06  data: 0x00000000
"""),
    # After restore, detect should see the original config restored
    'lf t55xx read b 0': (0, """[+] Reading Page 0:
[+] blk | hex data | binary                           | ascii
[+] ----+----------+----------------------------------+-------
[+]  00 | 00148040 | 00000000000101001000000001000000 | ..@
"""),
    'lf t55xx read b': (0, """[+] Reading Page 0:
[+] blk | hex data | binary                           | ascii
[+] ----+----------+----------------------------------+-------
[+]  01 | 00000000 | 00000000000000000000000000000000 | ....
"""),
    '_description': 'T55XX: wipe + restore + verify read-back (from real trace t55_to_t55)',
}

WRITE_LF_T55XX_BLOCK = {
    'lf t55xx wipe': (0, _LF_WIPE_RESP),
    # Sequential detect: original(READ) x2, wiped(after wipe) x2, original(after block writes/verify)
    'lf t55xx detect': [
        (0, _LF_DETECT_ORIGINAL),
        (0, _LF_DETECT_ORIGINAL),
        (0, _LF_DETECT_AFTER_WIPE),
        (0, _LF_DETECT_AFTER_WIPE),
        (0, _LF_DETECT_ORIGINAL),
    ],
    'lf t55xx write': (0, """[=] Writing page 0  block: 00  data: 0x00148040
"""),
    'lf t55xx read b 0': (0, """[+] Reading Page 0:
[+] blk | hex data | binary                           | ascii
[+] ----+----------+----------------------------------+-------
[+]  00 | 00148040 | 00000000000101001000000001000000 | ..@
"""),
    'lf t55xx read b': (0, """[+] Reading Page 0:
[+] blk | hex data | binary                           | ascii
[+] ----+----------+----------------------------------+-------
[+]  01 | 00000000 | 00000000000000000000000000000000 | ....
"""),
    '_description': 'T55XX: wipe + block write + verify (from real trace)',
}

WRITE_ISO15693_SUCCESS = {
    'hf 15 restore': (0, """[usb] pm3 --> hf 15 restore f /tmp/dump.bin

[+] Write OK
"""),
    '_description': 'ISO15693: restore with "Write OK"',
}

WRITE_ISO15693_FAIL = {
    'hf 15 restore': (0, """[usb] pm3 --> hf 15 restore f /tmp/dump.bin

[-] restore failed
"""),
    '_description': 'ISO15693: restore failed',
}

# ============================================================================
# ERASE FIXTURES — from activity_main.so wipe patterns
# ============================================================================

ERASE_MF1_SUCCESS = {
    'hf 14a info': (0, "[usb] pm3 --> hf 14a info\n\n[+]  UID: 2C AD C2 72\n[+] ATQA: 00 04\n[+]  SAK: 08 [2]\n[+] Possible types:\n[+]    MIFARE Classic 1K\n"),
    'hf mf fchk': (0, _fchk_all_found_1k()),
    'hf mf wrbl': (0, "[+] isOk:01\n"),
    'hf mf cgetblk': (-1, ''),  # Not gen1a
    '_description': 'Erase MF1: all keys found, wipe succeeds — "Card wiped successfully"',
}

ERASE_MF1_NO_KEYS = {
    'hf 14a info': (0, "[usb] pm3 --> hf 14a info\n\n[+]  UID: AA BB CC DD\n[+] ATQA: 00 04\n[+]  SAK: 08 [2]\n[+] Possible types:\n[+]    MIFARE Classic 1K\n[+] Static nonce: yes\n"),
    'hf mf fchk': (0, _fchk_no_keys_1k()),
    'hf mf darkside': (-1, '[-] Card not vulnerable\n'),
    '_description': 'Erase MF1: no keys recoverable — "No valid keys" toast',
}

ERASE_MF1_GEN1A = {
    'hf 14a info': (0, "[usb] pm3 --> hf 14a info\n\n[+]  UID: 11 22 33 44\n[+] ATQA: 00 04\n[+]  SAK: 08 [2]\n[+] Possible types:\n[+]    MIFARE Classic 1K\n"),
    'hf mf cgetblk': (0, "[+] Block 0: 112233449C4C4545000000000000000\n[+] isOk:01\n"),
    'hf mf wrbl': (0, "[+] isOk:01\n"),
    '_description': 'Erase MF1 Gen1a: magic card wipe via backdoor',
}

ERASE_T5577_SUCCESS = {
    'lf t55xx detect': (0, "[=] Chip Type      : T55x7\n[=] Block0         : 0x00148040\n"),
    'lf t55xx wipe': (0, "[usb] pm3 --> lf t55xx wipe\n\n[+] Card wiped\n"),
    '_description': 'Erase T5577: detect + wipe success',
}

ERASE_T5577_FAIL = {
    'lf t55xx detect': (0, "[=] Chip Type      : T55x7\n[=] Block0         : 0x00148040\n"),
    'lf t55xx wipe': (-1, ''),
    '_description': 'Erase T5577: wipe timeout',
    '_default_return': -1,
}

# ============================================================================
# DIAGNOSIS FIXTURES — additional
# ============================================================================

DIAGNOSIS_HW_TUNE_HF_FAIL = {
    'hw tune': (0, """[usb] pm3 --> hw tune
[=] Measuring antenna characteristics, please wait...

[=] ---------- LF Antenna ----------
[+] LF antenna: 32.44 V - 125.00 kHz
[+] LF antenna is OK

[=] ---------- HF Antenna ----------
[+] HF antenna: 0.08 V - 13.56 MHz
[!] HF antenna is NOT OK
"""),
    '_description': 'Hardware antenna test — HF fail, LF pass',
}

# ============================================================================
# SNIFF FIXTURES
# ============================================================================

SNIFF_14A_TRACE = {
    'hf 14a sniff': (0, """[usb] pm3 --> hf 14a sniff

[+] trace len = 1234
"""),
    '_description': '14A sniff: trace captured',
}

SNIFF_T5577_KEYS = {
    'lf t55xx sniff': (0, """[usb] pm3 --> lf t55xx sniff

[+] Default pwd write | 51243648 |
[+] Default write | 00148040 |
[+] key 51243648
"""),
    '_description': 'T5577 sniff: password recovered',
}

SNIFF_EMPTY = {
    'hf 14a sniff': (0, """[usb] pm3 --> hf 14a sniff

[-] No data captured
"""),
    '_description': 'Sniff: no data captured',
}

# ============================================================================
# AUTOCOPY ADDITIONAL FIXTURES
# ============================================================================

AUTO_COPY_NO_TAG = {
    '_default_return': -1,
    '_description': 'Auto Copy: no tag on reader — all PM3 commands timeout',
    '_tag_type': -1,
}

AUTO_COPY_VERIFY_FAIL = {
    'hf 14a info': (0, "[usb] pm3 --> hf 14a info\n\n[+]  UID: 2C AD C2 72\n[+] ATQA: 00 04\n[+]  SAK: 08 [2]\n[+] Possible types:\n[+]    MIFARE Classic 1K\n[+] Prng detection: weak\n"),
    'hf 14a raw': (0, "[-] isOk:00\n"),
    'hf mf fchk': (0, _fchk_all_found_1k()),
    'hf mf rdsc': (0, _rdsc_response()),
    'hf mf wrbl': (0, "[+] isOk:01\n"),
    'hf mf cgetblk': (-1, ''),
    '_default_return': -1,
    '_description': 'Auto Copy: scan+read+write succeed, verify reads mismatched data',
    '_tag_type': 1,
}


# ======================================================================
# LF TAG TYPE FIXTURES — scan + read + write for all 18 missing LF types
# Generated from V1090_PM3_PATTERN_MAP.md ground truth
# ======================================================================

SCAN_AWID = {
    'hf 14a info': HF14A_NO_TAG,
    'hf sea': HFSEA_NO_TAG,
    'lf sea': (0, """[usb] pm3 --> lf search

[+] Valid AWID ID
[+] FC: 123, CN: 4567
[+] Raw: 2004800000
"""),
    '_description': 'Valid AWID ID',
    '_tag_type': 11,
}

READ_LF_AWID = {
    'lf awid read': (0, """[usb] pm3 --> lf awid read

[+] Valid AWID ID
[+] FC: 123, CN: 4567
[+] Raw: 2004800000
"""),
    '_tag_type': 11,
    '_description': 'awid read success',
}

WRITE_LF_AWID = {
    'lf t55xx wipe': (0, _LF_WIPE_RESP),
    'lf t55xx detect': (0, _LF_DETECT_AFTER_WIPE),
    'lf awid clone': (0, """[usb] pm3 --> lf awid clone --fc 123 --cn 4567
[+] Preparing to clone AWID to T55x7
"""),
    'lf t55xx write b 7': (0, _LF_WRITE_B7_RESP),
    'lf t55xx write b 0': (0, _LF_WRITE_B0_RESP),
    'lf sea': (0, """[+] Valid AWID ID\n[+] FC: 123, CN: 4567\n[+] Raw: 2004800000\n"""),
    '_description': 'AWID: wipe + detect + clone + DRM + verify',
}

SCAN_IOPRX = {
    'hf 14a info': HF14A_NO_TAG,
    'hf sea': HFSEA_NO_TAG,
    'lf sea': (0, """[usb] pm3 --> lf search

[+] Valid IO Prox ID
[+] XSF(01)01:12345
"""),
    '_description': 'Valid IO Prox ID',
    '_tag_type': 12,
}

READ_LF_IOPRX = {
    'lf io read': (0, """[usb] pm3 --> lf io read

[+] Valid IO Prox ID
[+] XSF(01)01:12345
[+] FC: 01, CN: 12345
[+] Raw: 007E0180A5
"""),
    '_tag_type': 12,
    '_description': 'ioprx read success',
}

WRITE_LF_IOPRX = {
    'lf t55xx wipe': (0, _LF_WIPE_RESP),
    'lf t55xx detect': (0, _LF_DETECT_AFTER_WIPE),
    'lf io clone': (0, "[+] Preparing to clone IO Prox to T55x7\n"),
    'lf t55xx write b 7': (0, _LF_WRITE_B7_RESP),
    'lf t55xx write b 0': (0, _LF_WRITE_B0_RESP),
    'lf sea': (0, "[+] Valid IO Prox ID\n[+] XSF(01)01:12345\n"),
    '_description': 'IO Prox: wipe + detect + clone + DRM + verify',
}

SCAN_GPROX = {
    'hf 14a info': HF14A_NO_TAG,
    'hf sea': HFSEA_NO_TAG,
    'lf sea': (0, """[usb] pm3 --> lf search

[+] Valid Guardall G-Prox II ID
[+] FC: 123, CN: 4567
"""),
    '_description': 'Valid Guardall G-Prox II ID',
    '_tag_type': 13,
}

READ_LF_GPROX = {
    'lf gproxii read': (0, """[usb] pm3 --> lf gproxii read

[+] Valid Guardall G-Prox II ID
[+] FC: 123, CN: 4567
[+] Raw: 0880088008800880
"""),
    '_tag_type': 13,
    '_description': 'gprox read success',
}

WRITE_LF_GPROX = {
    'lf t55xx wipe': (0, _LF_WIPE_RESP),
    'lf t55xx detect': (0, _LF_DETECT_AFTER_WIPE),
    'lf gproxii clone': (0, "[+] Preparing to clone G-Prox II to T55x7\n"),
    'lf t55xx write b 7': (0, _LF_WRITE_B7_RESP),
    'lf t55xx write b 0': (0, _LF_WRITE_B0_RESP),
    'lf sea': (0, "[+] Valid Guardall G-Prox II ID\n[+] FC: 123, CN: 4567\n[+] Raw: 0880088008800880\n"),
    '_description': 'GProx II: wipe + detect + clone + DRM + verify',
}

SCAN_SECURAKEY = {
    'hf 14a info': HF14A_NO_TAG,
    'hf sea': HFSEA_NO_TAG,
    'lf sea': (0, """[usb] pm3 --> lf search

[+] Valid Securakey ID
[+] Raw: AABBCCDD00112233
"""),
    '_description': 'Valid Securakey ID',
    '_tag_type': 14,
}

READ_LF_SECURAKEY = {
    'lf securakey read': (0, """[usb] pm3 --> lf securakey read

[+] Valid Securakey ID
[+] Raw: AABBCCDD00112233
"""),
    '_tag_type': 14,
    '_description': 'securakey read success',
}

WRITE_LF_SECURAKEY = {
    'lf t55xx wipe': (0, _LF_WIPE_RESP),
    'lf t55xx detect': (0, _LF_DETECT_AFTER_WIPE),
    'lf securakey clone': (0, "[+] Preparing to clone Securakey to T55x7\n"),
    'lf t55xx write b 7': (0, _LF_WRITE_B7_RESP),
    'lf t55xx write b 0': (0, _LF_WRITE_B0_RESP),
    'lf sea': (0, "[+] Valid Securakey ID\n[+] Raw: AABBCCDD00112233\n"),
    '_description': 'Securakey: wipe + detect + clone + DRM + verify',
}

SCAN_VIKING = {
    'hf 14a info': HF14A_NO_TAG,
    'hf sea': HFSEA_NO_TAG,
    'lf sea': (0, """[usb] pm3 --> lf search

[+] Valid Viking ID
[+] Card ID: 12345678
"""),
    '_description': 'Valid Viking ID',
    '_tag_type': 15,
}

READ_LF_VIKING = {
    'lf viking read': (0, """[usb] pm3 --> lf viking read

[+] Viking - Card 12345678, Raw: 1234567800112233
"""),
    '_tag_type': 15,
    '_description': 'viking read success',
}

WRITE_LF_VIKING = {
    'lf t55xx wipe': (0, _LF_WIPE_RESP),
    'lf t55xx detect': (0, _LF_DETECT_AFTER_WIPE),
    'lf viking clone': (0, "[+] Preparing to clone Viking to T55x7\n"),
    'lf t55xx write b 7': (0, _LF_WRITE_B7_RESP),
    'lf t55xx write b 0': (0, _LF_WRITE_B0_RESP),
    'lf sea': (0, "[+] Valid Viking ID\n[+] Card ID: 12345678\n"),
    '_description': 'Viking: wipe + detect + clone + DRM + verify',
}

SCAN_PYRAMID = {
    'hf 14a info': HF14A_NO_TAG,
    'hf sea': HFSEA_NO_TAG,
    'lf sea': (0, """[usb] pm3 --> lf search

[+] Valid Pyramid ID
[+] FC: 123, CN: 4567
"""),
    '_description': 'Valid Pyramid ID',
    '_tag_type': 16,
}

READ_LF_PYRAMID = {
    'lf pyramid read': (0, """[usb] pm3 --> lf pyramid read

[+] Valid Pyramid ID
[+] FC: 123, CN: 4567
[+] Raw: 0000000000001E39
"""),
    '_tag_type': 16,
    '_description': 'pyramid read success',
}

WRITE_LF_PYRAMID = {
    'lf t55xx wipe': (0, _LF_WIPE_RESP),
    'lf t55xx detect': (0, _LF_DETECT_AFTER_WIPE),
    'lf pyramid clone': (0, "[+] Preparing to clone Pyramid to T55x7\n"),
    'lf t55xx write b 7': (0, _LF_WRITE_B7_RESP),
    'lf t55xx write b 0': (0, _LF_WRITE_B0_RESP),
    'lf sea': (0, "[+] Valid Pyramid ID\n[+] FC: 123, CN: 4567\n[+] Raw: 0000000000001E39\n"),
    '_description': 'Pyramid: wipe + detect + clone + DRM + verify',
}

SCAN_FDXB = {
    'hf 14a info': HF14A_NO_TAG,
    'hf sea': HFSEA_NO_TAG,
    'lf sea': (0, """[usb] pm3 --> lf search

[+] Valid FDX-B ID
[+] Animal ID: 999-00001234567
"""),
    '_description': 'Valid FDX-B ID',
    '_tag_type': 28,
}

READ_LF_FDXB = {
    'lf fdx read': (0, """[usb] pm3 --> lf fdx read

[+] Valid FDX-B ID found!
[+] Animal ID          999-000012345678
[+] FDXB - Raw: 0103E820C00103E820C0
"""),
    '_tag_type': 28,
    '_description': 'fdxb read success',
}

WRITE_LF_FDXB = {
    'lf t55xx wipe': (0, _LF_WIPE_RESP),
    'lf t55xx detect': (0, _LF_DETECT_AFTER_WIPE),
    'lf fdx clone': (0, """[=]       Country code 999
[=]      National code 12345678
[=] Preparing to clone FDX-B to T55x7 with animal ID: 999-12345678
[+] Blk | Data
[+] ----+------------
[+]  00 | 00098080
"""),
    'lf t55xx write b 7': (0, _LF_WRITE_B7_RESP),
    'lf t55xx write b 0': (0, _LF_WRITE_B0_RESP),
    'lf sea': (0, "[+] FDX-B / ISO 11784/5 Animal\n[+] Animal ID          999-000012345678\n"),
    '_description': 'FDX-B: wipe + detect + clone + DRM + verify (from real trace)',
}

SCAN_GALLAGHER = {
    'hf 14a info': HF14A_NO_TAG,
    'hf sea': HFSEA_NO_TAG,
    'lf sea': (0, """[usb] pm3 --> lf search

[+] Valid GALLAGHER ID
[+] Raw: AABBCCDDEE001122
"""),
    '_description': 'Valid GALLAGHER ID',
    '_tag_type': 29,
}

READ_LF_GALLAGHER = {
    'lf gallagher read': (0, """[usb] pm3 --> lf gallagher read

[+] Valid GALLAGHER ID found!
[+] Raw: AABBCCDDEE001122
"""),
    '_tag_type': 29,
    '_description': 'gallagher read success',
}

WRITE_LF_GALLAGHER = {
    'lf t55xx wipe': (0, _LF_WIPE_RESP),
    'lf t55xx detect': (0, _LF_DETECT_AFTER_WIPE),
    'lf gallagher clone': (0, "[+] Preparing to clone Gallagher to T55x7\n"),
    'lf t55xx write b 7': (0, _LF_WRITE_B7_RESP),
    'lf t55xx write b 0': (0, _LF_WRITE_B0_RESP),
    'lf sea': (0, "[+] Valid GALLAGHER ID\n[+] Raw: AABBCCDDEE001122\n"),
    '_description': 'Gallagher: wipe + detect + clone + DRM + verify',
}

SCAN_JABLOTRON = {
    'hf 14a info': HF14A_NO_TAG,
    'hf sea': HFSEA_NO_TAG,
    'lf sea': (0, """[usb] pm3 --> lf search

[+] Valid Jablotron ID
[+] Card ID: 12345678
"""),
    '_description': 'Valid Jablotron ID',
    '_tag_type': 30,
}

READ_LF_JABLOTRON = {
    'lf jablotron read': (0, """[usb] pm3 --> lf jablotron read

[+] Jablotron - Card: FF010201234568, Raw: 1234567800112233
"""),
    '_tag_type': 30,
    '_description': 'jablotron read success',
}

WRITE_LF_JABLOTRON = {
    'lf t55xx wipe': (0, _LF_WIPE_RESP),
    'lf t55xx detect': (0, _LF_DETECT_AFTER_WIPE),
    'lf jablotron clone': (0, "[+] Preparing to clone Jablotron to T55x7\n"),
    'lf t55xx write b 7': (0, _LF_WRITE_B7_RESP),
    'lf t55xx write b 0': (0, _LF_WRITE_B0_RESP),
    'lf sea': (0, "[+] Valid Jablotron ID\n[+] Card ID: 12345678\n"),
    '_description': 'Jablotron: wipe + detect + clone + DRM + verify',
}

SCAN_KERI = {
    'hf 14a info': HF14A_NO_TAG,
    'hf sea': HFSEA_NO_TAG,
    'lf sea': (0, """[usb] pm3 --> lf search

[+] Valid KERI ID
[+] Card ID: 12345678
"""),
    '_description': 'Valid KERI ID',
    '_tag_type': 31,
}

READ_LF_KERI = {
    'lf keri read': (0, """[usb] pm3 --> lf keri read

[+] Valid KERI ID found!
[+] KERI - Internal ID: 12345678, Raw: 1234567800112233
"""),
    '_tag_type': 31,
    '_description': 'keri read success',
}

WRITE_LF_KERI = {
    'lf t55xx wipe': (0, _LF_WIPE_RESP),
    'lf t55xx detect': (0, _LF_DETECT_AFTER_WIPE),
    'lf keri clone': (0, "[+] Preparing to clone KERI to T55x7\n"),
    'lf t55xx write b 7': (0, _LF_WRITE_B7_RESP),
    'lf t55xx write b 0': (0, _LF_WRITE_B0_RESP),
    'lf sea': (0, "[+] Valid KERI ID\n[+] Card ID: 12345678\n"),
    '_description': 'KERI: wipe + detect + clone + DRM + verify',
}

SCAN_NEDAP = {
    'hf 14a info': HF14A_NO_TAG,
    'hf sea': HFSEA_NO_TAG,
    'lf sea': (0, """[usb] pm3 --> lf search

[+] Valid NEDAP ID
[+] Card ID: 12345678
"""),
    '_description': 'Valid NEDAP ID',
    '_tag_type': 32,
}

READ_LF_NEDAP = {
    'lf nedap read': (0, """[usb] pm3 --> lf nedap read

[+] NEDAP - Card: 12345678, Raw: 1234567800112233
"""),
    '_tag_type': 32,
    '_description': 'nedap read success',
}

WRITE_LF_NEDAP = {
    'lf t55xx wipe': (0, _LF_WIPE_RESP),
    'lf t55xx detect': (0, _LF_DETECT_AFTER_WIPE),
    'lf nedap clone': (0, "[+] Preparing to clone NEDAP to T55x7\n"),
    'lf t55xx write b 7': (0, _LF_WRITE_B7_RESP),
    'lf t55xx write b 0': (0, _LF_WRITE_B0_RESP),
    'lf sea': (0, "[+] Valid NEDAP ID\n[+] Card ID: 12345678\n"),
    '_description': 'NEDAP: wipe + detect + clone + DRM + verify',
}

SCAN_NORALSY = {
    'hf 14a info': HF14A_NO_TAG,
    'hf sea': HFSEA_NO_TAG,
    'lf sea': (0, """[usb] pm3 --> lf search

[+] Valid Noralsy ID
[+] Card ID: 12345678
"""),
    '_description': 'Valid Noralsy ID',
    '_tag_type': 33,
}

READ_LF_NORALSY = {
    'lf noralsy read': (0, """[usb] pm3 --> lf noralsy read

[+] Noralsy - Card: 12345678, Raw: 1234567800112233
"""),
    '_tag_type': 33,
    '_description': 'noralsy read success',
}

WRITE_LF_NORALSY = {
    'lf t55xx wipe': (0, _LF_WIPE_RESP),
    'lf t55xx detect': (0, _LF_DETECT_AFTER_WIPE),
    'lf noralsy clone': (0, "[+] Preparing to clone Noralsy to T55x7\n"),
    'lf t55xx write b 7': (0, _LF_WRITE_B7_RESP),
    'lf t55xx write b 0': (0, _LF_WRITE_B0_RESP),
    'lf sea': (0, "[+] Valid Noralsy ID\n[+] Card ID: 12345678\n"),
    '_description': 'Noralsy: wipe + detect + clone + DRM + verify',
}

SCAN_PAC = {
    'hf 14a info': HF14A_NO_TAG,
    'hf sea': HFSEA_NO_TAG,
    'lf sea': (0, """[usb] pm3 --> lf search

[+] Valid PAC/Stanley ID
[+] Raw: AABBCCDD00112233
"""),
    '_description': 'Valid PAC/Stanley ID',
    '_tag_type': 34,
}

READ_LF_PAC = {
    'lf pac read': (0, """[usb] pm3 --> lf pac read

[+] PAC/Stanley - Card: FF01020304050607, Raw: AABBCCDD00112233
"""),
    '_tag_type': 34,
    '_description': 'pac read success',
}

WRITE_LF_PAC = {
    'lf t55xx wipe': (0, _LF_WIPE_RESP),
    'lf t55xx detect': (0, _LF_DETECT_AFTER_WIPE),
    'lf pac clone': (0, "[+] Preparing to clone PAC/Stanley to T55x7\n"),
    'lf t55xx write b 7': (0, _LF_WRITE_B7_RESP),
    'lf t55xx write b 0': (0, _LF_WRITE_B0_RESP),
    'lf sea': (0, "[+] Valid PAC/Stanley ID\n[+] Raw: AABBCCDD00112233\n"),
    '_description': 'PAC: wipe + detect + clone + DRM + verify',
}

SCAN_PARADOX = {
    'hf 14a info': HF14A_NO_TAG,
    'hf sea': HFSEA_NO_TAG,
    'lf sea': (0, """[usb] pm3 --> lf search

[+] Valid Paradox ID
[+] FC: 123, CN: 4567
[+] Raw: AABBCCDD00112233
"""),
    '_description': 'Valid Paradox ID',
    '_tag_type': 35,
}

READ_LF_PARADOX = {
    'lf paradox read': (0, """[usb] pm3 --> lf paradox read

[+] Valid Paradox ID found!
[+] FC: 123, CN: 4567
[+] Raw: AABBCCDD00112233
"""),
    '_tag_type': 35,
    '_description': 'paradox read success',
}

WRITE_LF_PARADOX = {
    'lf t55xx wipe': (0, _LF_WIPE_RESP),
    'lf t55xx detect': (0, _LF_DETECT_AFTER_WIPE),
    'lf paradox clone': (0, "[+] Preparing to clone Paradox to T55x7\n"),
    'lf t55xx write b 7': (0, _LF_WRITE_B7_RESP),
    'lf t55xx write b 0': (0, _LF_WRITE_B0_RESP),
    'lf sea': (0, "[+] Valid Paradox ID\n[+] FC: 123, CN: 4567\n[+] Raw: AABBCCDD00112233\n"),
    '_description': 'Paradox: wipe + detect + clone + DRM + verify',
}

SCAN_PRESCO = {
    'hf 14a info': HF14A_NO_TAG,
    'hf sea': HFSEA_NO_TAG,
    'lf sea': (0, """[usb] pm3 --> lf search

[+] Valid Presco ID
[+] Card ID: 12345678
"""),
    '_description': 'Valid Presco ID',
    '_tag_type': 36,
}

READ_LF_PRESCO = {
    'lf presco read': (0, """[usb] pm3 --> lf presco read

[+] Presco - Card: 12345678, Raw: 123456780011223344556677
"""),
    '_tag_type': 36,
    '_description': 'presco read success',
}

WRITE_LF_PRESCO = {
    'lf t55xx wipe': (0, _LF_WIPE_RESP),
    'lf t55xx detect': (0, _LF_DETECT_AFTER_WIPE),
    'lf presco clone': (0, "[+] Preparing to clone Presco to T55x7\n"),
    'lf t55xx write b 7': (0, _LF_WRITE_B7_RESP),
    'lf t55xx write b 0': (0, _LF_WRITE_B0_RESP),
    'lf sea': (0, "[+] Valid Presco ID\n[+] Card ID: 12345678\n"),
    '_description': 'Presco: wipe + detect + clone + DRM + verify',
}

SCAN_VISA2000 = {
    'hf 14a info': HF14A_NO_TAG,
    'hf sea': HFSEA_NO_TAG,
    'lf sea': (0, """[usb] pm3 --> lf search

[+] Valid Visa2000 ID
[+] Card ID: 12345678
"""),
    '_description': 'Valid Visa2000 ID',
    '_tag_type': 37,
}

READ_LF_VISA2000 = {
    'lf visa2000 read': (0, """[usb] pm3 --> lf visa2000 read

[+] Visa2000 - Card 12345678, Raw: 1234567800112233
"""),
    '_tag_type': 37,
    '_description': 'visa2000 read success',
}

WRITE_LF_VISA2000 = {
    'lf t55xx wipe': (0, _LF_WIPE_RESP),
    'lf t55xx detect': (0, _LF_DETECT_AFTER_WIPE),
    'lf visa2000 clone': (0, "[+] Preparing to clone Visa2000 to T55x7\n"),
    'lf t55xx write b 7': (0, _LF_WRITE_B7_RESP),
    'lf t55xx write b 0': (0, _LF_WRITE_B0_RESP),
    'lf sea': (0, "[+] Valid Visa2000 ID\n[+] Card ID: 12345678\n"),
    '_description': 'Visa2000: wipe + detect + clone + DRM + verify',
}

SCAN_HITAG = {
    # Route D: lowTypes → scan_lfsea → "lf sea"
    # lfsearch.parser() → hasKeyword("Valid Hitag") → type=38
    # scanForType only calls scan_lfsea for LF types — no hf 14a info or hf sea
    'lf sea': (0, """[usb] pm3 --> lf search

[+] Valid Hitag
[+] UID: AABBCCDD
"""),
    '_description': 'Hitag2 — scan_lfsea→"Valid Hitag"→type 38',
    '_tag_type': 38,
}

READ_LF_HITAG = {
    'lf hitag read': (0, """[usb] pm3 --> lf hitag read

[+] Valid Hitag
[+] UID: AABBCCDD
"""),
    '_tag_type': 38,
    '_description': 'hitag read success',
}

SCAN_NEXWATCH = {
    'hf 14a info': HF14A_NO_TAG,
    'hf sea': HFSEA_NO_TAG,
    'lf sea': (0, """[usb] pm3 --> lf search

[+] Valid NexWatch ID
[+] Raw: AABBCCDD00112233
"""),
    '_description': 'Valid NexWatch ID',
    '_tag_type': 45,
}

READ_LF_NEXWATCH = {
    'lf nexwatch read': (0, """[usb] pm3 --> lf nexwatch read

[+] NexWatch, Quadrakey
[+] ID: AABBCCDD00112233
[+] Raw: AABBCCDD0011223344556677
"""),
    '_tag_type': 45,
    '_description': 'nexwatch read success',
}

WRITE_LF_NEXWATCH = {
    'lf t55xx wipe': (0, _LF_WIPE_RESP),
    'lf t55xx detect': (0, _LF_DETECT_AFTER_WIPE),
    'lf nexwatch clone': (0, "[+] Preparing to clone NexWatch to T55x7\n"),
    'lf t55xx write b 7': (0, _LF_WRITE_B7_RESP),
    'lf t55xx write b 0': (0, _LF_WRITE_B0_RESP),
    'lf sea': (0, "[+] Valid NexWatch ID\n[+] Raw: AABBCCDD00112233\n"),
    '_description': 'NexWatch: wipe + detect + clone + DRM + verify',
}

WRITE_LF_INDALA = {
    'lf t55xx wipe': (0, _LF_WIPE_RESP),
    'lf t55xx detect': (0, _LF_DETECT_AFTER_WIPE),
    'lf indala clone': (0, "[+] Preparing to clone Indala to T55x7\n"),
    'lf t55xx write b 7': (0, _LF_WRITE_B7_RESP),
    'lf t55xx write b 0': (0, _LF_WRITE_B0_RESP),
    'lf sea': (0, "[+] Valid Indala ID\n[+] Raw: A0 00 00 00 00 12 34 56\n"),
    '_description': 'Indala: wipe + detect + clone + DRM + verify',
}

WRITE_LF_EM4305_DUMP = {
    'lf em 4x05_write': (0, """[usb] pm3 --> lf em 4x05_write

[+] Success writing to tag
"""),
    '_description': 'EM4305: dump write success — hasKeyword("Success writing to tag")',
}

WRITE_LF_EM4305_FAIL = {
    'lf em 4x05_write': (-1, ''),
    '_description': 'EM4305: dump write fail — PM3 timeout',
    '_default_return': -1,
}

WRITE_LF_FAIL = {
    # Generic LF write failure — no command matches, all return -1
    '_description': 'LF write: PM3 command returns error — "Write failed!"',
    '_default_return': -1,
}

# --- T55XX additional write fixtures ---

WRITE_LF_T55XX_RESTORE_FAIL = {
    'lf t55xx wipe': (0, _LF_WIPE_RESP),
    # Sequential detect: original(READ) x2, wiped(after wipe) x2
    'lf t55xx detect': [
        (0, _LF_DETECT_ORIGINAL),
        (0, _LF_DETECT_ORIGINAL),
        (0, _LF_DETECT_AFTER_WIPE),
        (0, _LF_DETECT_AFTER_WIPE),
    ],
    'lf t55xx restore': (-1, ''),
    '_description': 'T55XX: wipe + detect OK, restore times out',
    '_default_return': -1,
}

WRITE_LF_T55XX_BLOCK_FAIL = {
    'lf t55xx wipe': (0, _LF_WIPE_RESP),
    # Sequential detect: original(READ) x2, wiped(after wipe) x2
    'lf t55xx detect': [
        (0, _LF_DETECT_ORIGINAL),
        (0, _LF_DETECT_ORIGINAL),
        (0, _LF_DETECT_AFTER_WIPE),
        (0, _LF_DETECT_AFTER_WIPE),
    ],
    'lf t55xx write': (-1, ''),
    '_description': 'T55XX: wipe + detect OK, block write times out',
    '_default_return': -1,
}

WRITE_LF_T55XX_PASSWORD_WRITE = {
    'lf t55xx wipe': (0, _LF_WIPE_RESP),
    # Sequential detect: original(READ) x2, wiped(after wipe) x2, original(after restore/verify)
    'lf t55xx detect': [
        (0, _LF_DETECT_ORIGINAL),
        (0, _LF_DETECT_ORIGINAL),
        (0, _LF_DETECT_AFTER_WIPE),
        (0, _LF_DETECT_AFTER_WIPE),
        (0, _LF_DETECT_ORIGINAL),
    ],
    'lf t55xx restore': (0, """[+] loaded 48 bytes from binary file dump.bin
[=] Writing page 0  block: 01  data: 0x00000000
[=] Writing page 0  block: 02  data: 0x00000000
[=] Writing page 0  block: 03  data: 0x00000000
[=] Writing page 0  block: 04  data: 0x00000000
[=] Writing page 0  block: 05  data: 0x00000000
[=] Writing page 0  block: 06  data: 0x00000000
"""),
    'lf t55xx read b 0': (0, """[+] Reading Page 0:
[+] blk | hex data | binary                           | ascii
[+] ----+----------+----------------------------------+-------
[+]  00 | 00148040 | 00000000000101001000000001000000 | ..@
"""),
    'lf t55xx read b': (0, """[+] Reading Page 0:
[+] blk | hex data | binary                           | ascii
[+] ----+----------+----------------------------------+-------
[+]  01 | 00000000 | 00000000000000000000000000000000 | ....
"""),
    '_description': 'T55XX: password-protected tag — wipe + restore + verify (from real trace)',
}

# --- LF verify-fail fixture ---

WRITE_LF_EM410X_VERIFY_FAIL = {
    'lf t55xx wipe': (0, _LF_WIPE_RESP),
    'lf t55xx detect': (0, _LF_DETECT_AFTER_WIPE),
    'lf em 410x_write': (0, """[+] Writing T55x7 tag with UID 0x1122334455
[+] Blk | Data
[+] ----+------------
[+]  00 | 00148040
"""),
    'lf t55xx write b 7': (0, _LF_WRITE_B7_RESP),
    'lf t55xx write b 0': (0, _LF_WRITE_B0_RESP),
    # Verify re-reads — return a DIFFERENT ID to cause mismatch
    'lf sea': (0, """[+] Valid EM410x ID found!
[+] EM410x Tag ID: 0011223344
"""),
    '_description': 'EM410x: wipe + clone succeeds, verify sees different ID — mismatch',
}

# WRITE_LF_GPROX moved to main LF write section above

WRITE_ICLASS_TAG_SELECT_FAIL = {
    'hf iclass wrbl': (0, """[usb] pm3 --> hf iclass wrbl -b 6 -d 0102030405060708 -k aea684a6dab21232

[-] failed tag-select
"""),
    '_description': 'iCLASS: tag select failure during block write',
}

WRITE_ISO15693_UID_FAIL = {
    'hf 15 csetuid': (0, """[usb] pm3 --> hf 15 csetuid E004010012345678

[-] can't read card UID
"""),
    '_description': 'ISO15693: UID set failure — hasKeyword("can\'t read card UID")',
}

# ======================================================================
# SCAN EDGE CASES — BCC0, Gen2, POSSIBLE 7B
# ======================================================================

SCAN_BCC0_INCORRECT = {
    'hf 14a info': (0, """[usb] pm3 --> hf 14a info

[+]  UID: 2C AD C2 72
[+] ATQA: 00 04
[+]  SAK: 08 [2]
[!] BCC0 incorrect, expected 0x2C != 0xFF
"""),
    '_description': 'BCC0 incorrect — UID error detection',
    '_tag_type': -1,
}

SCAN_GEN2_CUID = {
    'hf 14a info': (0, """[usb] pm3 --> hf 14a info

[+]  UID: 2C AD C2 72
[+] ATQA: 00 04
[+]  SAK: 08 [2]
[+] Possible types:
[+]    MIFARE Classic 1K / Classic 1K CL2
[+] Magic capabilities : Gen 2 / CUID
[+] Prng detection: weak
"""),
    '_description': 'Gen 2 / CUID magic card',
    '_tag_type': 1,
}

SCAN_MF_POSSIBLE_7B = {
    'hf 14a info': (0, """[usb] pm3 --> hf 14a info

[+]  UID: 04 A1 B2 C3 D4 E5 F6
[+] ATQA: 00 44
[+]  SAK: 08 [2]
[+] Possible types:
[+]    MIFARE Classic
[+]    MIFARE Plus 2K / Plus EV1 2K
[=] proprietary non iso14443-4 card found, RATS not supported
[+] Static nonce: yes
"""),
    'hf mf cgetblk': CGETBLK_NOT_GEN1A,
    '_description': 'MIFARE POSSIBLE 7B (type 44)',
    '_tag_type': 44,
}
# ============================================================================
# UPDATED MASTER INDEXES
# ============================================================================


# ======================================================================
# READ TAG MODE — LF scan-phase fixtures
# scanForType for LF types sends lfread.READ[typ]() = type-specific read cmd
# SEPARATE from Scan Tag fixtures which use lf sea.
# Real device trace confirmed 2026-03-26.
# ======================================================================

RSCAN_EM410X = {
    'lf em 410x': (0, '''[usb] pm3 --> lf em 410x_read

[+] EM 410x ID 0F0368568B

EM TAG ID      : 0F0368568B

Possible de-scramble patterns

Unique TAG ID  : F0C016A5D1

[+] Raw: 0FFE8C6A00

[+] Raw: 1234567800

[+] Raw: 0001E2403B

[+] Raw: 007E0180A5

[+] Raw: 0103E820C0

[+] Raw: 1234567800

[+] Raw: 1234567800

[+] Raw: 1234567800

[+] Raw: 1234567800

[+] Raw: 1234567800

[+] Raw: 1234567800
'''),
    '_description': 'Read Tag scan: lfread.READ[8] sends lf em 410x',
    '_tag_type': 8,
}

RSCAN_HID_PROX = {
    'lf hid read': (0, '''[usb] pm3 --> lf hid read

[+] Valid HID Prox ID found!
[+] HID Prox - 200068012345
'''),
    '_description': 'Read Tag scan: lfread.READ[9] sends lf hid read',
    '_tag_type': 9,
}

RSCAN_INDALA = {
    'lf indala read': (0, '''[usb] pm3 --> lf indala read

[+] Valid Indala ID
[+] Raw: A0 00 00 00 00 12 34 56
'''),
    '_description': 'Read Tag scan: lfread.READ[10] sends lf indala read',
    '_tag_type': 10,
}

RSCAN_AWID = {
    'lf awid read': (0, '''[usb] pm3 --> lf awid read

[+] Valid AWID ID
[+] FC: 123, CN: 4567
[+] Raw: 2004800000
'''),
    '_description': 'Read Tag scan: lfread.READ[11] sends lf awid read',
    '_tag_type': 11,
}

RSCAN_IOPRX = {
    'lf io read': (0, '''[usb] pm3 --> lf io read

[+] Valid IO Prox ID
[+] XSF(01)01:12345

[+] Raw: 007E0180A5
'''),
    '_description': 'Read Tag scan: lfread.READ[12] sends lf io read',
    '_tag_type': 12,
}

RSCAN_GPROX = {
    'lf gproxii read': (0, '''[usb] pm3 --> lf gproxii read

[+] Valid Guardall G-Prox II ID
[+] FC: 123, CN: 4567

[+] Raw: 0FFE8C6A00
'''),
    '_description': 'Read Tag scan: lfread.READ[13] sends lf gproxii read',
    '_tag_type': 13,
}

RSCAN_SECURAKEY = {
    'lf securakey read': (0, '''[usb] pm3 --> lf securakey read

[+] Valid Securakey ID
[+] Raw: AABBCCDD00112233
'''),
    '_description': 'Read Tag scan: lfread.READ[14] sends lf securakey read',
    '_tag_type': 14,
}

RSCAN_VIKING = {
    'lf viking read': (0, '''[usb] pm3 --> lf viking read

[+] Viking - Card 12345678, Raw: 1234567800112233
'''),
    '_description': 'Read Tag scan: lfread.READ[15] sends lf viking read',
    '_tag_type': 15,
}

RSCAN_PYRAMID = {
    'lf pyramid read': (0, '''[usb] pm3 --> lf pyramid read

[+] Valid Pyramid ID
[+] FC: 123, CN: 4567

[+] Raw: 0001E2403B
'''),
    '_description': 'Read Tag scan: lfread.READ[16] sends lf pyramid read',
    '_tag_type': 16,
}

RSCAN_FDXB = {
    'lf fdx read': (0, '''[usb] pm3 --> lf fdx read

[+] Valid FDX-B ID found!
[+] Animal ID          999-000012345678
[+] FDXB - Raw: 0103E820C00103E820C0
'''),
    '_description': 'Read Tag scan: lfread.READ[28] sends lf fdx read',
    '_tag_type': 28,
}

RSCAN_GALLAGHER = {
    'lf gallagher read': (0, '''[usb] pm3 --> lf gallagher read

[+] Valid GALLAGHER ID found!
[+] Raw: AABBCCDDEE001122
'''),
    '_description': 'Read Tag scan: lfread.READ[29] sends lf gallagher read',
    '_tag_type': 29,
}

RSCAN_JABLOTRON = {
    'lf jablotron read': (0, '''[usb] pm3 --> lf jablotron read

[+] Jablotron - Card: FF010201234568, Raw: 1234567800112233
'''),
    '_description': 'Read Tag scan: lfread.READ[30] sends lf jablotron read',
    '_tag_type': 30,
}

RSCAN_KERI = {
    'lf keri read': (0, '''[usb] pm3 --> lf keri read

[+] Valid KERI ID found!
[+] KERI - Internal ID: 12345678, Raw: 1234567800112233
'''),
    '_description': 'Read Tag scan: lfread.READ[31] sends lf keri read',
    '_tag_type': 31,
}

RSCAN_NEDAP = {
    'lf nedap read': (0, '''[usb] pm3 --> lf nedap read

[+] NEDAP - Card: 12345678, Raw: 1234567800112233
'''),
    '_description': 'Read Tag scan: lfread.READ[32] sends lf nedap read',
    '_tag_type': 32,
}

RSCAN_NORALSY = {
    'lf noralsy read': (0, '''[usb] pm3 --> lf noralsy read

[+] Noralsy - Card: 12345678, Raw: 1234567800112233
'''),
    '_description': 'Read Tag scan: lfread.READ[33] sends lf noralsy read',
    '_tag_type': 33,
}

RSCAN_PAC = {
    'lf pac read': (0, '''[usb] pm3 --> lf pac read

[+] PAC/Stanley - Card: FF01020304050607, Raw: AABBCCDD00112233
'''),
    '_description': 'Read Tag scan: lfread.READ[34] sends lf pac read',
    '_tag_type': 34,
}

RSCAN_PARADOX = {
    'lf paradox read': (0, '''[usb] pm3 --> lf paradox read

[+] Valid Paradox ID found!
[+] FC: 123, CN: 4567
[+] Raw: AABBCCDD00112233
'''),
    '_description': 'Read Tag scan: lfread.READ[35] sends lf paradox read',
    '_tag_type': 35,
}

RSCAN_PRESCO = {
    'lf presco read': (0, '''[usb] pm3 --> lf presco read

[+] Presco - Card: 12345678, Raw: 123456780011223344556677
'''),
    '_description': 'Read Tag scan: lfread.READ[36] sends lf presco read',
    '_tag_type': 36,
}

RSCAN_VISA2000 = {
    'lf visa2000 read': (0, '''[usb] pm3 --> lf visa2000 read

[+] Visa2000 - Card 12345678, Raw: 1234567800112233
'''),
    '_description': 'Read Tag scan: lfread.READ[37] sends lf visa2000 read',
    '_tag_type': 37,
}

RSCAN_NEXWATCH = {
    'lf nexwatch read': (0, '''[usb] pm3 --> lf nexwatch read

[+] NexWatch, Quadrakey
[+] ID: AABBCCDD00112233
[+] Raw: AABBCCDD0011223344556677
'''),
    '_description': 'Read Tag scan: lfread.READ[45] sends lf nexwatch read',
    '_tag_type': 45,
}

# ============================================================================
# WRITE SCENARIO RESPONSES — complete SCENARIO_RESPONSES dicts for write walker
# Each extends the base scan+read data with write-specific overrides.
# These are DATA, not logic — just PM3 response constants.
# ============================================================================

# Base MFC 1K 4B responses — scan + read (keys found, sectors readable)
_BASE_MFC_1K_4B = {
    'hf 14a info': SCAN_MF_CLASSIC_1K_4B['hf 14a info'],
    'hf 14a reader': SCAN_MF_CLASSIC_1K_4B['hf 14a reader'],
    'hf mf fchk': READ_MF1K_ALL_DEFAULT_KEYS['hf mf fchk'],
    'hf mf rdsc': READ_MF1K_ALL_DEFAULT_KEYS['hf mf rdsc'],
}

# MFC 1K 4B: standard write success (non-Gen1a target)
# cgetblk returns ret=0 (completed) with error text — .so checks response, not ret
WRITE_SCENARIO_MFC_1K_4B_STANDARD_SUCCESS = {
    **_BASE_MFC_1K_4B,
    'hf mf cgetblk': CGETBLK_NOT_GEN1A,  # "Can't set magic card block" — .so hasKeyword check
    'hf 14a raw': WRITE_STANDARD_SUCCESS['hf 14a raw'],  # tagChk1 Gen1a raw detection → isOk:00
    'hf mf wrbl': WRITE_STANDARD_SUCCESS['hf mf wrbl'],  # isOk:01
}

# MFC 1K 4B: standard write failure (non-Gen1a, wrbl fails)
WRITE_SCENARIO_MFC_1K_4B_STANDARD_FAIL = {
    **_BASE_MFC_1K_4B,
    'hf mf cgetblk': CGETBLK_NOT_GEN1A,  # "Can't set magic card block"
    'hf mf wrbl': WRITE_STANDARD_FAIL['hf mf wrbl'],    # isOk:00
}

# MFC 1K 4B: Gen1a cload success
WRITE_SCENARIO_MFC_1K_4B_GEN1A_SUCCESS = {
    **_BASE_MFC_1K_4B,
    'hf mf cgetblk': (0, "[+] Block 0: 112233449C08040000000000000000000\n"),  # Gen1a detected
    'hf mf cload': WRITE_GEN1A_SUCCESS['hf mf cload'],
    'hf 14a raw': WRITE_GEN1A_SUCCESS['hf 14a raw'],
}

ALL_WRITE_SCENARIO_RESPONSES = {
    'mfc_1k_4b__write_standard_success': WRITE_SCENARIO_MFC_1K_4B_STANDARD_SUCCESS,
    'mfc_1k_4b__write_standard_fail': WRITE_SCENARIO_MFC_1K_4B_STANDARD_FAIL,
    'mfc_1k_4b__write_gen1a_success': WRITE_SCENARIO_MFC_1K_4B_GEN1A_SUCCESS,
}

# ============================================================================
# MASTER INDEXES
# ============================================================================

ALL_SCAN_SCENARIOS = {
    'no_tag': SCAN_NO_TAG,
    'mf_classic_1k_4b': SCAN_MF_CLASSIC_1K_4B,
    'mf_classic_1k_7b': SCAN_MF_CLASSIC_1K_7B,
    'mf_classic_4k_4b': SCAN_MF_CLASSIC_4K_4B,
    'mf_classic_4k_7b': SCAN_MF_CLASSIC_4K_7B,
    'mf_mini': SCAN_MF_MINI,
    'mf_ultralight': SCAN_MF_ULTRALIGHT,
    'mf_ultralight_c': SCAN_MF_ULTRALIGHT_C,
    'mf_ultralight_ev1': SCAN_MF_ULTRALIGHT_EV1,
    'ntag213': SCAN_NTAG213,
    'ntag215': SCAN_NTAG215,
    'ntag216': SCAN_NTAG216,
    'mf_desfire': SCAN_MF_DESFIRE,
    'multi_tags': SCAN_MULTI_TAGS,
    'mf_possible_4b': SCAN_MF_POSSIBLE_4B,
    'hf14a_other': SCAN_HF14A_OTHER,
    'iclass': SCAN_ICLASS,
    'iclass_elite': SCAN_ICLASS_ELITE,
    'iclass_se': SCAN_ICLASS_SE,
    'iso15693_icode': SCAN_ISO15693_ICODE,
    'iso15693_st': SCAN_ISO15693_ST,
    'legic': SCAN_LEGIC,
    'iso14443b': SCAN_ISO14443B,
    'topaz': SCAN_TOPAZ,
    'felica': SCAN_FELICA,
    'em410x': SCAN_EM410X,
    'hid_prox': SCAN_HID_PROX,
    'indala': SCAN_INDALA,
    't55xx_blank': SCAN_T55XX_BLANK,
    't55xx_read_success': SCAN_T55XX_READ_SUCCESS,
    't55xx_read_with_password': SCAN_T55XX_READ_WITH_PASSWORD,
    't55xx_read_detect_fail': SCAN_T55XX_READ_DETECT_FAIL,
    'awid': SCAN_AWID,
    'ioprx': SCAN_IOPRX,
    'gprox': SCAN_GPROX,
    'securakey': SCAN_SECURAKEY,
    'viking': SCAN_VIKING,
    'pyramid': SCAN_PYRAMID,
    'fdxb': SCAN_FDXB,
    'gallagher': SCAN_GALLAGHER,
    'jablotron': SCAN_JABLOTRON,
    'keri': SCAN_KERI,
    'nedap': SCAN_NEDAP,
    'noralsy': SCAN_NORALSY,
    'pac': SCAN_PAC,
    'paradox': SCAN_PARADOX,
    'presco': SCAN_PRESCO,
    'visa2000': SCAN_VISA2000,
    'hitag': SCAN_HITAG,
    'nexwatch': SCAN_NEXWATCH,
    'bcc0_incorrect': SCAN_BCC0_INCORRECT,
    'gen2_cuid': SCAN_GEN2_CUID,
    'mf_possible_7b': SCAN_MF_POSSIBLE_7B,
    'mf_classic_1k_gen1a': SCAN_MF_CLASSIC_1K_GEN1A,
    'em4305': SCAN_EM4305,
    # Read Tag mode LF scan fixtures
    'read_em410x': RSCAN_EM410X,
    'read_hid_prox': RSCAN_HID_PROX,
    'read_indala': RSCAN_INDALA,
    'read_awid': RSCAN_AWID,
    'read_ioprx': RSCAN_IOPRX,
    'read_gprox': RSCAN_GPROX,
    'read_securakey': RSCAN_SECURAKEY,
    'read_viking': RSCAN_VIKING,
    'read_pyramid': RSCAN_PYRAMID,
    'read_fdxb': RSCAN_FDXB,
    'read_gallagher': RSCAN_GALLAGHER,
    'read_jablotron': RSCAN_JABLOTRON,
    'read_keri': RSCAN_KERI,
    'read_nedap': RSCAN_NEDAP,
    'read_noralsy': RSCAN_NORALSY,
    'read_pac': RSCAN_PAC,
    'read_paradox': RSCAN_PARADOX,
    'read_presco': RSCAN_PRESCO,
    'read_visa2000': RSCAN_VISA2000,
    'read_nexwatch': RSCAN_NEXWATCH,
}

ALL_READ_SCENARIOS = {
    # --- MIFARE Classic 1K: all 27 branches ---
    'mf1k_all_default_keys': READ_MF1K_ALL_DEFAULT_KEYS,          # Branch 1: fchk all found → read
    'mf1k_partial_fchk': READ_MF1K_PARTIAL_FCHK,                  # Branch 2: fchk partial → nested → read
    'mf1k_no_keys': READ_MF1K_NO_KEYS,                            # Branch 3/5: no keys → darkside → nested
    'mf1k_fchk_timeout': READ_MF1K_FCHK_TIMEOUT,                  # Branch 4: fchk timeout
    'mf1k_darkside_fail': READ_MF1K_DARKSIDE_FAIL,                # Branch 6: darkside "not vulnerable"
    'mf1k_darkside_nested_fail': READ_MF1K_DARKSIDE_NESTED_FAIL,  # Branch 7: darkside → nested "not vulnerable" → Warning
    'mf1k_darkside_to_nested_alt': READ_MF1K_DARKSIDE_TO_NESTED_ALT,      # Branch 8: darkside → "Try nested"
    'mf1k_darkside_card_lost': READ_MF1K_DARKSIDE_CARD_LOST,      # Branch 9: darkside → card lost
    'mf1k_darkside_timeout': READ_MF1K_DARKSIDE_TIMEOUT,          # Branch 10: darkside timeout
    'mf1k_partial_nested_success': READ_MF1K_PARTIAL_NESTED_SUCCESS,  # Branch 11: nested → all keys
    'mf1k_nested_retry': READ_MF1K_NESTED_RETRY,                  # Branch 12: nested → retry → success
    'mf1k_nested_abort': READ_MF1K_NESTED_ABORT,                  # Branch 13: nested → user abort
    'mf1k_nested_timeout': READ_MF1K_NESTED_TIMEOUT,              # Branch 14: nested timeout
    'mf1k_nested_partial': READ_MF1K_NESTED_PARTIAL,              # Branch 14b: nested fails entirely
    'mf1k_nested_not_vulnerable': READ_MF1K_NESTED_NOT_VULNERABLE,  # Branch 15: nested "not vulnerable" → Warning
    'mf1k_hardnested_success': READ_MF1K_HARDNESTED_SUCCESS,      # Branch 16: hardnested → key found
    'mf1k_hardnested_fail': READ_MF1K_HARDNESTED_FAIL,            # Branch 17: hardnested → fail
    'mf1k_partial_read': READ_MF1K_PARTIAL_READ,                  # Branch 19: some sectors Auth error
    'mf1k_tag_lost': READ_MF1K_TAG_LOST,                          # Branch 20: card lost mid-read
    'mf1k_card_lost_mid_read': READ_MF1K_CARD_LOST_MID_READ,      # Branch 20b: card lost after sector 4
    'mf1k_all_sectors_fail': READ_MF1K_ALL_SECTORS_FAIL,          # Branch 21: every sector Auth error
    'mf1k_read_block_error': READ_MF1K_READ_BLOCK_ERROR,          # Branch 21b: hardware Read block error
    'mf1k_gen1a_csave_success': READ_MF1K_GEN1A_CSAVE_SUCCESS,    # Branch 22: Gen1a csave success
    'mf1k_gen1a_csave_fail': READ_MF1K_GEN1A_CSAVE_FAIL,          # Branch 23: Gen1a csave fail → standard
    # --- MIFARE Classic variant types (same read path) ---
    'mf_mini_all_keys': READ_MF_MINI_ALL_KEYS,
    'mf_plus_2k_all_keys': READ_MF_PLUS_2K_ALL_KEYS,
    'mf1k_7b_all_keys': READ_MF1K_7B_ALL_KEYS,
    'mf4k_7b_all_keys': READ_MF4K_7B_ALL_KEYS,
    # --- MIFARE Classic 4K variants ---
    'mf4k_all_keys': READ_MF4K_ALL_KEYS,
    'mf4k_no_keys': READ_MF4K_NO_KEYS,
    'mf4k_partial_fchk': READ_MF4K_PARTIAL_FCHK,
    'mf4k_darkside_fail': READ_MF4K_DARKSIDE_FAIL,
    'mf4k_gen1a_csave_success': READ_MF4K_GEN1A_CSAVE_SUCCESS,
    'mf4k_gen1a_csave_fail': READ_MF4K_GEN1A_CSAVE_FAIL,
    # --- Ultralight/NTAG ---
    'ultralight_success': READ_ULTRALIGHT_SUCCESS,
    'ultralight_partial': READ_ULTRALIGHT_PARTIAL,
    'ultralight_card_select_fail': READ_ULTRALIGHT_CARD_SELECT_FAIL,
    'ultralight_empty': READ_ULTRALIGHT_EMPTY,
    'ntag215_success': READ_NTAG215_SUCCESS,
    # --- Ultralight/NTAG variant types (same read path) ---
    'ultralight_c_success': READ_ULTRALIGHT_C_SUCCESS,
    'ultralight_ev1_success': READ_ULTRALIGHT_EV1_SUCCESS,
    'ntag213_success': READ_NTAG213_SUCCESS,
    'ntag216_success': READ_NTAG216_SUCCESS,
    # --- iCLASS ---
    'iclass_legacy': READ_ICLASS_LEGACY,
    'iclass_no_key': READ_ICLASS_NO_KEY,
    'iclass_dump_fail': READ_ICLASS_DUMP_FAIL,
    'iclass_elite': READ_ICLASS_ELITE,
    # --- ISO15693 ---
    'iso15693': READ_ISO15693,
    'iso15693_st': READ_ISO15693_ST,
    'iso15693_no_tag': READ_ISO15693_NO_TAG,
    'iso15693_timeout': READ_ISO15693_TIMEOUT,
    # --- LEGIC ---
    'legic': READ_LEGIC,
    'legic_identify_fail': READ_LEGIC_IDENTIFY_FAIL,
    'legic_card_select_fail': READ_LEGIC_CARD_SELECT_FAIL,
    # --- LF generic ---
    'lf_fail': READ_LF_FAIL,
    'lf_em410x': READ_LF_EM410X,
    'lf_hid': READ_LF_HID,
    'lf_indala': {'lf indala read': (0, "[usb] pm3 --> lf indala read\n\n[+] Valid Indala ID\n[+] Raw: A0 00 00 00 00 12 34 56\n"), '_tag_type': 10, '_description': 'Indala read success'},
    # --- T55xx ---
    'lf_t55xx': READ_LF_T55XX,
    'lf_t55xx_with_password': READ_LF_T55XX_WITH_PASSWORD,
    'lf_t55xx_detect_fail': READ_LF_T55XX_DETECT_FAIL,
    # --- EM4305 ---
    'lf_em4305_success': READ_LF_EM4305_SUCCESS,
    'lf_em4305_fail': READ_LF_EM4305_FAIL,
    'lf_em4305_block_read': READ_LF_EM4305_BLOCK_READ,
    # --- FeliCa ---
    'felica_success': READ_FELICA_SUCCESS,
    'felica_fail': READ_FELICA_FAIL,
    # --- T55xx block read ---
    'lf_t55xx_block_read': READ_LF_T55XX_BLOCK_READ,
    # LF type reads
    'lf_awid': READ_LF_AWID,
    'lf_io': READ_LF_IOPRX,
    'lf_gprox': READ_LF_GPROX,
    'lf_securakey': READ_LF_SECURAKEY,
    'lf_viking': READ_LF_VIKING,
    'lf_pyramid': READ_LF_PYRAMID,
    'lf_fdxb': READ_LF_FDXB,
    'lf_gallagher': READ_LF_GALLAGHER,
    'lf_jablotron': READ_LF_JABLOTRON,
    'lf_keri': READ_LF_KERI,
    'lf_nedap': READ_LF_NEDAP,
    'lf_noralsy': READ_LF_NORALSY,
    'lf_pac': READ_LF_PAC,
    'lf_paradox': READ_LF_PARADOX,
    'lf_presco': READ_LF_PRESCO,
    'lf_visa2000': READ_LF_VISA2000,
    'lf_hitag': READ_LF_HITAG,
    'lf_nexwatch': READ_LF_NEXWATCH,
}

ALL_WRITE_SCENARIOS = {
    'gen1a_success': WRITE_GEN1A_SUCCESS,
    'gen1a_cload': WRITE_MF1K_GEN1A_CLOAD,
    'gen1a_uid': WRITE_MF1K_GEN1A_UID,
    'standard_success': WRITE_STANDARD_SUCCESS,
    'standard_fail': WRITE_STANDARD_FAIL,
    'standard_partial': WRITE_MF1K_STANDARD_PARTIAL,
    'verify_fail': WRITE_MF1K_VERIFY_FAIL,
    'ultralight_success': WRITE_ULTRALIGHT_SUCCESS,
    'ultralight_fail': WRITE_ULTRALIGHT_FAIL,
    'iclass_success': WRITE_ICLASS_SUCCESS,
    'iclass_fail': WRITE_ICLASS_FAIL,
    'iclass_key_calc': WRITE_ICLASS_KEY_CALC,
    'iclass_key_calc_fail': WRITE_ICLASS_KEY_CALC_FAIL,
    'lf_em410x': WRITE_LF_EM410X,
    'lf_hid_clone': WRITE_LF_HID_CLONE,
    'lf_t55xx_restore': WRITE_LF_T55XX_RESTORE,
    'lf_t55xx_block': WRITE_LF_T55XX_BLOCK,
    'iso15693_success': WRITE_ISO15693_SUCCESS,
    'iso15693_fail': WRITE_ISO15693_FAIL,
    # LF type writes (17 types — Hitag has no write)
    'lf_awid': WRITE_LF_AWID,
    'lf_io': WRITE_LF_IOPRX,
    'lf_gprox': WRITE_LF_GPROX,
    'lf_securakey': WRITE_LF_SECURAKEY,
    'lf_viking': WRITE_LF_VIKING,
    'lf_pyramid': WRITE_LF_PYRAMID,
    'lf_fdxb': WRITE_LF_FDXB,
    'lf_gallagher': WRITE_LF_GALLAGHER,
    'lf_jablotron': WRITE_LF_JABLOTRON,
    'lf_keri': WRITE_LF_KERI,
    'lf_nedap': WRITE_LF_NEDAP,
    'lf_noralsy': WRITE_LF_NORALSY,
    'lf_pac': WRITE_LF_PAC,
    'lf_paradox': WRITE_LF_PARADOX,
    'lf_presco': WRITE_LF_PRESCO,
    'lf_visa2000': WRITE_LF_VISA2000,
    'lf_nexwatch': WRITE_LF_NEXWATCH,
    # New fixtures from first-principles audit (2026-03-26)
    'lf_indala': WRITE_LF_INDALA,
    'lf_em4305_dump': WRITE_LF_EM4305_DUMP,
    'lf_em4305_fail': WRITE_LF_EM4305_FAIL,
    'lf_write_fail': WRITE_LF_FAIL,
    'iclass_tag_select_fail': WRITE_ICLASS_TAG_SELECT_FAIL,
    'iso15693_uid_fail': WRITE_ISO15693_UID_FAIL,
    # New fixtures for write flow tests (2026-03-28)
    'ultralight_cant_select': WRITE_ULTRALIGHT_CANT_SELECT,
    'gen1a_cload_fail': WRITE_MF1K_GEN1A_CLOAD_FAIL,
    'lf_verify_mismatch': WRITE_LF_VERIFY_MISMATCH,
    # New fixtures from write flow audit (2026-03-28)
    'lf_t55xx_restore_fail': WRITE_LF_T55XX_RESTORE_FAIL,
    'lf_t55xx_block_fail': WRITE_LF_T55XX_BLOCK_FAIL,
    'lf_t55xx_password_write': WRITE_LF_T55XX_PASSWORD_WRITE,
    'lf_em410x_verify_fail': WRITE_LF_EM410X_VERIFY_FAIL,
    'lf_gprox': WRITE_LF_GPROX,
}

ALL_ERASE_SCENARIOS = {
    'erase_mf1_success': ERASE_MF1_SUCCESS,
    'erase_mf1_no_keys': ERASE_MF1_NO_KEYS,
    'erase_mf1_gen1a': ERASE_MF1_GEN1A,
    'erase_t5577_success': ERASE_T5577_SUCCESS,
    'erase_t5577_fail': ERASE_T5577_FAIL,
}

ALL_DIAGNOSIS_SCENARIOS = {
    'hw_tune_ok': DIAGNOSIS_HW_TUNE_OK,
    'hw_tune_lf_fail': DIAGNOSIS_HW_TUNE_LF_FAIL,
    'hw_tune_hf_fail': DIAGNOSIS_HW_TUNE_HF_FAIL,
}

ALL_SNIFF_SCENARIOS = {
    'sniff_14a_trace': SNIFF_14A_TRACE,
    'sniff_t5577_keys': SNIFF_T5577_KEYS,
    'sniff_empty': SNIFF_EMPTY,
}

ALL_AUTOCOPY_SCENARIOS = {
    # Legacy entries (in-file dicts, used by old test harness)
    'autocopy_happy': AUTO_COPY_MF1K_HAPPY,
    'autocopy_darkside': AUTO_COPY_MF1K_DARKSIDE,
    'autocopy_gen1a': AUTO_COPY_GEN1A,
    'autocopy_darkside_fail': AUTO_COPY_DARKSIDE_FAIL,
    'autocopy_write_fail': AUTO_COPY_WRITE_FAIL,
    'autocopy_no_tag': AUTO_COPY_NO_TAG,
    'autocopy_verify_fail': AUTO_COPY_VERIFY_FAIL,
    # ===================================================================
    # File-based scenarios (45 total) — generated by tools/generate_autocopy_fixtures.py
    # Each has fixture.py + .sh in tests/flows/auto-copy/scenarios/<name>/
    # ===================================================================
    # Category 1: Scan Phase Exits (3)
    'autocopy_scan_no_tag': {'_description': 'No tag found — all PM3 commands timeout', '_tag_type': -1, '_file_based': True},
    'autocopy_scan_multi_tag': {'_description': 'Multiple tags detected (collision)', '_tag_type': -1, '_file_based': True},
    'autocopy_scan_wrong_type': {'_description': 'Wrong/unsupported tag type found', '_tag_type': -1, '_file_based': True},
    # Category 2: MF Classic Variants (9)
    'autocopy_mf1k_happy': {'_description': 'MF1K: fchk all keys → rdsc → wrbl success', '_tag_type': 1, '_file_based': True},
    'autocopy_mf1k_darkside': {'_description': 'MF1K: darkside+nested recovery → write', '_tag_type': 1, '_file_based': True},
    'autocopy_mf1k_darkside_fail': {'_description': 'MF1K: static nonce → darkside fails', '_tag_type': 1, '_file_based': True},
    'autocopy_mf1k_gen1a': {'_description': 'MF1K Gen1a: magic card → csave/cload', '_tag_type': 1, '_file_based': True},
    'autocopy_mf4k_happy': {'_description': 'MF4K: 40 sectors → read → write', '_tag_type': 0, '_file_based': True},
    'autocopy_mf1k_write_fail': {'_description': 'MF1K: wrbl isOk:00 → write failed', '_tag_type': 1, '_file_based': True},
    'autocopy_mf1k_partial_keys': {'_description': 'MF1K: partial fchk → nested incomplete → missing keys', '_tag_type': 1, '_file_based': True},
    'autocopy_mf_mini_happy': {'_description': 'MIFARE Mini (type 25): 5 sectors', '_tag_type': 25, '_file_based': True},
    'autocopy_mf1k_7b_happy': {'_description': 'MF1K 7-byte UID (type 42)', '_tag_type': 42, '_file_based': True},
    # Category 3: UL/NTAG (4)
    'autocopy_ultralight_happy': {'_description': 'MIFARE Ultralight: dump → restore', '_tag_type': 2, '_file_based': True},
    'autocopy_ntag215_happy': {'_description': 'NTAG215: dump → restore', '_tag_type': 6, '_file_based': True},
    'autocopy_ntag_write_fail': {'_description': 'NTAG215: restore fails (block write error)', '_tag_type': 6, '_file_based': True},
    'autocopy_ultralight_ev1_happy': {'_description': 'Ultralight EV1: dump → restore', '_tag_type': 4, '_file_based': True},
    # Category 4: LF Tags (20)
    'autocopy_lf_em410x': {'_description': 'LF EM410x: full pipeline + DRM + verify', '_tag_type': 8, '_file_based': True},
    'autocopy_lf_hid': {'_description': 'LF HID Prox: full pipeline + DRM + verify', '_tag_type': 9, '_file_based': True},
    'autocopy_lf_indala': {'_description': 'LF Indala: full pipeline + DRM + verify', '_tag_type': 10, '_file_based': True},
    'autocopy_lf_awid': {'_description': 'LF AWID: block writes + DRM + verify', '_tag_type': 11, '_file_based': True},
    'autocopy_lf_io_prox': {'_description': 'LF IO Prox: full pipeline + DRM + verify', '_tag_type': 12, '_file_based': True},
    'autocopy_lf_gprox': {'_description': 'LF G-Prox II: full pipeline + DRM + verify', '_tag_type': 13, '_file_based': True},
    'autocopy_lf_securakey': {'_description': 'LF Securakey: full pipeline + DRM + verify', '_tag_type': 14, '_file_based': True},
    'autocopy_lf_viking': {'_description': 'LF Viking: full pipeline + DRM + verify', '_tag_type': 15, '_file_based': True},
    'autocopy_lf_pyramid': {'_description': 'LF Pyramid: full pipeline + DRM + verify', '_tag_type': 16, '_file_based': True},
    'autocopy_lf_paradox': {'_description': 'LF Paradox: full pipeline + DRM + verify', '_tag_type': 35, '_file_based': True},
    'autocopy_lf_fdxb': {'_description': 'LF FDX-B: full pipeline + DRM + verify', '_tag_type': 28, '_file_based': True},
    'autocopy_lf_gallagher': {'_description': 'LF Gallagher: full pipeline + DRM + verify', '_tag_type': 29, '_file_based': True},
    'autocopy_lf_jablotron': {'_description': 'LF Jablotron: full pipeline + DRM + verify', '_tag_type': 30, '_file_based': True},
    'autocopy_lf_keri': {'_description': 'LF KERI: full pipeline + DRM + verify', '_tag_type': 31, '_file_based': True},
    'autocopy_lf_nedap': {'_description': 'LF NEDAP: full pipeline + DRM + verify', '_tag_type': 32, '_file_based': True},
    'autocopy_lf_noralsy': {'_description': 'LF Noralsy: full pipeline + DRM + verify', '_tag_type': 33, '_file_based': True},
    'autocopy_lf_pac': {'_description': 'LF PAC: full pipeline + DRM + verify', '_tag_type': 34, '_file_based': True},
    'autocopy_lf_presco': {'_description': 'LF Presco: full pipeline + DRM + verify', '_tag_type': 36, '_file_based': True},
    'autocopy_lf_visa2000': {'_description': 'LF Visa2000: full pipeline + DRM + verify', '_tag_type': 37, '_file_based': True},
    'autocopy_lf_nexwatch': {'_description': 'LF NexWatch: full pipeline + DRM + verify', '_tag_type': 45, '_file_based': True},
    # Category 5: T55XX/EM4305 (2)
    'autocopy_t55xx_happy': {'_description': 'T55XX: detect → dump → restore → verify', '_tag_type': 23, '_file_based': True},
    'autocopy_em4305_happy': {'_description': 'EM4305: info → dump → write → verify', '_tag_type': 24, '_file_based': True},
    # Category 6: iCLASS (2)
    'autocopy_iclass_legacy': {'_description': 'iCLASS Legacy: chk → dump → calcnewkey → wrbl', '_tag_type': 17, '_file_based': True},
    'autocopy_iclass_elite': {'_description': 'iCLASS Elite: elite key → dump → write', '_tag_type': 18, '_file_based': True},
    # Category 7: ISO15693 (2)
    'autocopy_iso15693_happy': {'_description': 'ISO15693 ICODE: dump → restore', '_tag_type': 19, '_file_based': True},
    'autocopy_iso15693_st': {'_description': 'ISO15693 ST: dump → restore + csetuid', '_tag_type': 46, '_file_based': True},
    # Category 8: Cross-type Failures (3)
    'autocopy_lf_write_fail': {'_description': 'LF EM410x: clone timeout → write failed', '_tag_type': 8, '_file_based': True},
    'autocopy_lf_verify_fail': {'_description': 'LF EM410x: write OK → verify mismatch', '_tag_type': 8, '_file_based': True},
    'autocopy_mf1k_verify_fail': {'_description': 'MF1K: write OK → readback mismatch', '_tag_type': 1, '_file_based': True},
}

# Add to total
TOTAL_SCENARIOS = (
    len(ALL_SCAN_SCENARIOS) +
    len(ALL_READ_SCENARIOS) +
    len(ALL_WRITE_SCENARIOS) +
    len(ALL_ERASE_SCENARIOS) +
    len(ALL_DIAGNOSIS_SCENARIOS) +
    len(ALL_SNIFF_SCENARIOS) +
    len(ALL_AUTOCOPY_SCENARIOS)
)

if __name__ == '__main__':
    print("PM3 Fixture Summary:")
    cats = [
        ("Scan", ALL_SCAN_SCENARIOS),
        ("Read", ALL_READ_SCENARIOS),
        ("Write", ALL_WRITE_SCENARIOS),
        ("Erase", ALL_ERASE_SCENARIOS),
        ("Diagnosis", ALL_DIAGNOSIS_SCENARIOS),
        ("Sniff", ALL_SNIFF_SCENARIOS),
        ("AutoCopy", ALL_AUTOCOPY_SCENARIOS),
    ]
    for cat_name, cat_dict in cats:
        print(f"  {cat_name}: {len(cat_dict)} scenarios")
    print(f"  TOTAL: {TOTAL_SCENARIOS}")
    print()
    for cat_name, cat_dict in cats:
        print(f"\n  === {cat_name} ===")
        for name, fixture in sorted(cat_dict.items()):
            desc = fixture.get('_description', '')
            keys = [k for k in fixture.keys() if not k.startswith('_')]
            print(f"    {name}: {len(keys)} PM3 patterns -- {desc}")
