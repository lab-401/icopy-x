# v1.0.90 Scan Command Traces

Traced from REAL .so modules under QEMU ARM.
Each entry shows the EXACT ordered sequence of PM3 commands
sent by the firmware for a specific tag family.

## Key Discovery: scan.lf_wav_filter()

The firmware has a hidden `lf_wav_filter()` function in scan.so that:
1. Sends `data save f /tmp/lf_trace_tmp` to save raw LF antenna data
2. Opens and reads `/tmp/lf_trace_tmp` using Python's `open()`
3. Analyzes the waveform data (1800 lines of Cython C code)
4. Returns True/False — **gatekeeper for T55XX detection**

If `lf_wav_filter()` returns True, the pipeline proceeds to `lf t55xx detect`.
If False, T55XX detection is skipped entirely.

Under QEMU mock, `lf_wav_filter()` must be overridden to return True
when a T55XX fixture is active (no real antenna data available).

## Key Discovery: executor helper mocking

The scan pipeline uses `executor.hasKeyword()`, `executor.getContentFromRegexG()`,
and `executor.getContentFromRegexA()` to parse PM3 output. These are Cython functions
accessed through Python attribute lookup, so Python-level overrides work correctly.
All must be mocked to read from our Python-level response cache.

## Key Discovery: Real scan pipeline order differs from transliteration

**Real .so order:** 14a → LF search → (lf_wav_filter) → HF search → FeliCa → T55XX detect → EM4x05
**Transliteration:** 14a → HF search → LF search → T55XX → EM4x05 → FeliCa

---

## mf_classic_1k_4b — MIFARE Classic 1K (4-byte UID, SAK 08)

**PM3 commands (in order):**
```
hf 14a info
hf mf cgetblk 0
```

**Result screen:** 14054 bytes
**Status:** TAG FOUND ✓

---

## ntag215 — NTAG215 (SAK 00, 504 bytes)

**PM3 commands (in order):**
```
hf 14a info
hf mf cgetblk 0
hf mfu info
```

**Key:** `hf mfu info` TYPE field must contain "NTAG 215" for correct identification.
**Result screen:** 8716 bytes
**Status:** TAG FOUND ✓

---

## mf_ultralight — MIFARE Ultralight (SAK 00)

**PM3 commands (in order):**
```
hf 14a info
hf mf cgetblk 0
hf mfu info
```

**Key:** `hf mfu info` TYPE field must contain "Ultralight" for correct identification.
**Result screen:** 8716 bytes
**Status:** TAG FOUND ✓

---

## ntag213 — NTAG213 (SAK 00, 144 bytes)

**PM3 commands (in order):**
```
hf 14a info
hf mf cgetblk 0
hf mfu info
```

**Result screen:** 13949 bytes
**Status:** TAG FOUND ✓

---

## ntag216 — NTAG216 (SAK 00, 888 bytes)

**PM3 commands (in order):**
```
hf 14a info
hf mf cgetblk 0
hf mfu info
```

**Result screen:** 13978 bytes
**Status:** TAG FOUND ✓

---

## ultralight_c — MIFARE Ultralight C

**PM3 commands (in order):**
```
hf 14a info
hf mf cgetblk 0
hf mfu info
```

**Result screen:** 4165 bytes
**Status:** NO TAG FOUND ✗
**Note:** Ultralight C TYPE string may not match expected pattern in scan.so.

---

## ultralight_ev1 — MIFARE Ultralight EV1

**PM3 commands (in order):**
```
hf 14a info
hf mf cgetblk 0
hf mfu info
```

**Result screen:** 13426 bytes
**Status:** TAG FOUND ✓

---

## iclass_legacy — iCLASS Legacy (via HF search)

**PM3 commands (in order, with correct executor mocking):**
```
hf 14a info
lf sea
hf sea
hf iclass rdbl b 01 k AFA785A7DAB33378
```

**Key:** Standard iCLASS key (AFA785A7DAB33378) must return block data.
If standard key fails, firmware tries 4 more keys (total 5 rdbl attempts).
With executor.hasKeyword() correctly mocked, only 4 PM3 commands needed.
**Result screen:** 8716 bytes
**Status:** TAG FOUND ✓

---

## t55xx_blank — T55XX blank (via LF search + lf_wav_filter + detect)

**PM3 commands (in order, with lf_wav_filter override):**
```
hf 14a info
lf sea
data save f /tmp/lf_trace_tmp
lf t55xx detect
```

**Key flow:**
1. `lf sea` → "No known 125/134 kHz tags found!" → isT55XX flag set
2. `scan.lf_wav_filter()` sends `data save` then analyzes file
3. If lf_wav_filter returns True → `lf t55xx detect` runs
4. Detect returns chip type, modulation, Block0

**QEMU note:** lf_wav_filter must be overridden to return True (no real antenna).
**Result screen:** 8716 bytes
**Status:** TAG FOUND ✓

---

## t55xx_unknown — T55XX unknown modulation

Same flow as t55xx_blank, but `lf t55xx detect` would return:
```
Could not detect modulation automatically
```
Setting `chip='T55xx/Unknown'`, `modulate='--------'`, `known=False`.

**Status:** Needs lf_wav_filter override + appropriate detect response.

---
