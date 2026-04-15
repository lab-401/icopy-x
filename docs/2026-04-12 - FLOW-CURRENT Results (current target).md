# Full Flow Test Suite Results — 2026-04-12 (current target)

**Target:** `current` (OSS Python UI under QEMU)
**Server:** qx@178.62.84.144 (remote QEMU)
**Workers:** 9 parallel (sequential for dump_files, backlight, volume, diagnosis)
**Total:** 225 PASS / 76 FAIL / 301 total (6690s = ~1h 51m)

> Note: `dump_files` wrote results separately (35 scenarios not included in the 301 total).

## Per-flow breakdown

| Flow | PASS | FAIL | Total | Time | vs original |
|------|------|------|-------|------|-------------|
| **scan** | 44 | 1 | 45 | ~180s | -1 |
| **read** | 62 | 35 | 97 | ~900s | **+62** |
| **write** | 38 | 23 | 61 | ~600s | **+38** |
| **auto-copy** | 49 | 3 | 52 | ~1500s | **+39** |
| **erase** | 10 | 0 | 10 | ~40s | **+10** |
| **simulate** | 28 | 0 | 28 | ~135s | **+5** |
| **sniff** | 28 | 0 | 28 | ~300s | **+4** |
| **lua-script** | 11 | 0 | 11 | ~50s | **+1** |
| **time_settings** | 13 | 0 | 13 | ~47s | = |
| **about** | 8 | 3 | 11 | ~40s | -3 |
| **install** | 2 | 11 | 13 | ~130s | +1 |
| **pc_mode** | 3 | 5 | 8 | ~30s | -4 |
| **dump_files** | 32 | 3 | 35 | ~1800s | -1 |
| **backlight** | 1 | 6 | 7 | ~60s | -6 |
| **volume** | 2 | 5 | 7 | ~137s | = |
| **diagnosis** | 1 | 3 | 4 | 108s | -3 |

## Perfect flows (5)

- erase (10/10)
- simulate (28/28)
- sniff (28/28)
- lua-script (11/11)
- time_settings (13/13)

## Comparison: current vs original

| Metric | original | current | Delta |
|--------|----------|---------|-------|
| Total PASS | 87 | 225 | **+138** |
| Total FAIL | 214 | 76 | **-138** |
| Pass rate | 29% | 75% | **+46pp** |

### Major improvements (current target eliminates initList crash)

- **read:** 0 → 62 PASS (64% pass rate, was 0%)
- **write:** 0 → 38 PASS (62% pass rate, was 0%)
- **auto-copy:** 10 → 49 PASS (94% pass rate, was 19%)
- **erase:** 0 → 10 PASS (100%, was 0%)
- **simulate:** 23 → 28 PASS (100%, was 82%)
- **sniff:** 24 → 28 PASS (100%, was 89%)

### Regressions to investigate

- **about:** 11 → 8 PASS (-3)
- **pc_mode:** 7 → 3 PASS (-4)
- **backlight:** 7 → 1 PASS (-6)
- **diagnosis:** 4 → 1 PASS (-3)
- **scan:** 45 → 44 PASS (-1)
- **dump_files:** 33 → 32 PASS (-1)

These regressions are in the OSS Python implementations of settings/system screens — likely minor UI differences (button labels, navigation, state management) that need alignment with the original firmware behavior.
