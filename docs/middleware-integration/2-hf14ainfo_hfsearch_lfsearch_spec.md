# Leaf Parser Spec: hf14ainfo.so, hfsearch.so, lfsearch.so

**Ground truth source**: Decompiled `.so` binaries (Ghidra ARM decompilation) + extracted string tables.
All constants, regex patterns, and logic flow are cited from the binary. The archive transliterations
are used for structural reference only.

---

## 1. hf14ainfo.so -- HF 14443A Tag Parser

### 1.1 Module Overview

Parses `hf 14a info` PM3 output to extract UID, SAK, ATQA, and classify MIFARE tag types.
Also performs an active Gen1a probe via `hf mf cgetblk 0`.

**Source file**: `C:\Users\usertest\AppData\Local\Temp\tmpilmyofak\hf14ainfo.py`
(Cython 0.29.21, compiled for ARM:LE:32:v7)

**Imports**: `executor`, `tagtypes`

### 1.2 Module-Level Constants

| Constant | Value | Binary citation |
|----------|-------|-----------------|
| `CMD` | `'hf 14a info'` | STR@0x0001de26: `hf 14a info` |
| `TIMEOUT` | `5000` | `__pyx_int_5000` (STR@0x00001085) |

### 1.3 Regex Patterns (from binary string extraction)

| Pattern name | Regex value | Binary citation |
|-------------|-------------|-----------------|
| `_RE_UID` | `r'.*UID:(.*)\n'` | STR@0x0001df68: `.*UID:(.*)\n` |
| `_RE_ATQA` | `r'.*ATQA:(.*)\n'` | STR@0x0001df78: `.*ATQA:(.*)\n` |
| `_RE_SAK` | `r'.*SAK:(.*)\[.*\n'` | STR@0x0001df88: `.*SAK:(.*)\[.*\n` |
| `_RE_PRNG` | `r'.*Prng detection: (.*)\n'` | STR@0x0001dc88: `.*Prng detection: (.*)\n` |
| `_RE_ATS` | `r'.*ATS:(.*)'` | STR@0x0001dfa0: `.*ATS:(.*)` |
| `_RE_MANUFACTURER` | `r'.*MANUFACTURER:(.*)'` | STR@0x0001dde4: `.*MANUFACTURER:(.*)` |

### 1.4 Detection Keywords (from binary string extraction)

| Keyword constant | String value | Binary citation |
|-----------------|--------------|-----------------|
| `_KW_MIFARE_CLASSIC_1K` | `'MIFARE Classic 1K'` | STR@0x0001dc38 |
| `_KW_MIFARE_CLASSIC_4K` | `'MIFARE Classic 4K'` | STR@0x0001dc24 |
| `_KW_MIFARE_CLASSIC` | `'MIFARE Classic'` | STR@0x0001dd64 |
| `_KW_MIFARE_MINI` | `'MIFARE Mini'` | STR@0x0001de5c |
| `_KW_MIFARE_PLUS` | `'MIFARE Plus'` | STR@0x0001de50 |
| `_KW_MIFARE_PLUS_4K` | `'MIFARE Plus 4K'` | STR@0x0001dd34 |
| `_KW_MIFARE_ULTRALIGHT` | `'MIFARE Ultralight'` | STR@0x0001dc10 |
| `_KW_MIFARE_DESFIRE` | `'MIFARE DESFire'` | STR@0x0001dd44 |
| `_KW_NTAG` | `'NTAG'` | STR@0x0001df9c |
| `_KW_GEN1A` | `'Magic capabilities : Gen 1a'` | STR@0x0001db94 |
| `_KW_GEN2_CUID` | `'Magic capabilities : Gen 2 / CUID'` | STR@0x0001db70 |
| `_KW_STATIC_NONCE` | `'Static nonce: yes'` | STR@0x0001dc74 |
| `_KW_MULTIPLE_TAGS` | `'Multiple tags detected'` | STR@0x0001dbcc |
| `_KW_ANTICOLLISION` | `"Card doesn't support standard iso14443-3 anticollision"` | STR@0x0001daf8 |
| `_KW_BCC0_INCORRECT` | `'BCC0 incorrect'` | hf14ainfo_strings.txt line 614 |
| `_KW_PRNG_DETECTION` | `'Prng detection'` | STR@0x0001dd24 |

### 1.5 Tag Type Constants (accessed via `tagtypes` module)

These are string attribute names looked up on the `tagtypes` module at runtime:

| Attribute name | Binary citation |
|---------------|-----------------|
| `M1_S50_1K_4B` | `__pyx_k_M1_S50_1K_4B` |
| `M1_S50_1K_7B` | `__pyx_k_M1_S50_1K_7B` |
| `M1_S70_4K_4B` | `__pyx_k_M1_S70_4K_4B` |
| `M1_S70_4K_7B` | `__pyx_k_M1_S70_4K_7B` |
| `M1_MINI` | `__pyx_k_M1_MINI` |
| `M1_POSSIBLE_4B` | `__pyx_k_M1_POSSIBLE_4B` |
| `M1_POSSIBLE_7B` | `__pyx_k_M1_POSSIBLE_7B` |
| `MIFARE_DESFIRE` | `__pyx_k_MIFARE_DESFIRE` |
| `HF14A_OTHER` | `__pyx_k_HF14A_OTHER` |

Additional integer constants in binary: `__pyx_int_1`, `__pyx_int_2`, `__pyx_int_7`, `__pyx_int_8`, `__pyx_int_0`, `__pyx_int_5000`, `__pyx_int_5888`, `__pyx_int_neg_1`.

### 1.6 Exported Functions

#### `has_static_nonce() -> bool`
- **Signature**: No arguments
- **Behavior**: Calls `executor.hasKeyword('Static nonce: yes')`
- **Returns**: `True` if keyword found in cached PM3 output, `False` otherwise
- **Binary citation**: References `__pyx_kp_u_Static_nonce_yes` and `hasKeyword`

#### `has_prng_level() -> bool`
- **Signature**: No arguments
- **Behavior**: Calls `executor.hasKeyword('Prng detection')`
- **Returns**: `True` if keyword found, `False` otherwise
- **Binary citation**: References `__pyx_k_Prng_detection` (note: checks bare string, not the regex)

#### `is_gen1a_magic() -> bool`
- **Signature**: No arguments
- **Behavior**:
  1. Saves `executor.CONTENT_OUT_IN__TXT_CACHE` (binary references `__pyx_k_CONTENT_OUT_IN__TXT_CACHE`)
  2. Calls `executor.startPM3Task('hf mf cgetblk 0', ...)` -- active Gen1a backdoor probe
     (Binary references `__pyx_k_hf_mf_cgetblk_0`)
  3. If PM3 task returns success, checks `executor.getPrintContent()` for `'data:'` or success indicators
  4. Restores original cache
  5. Falls back to `executor.hasKeyword('Magic capabilities : Gen 1a')`
- **Returns**: `True` if Gen1a magic card detected, `False` otherwise
- **PM3 command**: `hf mf cgetblk 0` (binary: STR@0x0001dcb4)
- **Binary citation**: `__pyx_pw_9hf14ainfo_5is_gen1a_magic @0x00018220`, references `startPM3Task`, `getPrintContent`, `isEmptyContent`, `CONTENT_OUT_IN__TXT_CACHE`, `data:`, `fail`

#### `get_prng_level() -> str`
- **Signature**: No arguments
- **Behavior**: Calls `executor.getContentFromRegexG('.*Prng detection: (.*)\n')`, then `.strip()`
- **Returns**: Extracted PRNG level string (e.g., `'weak'`, `'hard'`)
- **Binary citation**: `__pyx_pw_9hf14ainfo_9get_prng_level @0x00014c14`

#### `get_manufacturer() -> str`
- **Signature**: No arguments
- **Behavior**: Calls `executor.getContentFromRegexG('.*MANUFACTURER:(.*)')`, then `.strip()`
- **Returns**: Manufacturer string
- **Binary citation**: `__pyx_pw_9hf14ainfo_19get_manufacturer @0x00015064`

#### `get_uid() -> str`
- **Signature**: No arguments
- **Behavior**: Calls `executor.getContentFromRegexG('.*UID:(.*)\n')`, then `.strip().replace(' ', '')`
- **Returns**: UID hex string with spaces removed
- **Binary citation**: `__pyx_pw_9hf14ainfo_11get_uid @0x00015624`

#### `get_atqa() -> str`
- **Signature**: No arguments
- **Behavior**: Calls `executor.getContentFromRegexG('.*ATQA:(.*)\n')`, then `.strip().replace(' ', '')`
- **Returns**: ATQA hex string with spaces removed
- **Binary citation**: `__pyx_pw_9hf14ainfo_15get_atqa @0x00016204`

#### `get_ats() -> str`
- **Signature**: No arguments
- **Behavior**: Calls `executor.getContentFromRegexG('.*ATS:(.*)')`, then `.strip().replace(' ', '')`
- **Returns**: ATS hex string with spaces removed
- **Binary citation**: `__pyx_pw_9hf14ainfo_17get_ats @0x00016658`

#### `get_sak() -> str`
- **Signature**: No arguments
- **Behavior**: Calls `executor.getContentFromRegexG('.*SAK:(.*)\[.*\n')`, then `.strip().replace(' ', '')`
- **Returns**: SAK hex string with spaces removed
- **Binary citation**: `__pyx_pw_9hf14ainfo_13get_sak @0x00017dcc`

#### `get_uid_length() -> int`
- **Signature**: No arguments
- **Behavior**: Gets UID via `get_uid()`, returns `len(uid) // 2`
- **Returns**: UID length in bytes (4 or 7 typically)
- **Binary citation**: `__pyx_pw_9hf14ainfo_21get_uid_length @0x0001715c`

#### `is_maybe_mifare() -> bool`
- **Signature**: No arguments
- **Behavior**: Checks if cached output indicates a potential MIFARE tag. References `getM1Types`, `is_mifare`, `tagtypes`
- **Returns**: `True`/`False`
- **Binary citation**: `__pyx_pw_9hf14ainfo_7is_maybe_mifare @0x00017800`

#### `parser() -> dict`
- **Signature**: No arguments
- **Behavior**: Main parsing function. Reads from `executor.CONTENT_OUT_IN__TXT_CACHE` (populated by prior `startPM3Task('hf 14a info', 5000)`)
- **Binary citation**: `__pyx_pw_9hf14ainfo_23parser @0x0001925c`

### 1.7 parser() Return Value Specification

The `parser()` function returns a dict with the following possible shapes:

#### Case 1: Multiple tags detected
```python
# Condition: executor.hasKeyword('Multiple tags detected')
{'found': True, 'hasMulti': True}
```

#### Case 2: Anticollision failure
```python
# Condition: executor.hasKeyword("Card doesn't support standard iso14443-3 anticollision")
{'found': False}
```

#### Case 3: BCC0 error
```python
# Condition: executor.hasKeyword('BCC0 incorrect')
{
    'found': True,
    'uid': 'BCC0 incorrect',
    'len': 0,
    'sak': 'no',
    'atqa': 'no',
    'bbcErr': True,
    'static': <bool>,   # from has_static_nonce()
    'gen1a': <bool>,     # from is_gen1a_magic()
    'type': <int>,       # tag type from classification
}
```

#### Case 4: MIFARE DESFire (without Classic 1K/4K)
```python
# Condition: hasKeyword('MIFARE DESFire') AND NOT hasKeyword('MIFARE Classic 1K')
#            AND NOT hasKeyword('MIFARE Classic 4K')
{
    'found': True,
    'uid': '<hex>',
    'len': <int>,
    'sak': '<hex>',
    'atqa': '<hex>',
    'bbcErr': False,
    'ats': '<hex>',      # OPTIONAL: only if ATS regex matches
    'type': tagtypes.MIFARE_DESFIRE,  # = 39
}
```

#### Case 5: MIFARE Ultralight / NTAG
```python
# Condition: hasKeyword('MIFARE Ultralight') OR hasKeyword('NTAG')
# (checked AFTER DESFire to avoid NTAG424DNA false positive)
{'found': True, 'isUL': True}
```

#### Case 6: Standard MIFARE classification
```python
{
    'found': True,
    'uid': '<hex>',
    'len': <int>,
    'sak': '<hex>',
    'atqa': '<hex>',
    'bbcErr': False,
    'static': <bool>,
    'gen1a': <bool>,
    'type': <int>,
    'manufacturer': '<str>',  # OPTIONAL: only for M1_POSSIBLE types
}
```

### 1.8 Tag Type Classification Logic

Priority order (from decompiled parser function):

1. **MIFARE Mini**: `hasKeyword('MIFARE Mini')` -> `tagtypes.M1_MINI`
   (checked first because Mini output also contains "MIFARE Classic 1K")

2. **MIFARE Classic 4K**: `hasKeyword('MIFARE Classic 4K')` ->
   - `uid_len == 7`: `tagtypes.M1_S70_4K_7B`
   - else: `tagtypes.M1_S70_4K_4B`

3. **MIFARE Plus 4K**: `hasKeyword('MIFARE Plus 4K')` ->
   - `uid_len == 7`: `tagtypes.M1_S70_4K_7B`
   - else: `tagtypes.M1_S70_4K_4B`

4. **MIFARE Classic 1K**: `hasKeyword('MIFARE Classic 1K')` ->
   - `uid_len == 7`: `tagtypes.M1_S50_1K_7B`
   - else: `tagtypes.M1_S50_1K_4B`

5. **Has PRNG or static nonce** (`has_prng_level()` or `has_static_nonce()`):
   - If `hasKeyword('MIFARE Classic')` or `hasKeyword('MIFARE Plus')`:
     - `uid_len == 7`: `tagtypes.M1_POSSIBLE_7B`
     - else: `tagtypes.M1_POSSIBLE_4B`
     - Sets `manufacturer` from `_RE_MANUFACTURER` regex or default `'Default 1K (4B)'`
   - Else (PRNG but no keyword):
     - `uid_len == 7`: `tagtypes.M1_S50_1K_7B`
     - else: `tagtypes.M1_S50_1K_4B`

6. **No PRNG, no static nonce**:
   - If `hasKeyword('MIFARE Classic')` or `hasKeyword('MIFARE Plus')`:
     - `uid_len == 7`: `tagtypes.M1_POSSIBLE_7B`
     - else: `tagtypes.M1_POSSIBLE_4B`
     - Sets `manufacturer` from regex or default
   - Else: `tagtypes.HF14A_OTHER`

### 1.9 Executor Interaction

| Operation | Method | Arguments |
|-----------|--------|-----------|
| Check keyword in output | `executor.hasKeyword(keyword)` | String from keyword constants |
| Extract regex match | `executor.getContentFromRegexG(pattern)` | Regex pattern strings |
| Run PM3 command | `executor.startPM3Task(cmd, timeout)` | `'hf mf cgetblk 0'`, timeout |
| Get PM3 response | `executor.getPrintContent()` | None |
| Check empty response | `executor.isEmptyContent()` | None |
| Save/restore cache | `executor.CONTENT_OUT_IN__TXT_CACHE` | Direct attribute read/write |

---

## 2. hfsearch.so -- HF Search Parser

### 2.1 Module Overview

Parses `hf search` (abbreviated `hf sea`) PM3 output to classify HF tags by protocol.
Returns a dict indicating which HF protocol was found.

**Source file**: `C:\Users\ADMINI~1\AppData\Local\Temp\1\tmprriqzsry\hfsearch.py`
(Cython 0.29.23, compiled for ARM:LE:32:v7)

**Imports**: `executor`, `hffelica`

**NOTE**: hfsearch does NOT import `tagtypes`. All type integer values are hardcoded in the binary.

### 2.2 Module-Level Constants

| Constant | Value | Binary citation |
|----------|-------|-----------------|
| `CMD` | `'hf sea'` | STR@0x00016818: `hf sea` -> `__pyx_kp_u_hf_sea` |
| `TIMEOUT` | `10000` | `__pyx_int_10000` (STR@0x00000971) |

### 2.3 Detection Keywords (from binary string extraction)

| Keyword constant | String value | Binary citation |
|-----------------|--------------|-----------------|
| `_KW_NO_KNOWN` | `'No known/supported 13.56 MHz tags found'` | STR@0x00016610: `__pyx_k_No_known_supported_13_56_MHz_tag` |
| `_KW_ICLASS` | `'Valid iCLASS tag'` | STR@0x00016674: `__pyx_kp_u_Valid_iCLASS_tag` |
| `_KW_ISO15693` | `'Valid ISO15693'` | STR@0x0001668c: `__pyx_kp_u_Valid_ISO15693` |
| `_KW_ST_MICRO` | `'ST Microelectronics SA France'` | STR@0x000166a0: `__pyx_kp_u_ST_Microelectronics_SA_France` |
| `_KW_LEGIC` | `'Valid LEGIC Prime'` | STR@0x000166d8: `__pyx_kp_u_Valid_LEGIC_Prime` |
| `_KW_FELICA` | `'Valid ISO18092 / FeliCa'` | STR@0x000166f0: `__pyx_kp_u_Valid_ISO18092_FeliCa` |
| `_KW_ISO14443B` | `'Valid ISO14443-B'` | STR@0x00016714: `__pyx_kp_u_Valid_ISO14443_B` |
| `_KW_MIFARE` | `'MIFARE'` | STR@0x00016730: `__pyx_n_u_MIFARE` |
| `_KW_TOPAZ` | `'Valid Topaz'` | STR@0x00016748: `__pyx_kp_u_Valid_Topaz` |

### 2.4 Regex Patterns (from binary string extraction)

| Pattern | Regex value | Binary citation |
|---------|-------------|-----------------|
| UID regex | `r'.*UID:\s(.*)'` | STR: `.*UID:\s(.*)` |
| UID alt regex | `r'.*UID.*:(.*)'` | STR: `.*UID.*:(.*)` |
| MSN regex | `r'.*MSN:\s(.*)'` | STR: `.*MSN:\s(.*)` |
| MCD regex | `r'.*MCD:\s(.*)'` | STR: `.*MCD:\s(.*)` |
| ATQB regex | `r'.*ATQB.*:(.*)'` | STR: `.*ATQB.*:(.*)` |
| ATQA regex | `r'.*ATQA.*:(.*)'` | STR: `.*ATQA.*:(.*)` |

### 2.5 Hardcoded Integer Constants

| Integer | Decimal | Hex | Usage |
|---------|---------|-----|-------|
| `__pyx_int_20` | 20 | 0x14 | LEGIC_MIM256 type |
| `__pyx_int_22` | 22 | 0x16 | ISO14443B type |
| `__pyx_int_27` | 27 | 0x1B | TOPAZ type |
| `__pyx_int_10000` | 10000 | 0x2710 | TIMEOUT |
| `__pyx_int_1` | 1 | 0x01 | Boolean True |

**ISO15693 types** (hardcoded as hex in decompiled code, NOT from `__pyx_int`):
- `0x13` (19) = ISO15693_ICODE (when NOT ST Microelectronics)
- `0x2e` (46) = ISO15693_ST_SA (when ST Microelectronics)

Citation: Decompiled `__pyx_pw_8hfsearch_1parser` at offset ~3606-3610:
```
uVar13 = 0x13;   // 19 = ISO15693_ICODE
...
uVar13 = 0x2e;   // 46 = ISO15693_ST_SA
...
PyLong_FromLong(uVar13);  // converts to Python int for dict
```

### 2.6 Exported Functions

#### `parser() -> dict`
- **Signature**: No arguments
- **Binary citation**: `__pyx_pw_8hfsearch_1parser @0x000138c8`

### 2.7 parser() Return Value Specification

Detection priority order (from decompiled binary, verified against string reference order):

#### Check 1: No known tag
```python
# Condition: executor.hasKeyword('No known/supported 13.56 MHz tags found')
{'found': False}
```

#### Check 2: iCLASS
```python
# Condition: executor.hasKeyword('Valid iCLASS tag')
{'found': True, 'isIclass': True}
```

#### Check 3: ISO15693
```python
# Condition: executor.hasKeyword('Valid ISO15693')
# Sub-check: executor.hasKeyword('ST Microelectronics SA France')
#   -> True:  type = 46 (ISO15693_ST_SA)
#   -> False: type = 19 (ISO15693_ICODE)
#
# UID extraction: executor.getContentFromRegexG('.*UID:\s(.*)')
#   -> .strip().replace(' ', '')
{
    'found': True,
    'uid': '<hex>',
    'type': 19  # or 46 for ST Micro
}
```

#### Check 4: LEGIC Prime
```python
# Condition: executor.hasKeyword('Valid LEGIC Prime')
# MCD extraction: executor.getContentFromRegexG('.*MCD:\s(.*)')
# MSN extraction: executor.getContentFromRegexG('.*MSN:\s(.*)')
{
    'found': True,
    'mcd': '<hex>',
    'msn': '<hex>',
    'type': 20  # LEGIC_MIM256
}
```

#### Check 5: ISO14443-B
```python
# Condition: executor.hasKeyword('Valid ISO14443-B')
# UID extraction: executor.getContentFromRegexG('.*UID.*:(.*)')
# ATQB extraction: executor.getContentFromRegexG('.*ATQB.*:(.*)')
{
    'found': True,
    'uid': '<hex>',
    'atqb': '<hex>',
    'type': 22  # ISO14443B
}
```

#### Check 6: MIFARE (ISO14443-A)
```python
# Condition: executor.hasKeyword('MIFARE')
{'found': True, 'isMifare': True}
```

#### Check 7: Topaz
```python
# Condition: executor.hasKeyword('Valid Topaz')
# UID extraction: executor.getContentFromRegexG('.*UID.*:(.*)')
# ATQA extraction: executor.getContentFromRegexG('.*ATQA.*:(.*)')
{
    'found': True,
    'uid': '<hex>',
    'atqa': '<hex>',
    'type': 27  # TOPAZ
}
```

#### Check 8: FeliCa
```python
# Condition: executor.hasKeyword('Valid ISO18092 / FeliCa')
# NOTE: FeliCa detection is present in the binary (keyword check exists),
# but the archive shows it returns {'found': False} or delegates to hffelica module.
# The binary imports hffelica but FeliCa handling returns found=False from hfsearch.
```

#### Default: No tag
```python
{'found': False}
```

### 2.8 Executor Interaction

| Operation | Method | Arguments |
|-----------|--------|-----------|
| Check keyword | `executor.hasKeyword(keyword)` | Detection keyword strings |
| Extract regex | `executor.getContentFromRegexG(pattern)` | Regex patterns above |

The `hffelica` module is imported but FeliCa detection through hfsearch returns `found=False`.
Actual FeliCa handling is done separately by `scan.so` calling `hffelica.parser()` directly.

---

## 3. lfsearch.so -- LF Search Parser

### 3.1 Module Overview

Parses `lf search` (abbreviated `lf sea`) PM3 output to identify LF tag types.
Contains helper functions for hex string cleaning, FC/CN extraction, and UID/RAW data extraction.

**Source file**: `C:\Users\usertest\AppData\Local\Temp\tmp1f20_vuj\lfsearch.py`
(Cython 0.29.21, compiled for ARM:LE:32:v7)

**Imports**: `executor`, `re`, `tagtypes`

### 3.2 Module-Level Constants

| Constant | Value | Binary citation |
|----------|-------|-----------------|
| `CMD` | `'lf sea'` | STR@0x000212bc: `lf sea` |
| `TIMEOUT` | `10000` | STR@0x0002126c: `TIMEOUT` + `__pyx_int_10000` |
| `COUNT` | `0` | STR@0x00021330: `COUNT` + `__pyx_int_0` |

### 3.3 Public Regex Patterns (module-level, from binary string extraction)

| Pattern name | Regex value | Binary citation |
|-------------|-------------|-----------------|
| `REGEX_ANIMAL` | `r'.*ID\s+([xX0-9A-Fa-f\-]{2,})'` | STR@0x000210a0 + lfsearch_strings.txt line 1171 |
| `REGEX_CARD_ID` | `r'(?:Card\|ID\|id\|CARD\|ID\|UID\|uid\|Uid)\s*:*\s*([xX0-9a-fA-F ]+)'` | STR@0x00020cf0 |
| `REGEX_EM410X` | `r'EM TAG ID\s+:[\s]+([xX0-9a-fA-F]+)'` | lfsearch_strings.txt line 1159 |
| `REGEX_HID` | `r'HID Prox - ([xX0-9a-fA-F]+)'` | STR@0x00020df8 |
| `REGEX_PROX_ID_XSF` | `r'(XSF\(.*?\).*?:[xX0-9a-fA-F]+)'` | lfsearch_strings.txt line 1183 |
| `REGEX_RAW` | `r'.*(?:Raw\|Raw\|RAW\|hex\|HEX\|Hex)\s*:*\s*([xX0-9a-fA-F ]+)'` | lfsearch_strings.txt line 1153 |

### 3.4 Internal Regex Patterns (from binary string extraction)

| Pattern | Regex value | Binary citation |
|---------|-------------|-----------------|
| `_RE_FC` | `r'FC:*\s+([xX0-9a-fA-F]+)'` | STR@0x00020e30 area, lfsearch_strings.txt line 1182 |
| `_RE_CN` | `r'(CN\|Card\|Card ID):*\s+(\d+)'` | STR@0x00020e30 |
| `_RE_LEN` | `r'(len\|Len\|LEN\|format\|Format):*\s+(\d+)'` | STR@0x00020d2c |
| `_RE_CHIPSET` | `r'Chipset detection:\s(.*)'` | STR@0x00020e14 |
| `_RE_SUBTYPE` | `r'subtype:*\s+(\d+)'` | STR@0x000210d0 |
| `_RE_CUSTOMER_CODE` | `r'customer code:*\s+(\d+)'` | STR@0x00020ebc |

### 3.5 Detection Keywords (from binary string extraction)

| Keyword | String value | Binary citation |
|---------|--------------|-----------------|
| `_KW_NO_KNOWN` | `'No known 125/134 kHz tags found!'` | STR@0x00020ca8 |
| `_KW_NO_DATA` | `'No data found!'` | STR@0x00021070 |
| `_KW_CHIPSET_DETECTION` | `'Chipset detection'` | STR@0x00020f24 |
| `_KW_CHIPSET_EM4X05` | `'Chipset detection: EM4x05 / EM4x69'` | STR@0x00020ccc |

**Tag detection keywords** (all from binary string table):

| Keyword | Binary citation |
|---------|-----------------|
| `'Valid EM410x ID'` | STR@0x00020ff0 |
| `'Valid HID Prox ID'` | STR@0x00020efc |
| `'Valid AWID ID'` | STR@0x00021050 |
| `'Valid IO Prox ID'` | STR@0x00020f74 |
| `'Valid Indala ID'` | STR@0x00020fe0 |
| `'Valid Viking ID'` | STR@0x00020fc0 |
| `'Valid Pyramid ID'` | STR@0x00020f38 |
| `'Valid Jablotron ID'` | STR@0x00020e74 |
| `'Valid NEDAP ID'` | STR@0x00021020 |
| `'Valid Guardall G-Prox II ID'` | STR@0x00020d54 |
| `'Valid FDX-B ID'` | STR@0x00021030 |
| `'Valid Securakey ID'` | STR@0x00020e60 |
| `'Valid KERI ID'` | STR@0x00021040 |
| `'Valid PAC/Stanley ID'` | STR@0x00020de0 |
| `'Valid Paradox ID'` | STR@0x00020f4c |
| `'Valid NexWatch ID'` | STR@0x00020ee8 |
| `'Valid Visa2000 ID'` | STR@0x00020ed4 |
| `'Valid GALLAGHER ID'` | STR@0x00020e88 |
| `'Valid Noralsy ID'` | STR@0x00020f60 |
| `'Valid Presco ID'` | STR@0x00020fd0 |
| `'Valid Hitag'` | STR@0x000210fc |

### 3.6 Tag Type Constants (accessed via `tagtypes` module)

These attribute names are looked up on the `tagtypes` module at runtime:

| Attribute | Binary citation |
|-----------|-----------------|
| `EM410X_ID` | `__pyx_n_s_EM410X_ID` (STR@0x00021223) |
| `HID_PROX_ID` | `__pyx_n_s_HID_PROX_ID` (STR@0x00021120) |
| `INDALA_ID` | `__pyx_n_s_INDALA_ID` (STR@0x000211c8) |
| `AWID_ID` | `__pyx_n_s_AWID_ID` (STR@0x00021284) |
| `IO_PROX_ID` | `__pyx_n_s_IO_PROX_ID` (STR@0x00021180) |
| `GPROX_II_ID` | `__pyx_n_s_GPROX_II_ID` (STR@0x0002112c) |
| `SECURAKEY_ID` | `__pyx_n_s_SECURAKEY_ID` (STR@0x00021080) |
| `VIKING_ID` | `__pyx_n_s_VIKING_ID` (STR@0x00021198) |
| `PYRAMID_ID` | `__pyx_n_s_PYRAMID_ID` (STR@0x0002115c) |
| `FDXB_ID` | `__pyx_n_s_FDXB_ID` (STR@0x00021240) |
| `GALLAGHER_ID` | `__pyx_n_s_GALLAGHER_ID` (STR@0x000210c0) |
| `JABLOTRON_ID` | `__pyx_n_s_JABLOTRON_ID` (STR@0x000210b0) |
| `KERI_ID` | `__pyx_n_s_KERI_ID` (STR@0x00021274) |
| `NEDAP_ID` | `__pyx_n_s_NEDAP_ID` (STR@0x00021228) |
| `NORALSY_ID` | `__pyx_n_s_NORALSY_ID` (STR@0x00021174) |
| `PAC_ID` | `__pyx_n_s_PAC_ID` (lfsearch_strings.txt) |
| `PARADOX_ID` | `__pyx_n_s_PARADOX_ID` (STR@0x00021168) |
| `PRESCO_ID` | `__pyx_n_s_PRESCO_ID` (STR@0x000211bc) |
| `VISA2000_ID` | `__pyx_n_s_VISA2000_ID` (STR@0x00021108) |
| `HITAG2_ID` | `__pyx_n_s_HITAG2_ID` (STR@0x000211d4) |
| `NEXWATCH_ID` | `__pyx_n_s_NEXWATCH_ID` (STR@0x00021114) |

### 3.7 Exported Functions

#### `cleanHexStr(hexStr) -> str`
- **Signature**: `cleanHexStr(hexStr)`
- **Behavior**:
  1. If starts with `'0x'` or `'0X'` (binary: `__pyx_kp_u_0x`, `__pyx_kp_u_0X`), strip prefix using `lstrip`
  2. Remove all spaces via `.replace(' ', '')`
- **Returns**: Cleaned hex string
- **Binary citation**: `__pyx_pw_8lfsearch_1cleanHexStr @0x0001976c`, references `startswith`, `lstrip`, `replace`

#### `parseFC() -> str`
- **Signature**: No arguments
- **Behavior**: `executor.getContentFromRegexG(_RE_FC, 1)`, then `.strip()`
- **Returns**: FC value string or `''`
- **Binary citation**: `__pyx_pw_8lfsearch_15parseFC @0x0001a5b0`

#### `parseCN() -> str`
- **Signature**: No arguments
- **Behavior**: `executor.getContentFromRegexG(_RE_CN, 2)`, then `.strip()`
- **Returns**: CN value string or `''`
- **Binary citation**: `__pyx_pw_8lfsearch_17parseCN @0x0001aaa0`

#### `parseLen() -> str`
- **Signature**: No arguments
- **Behavior**: `executor.getContentFromRegexG(_RE_LEN, 2)`, then `.strip()`
- **Returns**: Format/len value string or `''`
- **Binary citation**: `__pyx_pw_8lfsearch_19parseLen @0x0001a0bc`

#### `getFCCN() -> str`
- **Signature**: No arguments
- **Behavior**: Calls `parseFC()` and `parseCN()`, formats with `'FC,CN: {},{}' .format(fc, cn)`
  The binary references `__pyx_k_FC_CN` (the format string `'FC,CN: {},{}'`).
  **Note**: The `.format()` call uses the `fill_char` mechanism from the binary, suggesting
  zero-padding (e.g., FC padded to 3 digits, CN padded to 5 digits).
- **Returns**: Formatted FC,CN string (e.g., `'FC,CN: 123,04567'`)
- **Binary citation**: `__pyx_pw_8lfsearch_21getFCCN @0x00016258`, references `format`, `fill_char`

#### `getXsf() -> str or None`
- **Signature**: No arguments
- **Behavior**: `executor.getContentFromRegexG(REGEX_PROX_ID_XSF, 1)`, then `.strip()`
- **Returns**: XSF data string or `None` if not found
- **Binary citation**: `__pyx_pw_8lfsearch_23getXsf @0x0001af90`

#### `setUID(seaObj, regex=REGEX_CARD_ID, group=0) -> None`
- **Signature**: `setUID(map_dict, regex=REGEX_CARD_ID, group=0)` -- has optional parameters
  (binary: `__pyx_pf_8lfsearch_26__defaults__` exists for default parameter values)
- **Behavior**: `executor.getContentFromRegexG(regex, group)`, clean with `cleanHexStr()`, set `seaObj['data']`
- **Binary citation**: `__pyx_pw_8lfsearch_5setUID @0x000189bc`, module audit confirms: `setUID(map_dict, regex='...', group=0)`

#### `setRAW(seaObj) -> None`
- **Signature**: `setRAW(map_dict)`
- **Behavior**: `executor.getContentFromRegexG(REGEX_RAW, 1)`, clean with `cleanHexStr()`, set `seaObj['raw']`
- **Binary citation**: `__pyx_pw_8lfsearch_13setRAW @0x00017320`

#### `setUID2FCCN(seaObj) -> None`
- **Signature**: `setUID2FCCN(map_dict)`
- **Behavior**: Sets `seaObj['data'] = getFCCN()`, `seaObj['fc'] = parseFC()`, `seaObj['cn'] = parseCN()`, `seaObj['len'] = parseLen()`
- **Binary citation**: `__pyx_pw_8lfsearch_7setUID2FCCN @0x00018220`

#### `setUID2Raw(seaObj) -> None`
- **Signature**: `setUID2Raw(map_dict)`
- **Behavior**: Sets `seaObj['raw'] = seaObj['data']`
- **Binary citation**: `__pyx_pw_8lfsearch_9setUID2Raw @0x0001592c`

#### `setRAWForRegex(seaObj, regex, group) -> None`
- **Signature**: `setRAWForRegex(map_dict, regex, group)`
- **Behavior**: `executor.getContentFromRegexG(regex, group)`, clean with `cleanHexStr()`, set `seaObj['raw']`
- **Binary citation**: `__pyx_pw_8lfsearch_11setRAWForRegex @0x0001778c`

#### `cleanAndSetRaw(seaObj, hexStr) -> None`
- **Signature**: `cleanAndSetRaw(map_dict, raw)`
- **Behavior**: `seaObj['raw'] = cleanHexStr(hexStr)`
- **Binary citation**: `__pyx_pw_8lfsearch_3cleanAndSetRaw @0x00019480`

#### `hasFCCN() -> bool`
- **Signature**: No arguments
- **Behavior**: Calls `parseFC()`, returns `bool(result)`
- **Binary citation**: lfsearch_strings.txt: `hasFCCN`, module audit confirms

#### `parser() -> dict`
- **Signature**: No arguments
- **Binary citation**: `__pyx_pw_8lfsearch_25parser @0x0001b408`

### 3.8 parser() Return Value Specification

Detection priority order (from binary, verified against string table order and scan fixtures):

#### Check 1: No data found
```python
# Condition: executor.hasKeyword('No data found!')
{'found': False}
```
**Note**: The `!` at the end matters -- the binary string is `'No data found!'` (STR@0x00021070).

#### Check 2-22: Tag-specific detection (in order)

Each tag follows a pattern: check keyword -> extract data -> set type -> return.

| # | Keyword | Type attr | Data extraction method |
|---|---------|-----------|----------------------|
| 2 | `'Valid EM410x ID'` | `EM410X_ID` | `REGEX_EM410X` -> data, raw=data |
| 3 | `'Valid HID Prox ID'` | `HID_PROX_ID` | `REGEX_HID` -> data, raw=data |
| 4 | `'Valid AWID ID'` | `AWID_ID` | `setUID2FCCN()` + `setRAW()` |
| 5 | `'Valid IO Prox ID'` | `IO_PROX_ID` | `getXsf()` -> data, `setRAW()` |
| 6 | `'Valid Indala ID'` | `INDALA_ID` | `setRAW()`, data=raw |
| 7 | `'Valid Viking ID'` | `VIKING_ID` | `setUID()` + `setRAW()` |
| 8 | `'Valid Pyramid ID'` | `PYRAMID_ID` | `setUID2FCCN()` + `setRAW()` |
| 9 | `'Valid Jablotron ID'` | `JABLOTRON_ID` | `setUID()` + `setRAW()` |
| 10 | `'Valid NEDAP ID'` | `NEDAP_ID` | `setUID()` + `setRAW()` + subtype + customer code |
| 11 | `'Valid Guardall G-Prox II ID'` | `GPROX_II_ID` | `setUID2FCCN()` + `setRAW()` |
| 12 | `'Valid FDX-B ID'` | `FDXB_ID` | `REGEX_ANIMAL` -> data, raw=data |
| 13 | `'Valid Securakey ID'` | `SECURAKEY_ID` | `setUID2FCCN()` + `setRAW()` |
| 14 | `'Valid KERI ID'` | `KERI_ID` | `setUID2FCCN()` + `setRAW()` |
| 15 | `'Valid PAC/Stanley ID'` | `PAC_ID` | `setUID()` + `setRAW()` |
| 16 | `'Valid Paradox ID'` | `PARADOX_ID` | `setUID2FCCN()` + `setRAW()` |
| 17 | `'Valid NexWatch ID'` | `NEXWATCH_ID` | `setUID()` + `setRAW()` |
| 18 | `'Valid Visa2000 ID'` | `VISA2000_ID` | `setUID()` + `setRAW()` |
| 19 | `'Valid GALLAGHER ID'` | `GALLAGHER_ID` | `setUID2FCCN()` + `setRAW()` |
| 20 | `'Valid Noralsy ID'` | `NORALSY_ID` | `setUID()` + `setRAW()` |
| 21 | `'Valid Presco ID'` | `PRESCO_ID` | `setUID()` (no setRAW) |
| 22 | `'Valid Hitag'` | `HITAG2_ID` | `setUID()` (no setRAW) |

All return format: `{'found': True, 'data': ..., 'raw': ..., 'type': tagtypes.<ATTR>, ...}`

**NEDAP special fields**: Also sets `'subtype'` (from `_RE_SUBTYPE`) and `'code'` (from `_RE_CUSTOMER_CODE`).

**FCCN types** (AWID, Pyramid, G-Prox II, Securakey, KERI, Paradox, GALLAGHER): Also set `'fc'`, `'cn'`, `'len'` keys.

#### Check 23: No known tags but signal present (T55XX)
```python
# Condition: executor.hasKeyword('No known 125/134 kHz tags found!')
# (only reached if 'No data found!' was NOT present)
{'found': True, 'isT55XX': True}
```

#### Check 24: Chipset detection
```python
# Condition: executor.hasKeyword('Chipset detection')
# Chipset extraction: executor.getContentFromRegexG('Chipset detection:\s(.*)', 1)
#   -> contains 'EM': chipset = 'EM4305'
#   -> contains 'T5': chipset = 'T5577'
#   -> else: chipset = 'X'
{'chipset': '<str>', 'found': False}
```
Binary references: `EM4305` (STR@0x00021255), `T5577` (STR@0x00021259)

#### Check 25: Default fallback
```python
{'found': False}
```

### 3.9 Executor Interaction

| Operation | Method | Arguments |
|-----------|--------|-----------|
| Check keyword | `executor.hasKeyword(keyword)` | Detection keyword strings |
| Extract regex (group) | `executor.getContentFromRegexG(pattern, group)` | Regex + group index |
| Extract regex (all) | `executor.getContentFromRegexA(pattern)` | Regex pattern (referenced in binary) |

---

## 4. Cross-Module Data Flow

### How these parsers feed into scan.so

The `scan.so` orchestrator calls these parsers in sequence:

```
1. executor.startPM3Task('hf 14a info', 5000)
   -> hf14ainfo.parser()  ->  dict with found/uid/sak/atqa/type/etc.

2. executor.startPM3Task('lf sea', 10000)
   -> lfsearch.parser()   ->  dict with found/data/raw/type/etc.

3. executor.startPM3Task('hf sea', 10000)
   -> hfsearch.parser()   ->  dict with found/isMifare/isIclass/uid/type/etc.
```

Key decision points in scan.so:
- If `hfsearch.parser()['isMifare']` is True -> use `hf14ainfo.parser()` results for type
- If `hfsearch.parser()['isIclass']` is True -> proceed to iCLASS identification
- If `lfsearch.parser()['found']` is True -> use LF tag type directly
- If `lfsearch.parser()['isT55XX']` is True -> proceed to T55XX detection

### Dict key reference (all modules)

| Key | Source module | Type | Description |
|-----|--------------|------|-------------|
| `found` | all | bool | Tag detection success |
| `hasMulti` | hf14ainfo | bool | Multiple tags detected |
| `isUL` | hf14ainfo | bool | MIFARE Ultralight/NTAG |
| `uid` | hf14ainfo, hfsearch | str | Tag UID (hex) |
| `len` | hf14ainfo, lfsearch | int/str | UID length or format length |
| `sak` | hf14ainfo | str | SAK value (hex) |
| `atqa` | hf14ainfo, hfsearch | str | ATQA value (hex) |
| `ats` | hf14ainfo | str | ATS value (hex) |
| `bbcErr` | hf14ainfo | bool | BCC0 error flag |
| `static` | hf14ainfo | bool | Static nonce detected |
| `gen1a` | hf14ainfo | bool | Gen1a magic card |
| `type` | all | int | Tag type ID from tagtypes |
| `manufacturer` | hf14ainfo | str | Manufacturer string |
| `isMifare` | hfsearch | bool | MIFARE detected by hf search |
| `isIclass` | hfsearch | bool | iCLASS detected |
| `mcd` | hfsearch | str | LEGIC MCD (hex) |
| `msn` | hfsearch | str | LEGIC MSN (hex) |
| `atqb` | hfsearch | str | ATQB value (hex) |
| `data` | lfsearch | str | Tag ID/data |
| `raw` | lfsearch | str | Raw modulation data |
| `fc` | lfsearch | str | Facility Code |
| `cn` | lfsearch | str | Card Number |
| `subtype` | lfsearch | str | NEDAP subtype |
| `code` | lfsearch | str | NEDAP customer code |
| `isT55XX` | lfsearch | bool | T55XX blank card |
| `chipset` | lfsearch | str | Detected chipset type |

---

## 5. Verification Against Test Fixtures

Cross-referencing the spec against scan scenario fixtures:

| Scenario | TAG_TYPE | Parser path | Verified |
|----------|----------|-------------|----------|
| scan_em410x | 8 (EM410X_ID) | lfsearch: `'Valid EM410x ID'` | Yes -- fixture has `EM TAG ID : 0F0368568B` |
| scan_hid_prox | 9 (HID_PROX_ID) | lfsearch: `'Valid HID Prox ID'` | Yes -- fixture has `HID Prox - 200068012345` |
| scan_awid | 11 (AWID_ID) | lfsearch: `'Valid AWID ID'` + FC/CN | Yes -- fixture has `FC: 123, CN: 4567` |
| scan_ioprx | 12 (IO_PROX_ID) | lfsearch: `'Valid IO Prox ID'` + XSF | Yes -- fixture has `XSF(01)01:12345` |
| scan_iclass | 17 (iCLASS) | hfsearch: `'Valid iCLASS tag'` | Yes -- fixture has `Valid iCLASS tag / PicoPass tag found` |
| scan_iso15693_icode | 19 (ISO15693_ICODE) | hfsearch: `'Valid ISO15693'` w/o ST | Yes -- fixture has `Valid ISO15693 tag found` |
| scan_legic | 20 (LEGIC_MIM256) | hfsearch: `'Valid LEGIC Prime'` | Yes -- fixture has `MCD: 3C`, `MSN: 01 02 03` |
| scan_topaz | 27 (TOPAZ) | hfsearch: `'Valid Topaz'` | Yes -- fixture has `UID: 11 22 33...`, `ATQA: C0 04` |
| scan_nedap | 32 (NEDAP_ID) | lfsearch: `'Valid NEDAP ID'` | Yes -- fixture has `Card ID: 12345678` |
| scan_mf_classic_1k_4b | 1 (M1_S50_1K_4B) | hf14ainfo: Classic 1K + 4B UID | Yes -- UID `2CADC272` = 4 bytes, SAK 08 |
| scan_mf_desfire | 39 (MIFARE_DESFIRE) | hf14ainfo: DESFire + ATS | Yes -- SAK 20, ATS present |
| scan_t55xx_blank | 23 (T55XX) | lfsearch: `isT55XX=True` | Yes -- `No known 125/134 kHz tags found!` w/o `No data found!` |

All fixture TAG_TYPE values match the parser classification logic documented above.
