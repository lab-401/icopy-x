# PLAN: Fix ALL RFID Write Failures

## Evidence Base

- **OSS trace**: `docs/Real_Hardware_Intel/trace_autocopy_scan_dumps_20260410.txt` (ALL writes failed)
- **Original AWID trace**: `docs/Real_Hardware_Intel/awid_write_trace_20260328.txt` (writes work)
- **Original FDX-B trace**: `docs/Real_Hardware_Intel/fdxb_t55_write_trace_20260328.txt` (writes work)
- **Original MFC trace**: `docs/Real_Hardware_Intel/full_read_write_trace_20260327.txt` (writes work)
- **Original T55xx trace**: `docs/Real_Hardware_Intel/t55_to_t55_write_trace_20260328.txt` (writes work)
- **Original LF+HF autocopy**: `docs/Real_Hardware_Intel/trace_lf_hf_write_autocopy_20260402.txt` (writes work)

## Root Cause Summary

| Tag Type | Root Cause | File:Line |
|----------|-----------|-----------|
| **ALL LF (AWID, FDX-B, etc.)** | `check_detect()` fails → returns -9 → write aborted before any write commands sent | `lfwrite.py:488-490` |
| **MFC non-Gen1a** | `wrbl` commands sent but some fail with `isOk:00`; verify reports wrong result | `hfmfwrite.py:330-395` |
| **Ultralight** | `hf mfu restore` fails: "Failed convert on load to new format" | `hfmfuwrite.py:66-109` |

---

## Flow 1: LF Write (AWID, FDX-B, EM410x, HID, Indala, etc.)

### Problem
`lfwrite.py:488`: `check_detect()` calls `lft55xx.detectT55XX()` which sends `lf t55xx detect`. When the T5577 target tag is password-protected (password `20206666` set by a previous iCopy-X write), the detect command returns "Could not detect modulation" → no "Chip Type" keyword → `detectT55XX()` returns -1 → `check_detect()` returns -1 → `write()` returns -9 → **write aborted, zero write commands sent**.

### What the Original Does (from traces)
1. `lf t55xx wipe p 20206666` — wipe with known password FIRST
2. `lf t55xx detect` — now detects clean tag
3. Write data blocks (`lf t55xx write b N d XXXX`)
4. Set password block 7 + config block 0
5. Verify with `lf t55xx detect p 20206666` + `lf sea` + tag-specific read

### Fix Required
**`lfwrite.py` `check_detect()` (lines 413-442)**:

The function needs to try password-based wipe BEFORE detection, matching the original firmware:

```
1. Try detect without password
2. If fails → try detect with password 20206666
3. If still fails → try wipe with password 20206666, then detect
4. If all fail → return -1
```

The original firmware's `check_detect` does:
```
detect → if fail → chk password → if found → wipe → detect again
```

Also: after writing data, the original firmware writes the password protection back. Our `write_raw()` and PAR_CLONE_MAP functions don't set password block 7 or update config block 0 afterward.

### Files to Modify
- `src/middleware/lfwrite.py`: Fix `check_detect()` to attempt password wipe before giving up
- `src/middleware/lft55xx.py`: Verify `wipe()` function works with password arg

---

## Flow 2: MFC non-Gen1a Write

### Problem
The `wrbl` commands are sent but some fail with `isOk:00` / "Write block error". From the trace:
```
hf mf wrbl 20 A 000000000000 00000000000000000000000000000000
→ isOk:00, Cmd Error: 04, Write block error
```

This means Key A `000000000000` does NOT have write permission for block 20. The real keys for sectors 0-5 are `4A6352684677` (A) / `536653644c65` (B), not `000000000000`. The code is writing with extracted Key A from the trailer, but the access bits show "wrB" — write requires Key B, not Key A.

From the trace sector trailer decode:
```
block 20  rdAB wrB        ← WRITE REQUIRES KEY B
```

Our code at `hfmfwrite.py` line ~360 uses Key A by default. It should check access bits and use Key B when required.

### What the Original Does (from traces)
The original uses the correct key type (A or B) based on access bit analysis. It reads the trailer first, decodes access bits, then chooses the appropriate key for write operations.

### Fix Required
**`hfmfwrite.py`**: The `write_common()` function must:
1. For each sector, read the trailer to get access bits
2. Determine which key (A or B) has write permission for each block
3. Use that key in the `wrbl` command

### Files to Modify
- `src/middleware/hfmfwrite.py`: Fix key selection logic in block write loop

---

## Flow 3: Ultralight/NTAG Write

### Problem
```
hf mfu restore s e f /mnt/upan/dump/mfu/M0-UL_00000000000000_1.bin
→ "Failed convert on load to new Ultralight/NTAG format"
→ Nikola.D: -10
```

The PM3 command itself fails because the dump file format is incompatible. The RRG PM3 binary expects a specific binary format for MFU dump files. The file was dumped by our firmware (via `hf mfu dump f ...`), but the restore command can't parse it.

### What the Original Does
The original firmware uses the same `hf mfu restore` command — but with files dumped by the original firmware. The file format should be identical since both use the same PM3 binary.

### Investigation Needed
1. Check if the dump file was corrupted during save
2. Check if our `hfmfuread.py` is modifying the file after PM3 dumps it
3. Compare the file size (120 bytes) against expected MFU dump size
4. The error "Failed convert on load to new Ultralight/NTAG format" suggests the file header is wrong

### Files to Investigate
- `src/middleware/hfmfuread.py`: Check if it post-processes the dump file
- `src/middleware/hfmfuwrite.py`: Check the restore command construction

---

## Flow 4: Erase (both LF and HF)

### LF Erase Problem
Erase for LF tags likely hits the same `check_detect()` / password-protected tag issue as LF write. The erase function needs to handle password-protected T5577 tags.

### HF Erase Problem
User reports "Unknown error" toast for MFC 1K non-Gen1a erase. The erase function probably can't write zeros because of the same Key A vs Key B issue as MFC write.

### Files to Investigate
- `src/middleware/erase.py`: Check erase logic for both LF and HF paths

---

## Execution Order

### Phase 1: LF Write (highest ROI — fixes AWID, FDX-B, EM410x, HID, and 15+ other LF types)
1. Fix `lfwrite.py check_detect()` — try password wipe before failing
2. Verify with real device trace (deploy telemetry, test AWID write)

### Phase 2: MFC Write (fixes Mifare Classic 1K/4K standard cards)
1. Fix `hfmfwrite.py` — use correct key type (A or B) based on access bits
2. Verify with real device trace

### Phase 3: MFU Write (fixes Ultralight, NTAG)
1. Investigate dump file format
2. Fix if our code modifies the file post-dump

### Phase 4: Erase
1. Fix LF erase (same password issue as LF write)
2. Fix HF erase (same key selection issue as MFC write)

### Phase 5: Verify ALL writes with telemetry
1. Deploy telemetry
2. Test each tag type: AWID, FDX-B, MFC Gen1a, MFC non-Gen1a, Ultralight
3. Compare traces against original
