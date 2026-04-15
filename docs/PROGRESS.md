# iCopy-X Open — Progress Tracker

## Goal
Open-source 1:1 replacement for iCopy-X v1.0.90 firmware with **provable parity**.

## Method
For each UI flow: deep dive into the original 1.0.90 .so binaries using recorded logs, traces, screenshots from real hardware, Ghidra decompilations — then build 100% UI path walkers that prove every screen state matches.

## Primary Sources of Truth (in priority order)
1. **v1.0.90 `.so` binaries** — the compiled Cython modules (62 files, 162K strings extracted)
2. **Ghidra decompilations** — 925K lines across all 59 modules
3. **Real device straces** — PM3 TCP traces, framebuffer captures, key sequences
4. **Real device screenshots** — RGB565 framebuffer captures at 100ms intervals
5. **QEMU ARM emulation** — boots real .so modules, captures every screen state

Nothing else is a source of truth. Transliterated Python and reimplemented middleware are **outputs**, not inputs.

---

## 7-Step Procedure

| Step | Description | Status |
|------|-------------|--------|
| 1 | Decompile and emulate under QEMU | **DONE** — 59 .so Ghidra-decompiled (925K lines). QEMU boots real firmware. |
| 2 | Navigate every UI branch to every leaf | **IN PROGRESS** — see per-flow status below |
| 3 | Extract all strings from .so binaries | **70%** — 65 string files extracted. PM3 pattern map complete. Cross-reference pending. |
| 4 | Build verified UI Map | PENDING — needs consolidation of all flow docs + QEMU captures |
| 5 | Update middleware map | PENDING — flow docs contain middleware calls, need single reference |
| 6 | Update transliteration layer | PENDING — known bugs: lf_wav_filter, lfverify (7 bugs), scan pipeline order, hficlass blob |
| 7 | Implement with provable parity | PENDING |

---

## Step 2: Per-Flow Navigation Status

Each flow follows the same procedure:
1. Extract complete flow tree from .so binary strings + Ghidra decompilation
2. Identify every PM3 command, response pattern (hasKeyword/regex), and branch point
3. Build PM3 mock fixtures for every branch
4. Run QEMU walker — navigate to every state, OCR every frame, validate entry + outcome
5. Cross-reference: every .so string accounted for by at least one scenario
6. 100% coverage or repeat

### Scan Tag
| Item | Status |
|------|--------|
| Flow document | **DONE** — extracted from scan.so, hf14ainfo.so, hfsearch.so, lfsearch.so, hfmfuinfo.so |
| .so string extraction | **DONE** — all scan-related modules |
| PM3 command traces (QEMU) | **DONE** — 12 tag families traced |
| Scan fixtures | **DONE** — 52 scan fixtures covering all 44 tag types |
| QEMU walker | **DONE** — 44 scenarios, all pass with screenshot validation |
| Real device captures | **DONE** — framebuffer captures for 5+ tag types |
| String cross-reference | **DONE** — 81/81 branch patterns (100%) |

### Read Tag
| Item | Status |
|------|--------|
| Flow document | **DONE** — V1090_READ_FLOW_COMPLETE.md (1484 lines). All reader classes mapped. |
| .so string extraction | **DONE** — hfmfkeys, hfmfread, hfmfuread, hficlass, iclassread, hf15read, legicread, lfread, lft55xx, lfem4x05, felicaread, hf14aread |
| Decision trees | **DONE** — V1090_HFICLASS_DECISION_TREE.md, V1090_SCAN_DECISION_TREE.md, V1090_SEARCH_DECISION_TREES.md |
| MIFARE branch mapping | **DONE** — V1090_MIFARE_BRANCH_STRINGS.md. 27 branches × 8 type variants. |
| Read fixtures | **DONE** — 73 read fixtures, 52 scan fixtures. All built from .so decision trees. |
| QEMU walker | **DONE** — **40/40 types, 400+ scenarios, 0 failures.** All LF fixtures fixed (REGEX_CARD_ID false matches, type ID routing, T5577/EM4305 flows). |
| Step 4 verification | **DONE** — `verify_coverage.py --scope read`: PM3 commands 50/50 (100%), branch keywords 27/27 (100%), 0 CRITICAL gaps. |
| Real tag list verified | **DONE** — 42 types from real tagtypes.so getName(). 4 types excluded (38/39/40/47 not in getReadable). |

### Write Tag
| Item | Status |
|------|--------|
| Flow document | **DONE** — V1090_WRITE_FLOW_COMPLETE.md (1317 lines) |
| .so string extraction | **DONE** — hfmfwrite, hfmfuwrite, hf15write, iclasswrite, lfwrite |
| PM3 command traces | NOT STARTED |
| Write fixtures | PARTIAL — 36 write fixtures exist but not walker-validated |
| QEMU walker | **NOT STARTED** |
| String cross-reference | NOT STARTED |

### Auto Copy
| Item | Status |
|------|--------|
| Flow document | **DONE** — V1090_AUTOCOPY_FLOW_COMPLETE.md (785 lines) |
| .so string extraction | DONE — scan + read + write modules cover this |
| PM3 command traces | PARTIAL — 5 autocopy fixtures exist, real device MF1K→Gen1a trace captured |
| QEMU walker | **NOT STARTED** |

### Erase Tag
| Item | Status |
|------|--------|
| Flow document | **DONE** — V1090_ERASE_FLOW_COMPLETE.md (583 lines) |
| .so string extraction | DONE |
| Erase fixtures | PARTIAL — 5 erase fixtures exist |
| QEMU walker | **NOT STARTED** |

### Sniff TRF
| Item | Status |
|------|--------|
| Flow document | **DONE** — V1090_SNIFF_FLOW_COMPLETE.md (828 lines) |
| .so string extraction | DONE — sniff.so |
| Sniff fixtures | PARTIAL — 3 fixtures |
| QEMU walker | **NOT STARTED** |

### Simulation
| Item | Status |
|------|--------|
| Flow document | **DONE** — V1090_SIMULATION_FLOW_COMPLETE.md (675 lines) |
| QEMU walker | **NOT STARTED** |

### Dump Files
| Item | Status |
|------|--------|
| Flow document | **DONE** — V1090_DUMPFILES_FLOW_COMPLETE.md (621 lines) |
| QEMU walker | **NOT STARTED** |

### Diagnosis
| Item | Status |
|------|--------|
| Flow document | PARTIAL — hw tune fixtures exist, full flow doc needed |
| QEMU walker | **NOT STARTED** |

### Settings (Backlight, Volume, Time, PC-Mode)
| Item | Status |
|------|--------|
| Flow document | **DONE** — V1090_SETTINGS_FLOWS_COMPLETE.md (939 lines) |
| QEMU walker | **NOT STARTED** |

### About / Update
| Item | Status |
|------|--------|
| Flow document | **DONE** — V1090_ABOUT_UPDATE_FLOW_COMPLETE.md (999 lines) |
| QEMU walker | **NOT STARTED** |

### LUA Script
| Item | Status |
|------|--------|
| Flow document | PARTIAL — menu position known, console rendering documented |
| QEMU walker | **NOT STARTED** |

---

## Infrastructure Built

| Tool | Purpose | Lines |
|------|---------|-------|
| `tools/walkers/walk_all_reads.py` | Read Tag parallel QEMU walker with OCR self-testing | 1125 |
| `tools/walkers/walk_scan_scenarios.sh` | Scan Tag sequential walker (44 scenarios) | 50 |
| `tools/walkers/walk_scan_parallel.sh` | Scan Tag parallel walker (4 workers) | ~300 |
| `tools/pm3_fixtures.py` | PM3 mock responses for every branch | 2568 |
| `tools/verify_coverage.py` | **Step 4 verification** — scoped .so string coverage (PM3 cmds, branch keywords, regex) | 486 |
| `tools/xref_strings.py` | Legacy cross-reference (superseded by verify_coverage.py) | 403 |
| `tools/minimal_launch_090.py` | QEMU launcher with executor mock + showScanToast bridge | ~700 |
| `tools/read_list_map.json` | 44-item Read Tag list positions verified | 50 |
| `tools/qemu_shims/` | Python shims for Cython modules under QEMU | ~500 |

**Fixture counts:** 52 scan + 73 read + 36 write + 5 erase + 7 autocopy + 3 diagnosis + 3 sniff = **179 total**

**Primary source documents:**
- 65 `.so` string extraction files (162K strings)
- V1090_PM3_PATTERN_MAP.md — every regex and hasKeyword from every .so
- V1090_MIFARE_BRANCH_STRINGS.md — 27 MIFARE branches with exact patterns
- V1090_SCAN_COMMAND_TRACES.md — QEMU-traced PM3 command sequences
- V1090_REAL_DEVICE_TRACES.md — real hardware strace captures
- 10 flow documents (8,231 lines total) extracted from .so binaries

---

## What's Next

**Immediate: Finish Read Tag walker (Step 2 for Read)**
- Resolve 21 remaining walker failures using .so ground truth
- Key blockers: scan routing for types 38/39/47, executor helper propagation for iCLASS

**Then: Write Tag walker (Step 2 for Write)**
- Same procedure: extract branches from .so → build fixtures → run walker → cross-reference
- V1090_WRITE_FLOW_COMPLETE.md already exists, 36 write fixtures exist
- Need: PM3 command traces, QEMU walker, string cross-reference

**Then: Remaining flows in order of PM3 complexity**
1. Auto Copy (scan → read → write combined — reuses existing fixtures)
2. Erase Tag (scan → wipe — simpler flow)
3. Sniff TRF (capture → decode)
4. Simulation (replay — no PM3 write)
5. Dump Files (file browser — no PM3)
6. Diagnosis (hw tune)
7. Settings (no PM3)
8. About/Update
9. LUA Script

**Then: Steps 3-7 in order**
- Step 3: Complete string cross-reference for ALL flows
- Step 4: Consolidate into UI_MAP_EXHAUSTIVE.md
- Step 5: Single middleware command reference
- Step 6: Systematic transliteration comparison
- Step 7: Implement
