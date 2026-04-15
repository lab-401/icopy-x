# Compatibility Layer Flip — Task Document (2026-04-16)

## Branch: `refactor/compat-flip`

---

## Objective

Reverse the PM3 compatibility layer so that **iceman (RRG) syntax is native** in all middleware modules, and **factory/legacy syntax is the translation layer**.

Currently:
- 48 middleware modules use old-style (factory) PM3 commands and regex patterns
- `pm3_compat.translate()` converts old→new commands before sending
- `pm3_compat.translate_response()` normalizes new→old responses after receiving

After this refactor:
- All middleware modules use iceman CLI-flag syntax and iceman output patterns natively
- `pm3_compat.translate()` converts new→old commands (for factory firmware)
- `pm3_compat.translate_response()` normalizes old→new responses (for factory firmware)

## Why

- Iceman is the primary target — factory is legacy
- Current architecture means every PM3 interaction goes through two translation layers
- Maintenance burden: adding new PM3 features requires understanding both syntaxes
- New contributors will expect iceman syntax (it's the upstream standard)

---

## Device Access

```
SSH: sshpass -p 'fa' ssh -p 2222 root@localhost
```
Requires reverse SSH tunnel from the device. User establishes manually.

### Key device paths
- App: `/home/pi/ipk_app_main/`
- PM3 binary: `/home/pi/ipk_app_main/pm3/proxmark3`
- Dump files: `/mnt/upan/dump/`
- IPK install: copy to `/mnt/upan/`, install via device UI Settings > Install

### Build & Deploy
```bash
python3 tools/build_ipk.py --output /tmp/icopy-x-latest.ipk
sshpass -p 'fa' scp -P 2222 /tmp/icopy-x-latest.ipk root@localhost:/mnt/upan/
```
Install via device UI: Settings > Install. Device reboots after install.

### Live Tracing
Full protocol: `docs/HOW_TO_RUN_LIVE_TRACES.md`

---

## CRITICAL RULES

1. **No atomic device edits** — deploy via IPK only (hot-patch requires explicit user authorization)
2. **NEVER flash PM3 bootrom** — no JTAG = permanent brick
3. **NEVER access ~/.ssh on any device**
4. **Never change activity flow architecture** — only refactor WITHIN existing activities
5. **Always clean up sitecustomize.py** after tracing — leaving it crashes the app
6. **Both firmware variants must work** — every change must be verified against BOTH iceman and factory PM3
7. **No regressions** — existing test fixtures must continue to pass throughout

---

## Scope

### Quantified touchpoints

| Category | Count | Location |
|----------|-------|----------|
| Middleware modules with PM3 commands | 27 | `src/middleware/*.py` |
| `startPM3Task()` calls | 110 | Commands to translate |
| `hasKeyword()` calls | 108 | Response patterns to update |
| `getContentFromRegex()` / `getPrintContent()` calls | 107 | Regex patterns to update |
| Command translation rules (old→new) | 65 | `pm3_compat.py` — to reverse |
| Response normalizer functions | 28 | `pm3_compat.py` — to reverse |
| Response format catalog entries | 376 lines | `pm3_response_catalog.py` — reference |

### Affected middleware modules (by flow)

| Flow | Module(s) | PM3 Commands | Complexity |
|------|-----------|-------------|------------|
| **Scan** | `scan.py`, `hf14ainfo.py`, `hfsearch.py` | hf 14a info, hf search, lf search, lf t55xx detect | High — most-used, many response patterns |
| **Read MFC** | `hfmfread.py`, `hfmfkeys.py` | hf mf fchk, hf mf rdbl, hf mf rdsc, hf mf nested, darkside | High — key recovery has complex output |
| **Write MFC** | `hfmfwrite.py` | hf mf wrbl, hf mf csetblk, hf mf cgetblk | Medium |
| **Read MFU** | `hfmfuread.py`, `hfmfuinfo.py` | hf mfu info, hf mfu rdbl | Medium |
| **Write MFU** | `hfmfuwrite.py` | hf mfu wrbl | Low |
| **Read LF** | `lfread.py`, `lft55xx.py`, `lfem4x05.py` | lf t55xx read, lf em 4x05_read, data rawdemod | High — T55xx has many output formats |
| **Write LF** | `lfwrite.py`, `lft55xx.py` | lf t55xx write, lf em 410x clone, lf hid clone | Medium |
| **Verify LF** | `lfverify.py` | lf t55xx read (verify mode) | Low |
| **Read iCLASS** | `iclassread.py`, `hficlass.py` | hf iclass rdbl, hf iclass dump | Medium |
| **Write iCLASS** | `iclasswrite.py` | hf iclass wrbl | Medium |
| **Read ISO15693** | `hf15read.py` | hf 15 rdbl | Low |
| **Write ISO15693** | `hf15write.py` | hf 15 wrbl | Low |
| **Read FeliCa** | `felicaread.py` | hf felica reader, hf felica rdbl | Low |
| **Read Legic** | `legicread.py` | hf legic rdbl | Low |
| **Erase** | `erase.py` | hf mf wrbl (block erase), lf t55xx wipe | Medium |
| **Sniff** | `sniff.py` | hf sniff, lf sniff | Low |
| **Diagnosis** | `executor.py` (hw commands) | hw version, hw status, mem spiffs | Low |
| **Flash** | `pm3_flash.py` | hw version, flash commands | Low |
| **LF Search** | `lfsearch.py` | lf search, lf t55xx detect, em4x05 | High — many chipset patterns |

---

## Execution Method: Multi-Agent Orchestrated Refactor

### Phase 1: Exhaustive Audit (BEFORE ANY CODE CHANGES)

**Agent A (Auditor):** Performs a complete audit of every middleware module. For each module, produces:
- Every `startPM3Task()` call: current command string, required iceman equivalent
- Every `hasKeyword()` call: current keyword, required iceman equivalent
- Every `getContentFromRegex()` / `getPrintContent()` call: current pattern, required iceman pattern
- Cross-reference against `pm3_compat.py` translation rules and `pm3_response_catalog.py`

Output: A structured TODO list, module by module, method by method, with:
- File path and line number
- Current (factory) syntax
- Required (iceman) syntax
- Affected flow(s)

**Agent B (Audit Reviewer):** Reviews Agent A's output against the actual codebase. Confirms:
- 100% code coverage — every PM3 interaction is accounted for
- No missing modules or methods
- Cross-references are correct
- Iterates with Agent A until complete

**User checkpoint:** Orchestrator presents the complete audit to the user for approval before any code changes begin.

### Phase 2: Flow-by-Flow Implementation

Process repeats for each flow (Scan, Read, Write, Erase, etc.) in order:

**Agent 1 (Implementer):** Refactors the middleware module(s) for this flow:
- Updates all `startPM3Task()` commands to iceman syntax
- Updates all `hasKeyword()` / `getContentFromRegex()` patterns to match iceman output
- Updates `pm3_compat.py` to add reverse translation (new→old) for this flow's commands
- Updates `pm3_compat.py` to add reverse response normalization (old→new) for this flow

**Agent 2 (Fixture Validator):** Tests bidirectional compatibility using real PM3 fixtures:
- Runs the refactored module against **iceman fixtures** (new format) — must work natively
- Runs the refactored module against **factory fixtures** (old format) via the reversed compat layer — must also work
- Reports any mismatches

**Agent 3 (Test Writer):** Writes/updates tests for this flow:
- Tests that iceman commands are generated correctly (no compat layer)
- Tests that factory commands are generated correctly (via reversed compat layer)
- Tests that iceman responses parse correctly (no compat layer)
- Tests that factory responses parse correctly (via reversed compat layer)

**Agent 4 (Test Runner):** Runs the test suite continuously:
- Reports pass/fail status after each implementation change
- Catches regressions in previously-completed flows
- All agents iterate until Agent 4 reports 100% pass

**User checkpoint:** After all agents agree, the user tests the flow on the real device:
- Orchestrator sets up real-time tracing (sitecustomize.py instrumentation)
- User performs the flow on the physical device
- Orchestrator pulls trace, verifies PM3 commands and responses match expectations
- User approves → move to next flow

### Phase 3: Cleanup

After all flows are verified:
- Remove old (now-unused) translation rules from `pm3_compat.py`
- Remove `pm3_response_catalog.py` if fully absorbed
- Update `pm3_compat.detect_pm3_version()` — factory becomes the "needs translation" path
- Final full regression test
- Device verification of complete flow suite

---

## Key Files

### Compatibility layer
- `src/middleware/pm3_compat.py` — command & response translation (1477 lines)
- `src/middleware/pm3_response_catalog.py` — response format diff catalog (376 lines)
- `src/middleware/executor.py` — calls translate/translate_response (integration point)

### Middleware modules (by priority)
1. `src/middleware/scan.py` — scan orchestrator
2. `src/middleware/hf14ainfo.py` — HF 14A tag identification
3. `src/middleware/hfmfread.py` — MIFARE Classic read + key recovery
4. `src/middleware/hfmfkeys.py` — key management
5. `src/middleware/hfmfwrite.py` — MIFARE Classic write
6. `src/middleware/erase.py` — tag erasure
7. `src/middleware/lfsearch.py` — LF tag identification
8. `src/middleware/lft55xx.py` — T55xx read/write/detect
9. `src/middleware/lfread.py` — LF tag reading
10. `src/middleware/lfwrite.py` — LF tag writing
11. `src/middleware/hfsearch.py` — HF search
12. `src/middleware/hficlass.py` — iCLASS operations
13. `src/middleware/iclassread.py` — iCLASS read
14. `src/middleware/iclasswrite.py` — iCLASS write
15. `src/middleware/hf15read.py` — ISO15693 read
16. `src/middleware/hf15write.py` — ISO15693 write
17. `src/middleware/hfmfuread.py` — MIFARE Ultralight read
18. `src/middleware/hfmfuwrite.py` — MIFARE Ultralight write
19. `src/middleware/felicaread.py` — FeliCa read
20. `src/middleware/legicread.py` — Legic read
21. `src/middleware/lfverify.py` — LF verification
22. `src/middleware/lfem4x05.py` — EM4x05 operations
23. `src/middleware/sniff.py` — HF/LF sniffing
24. `src/middleware/pm3_flash.py` — PM3 firmware flash

### Test infrastructure
- `tests/ui/` — UI tests
- `tests/flows/` — QEMU flow tests with fixtures
- `tools/pm3_fixtures.py` — 179 PM3 mock response scenarios

---

## Flow Execution Order

Execute in this order (most-used and highest-risk first):

1. **Scan** (scan.py, hf14ainfo.py, hfsearch.py, lfsearch.py)
2. **Read HF** (hfmfread.py, hfmfkeys.py, hfmfuread.py, hfmfuinfo.py)
3. **Write HF** (hfmfwrite.py, hfmfuwrite.py)
4. **Erase** (erase.py)
5. **Read LF** (lfread.py, lft55xx.py, lfem4x05.py)
6. **Write LF** (lfwrite.py, lft55xx.py)
7. **Verify LF** (lfverify.py)
8. **iCLASS** (hficlass.py, iclassread.py, iclasswrite.py)
9. **ISO15693** (hf15read.py, hf15write.py)
10. **FeliCa** (felicaread.py)
11. **Legic** (legicread.py)
12. **Sniff** (sniff.py)
13. **Diagnosis** (executor.py hw commands)
14. **Flash** (pm3_flash.py)

---

## Success Criteria

- [ ] All middleware modules use iceman syntax natively
- [ ] `pm3_compat.py` reversed: translates iceman→factory (not factory→iceman)
- [ ] Both IPK variants work: flash (iceman, no translation) and no-flash (factory, via compat layer)
- [ ] All existing tests pass
- [ ] New bidirectional tests cover every translated command and response pattern
- [ ] Every flow verified on real hardware with both firmware variants
- [ ] User approved each flow via live device testing
