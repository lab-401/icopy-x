# Handover: Middleware Transliteration — Phase 4 (Write Pipeline)

## Who You Are

You are the orchestrator for transliterating the iCopy-X closed-source middleware from compiled `.so` modules to open-source Python. You are continuing from a previous session that completed Phases 2 (Scan) and 3 (Read).

## What Has Been Done

### Phase 2: Scan — COMPLETE (45/45 PASS)
Modules implemented in `src/middleware/`:
- `executor.py` — PM3 communication layer (23 functions, TCP socket, Nikola.D protocol)
- `hf14ainfo.py` — HF 14443A tag parser (UID, SAK, ATQA classification)
- `hfsearch.py` — HF search parser (iCLASS, ISO15693, LEGIC, ISO14443-B, Topaz, FeliCa detection)
- `lfsearch.py` — LF search parser (21 tag types, FC/CN extraction, regex helpers)
- `scan.py` — Scanner orchestrator class (pipeline: 14a → lfsea → hfsea → t55xx → em4x05 → felica)
- `template.py` — Result display renderer (TYPE_TEMPLATE with 48 entries, 13 draw functions)
- `lft55xx.py` — T55xx detect/dump/check (scan + read functions)
- `hficlass.py` — iCLASS parser + key checking (Legacy/Elite)
- `hffelica.py` — FeliCa parser

### Phase 3: Read — COMPLETE (97/97 PASS)
Additional modules:
- `lfread.py` — LF read dispatch (22 tag-type read functions)
- `lfem4x05.py` — EM4x05 info/dump/read operations
- `iclassread.py` — iCLASS Legacy/Elite read flow

Also modified:
- `src/lib/activity_read.py` — Added ProgressBar + "Reading..." text during read phase, console overlap fix

### Phase 4: Write — BASELINE CAPTURED, NOT STARTED
- **Baseline**: 29/61 PASS, 32 FAIL
- **Spec saved**: `docs/middleware-integration/6-write_spec.md` (944 lines)
- **Failures**: ALL LF writes (19), ALL T55xx (5), ALL iCLASS writes (5), EM4305 (1), 2 others
- **Root cause**: Our middleware modules (lft55xx.py, hficlass.py, lfem4x05.py) shadow the original .so but lack write-phase functions

---

## Project Architecture

### Directory Structure
```
src/middleware/   — Our Python reimplementations (shadow .so from QEMU rootfs)
src/lib/          — UI layer (activities, widgets, renderers) — mostly complete
src/screens/      — JSON UI schemas — DO NOT MODIFY
tools/            — Launchers, comparison tools, QEMU shims
tests/flows/      — Test scenarios (scan/read/write/erase/etc.)
docs/middleware-integration/  — Transliteration specs (1-6)
decompiled/       — Ghidra decompiled .so files (ground truth)
docs/v1090_strings/  — Extracted string tables from .so files
docs/Real_Hardware_Intel/  — Real device traces and screenshots
```

### How Testing Works
```
Local machine (development):     src/middleware/*.py edited here
                                  ↓ rsync
Remote QEMU server:              qx@178.62.84.144 (pw: proxmark)
  ~/icopy-x-reimpl/              Tests run here under QEMU ARM emulation
```

**CRITICAL**: The remote QEMU server is NOT under source control. It is ONLY used for testing. ALL development happens locally. rsync files to remote, run tests, rsync results back.

### Test Targets
| Target | Command | What It Tests |
|--------|---------|--------------|
| `original` | `TEST_TARGET=original` | Real v1.0.90 .so (baseline, read-only) |
| `current` | `TEST_TARGET=current` | Our Python modules from src/middleware/ |
| `original_current_ui` | `TEST_TARGET=original_current_ui` | Our UI + original .so middleware |

For middleware transliteration, use `TEST_TARGET=current`.

### Test Commands
```bash
# Scan (45 scenarios)
TEST_TARGET=current bash tests/flows/scan/test_scans_parallel.sh 9

# Read (97 scenarios)
TEST_TARGET=current bash tests/flows/read/test_reads_parallel.sh 9

# Write (61 scenarios)
TEST_TARGET=current bash tests/flows/write/test_writes_parallel.sh 9

# Parity comparison
python3 tools/compare_ui_states.py --flow scan --all --baseline original_current_ui --target current
```

### Rsync Pattern
```bash
# Push middleware to remote
sshpass -p 'proxmark' rsync -avz --delete src/middleware/ qx@178.62.84.144:~/icopy-x-reimpl/src/middleware/

# Push activity_read.py if modified
sshpass -p 'proxmark' rsync -avz src/lib/activity_read.py qx@178.62.84.144:~/icopy-x-reimpl/src/lib/activity_read.py

# Pull results back locally
rm -rf tests/flows/_results/current/write/
sshpass -p 'proxmark' rsync -avz qx@178.62.84.144:~/icopy-x-reimpl/tests/flows/_results/current/write/ tests/flows/_results/current/write/
```

---

## ABSOLUTE LAWS

### Ground Truth Sources (ONLY these)
1. **Decompiled .so files**: `decompiled/*.txt` (Ghidra ARM decompilation)
2. **Real device traces**: `docs/Real_Hardware_Intel/trace_*.txt`
3. **Real device screenshots**: `docs/Real_Hardware_Intel/Screenshots/`
4. **String extractions**: `docs/v1090_strings/*.txt`
5. **Test fixtures**: `tests/flows/*/scenarios/*/fixture.py`
6. **Transliteration specs**: `docs/middleware-integration/*.md`
7. **Archive references** (structural ONLY): `/home/qx/archive/lib_transliterated/*.py`

### Rules
1. **Tests are IMMUTABLE.** NEVER edit test files, fixtures, expected.json, or test scripts without explicit user permission.
2. **JSON UI schemas are IMMUTABLE.** NEVER edit files in `src/screens/`.
3. **The UI renderer is IMMUTABLE.** NEVER edit `json_renderer.py`, `widget.py`, or similar.
4. **The `.so` middleware IS the logic.** Never reimplement — transliterate.
5. **Never guess.** Every line of code MUST cite a ground truth source.
6. **Never deviate from ground truth** to make tests pass.
7. **NEVER flash PM3 bootrom.** No JTAG = bricked device.
8. **NEVER access ~/.ssh on any device.**
9. **The remote QEMU server is for TESTING ONLY.** Never develop there. Never modify source on remote. Always rsync from local.
10. **UI outputs must be verifiably identical** to original middleware, down to the pixel. Use `tools/compare_ui_states.py` as the metric.
11. **Data outputs must be verifiably identical.** Use `scenario_states.json` as the comparison benchmark.
12. **Tests are an INDICATION, not the goal.** Your responsibility is 100% coverage and identical outputs. If it's not perfect, it's not done.
13. **ALL tests must RUN TO COMPLETION and ALL must PASS.** No timeouts, no crashes, no skips.
14. **Do NOT use blind sleeps.** Poll output every 30-60s when waiting for background tasks. Catch failures in seconds, not minutes.
15. **Always rm -rf local _results/ before rsyncing results back.** rsync doesn't delete stale files.

---

## Multi-Agent Approach — DETAILED PROTOCOL

For each module/fix, follow this 5-agent protocol strictly. You (the orchestrator) control all agents and enforce quality.

### Agent 1: SPEC AGENT
- **Input**: Ground truth sources (decompiled .so, strings, traces, fixtures)
- **Output**: Method-level transliteration spec with every constant, command, and regex cited
- **Saves to**: `docs/middleware-integration/N-module_spec.md`
- **Rule**: NEVER use archive references as authoritative. Only decompiled .so and traces.

### Agent 2: IMPLEMENTATION AGENT
- **Input**: Spec from Agent 1
- **Output**: Python `.py` module in `src/middleware/`
- **Rule**: Every line cites ground truth. Match original .so API exactly (same function names, same parameters, same return values).
- **Import pattern**: `import executor` inside function bodies (late binding)

### Agent 3: AUDIT AGENT (Clean Room)
- **Step 1**: Reads code WITHOUT the spec. Forms independent understanding.
- **Step 2**: Given the spec, verifies code matches.
- **Output**: PASS or list of violations with specific line numbers.
- **Loop**: If violations found, return to Agent 2.

### Agent 4: TEST AGENT
- **Runs**: Tests on remote QEMU via SSH
- **Verifies**: All scenarios PASS
- **Compares**: Pixel-perfect parity via `compare_ui_states.py`
- **Visually examines**: Screenshots from `scenario_states.json`
- **If FAIL**: Triggers Agent 5

### Agent 5: DEBUG AGENT
- **Compares**: Original vs current behavior using QEMU logs and state dumps
- **Reads**: QEMU logs at `tests/flows/_results/current/*/scenarios/*/qemu.log` on remote
- **Identifies**: Root cause with ground truth citation
- **Uses tooling**: If not enough ground truth is established, use strace on QEMU on the "original" target to get detailed traces, and perform the same on QEMU for the "current" target - and compare the two. This is DIRECT GROUND TRUTH.
- **Feeds back to**: Agent 1 (spec refinement) or Agent 2 (code fix)

### Orchestrator Responsibilities
1. **Dispatch agents with complete context.** Brief them like a colleague who just walked in — they don't know the conversation history.
2. **Control sub-agents tightly.** Do NOT let them guess. Require ground truth citations for every claim.
3. **Poll agent progress every 30-60s.** If an agent is running a background command, check output regularly. Do NOT use blind sleeps > 60s.
4. **Iterate until perfect.** Loop through Agents 2→3→4→5→1 until ALL scenarios pass AND pixel-perfect parity is achieved.
5. **Enforce the laws.** If an agent tries to modify tests, JSON schemas, or the UI renderer, REJECT the change.
6. **Verify before trusting.** After every agent completes, independently verify their claims (check files, run quick tests).
7. **Commit incrementally.** Commit working changes frequently. Don't accumulate massive uncommitted diffs.

### Agent Anti-Patterns to Prevent
- **"Let me try..."** — NO. Ground truth first, then implement.
- **"Perhaps the issue is..."** — NO. Read the QEMU log, read the fixture, read the decompiled source.
- **Modifying tests to make them pass** — NEVER. The tests define the expected behavior.
- **Using blind `sleep 300`** — NO. Poll every 30-60s with `cat output | grep TOTAL`.
- **Developing on remote** — NEVER. Edit locally, rsync, test remotely, rsync results back.
- **Reverting working code** — NEVER without checking. Agents sometimes break things while fixing other things.

---

## Phase 4: Write Pipeline — Implementation Plan

### What Needs To Be Done

The 32 failing write scenarios all fail because our middleware modules shadow the original .so but lack write-phase functions. The fix is to add write functions to existing modules and create new modules where needed.

### Failure Categories

**Category 1: LF writes (19 failures)**
- All `write_lf_*` scenarios
- Root cause: `lfwrite.so` imports `lft55xx` (our .py), `lfverify` (no .py exists). Missing write functions in lft55xx.py, and lfverify.py doesn't exist.
- Fix: Add write functions to lft55xx.py, create lfverify.py

**Category 2: T55xx writes (5 failures)**
- `write_t55xx_block_*`, `write_t55xx_password_write`, `write_t55xx_restore_*`
- Root cause: lft55xx.py missing: `wipe()`, `readBlock()`, `lock()`, `switch_lock()`, `is_b0_lock()`, `getB0WithKey()`, `getB0WithKeys()`
- Fix: Add these functions to lft55xx.py

**Category 3: iCLASS writes (5 failures)**
- `write_iclass_*` scenarios
- Root cause: `iclasswrite.so` imports `hficlass` (our .py). Write flow calls functions we may not have.
- Fix: Check QEMU logs, add missing functions. May need iclasswrite.py.

**Category 4: EM4305 write (1 failure)**
- `write_em4305_dump_success`
- Root cause: lfem4x05.py `verify4x05()` is a stub returning False
- Fix: Implement real verify logic

### Key Resources
- **Write spec**: `docs/middleware-integration/6-write_spec.md` (944 lines, very detailed)
- **DRM note**: hfmfwrite.so has DRM checks but the MFC write scenarios ALREADY PASS (29/61). This means hfmfwrite.so loads correctly from QEMU rootfs. Don't touch MFC write — it works.
- **Archive references** (structure only):
  - `/home/qx/archive/lib_transliterated/lfwrite.py`
  - `/home/qx/archive/lib_transliterated/lft55xx.py`
  - `/home/qx/archive/lib_transliterated/lfverify.py`
  - `/home/qx/archive/lib_transliterated/iclasswrite.py`

### Implementation Strategy
1. Read QEMU logs for one scenario per category to identify exact crash point
2. Add minimum functions needed — don't implement entire modules if only 2-3 functions are needed
3. Test each category independently after fixing
4. Run full write suite once all categories are fixed
5. Run scan + read regression to ensure no breakage
6. Run pixel-perfect comparison
7. Commit and push

### Diagnostic First Step
For each failing category, SSH to remote and read the QEMU log:
```bash
sshpass -p 'proxmark' ssh qx@178.62.84.144 "cat ~/icopy-x-reimpl/tests/flows/_results/current/write/scenarios/write_lf_em410x_success/qemu.log | grep -i 'error\|traceback\|exception\|import' | head -20"
```
This will tell you EXACTLY which function is missing or crashing.

---

## Current File Inventory

### src/middleware/ (14 files)
```
__init__.py          — Package marker
erase.py             — Erase tag middleware (pre-existing)
executor.py          — PM3 communication layer
hf14ainfo.py         — HF 14443A parser
hffelica.py          — FeliCa parser
hficlass.py          — iCLASS parser + key checking
hfsearch.py          — HF search parser
iclassread.py        — iCLASS read flow
lfem4x05.py          — EM4x05 operations
lfread.py            — LF read dispatch
lfsearch.py          — LF search parser
lft55xx.py           — T55xx detect/dump/check
scan.py              — Scanner orchestrator
template.py          — Result display renderer
```

### docs/middleware-integration/ (6 specs)
```
1-executor_spec.md
2-hf14ainfo_hfsearch_lfsearch_spec.md
3-scan_spec.md
4-template_spec.md
5-read_spec.md
6-write_spec.md
```

---

## Passing Test Counts (as of handover)
| Flow | Target=current | Target=original_current_ui |
|------|---------------|--------------------------|
| Scan | 45/45 PASS | 45/45 PASS |
| Read | 97/97 PASS | 95/97 PASS (2 flaky EM4305) |
| Write | 29/61 PASS | Not yet run |

---

## Memory References
Key memories saved in `/home/qx/.development assistant/projects/-home-qx-icopy-x-reimpl/memory/`:
- `feedback_pixel_perfect_parity.md` — UI/data outputs must be verifiably identical
- `feedback_tests_immutable.md` — NEVER modify test files without permission
- `project_startPM3Task_return.md` — startPM3Task returns 1=completed, -1=error
- `feedback_no_middleware_in_tests.md` — Tests provide fixtures, don't reimplement .so logic
- `feedback_ground_truth_only.md` — Every line must cite decompiled .so, trace, or screenshot
- `feedback_agent_rules.md` — Read docs first, never guess, never block user

Read MEMORY.md for the full index.
