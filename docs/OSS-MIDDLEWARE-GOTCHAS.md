# OSS Middleware Gotchas

Known firmware quirks and behaviors that our middleware must handle differently from the original v1.0.90 .so modules.

---

## 1. MIFARE Plus 2K display label shows "M1 Mini 0.3K"

**Firmware behavior:** The v1.0.90 `hf14ainfo.so` correctly classifies MIFARE Plus 2K cards as `scan_cache.type = 26` and uses 32-sector fchk (`hf mf fchk 2`). However, the UI rendering layer maps type 26 to the display string "M1 Mini 0.3K" — the same label used for type 25 (actual Mini). The internal classification is correct; only the display is wrong.

**Evidence:**
- `scan_cache` shows `type: 26` for Plus 2K (correct)
- `hf mf fchk 2` sends 32-sector key check (correct for Plus 2K)
- Content text renders "M1 Mini 0.3K" on scan/read screens (wrong label)
- Real device traces confirm SAK 08 Plus 2K cards produce type 26 with 32-sector behavior

**Middleware fix:** Map type 26 to display string "M1 Plus 2K" (or "MIFARE Plus 2K"). The read list already labels position 6 as "M1 Plus 2K" — the scan result display should match.

**Discovered:** 2026-03-29, write flow audit of `write_mf_plus_2k_success`

---

## 2. T55XX DRM password protection on every LF clone write

**Firmware behavior:** The v1.0.90 `lfwrite.so` writes a DRM password (`20206666`) to every T55XX tag after cloning ANY LF tag type. The sequence is:

```
lf t55xx wipe p 20206666        → wipe with existing password
lf <type> clone                  → write the tag data
lf t55xx detect                  → read Block0 config after clone
lf t55xx write b 7 d 20206666   → write password to block 7
lf t55xx write b 0 d <config>   → set password-enable bit in Block0
lf t55xx detect p 20206666      → verify password is active
```

After this sequence, the T55XX tag requires password `20206666` for ALL subsequent operations (read, write, wipe). Tags written by the iCopy-X are effectively locked to iCopy-X devices unless the password is known.

**Impact:** All 20 LF clone types (EM410x, HID, Indala, AWID, IO ProxII, FDX-B, Viking, Pyramid, Gallagher, Jablotron, Keri, Nedap, Noralsy, PAC, Paradox, Presco, Visa2000, NexWatch, GProx II, Securakey) get this DRM treatment.

**Middleware fix:** Do NOT write DRM password. Skip the `lf t55xx write b 7` and `lf t55xx write b 0` (password config) steps. The T55XX wipe should use no password (`lf t55xx wipe` without `-p`), or only use the password if the tag is already DRM-locked from a previous iCopy-X write.

**Discovered:** 2026-03-28, real device traces (`fdxb_t55_write_trace_20260328.txt`, `awid_write_trace_20260328.txt`) + write flow test fixtures for all 20 LF types

---

## 3. T55XX erase hardcodes DRM password `20206666` as first wipe attempt

**Firmware behavior:** The v1.0.90 `lft55xx.so` erase flow (`lft55xx.wipe()`) does NOT detect the chip first. It immediately tries `lf t55xx wipe p 20206666` — the same DRM password it writes during clone operations (see gotcha #2). Only if the post-wipe `lf t55xx detect` fails does it fall back to:
1. `lf t55xx detect` (no password)
2. `lf t55xx detect p 20206666` (with DRM password)
3. `lf t55xx chk f /tmp/.keys/t5577_tmp_keys` (brute-force key check, ~30s)

This means the erase flow assumes tags were written by iCopy-X and tries its own DRM password first. Tags locked with a different password require the full fallback chain.

**Evidence:**
- Real device trace `trace_erase_flow_20260330.txt` lines 707-722: `lf t55xx wipe p 20206666` is the FIRST command, no prior `lf t55xx detect`
- Successful erase (DRM tag): wipe → detect OK → done
- Failed erase: wipe → detect fails → detect with password fails → chk (32s) → FINISH

**Middleware fix:** Since our middleware skips DRM password writes (gotcha #2), the erase simplifies to plain `lf t55xx wipe` (no password needed). The fallback chain for third-party DRM-locked tags remains useful.

**Discovered:** 2026-03-30, real device traces (`trace_erase_flow_20260330.txt`) + erase flow test fixtures
