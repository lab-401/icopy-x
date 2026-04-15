# v1.0.90 Real Device Traces — Activity Transitions + PM3 Command Sequences

**Source:** Python tracer injected into running iCopy-X device via SSH (2026-03-25)
**Method:** Monkey-patched actstack.start/finish_activity, executor.startPM3Task, read.Reader.start, hfmfkeys, hfmfread

## 1. Read Flow — MIFARE Classic 1K 4B (default keys + custom keys)

### Activity Sequence:
```
START_ACTIVITY(ReadListActivity, None)
  → scan: hf 14a info → hf mf cgetblk 0
  → READER_START(1, {'infos': scan_cache, 'force': False})
  → hfmfkeys.fchks(scan_cache, 1024)
  → PM3: hf mf fchk 1 /tmp/.keys/mf_tmp_keys (timeout=600000)
  → hfmfkeys.keysFromPrintParse(1024) → returns 32
  → fchks returns 1
  → hfmfread.readAllSector(1024, scan_cache, ReadActivity.onReading)
  → PM3: hf mf rdsc 0-15 B <key> (16 commands)
  → hfmfread.callListener(sector, 16, listener) per sector
  → hfmfread.cacheFile(.eml) + cacheFile(.bin)
  → readAllSector returns 1
```

### Key Facts:
- fchk timeout: **600000ms** (10 minutes!)
- fchks returns **1** on success (not -1)
- readAllSector listener: `ReadActivity.onReading` bound to `ReadListActivity` instance
- callListener args: (sector_num, total_sectors, listener_method)
- Two dump files saved: .eml and .bin
- Each sector may use a DIFFERENT key (non-default cards)

## 2. Write Flow — Gen1a Magic Card

### Activity Sequence:
```
START_ACTIVITY(WarningWriteActivity, '/path/to/dump.bin')
FINISH_ACTIVITY(WarningWriteActivity)  ← user confirmed warning
START_ACTIVITY(WriteActivity, '/path/to/dump.bin')
  → PM3: hf 14a info  ← scan target card
  → PM3: hf mf cload b /path/to/dump.bin (timeout=8888)  ← Gen1a bulk load
  → Gen1a freeze sequence:
    → hf 14a raw -p -a -b 7 40   ← wake
    → hf 14a raw -p -a 43        ← backdoor
    → hf 14a raw -c -p -a e000   ← config read
    → hf 14a raw -c -p -a e100   ← config write
    → hf 14a raw -c -p -a 85000000000000000000000000000008  ← FREEZE
    → hf 14a raw -c -a 5000      ← halt
  → PM3: hf 14a info  ← verify UID changed
```

### Key Facts:
- WarningWriteActivity shown BEFORE WriteActivity (user must confirm)
- Dump file path passed as string argument to both activities
- Gen1a detected automatically → uses cload (not wrbl)
- Gen1a freeze is exactly 6 raw commands
- Verify = hf 14a info to check UID changed

## 3. AutoCopy Flow — MF1K to Standard (non-Gen1a) Card

### Activity Sequence:
```
START_ACTIVITY(AutoCopyActivity, None)
  → [READ PHASE - same as Read flow]
  → scan: hf 14a info → hf mf cgetblk 0
  → READER_START(1, {infos, force:False})
  → fchks(scan_cache, 1024) → fchk → 32 keys → returns 1
  → readAllSector(1024, scan_cache, AutoCopyActivity.onReading)
  → 16× rdsc → callListener per sector
  → cacheFile(.eml) + cacheFile(.bin)
  → readAllSector returns 1

  → [DATA READY SCREEN - ~5s pause for card swap]

START_ACTIVITY(WarningWriteActivity, '/path/to/dump.bin')
FINISH_ACTIVITY(WarningWriteActivity)
START_ACTIVITY(WriteActivity, '/path/to/dump.bin')
  → [WRITE PHASE - standard card]
  → PM3: hf 14a info → hf mf cgetblk 0 (not Gen1a)
  → fchks(scan_cache, 1024, False)  ← 3rd arg False!
  → PM3: hf mf fchk → 32 keys → fchks returns 1
  → PM3: hf mf rdbl 63 A ffffffffffff  ← reads last trailer first
  → PM3: hf mf wrbl × 48 data blocks (all zeros → source data)
  → PM3: hf mf wrbl × 16 trailer blocks (source keys + access bits)
  → WRITE ORDER: reverse sector order, data first, trailers last, block 0 near end
  → PM3: hf 14a info → verify
```

### Key Facts:
- AutoCopyActivity does NOT push ReadListActivity — it does the read internally
- The read listener is `AutoCopyActivity.onReading` (not ReadActivity)
- fchks called with 3rd arg `False` during write phase (unknown purpose — maybe "don't save keys"?)
- Standard write reads target trailer first (rdbl 63) before writing
- Write order: blocks 60,61,62 → 56,57,58 → ... → 0,1,2 → then trailers 63,59,...,3
- Block 0 (UID) written second-to-last — safety pattern

## 4. Erase Flow — Gen1a (Magic Wipe)

### Activity Sequence:
```
START_ACTIVITY(WipeTagActivity, None)
  → PM3: hf 14a info  ← scan
  → PM3: hf mf cwipe (timeout=28888)  ← SINGLE magic wipe command
  → PM3: hf 14a info  ← verify
FINISH_ACTIVITY(WipeTagActivity)
```

### Key Facts:
- Activity is **WipeTagActivity** (not EraseActivity or EraseTagActivity)
- Gen1a erase = single `hf mf cwipe` command
- cwipe timeout: 28888ms
- No key recovery needed

## 5. Erase Flow — Standard Card (Non-Gen1a)

### Activity Sequence:
```
START_ACTIVITY(WipeTagActivity, None)
  → PM3: hf 14a info  ← scan
  → PM3: hf mf cgetblk 0  ← Gen1a check (fails)
  → PM3: hf mf fchk 1 /tmp/.keys/mf_tmp_keys  ← key recovery
  → fchks returns 1
  → PM3: hf mf wrbl × 48 data blocks (all 00000000...)  ← zero all data
  → PM3: hf mf wrbl × 16 trailer blocks  ← reset to default keys
    → Trailer data: FFFFFFFFFFFFFF078069FFFFFFFFFFFF
    → Retry pattern: key A → key A → key A → key B (up to 4 attempts per trailer)
  → PM3: hf 14a info + hf mf cgetblk 0  ← verify
```

### Key Facts:
- Same WipeTagActivity for both Gen1a and standard
- Standard erase requires FULL key recovery first
- Data blocks zeroed, trailers reset to default (FF×6 + 078069 + FF×6)
- Trailer writes retry up to 3× with key A, then fall back to key B
- Same reverse write order as AutoCopy write phase

## 6. Read Flow — MIFARE Classic 4K Gen1b Magic Card (csave path)

**Source:** strace on real device, 2026-03-28
**Trace file:** `mf4k_read_trace_20260328.txt`

### PM3 Command Sequence:
```
PM3> hf 14a info
  → UID: E9 78 4E 21, SAK: 18, ATQA: 00 02
  → MIFARE Classic 4K / Classic 4K CL2
  → Magic capabilities : Gen 1b
  → Prng detection: weak

PM3> hf mf cgetblk 0
  → data: E9 78 4E 21 FE 98 02 00 62 63 64 65 66 67 68 69
  → isOk:01

PM3> hf mf csave 4 o /mnt/upan/dump/mf1/M1-4K-4B_E9784E21_2
  → saved 4096 bytes to binary file
  → saved 256 blocks to text file
```

### Key Facts:
- Gen1b detected via cgetblk success (block 0 data returned)
- **Only 3 PM3 commands** — csave bypasses fchk/darkside/nested/rdsc entirely
- csave size flag "4" for 4K (vs "1" for 1K)
- File saved to `/mnt/upan/dump/mf1/` (same dir as 1K dumps)
- 4096 bytes = 256 blocks (32 small sectors × 4 blocks + 8 large sectors × 16 blocks)
- Gen1a and Gen1b are treated identically by the .so (cgetblk success = magic)

## 7. Read Flow — MIFARE Classic 4K Non-Magic (fchk + rdsc × 40)

**Source:** strace on real device, 2026-03-28
**Trace file:** `mf4k_nonmagic_app_trace_20260328.txt`

### PM3 Command Sequence (happy path — run 4 of 4):
```
PM3> hf 14a info
PM3> hf mf cgetblk 0       → fails (not magic)
PM3> hf mf fchk 4 /tmp/.keys/mf_tmp_keys   → 80/80 keys found
PM3> hf mf rdsc 0 B ffffffffffff
PM3> hf mf rdsc 1 B ffffffffffff
  ... (sectors 2-38)
PM3> hf mf rdsc 39 B ffffffffffff
```

### Key Facts:
- fchk size flag **"4"** for 4K cards (not "2")
- 40 rdsc commands: sectors 0-31 (small, 4 blocks each) + sectors 32-39 (large, 16 blocks each)
- rdsc returns **16 block lines for large sectors** — verified via .eml dump (255 lines = 256 blocks - 1 trailing newline)
- Multiple sad paths observed: fchk-only (card removed), rdsc retries on sector 0 (card intermittent)
- Total: 43 PM3 commands for a full 4K happy-path read (1 + 1 + 1 + 40)
