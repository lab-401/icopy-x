# AUTO-COPY Flow Handover

## Status: 47/52 PASS, 4 FAIL, 1 TIMEOUT

## Context

The AUTO-COPY flow orchestrates SCAN→READ→WRITE→VERIFY using existing middleware modules. It has NO dedicated middleware .so — `AutoCopyActivity` (activity_main.py:4283) calls `scan.Scanner()`, `read.Reader()`, and `write.write()`/`write.verify()` directly.

All 33 middleware .py modules are in place. Runtime probe confirmed **21 .py, 0 .so** loaded. The 47 passing scenarios cover all tag families (LF, HF, MFC, Ultralight, NTAG, iClass, ISO15693, T55xx, EM4305).

## Prior Work This Session (Committed as 3c7ebae)

- **hfmfwrite.py**: verify() → UID-only check (hf 14a info + hf mf cgetblk 0); write_with_standard() → returns -1 on any block failure
- **activity_main.py**: WriteActivity.onCreate() calls template.draw() for tag info on canvas
- **container.py**: NEW — get_public_id() lookup table, eliminated last .so dependency
- **common.sh**: navigate_to_read_tag() — DOWN×2 for original (no Dump Files), DOWN×3 for current
- **Write flow: 61/61 PASS, 0 .so**

## The 5 Remaining Issues

### ROOT CAUSE (shared by all 4 MFC failures)

**File: `src/middleware/hfmfkeys.py`, line 205-217**

The `keysFromPrintParse()` function parses the fchk key table but **ignores the `res` column**:

```
| Sec | key A          |res| key B          |res|
| 000 | ffffffffffff   | 0 | ffffffffffff   | 0 |   ← res=0 means FAILED
```

The regex captures keys regardless of `res` value:
```python
_RE_KEY_TABLE = re.compile(
    r'\|\s*(\d+)\s*\|\s*([A-Fa-f0-9]{12})\s*\|\s*(\d+)\s*\|\s*([A-Fa-f0-9]{12})\s*\|\s*(\d+)\s*\|'
)
```
Current code stores ALL keys. The original .so only stores keys where `res=1`.

**This single bug causes all 4 failures**: keys get stored with res=0 → `hasAllKeys()` returns True → key recovery is skipped → read proceeds with bad keys → blocks fail to read → empty blocks saved → "Read Successful" with garbage data.

### Failure Details

| # | Scenario | Fixture | Expected | Actual |
|---|----------|---------|----------|--------|
| 1 | `autocopy_mf1k_darkside_fail` | fchk: `found 0/32`, darkside: `not vulnerable` | WarningM1Activity (M1:Sniff) | Read succeeds with empty blocks |
| 2 | `autocopy_mf1k_fchk_timeout` | fchk: `ret=-1` (timeout) | Toast "Read Failed" | Read succeeds with empty blocks |
| 3 | `autocopy_mf1k_partial_keys` | fchk: `found 8/32`, nested: `ret=-1` (card lost) | Toast "Read Failed" or partial | Read succeeds with partial data |
| 4 | `autocopy_mf1k_read_fail` | fchk: `found 32/32`, rdsc: `isOk:00` (auth fail) | Toast "Read Failed" | Read succeeds with empty blocks |

### Fix Plan

**Fix 1: `src/middleware/hfmfkeys.py` — `keysFromPrintParse()`** (PRIMARY FIX)

Change the regex to capture `res` columns and only store keys where `res=1`:

```python
_RE_KEY_TABLE = re.compile(
    r'\|\s*(\d+)\s*\|\s*([A-Fa-f0-9]{12})\s*\|\s*(\d+)\s*\|\s*([A-Fa-f0-9]{12})\s*\|\s*(\d+)\s*\|'
)

def keysFromPrintParse(size):
    text = executor.CONTENT_OUT_IN__TXT_CACHE if executor else ''
    for m in _RE_KEY_TABLE.finditer(text):
        sector = int(m.group(1))
        key_a = m.group(2).upper()
        res_a = int(m.group(3))
        key_b = m.group(4).upper()
        res_b = int(m.group(5))
        if res_a == 1:
            putKey2Map(sector, A, key_a)
        if res_b == 1:
            putKey2Map(sector, B, key_b)
```

This fixes scenarios 1, 3, and 4. When `found 0/32`, no keys stored → `hasAllKeys()` returns False → key recovery runs → darkside fails → WarningM1Activity shown.

**Fix 2: `src/middleware/hfmfkeys.py` — `fchks()`** (for scenario 2)

When `ret=-1` (timeout), the function already returns -1 (line 236). But `read.py::_read_mfc()` line 101 calls `fchks()` and doesn't check its return value. After a fchk timeout, it falls through to `hasAllKeys()` which may return True from stale KEYS_MAP data.

Fix in `read.py::_read_mfc()`:
```python
ret = hfmfkeys.fchks(infos, size, with_call=True)
if ret == -1:
    # fchk timed out — propagate failure
    return (-1, '')
```

**Fix 3: `src/middleware/hfmfread.py` — `readAllSector()`** (defense-in-depth)

When ALL sector reads fail (zero blocks successfully read), return empty list instead of list of empty blocks. This prevents the caller from creating a dump file with garbage.

```python
def readAllSector(size, infos, listener):
    sc = mifare.getSectorCount(size) if mifare else 16
    data_list = []
    real_read_count = 0
    for sector in range(sc):
        ...
        blocks = readBlocks(sector, keyA, keyB, infos)
        if blocks and isinstance(blocks, list):
            data_list.extend(blocks)
            real_read_count += len(blocks)
        else:
            ...empty blocks...
    if real_read_count == 0:
        return []  # Total failure — no blocks readable
    return data_list
```

### Timeout: `autocopy_mf4k_happy`

MFC 4K has 40 sectors (256 blocks). Write phase: 256 wrbl × 0.5s PM3_DELAY = 128s. Plus read phase (~60s) and scan (~10s) = ~200s. With verify, this exceeds the default BOOT_TIMEOUT.

The scenario script already sets `BOOT_TIMEOUT=600` but the parallel runner may override this. Re-running sequentially should fix it — if not, increase the timeout further.

## Verification After Fixes

```bash
# 1. Run the 4 failing scenarios
for s in autocopy_mf1k_darkside_fail autocopy_mf1k_fchk_timeout autocopy_mf1k_partial_keys autocopy_mf1k_read_fail; do
    killall -9 qemu-arm-static 2>/dev/null; sleep 1
    rm -rf tests/flows/_results/current/auto-copy/scenarios/$s
    TEST_TARGET=current bash tests/flows/auto-copy/scenarios/$s/$s.sh
done

# 2. Run mf4k_happy with extended timeout
killall -9 qemu-arm-static 2>/dev/null; sleep 1
rm -rf tests/flows/_results/current/auto-copy/scenarios/autocopy_mf4k_happy
BOOT_TIMEOUT=600 TEST_TARGET=current bash tests/flows/auto-copy/scenarios/autocopy_mf4k_happy/autocopy_mf4k_happy.sh

# 3. Regression: re-run all 52
sudo rm -rf /mnt/upan/dump/ && mkdir -p /mnt/upan/dump && chmod 777 /mnt/upan/dump
TEST_TARGET=current bash tests/flows/auto-copy/test_auto_copy_parallel.sh --clean-flow-only 4

# 4. Also verify no write regressions (the fchk fix affects MFC read path)
TEST_TARGET=current bash tests/flows/write/test_writes_parallel.sh --clean-flow-only 4

# 5. Also verify no read regressions
TEST_TARGET=current bash tests/flows/read/test_reads_parallel.sh --clean-flow-only 4
```

## Key Files

| File | Lines | What to Fix |
|------|-------|-------------|
| `src/middleware/hfmfkeys.py` | 205-217, 219-238 | keysFromPrintParse: check res column; fchks: already returns -1 on timeout |
| `src/middleware/hfmfread.py` | 332-353 | readAllSector: track real_read_count, return [] if zero |
| `src/middleware/read.py` | 101-113 | _read_mfc: check fchks return value |

## Important Rules

- Tests are IMMUTABLE — never modify fixture.py, expected.json, or scenario .sh files
- Ground truth is the original .so binary behavior — the `res` column check is from `hfmfkeys.so` decompiled behavior
- After fixing, confirm the module probe still shows 0 .so (inject probe into launcher_current.py, run a write scenario, check log for `[MODULE-PROBE]`)
- Clean `/mnt/upan/dump/` before each full test run to avoid stale dump file interference
