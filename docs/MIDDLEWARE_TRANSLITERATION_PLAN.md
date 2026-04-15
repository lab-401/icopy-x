# Middleware Transliteration Master Plan

## Goal

Provable, 1:1 functional and UI parity with the original iCopy-X v1.0.90 firmware.
Replace ALL closed-source `.so` middleware modules with open-source Python equivalents.
When we achieve true parity, all 430+ test scenarios will pass — tests confirm parity,
they are NOT the goal.

---

## ABSOLUTE LAWS (for ALL agents)

### Ground Truth Sources (ONLY these)
1. **Decompiled .so files**: `decompiled/*.txt` (66 files, 40M, 1M lines)
2. **Real device traces**: `docs/Real_Hardware_Intel/trace_*.txt` (21 traces)
3. **Real device screenshots**: `docs/Real_Hardware_Intel/Screenshots/` (6,122 images)
4. **String extractions**: `docs/v1090_strings/*.txt` (68 files)
5. **Test fixtures**: `tests/flows/*/scenarios/*/fixture.py` (419 scenarios)
6. **Flow specifications**: `docs/flows/*/README.md` (18 flows)
7. **UI mappings**: `docs/UI_Mapping/*/README.md` (17 activities)

### Rules
1. **Tests are immutable.** NEVER edit test files.
2. **The `.so` middleware IS the logic.** Never reimplement — transliterate.
3. **Never guess.** Every line of code MUST cite a ground truth source.
4. **Never put logic in the UI.** Middleware sends PM3 commands. Activities render.
5. **DEBUG and TRACE** — we have a fully emulated original system. Trace, don't guess.
6. **Never deviate from ground truth** to make tests pass.
7. **NEVER flash PM3 bootrom.** No JTAG = bricked device.
8. **Request real device** if totally stuck — don't guess.

### Agent Protocol (per flow)
1. **Spec Agent**: Studies ground truth, builds transliteration spec
2. **Implementation Agent**: Writes code from the spec
3. **Audit Agent**: Clean-room review — does code match spec?
4. **Test Agent**: Runs flow scenarios via QEMU (`--firmware-target=current`)
5. **Debug Agent**: Traces original vs current behavior, identifies root cause

Loop 2→3→4→5→1 until all scenarios pass.

---

## MODULE INVENTORY

### Already Implemented (12 modules — UI layer)
actbase.py, actmain.py, actstack.py, activity_main.py, activity_tools.py,
activity_read.py, hmi_driver.py, images.py, keymap.py, resources.py, widget.py,
erase.py (middleware)

### To Transliterate (38 modules)

**Tier 0 — Foundation** (used by ALL flows):
- executor.so (PM3 command dispatch, socket comms) — 95 exports
- commons.so (byte/hex utilities) — 8 exports
- tagtypes.so (tag type registry, DRM) — 69 exports
- container.so (data structures) — 19 exports

**Tier 1 — Scan Pipeline** (45 scenarios):
- scan.so (Scanner class, async pipeline) — 46 exports
- hf14ainfo.so (HF tag parser: UID, SAK, ATQA) — 16 exports
- hfsearch.so (HF search parser) — 12 exports
- lfsearch.so (LF search parser) — 14 exports
- template.so (result display, TYPE_TEMPLATE) — 28 exports

**Tier 2 — Read Pipeline** (99 scenarios):
- read.so (Reader class, 10 protocol handlers) — 22 exports
- hfmfread.so (MIFARE Classic reader) — 16 exports
- hf14aread.so (ISO14443A reader) — 8 exports
- hfmfuread.so / hfmfuinfo.so (Ultralight reader) — 14 exports
- hf15read.so (ISO15693 reader) — 10 exports
- iclassread.so (iCLASS reader) — 12 exports
- legicread.so (LEGIC reader) — 8 exports
- felicaread.so / hffelica.so (FeliCa reader) — 10 exports
- lfread.so (LF reader, 20+ protocols) — 27 exports
- lfem4x05.so (EM4x05 reader) — 14 exports

**Tier 3 — Write Pipeline** (63 scenarios):
- write.so (write dispatcher) — 17 exports
- hfmfwrite.so (MFC write, DRM gated) — 39 exports
- lfwrite.so (LF write, DRM password) — 17 exports
- hf15write.so (ISO15693 write) — 8 exports
- hfmfuwrite.so (Ultralight write) — 10 exports
- iclasswrite.so (iCLASS write, Elite keys) — 14 exports

**Tier 4 — Erase/Keys** (10 scenarios):
- hfmfkeys.so (key management) — 22 exports
- lft55xx.so (T55xx utilities) — 18 exports
- mifare.so (MIFARE utilities) — 12 exports
- lfverify.so (LF verification) — 8 exports

**Tier 5 — Specialized**:
- sniff.so (traffic capture) — 16 exports
- gadget_linux.so (USB serial) — 10 exports
- audio.so (sound playback, DRM) — 12 exports
- audio_copy.so (audio cloning) — 6 exports
- appfiles.so (file management) — 14 exports
- application.so (app launcher) — 8 exports
- config.so (configuration) — 10 exports
- settings.so (device settings) — 8 exports
- update.so (firmware update) — 12 exports
- activity_update.so (update UI) — 14 exports
- debug.so (debug utilities) — 6 exports
- bytestr.so (byte string utils) — 4 exports
- sermain.so / serpool.so (serial pool) — 12 exports
- server_iclassse.so (iCLASS SE server) — 8 exports
- ymodem.so (YMODEM protocol) — 6 exports
- games.so (easter egg) — 4 exports
- vsp_tools.so (VSP utilities) — 6 exports

---

## TRANSLITERATION ORDER

### Phase 0: System Settings (warm-up, no PM3)
**Volume + Backlight** — already passing (7+7 scenarios)
- These use activity_main.py (already implemented) + audio.so + settings.so
- Goal: verify the test infrastructure works, build confidence

### Phase 1: About + PC Mode (system flows, low RFID)
**About** — update display, install flow
- Needs: activity_update.so, update.so (transliterate search/check/install)
- Already partially working (11 scenarios pass)

**PC Mode** — USB gadget control
- Needs: gadget_linux.so (USB module management)
- Already partially working (8 scenarios pass)

### Phase 2: Scan (foundation for ALL RFID flows)
**45 scenarios** — tag detection across all protocols
- Needs: executor.so, scan.so, hf14ainfo.so, hfsearch.so, lfsearch.so, template.so
- executor.so is the most critical: PM3 socket comms, startPM3Task, hasKeyword, getContentFromRegex
- Ground truth: `trace_scan_flow_20260331.txt`, `trace_lf_scan_flow_20260331.txt`

### Phase 3: Read (builds on Scan)
**99 scenarios** — card readout across all protocols
- Needs: read.so + all protocol-specific read modules (hfmfread, lfread, etc.)
- Ground truth: `trace_read_flow_20260401.txt`, `trace_iclass_elite_read_20260401.txt`

### Phase 4: Write (builds on Scan + Read)
**63 scenarios** — card programming
- Needs: write.so + all protocol-specific write modules
- DRM blocker: hfmfwrite.so checks cpuinfo serial
- Ground truth: `trace_write_activity_attrs_20260402.txt`

### Phase 5: Auto-Copy (composes Scan + Read + Write)
**51 scenarios** — 3-stage pipeline
- Needs: container.so + all Scan/Read/Write modules
- Ground truth: `trace_autocopy_mf1k_standard.txt`

### Phase 6: Simulate
**32 scenarios** — tag emulation
- Reuses write infrastructure

### Phase 7: Erase (builds on Write + Keys)
**10 scenarios** — tag wipe
- Needs: tagtypes.so, hfmfkeys.so, lft55xx.so
- erase.py middleware already exists (partial)
- Ground truth: `trace_erase_flow_20260330.txt`

### Phase 8: Dump Files
**35 scenarios** — file export/import
- Composite: Scan + Read + Write + Erase + file I/O

### Phase 9: Sniff
**28 scenarios** — passive capture
- Needs: sniff.so
- Ground truth: `trace_sniff_flow_20260403.txt`

### Phase 10: LUA Scripts
**11 scenarios** — user script execution

### Phase 11: Time Settings
**13 scenarios** — system clock (already passing)

---

## PER-FLOW AGENT WORKFLOW

```
┌─────────────────────────────────────────────────────┐
│ ORCHESTRATOR (you)                                   │
│  - Dispatches per-flow tasks                        │
│  - Audits code quality, modularity                  │
│  - Orders refactors when needed                     │
│  - Maintains progress tracker                       │
└───────┬─────────────────────────────────────────────┘
        │
        ├── [1] SPEC AGENT ──────────────────────────┐
        │   Reads: decompiled .so, strings, traces    │
        │   Outputs: method-level transliteration spec │
        │   Cites: every constant, every command       │
        │                                              │
        ├── [2] IMPLEMENTATION AGENT ────────────────┐│
        │   Input: spec from Agent 1                  ││
        │   Outputs: Python .py module                ││
        │   Rule: every line cites ground truth       ││
        │                                              ││
        ├── [3] AUDIT AGENT ─────────────────────────┐││
        │   Step 1: reads code WITHOUT spec           │││
        │   Step 2: given spec, verifies match        │││
        │   Outputs: PASS or list of violations       │││
        │   Loop: back to Agent 2 if violations       │││
        │                                              │││
        ├── [4] TEST AGENT ──────────────────────────┐│││
        │   Runs: TEST_TARGET=current scenarios       ││││
        │   Outputs: PASS/FAIL report per scenario    ││││
        │   If FAIL: triggers Agent 5                 ││││
        │                                              ││││
        └── [5] DEBUG AGENT ─────────────────────────┘│││
            Compares: original vs current behavior     │││
            Uses: QEMU tracing, state dumps            │││
            Outputs: root cause analysis               │││
            Feeds back to: Agent 1 (spec refinement)   │││
                                                       │││
            ← Loop until ALL scenarios PASS ──────────┘┘┘
```

---

## TESTING TARGETS

| Target | Command | What It Tests |
|--------|---------|--------------|
| `original` | `TEST_TARGET=original` | Real v1.0.90 .so (baseline) |
| `current` | `TEST_TARGET=current` | src/lib + src/middleware (dev) |
| `original_current_ui` | `TEST_TARGET=original_current_ui` | Installed IPK (our UI + orig middleware) |

For middleware transliteration, use `TEST_TARGET=current` — this loads our Python
modules from `src/lib/` and `src/middleware/`, shadowing the original .so files.

---

## PROGRESS TRACKER

| # | Flow | Scenarios | Modules Needed | Status | Pass Rate |
|---|------|-----------|---------------|--------|-----------|
| 0a | Volume | 7 | (none new) | DONE | 7/7 |
| 0b | Backlight | 7 | (none new) | DONE | 7/7 |
| 1a | About | 11 | activity_update, update | DONE | 11/11 |
| 1b | PC Mode | 8 | gadget_linux | DONE | 8/8 |
| 2 | Scan | 45 | executor, scan, hf14ainfo, hfsearch, lfsearch, template | TODO | 0/45 |
| 3 | Read | 99 | read, hfmfread, hf14aread, hfmfuread, hf15read, iclassread, legicread, felicaread, lfread, lfem4x05 | TODO | 0/99 |
| 4 | Write | 63 | write, hfmfwrite, lfwrite, hf15write, hfmfuwrite, iclasswrite | TODO | 0/63 |
| 5 | Auto-Copy | 51 | container | TODO | 0/51 |
| 6 | Simulate | 32 | (reuses write) | TODO | 0/32 |
| 7 | Erase | 10 | tagtypes, hfmfkeys, lft55xx | TODO | 0/10 |
| 8 | Dump Files | 35 | appfiles | TODO | 0/35 |
| 9 | Sniff | 28 | sniff | TODO | 0/28 |
| 10 | LUA Scripts | 11 | (lua runner) | TODO | 0/11 |
| 11 | Time Settings | 13 | (none new) | DONE | 13/13 |
| **TOTAL** | | **420** | | | **46/420** |

---

## KEY GROUND TRUTH CITATIONS

### executor.so — The PM3 Communication Layer
- Decompiled: `decompiled/executor_ghidra_raw.txt` (714K)
- Strings: `docs/v1090_strings/executor_strings.txt`
- Protocol: Nikola.D format (`startPM3Task` → socket → response parsing)
- Key methods: `startPM3Task(cmd, timeout)`, `hasKeyword(keyword)`, `getContentFromRegex(pattern)`
- Trace: ALL PM3 traces show executor behavior

### scan.so — The Tag Scanner
- Decompiled: `decompiled/scan_ghidra_raw.txt` (1.3M)
- Strings: `docs/v1090_strings/scan_strings.txt`
- Trace: `trace_scan_flow_20260331.txt`, `trace_lf_scan_flow_20260331.txt`
- Key methods: `setScanCache()`, `getScanCache()`, `Scanner.scan_all_asynchronous()`
- 45 test fixtures in `tests/flows/scan/scenarios/*/fixture.py`

### template.so — Result Display
- Decompiled: `decompiled/template_ghidra_raw.txt`
- Strings: `docs/v1090_strings/template_strings.txt`
- Key method: `template.draw(canvas)` — renders scan/read results
- Citations: scan/read screenshots for expected display format

### Archive References (structural only, NOT authoritative)
- `/home/qx/archive/lib_transliterated/*.py` — 60 proof-of-concept files
- Use for: import patterns, class structure, general approach
- Do NOT use for: constants, logic, PM3 commands, regex patterns

---

## CODE ORGANIZATION

All new middleware goes in `src/middleware/`:
```
src/middleware/
├── __init__.py
├── erase.py              # Already exists
├── executor.py           # PM3 command dispatch
├── scan.py               # Scanner
├── read.py               # Reader
├── write.py              # Writer
├── template.py           # Result display
├── commons.py            # Byte utilities
├── tagtypes.py           # Tag registry
├── container.py          # Data structures
├── hf14ainfo.py          # HF parser
├── hfsearch.py           # HF search
├── lfsearch.py           # LF search
├── hfmfread.py           # MFC reader
├── hfmfwrite.py          # MFC writer
├── lfread.py             # LF reader
├── lfwrite.py            # LF writer
├── hfmfkeys.py           # Key management
├── lft55xx.py            # T55xx utilities
├── sniff.py              # Traffic capture
└── ...
```

Each module MUST:
1. Match the original .so's API exactly (same function names, same parameters)
2. Cite ground truth for every constant and command
3. Be independently testable
4. Not duplicate logic from other modules

---

## HANDOVER PROTOCOL

When context gets tight:
1. Update this document with current progress
2. Write a handover prompt with:
   - Current phase and status
   - What's been completed
   - What's blocked and why
   - Next immediate action
   - Any open questions
3. Save to `docs/HANDOVER_MIDDLEWARE.md`
