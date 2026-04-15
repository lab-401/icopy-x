# Simulation Flow — Real Device Framebuffer Capture

**Date**: 2026-04-03
**Method**: /dev/fb1 RGB565 at 500ms intervals, 396 frames → 74 unique states
**Device**: iCopy-X real hardware

---

## Flow 1: M1 S50 1K — HF sim WITH trace data (TraceLen: 1119)

| State | Screenshot | Description |
|-------|-----------|-------------|
| 001 | state_001.png | Main Page 2/3 — Simulation selected |
| 002 | state_002.png | Simulation 1/4 — type list page 1 |
| 003 | state_003.png | M1 S50 1k — sim UI, UID field (no buttons yet) |
| 004 | state_004.png | M1 S50 1k — sim UI, Stop/Start buttons visible |
| 005 | state_005.png | M1 S50 1k — editing UID field (cursor on digit 1) |
| 006-009 | state_006-009.png | M1 S50 1k — editing variations |
| 010 | state_010.png | Simulation in progress toast (dark overlay) |
| 011 | state_011.png | Simulation in progress (continued) |
| 012 | state_012.png | Back to sim UI after stop |
| 013 | state_013.png | Simulation in progress (2nd run) |
| 014 | state_014.png | Trace — loading state |
| 015 | state_015.png | Trace — TraceLen: 1119, Cancel/Save buttons |

## Flow 2: Ultralight — HF sim WITH trace data (TraceLen: 329) + Save

| State | Screenshot | Description |
|-------|-----------|-------------|
| 018-019 | state_018-019.png | Simulation list — Ultralight highlighted |
| 020 | state_020.png | Simulation 1/4 list (Ultralight at pos 3) |
| 021-029 | state_021-029.png | Ultralight sim UI + editing + simulating |
| 030-031 | state_030-031.png | Simulation in progress |
| 032 | state_032.png | Simulation in progress (overlay variant) |
| 033-037 | state_033-037.png | Trace loading + display |
| 038 | state_038.png | Simulation list returned |
| 039 | state_039.png | Trace — TraceLen: 329 |
| 040 | state_040.png | Trace file saved toast |

## Flow 3: Em410x ID — LF sim (no trace)

| State | Screenshot | Description |
|-------|-----------|-------------|
| 041-046 | state_041-046.png | Navigation to page 2, Em410x sim UI |
| 047 | state_047.png | Simulation 2/4 — LF types list |
| 048-049 | state_048-049.png | Em410x — simulation in progress |
| 050-051 | state_050-051.png | Simulation in progress (dark overlay) |

## Flow 4: FDX-B ID Data — LF sim (no trace)

| State | Screenshot | Description |
|-------|-----------|-------------|
| 052 | state_052.png | Simulation 1/4 — M1 S70 4K highlighted |
| 053 | state_053.png | LF sim in progress |
| 054 | state_054.png | Simulation 2/4 — IO Prox highlighted |
| 055 | state_055.png | Simulation 3/4 — page 3 list |
| 056 | state_056.png | Simulation 3/4 — FDX-B ID Data highlighted |

## Flow 5: Ntag215 — HF sim WITH trace data (TraceLen: 1589)

| State | Screenshot | Description |
|-------|-----------|-------------|
| 057-059 | state_057-059.png | Navigation + Ntag215 sim UI |
| 060 | state_060.png | Ntag215 — sim UI with UID field |
| 061-062 | state_061-062.png | Simulation in progress |
| 063 | state_063.png | Trace — TraceLen: 0 (empty trace) |
| 064-067 | state_064-067.png | Ntag215 editing + simulating (2nd run) |
| 068-069 | state_068-069.png | Simulation in progress |
| 070 | state_070.png | Trace Loading... |
| 071 | state_071.png | Trace — TraceLen: 1589 |

## Flow 6: Nedap ID — LF sim (page 4)

| State | Screenshot | Description |
|-------|-----------|-------------|
| 058 | state_058.png | Simulation 4/4 — Nedap ID (single item on page 4) |

## Navigation / List Pages

| State | Screenshot | Description |
|-------|-----------|-------------|
| 002 | state_002.png | Page 1/4: M1 S50 1k, M1 S70 4k, Ultralight, Ntag215, FM11RF005SH |
| 047 | state_047.png | Page 2/4: Em410x ID, HID Prox ID, AWID ID, IO Prox ID, G-Prox II ID |
| 055 | state_055.png | Page 3/4: Viking ID, Pyramid ID, FDX-B ID Animal, FDX-B ID Data, Jablotron ID |
| 058 | state_058.png | Page 4/4: Nedap ID |

## Key UI Observations

1. **Title format**: "Simulation" (no page indicator in sim UI), "Simulation X/4" (in list view)
2. **Buttons in sim UI**: M1="Stop", M2="Start"
3. **Buttons during sim**: M1="Stop", M2="Start" (unchanged from sim UI)
4. **Toast during sim**: "Simulation in progress..." (dark overlay, centered)
5. **Trace screen title**: "Trace" (separate activity)
6. **Trace buttons**: M1="Cancel", M2="Save"
7. **Trace content**: "TraceLen: N" (HF only, N=0 for no reader contact)
8. **Trace save toast**: "Trace file saved"
9. **Trace loading**: "Trace Loading..." toast
10. **List numbering**: 1-based (1. M1 S50 1k through 16. Nedap ID)
11. **Field labels**: "UID:" with value in bordered cells
12. **Edit cursor**: highlighted cell border on focused digit
