# Minor Flows Handover: Time Settings, PC Mode, About

You are continuing work on the iCopy-X open-source firmware reimplementation.

## Your task

Implement **THREE minor system UI flows** end-to-end, from Phase 1 (scenario creation + original firmware validation) through Phase 2 (open-source UI integration). These are:

1. **Time Settings** (`TimeSyncActivity`) -- 6-field date/time cursor editor
2. **PC Mode** (`PCModeActivity`) -- USB mass storage gadget controller
3. **About** (`AboutActivity` + `UpdateActivity`) -- device info display + firmware update launcher

All three are **pure system UI flows** -- they send **ZERO PM3 RFID commands**. They have **no existing flow scenarios**. You are building everything from scratch.

---

## THREE ABSOLUTE LAWS

### LAW 1: NO MIDDLEWARE
These activities are thin UI shells. They do NOT send PM3 tag commands (`hf`, `lf`). Time Settings writes the system clock. PC Mode toggles USB kernel modules via `gadget_linux.so`. About reads version info and launches the update installer. If you find yourself importing `scan`, `read`, `write`, or building PM3 command strings -- **STOP.**

The Erase flow is the ONLY justified middleware exception in this project. See `docs/flows/dump_files/ui-integration/README.md` Section 6.3 for why, and the structure (`src/middleware/erase.py`) put in place. None of these three flows warrant an exception.

### LAW 2: NO CHANGING SCENARIOS (Phase 2)
Once Phase 1 scenarios pass with `--target=original`, they become **IMMUTABLE** acceptance criteria. If a scenario fails with `--target=current`, the bug is in your implementation. Present evidence and ask before modifying any test.

### LAW 3: VALIDATE CONTENT, NOT STATE COUNT
At EACH critical gate, validate at least **2** of: title text, button text + active state, content text, toast text. State count is a smoke test only -- it catches crashes, not wrong content. A test that only checks "5 unique states" can pass with completely wrong button labels.

---

## Phase 1: Build Flow Scenarios

### What Phase 1 IS
Extract the complete logic tree from the original `.so` binary. Build a scenario for EACH leaf. Run ALL scenarios against `--target=original`. Iterate until 100% PASS.

### Methodology

**READ FIRST:** `docs/HOW_TO_BUILD_FLOWS.md` -- complete reference for:
- Deriving logic trees from `.so` string extractions and decompiled output
- Fixture system (PM3 mock responses) -- though these three flows need minimal/no PM3 fixtures
- Scenario architecture, state capture, trigger patterns
- The `wait_for_ui_trigger` function and field:value matching

**For each flow:**

1. **Extract the logic tree** from `decompiled/activity_main_ghidra_raw.txt` and `docs/UI_Mapping/{N}_{flow}/README.md`. Identify every state, every transition, every branch.

2. **Write one scenario per leaf.** Each scenario navigates from the main menu to the target state, validates content at each gate, and exits cleanly. Use the pattern from existing flows:
   ```
   tests/flows/{flow}/
     includes/{flow}_common.sh       # shared infrastructure
     scenarios/{name}/{name}.sh      # scenario script
     scenarios/{name}/fixture.py     # PM3 mock (minimal for these flows)
     test_{flow}_parallel.sh         # parallel runner
   ```

3. **Use QEMU tracing** to discover exact behavior. When unsure, run the original firmware and capture state dumps:
   ```bash
   export DISPLAY=:50
   Xvfb :50 -screen 0 240x240x24 -ac +render -noreset &>/dev/null &
   TEST_TARGET=original python3 tools/launcher_current.py \
     --fixture /path/to/fixture.py \
     --keys "GOTO:{index},SLEEP:2,STATE_DUMP,{keys},STATE_DUMP,FINISH"
   ```
   Inspect the JSON state dumps to see exact titles, button text, content, and canvas items.

4. **Validate per gate**, not just final state:
   ```bash
   # Gate 1: Activity entered
   wait_for_ui_trigger "title:Time Settings" 30 "${raw_dir}" frame_idx

   # Gate 2: Correct buttons
   wait_for_ui_trigger "M1:Edit" 5 "${raw_dir}" frame_idx
   wait_for_ui_trigger "M2:Edit" 5 "${raw_dir}" frame_idx

   # Gate 3: Content verification
   wait_for_ui_trigger "content:2026" 5 "${raw_dir}" frame_idx
   ```

5. **Run on remote QEMU server** for reliability:
   ```bash
   sshpass -p proxmark rsync -az --delete --exclude='.git' --exclude='tests/flows/_results' \
     --exclude='__pycache__' --exclude='.development assistant' \
     /home/qx/icopy-x-reimpl/ qx@178.62.84.144:/home/qx/icopy-x-reimpl/
   sshpass -p proxmark ssh qx@178.62.84.144 \
     'cd ~/icopy-x-reimpl && TEST_TARGET=original bash tests/flows/{flow}/test_{flow}_parallel.sh'
   ```
   **Do NOT use blind sleeps.** Poll results every 60s.

### Flow Specifications

Each flow has a complete specification with state machines, logic trees, and proposed scenarios:

| Flow | Spec | GOTO Index | Proposed Scenarios |
|------|------|------------|-------------------|
| Time Settings | `docs/flows/time_settings/README.md` | `GOTO:12` | 13 |
| PC Mode | `docs/flows/pc_mode/README.md` | `GOTO:6` | 9 |
| About | `docs/flows/about/README.md` | `GOTO:10` | 9 |

**READ ALL THREE SPECS BEFORE STARTING.**

### Reference Implementations

Study these existing flow tests as templates for scenario structure, common.sh patterns, parallel runners, and trigger validation:

| Flow | Scenarios | Dir | Best for learning |
|------|-----------|-----|-------------------|
| Erase | 10 | `tests/flows/erase/` | Simple flow, per-gate validation, toast checking |
| Sniff | 28 | `tests/flows/sniff/` | Multi-state flow, content validation |
| Dump Files | 35 | `tests/flows/dump_files/` | Complex flow, sub-activity launching |

---

## Phase 2: Open-Source UI Integration

### What Phase 2 IS
Craft Python UI code that faithfully reproduces the original firmware's behavior. The Phase 1 tests pass as a CONSEQUENCE of correct implementation -- not by reverse-engineering expectations.

### What Phase 2 IS NOT
"Making tests pass." Do not hack, shortcut, or add conditional logic that checks for test-specific conditions.

### Methodology

**READ:** `docs/HOW_TO_INTEGRATE_A_FLOW.md` -- 4-layer architecture, JSON UI system, activity lifecycle.

**READ:** `docs/flows/dump_files/ui-integration/README.md` -- Post-mortem with critical lessons:
- **QEMU LD_PREFIX file redirection** -- QEMU redirects `/mnt/upan/` to rootfs. Symlinks required:
  ```bash
  sudo ln -sf /mnt/upan/dump /mnt/sdcard/root2/root/mnt/upan/dump
  sudo ln -sf /mnt/upan/keys /mnt/sdcard/root2/root/mnt/upan/keys
  ```
- **Scan cache must use native Python types** (int for type, bool for found -- NOT strings)
- **template.draw() overwrites title bar** -- reset `_is_title_inited` and re-call `setTitle()` after
- **Per-gate validation catches bugs that state-count misses** -- always validate content
- **Cross-target comparison** -- run `--target=original` and `--target=current`, diff state dumps
- **No middleware** -- with Erase exception documented in Section 6.3

### For each flow:

1. **Read the existing Python implementation** in `src/lib/activity_main.py`. The current code was built from decompiled binary analysis and may be close to correct, or may have bugs.

2. **Run Phase 1 scenarios with `--target=current`**. Note failures.

3. **Fix the Python code** to match original behavior. Use cross-target state dump comparison to find differences:
   ```bash
   # Run both targets
   TEST_TARGET=original SCENARIO=time_display FLOW=time_settings bash tests/flows/time_settings/scenarios/time_display/time_display.sh
   TEST_TARGET=current  SCENARIO=time_display FLOW=time_settings bash tests/flows/time_settings/scenarios/time_display/time_display.sh

   # Compare state dumps
   diff <(python3 -c "...original state...") <(python3 -c "...current state...")
   ```

4. **Iterate until all scenarios PASS** with `--target=current`.

5. **Verify no regressions** on ALL existing suites:
   - Scan (45), Read (99), Write (63), Auto-Copy (52), Simulate (32), Erase (10), Sniff (28), Dump Files (35)

---

## Ground Truth Resources

### Per-Flow Resources

| Resource | Time Settings | PC Mode | About |
|----------|--------------|---------|-------|
| **UI Mapping** | `docs/UI_Mapping/14_time_settings/README.md` | `docs/UI_Mapping/08_pcmode/README.md` | `docs/UI_Mapping/12_about/README.md` |
| **Screenshots** | `Screenshots/time_settings_*.png` (14 files) | `Screenshots/pc_mode.png` | `Screenshots/about_*.png` (3 files) |
| **Activity code** | `activity_main.py` L1689-1997 | `activity_main.py` L1384-1679 | `activity_main.py` L469-651, L6218-6278 |
| **Archive prototype** | `archive/ui/screens/time_settings.json` | `archive/ui/activities/pcmode.py` | `archive/ui/activities/about.py`, `update.py` |
| **Decompiled** | `decompiled/activity_main_ghidra_raw.txt` | Same + `gadget_linux_ghidra_raw.txt` | Same + `activity_update_ghidra_raw.txt`, `update_ghidra_raw.txt` |

### Shared Resources

| Resource | Path |
|----------|------|
| **Build methodology** | `docs/HOW_TO_BUILD_FLOWS.md` |
| **Integration methodology** | `docs/HOW_TO_INTEGRATE_A_FLOW.md` |
| **Model spec (Dump Files)** | `docs/flows/dump_files/README.md` |
| **Model post-mortem** | `docs/flows/dump_files/ui-integration/README.md` |
| **String resources** | `src/lib/resources.py` |
| **Test infrastructure** | `tests/includes/common.sh` |
| **Example: simple flow** | `tests/flows/erase/` (10 scenarios, minimal complexity) |
| **Example: complex flow** | `tests/flows/dump_files/` (35 scenarios, sub-activities) |

### String Resources Quick Reference

**Time Settings:** `time_sync` (title), `edit`, `cancel`, `save` (buttons), `time_syncing`, `time_syncok` (toasts)

**PC Mode:** `pc-mode` (title), `start`, `stop`, `button` (buttons), `processing`, `pcmode_running` (toasts), `connect_computer` (content)

**About:** `about` (title), `aboutline1`-`aboutline6` (page 1), `aboutline1_update`-`aboutline5_update` (page 2), `update` (UpdateActivity title), `update_finish`, `update_unavailable`, `install_failed` (toasts)

---

## Execution Order

### Recommended sequence (simplest first):

1. **About** (simplest -- 2-page static viewer, no state machine, no background threads)
   - Phase 1: Build 9 scenarios, validate against original
   - Phase 2: Fix any rendering issues in current Python code

2. **Time Settings** (medium -- 2-state editor with cursor, value wrapping, day clamping)
   - Phase 1: Build 13 scenarios, validate against original
   - Phase 2: Fix field rendering, button transitions, toast timing

3. **PC Mode** (most complex -- 4-state machine with background threads, USB gadget mocking)
   - Phase 1: Build 9 scenarios with gadget mocks, validate against original
   - Phase 2: Fix state transitions, button labels, toast timing

### For each flow, complete Phase 1 AND Phase 2 before moving to the next.

---

## Definition of Done

### Per Flow
1. ALL Phase 1 scenarios PASS with `--target=original`
2. ALL Phase 1 scenarios PASS with `--target=current`
3. Every scenario validates content at each gate (title + buttons + content/toast)
4. NO middleware -- activities send ZERO PM3 RFID commands
5. NO scenario modifications after Phase 1 validation

### Overall
1. All three flows complete: About + Time Settings + PC Mode
2. No regressions on existing suites (364 scenarios across 8 flows)
3. Post-mortem documentation in `docs/flows/{flow}/ui-integration/README.md`

---

## Environment

- **Branch:** `feat/ui-integrating`
- **Local QEMU:** `/home/qx/.local/bin/qemu-arm-static`, rootfs at `/mnt/sdcard/root2/root/`
- **Remote QEMU:** `qx@178.62.84.144` (password: `proxmark`, 48 cores)
- **Real device:** `sshpass -p 'fa' ssh -p 2222 root@localhost` (tunnel must be up)
- **Display:** Xvfb on `:50` or `:99` (240x240x24)
- **QEMU LD_PREFIX symlinks:** MUST exist on both local and remote:
  ```bash
  sudo ln -sf /mnt/upan/dump /mnt/sdcard/root2/root/mnt/upan/dump
  sudo ln -sf /mnt/upan/keys /mnt/sdcard/root2/root/mnt/upan/keys
  ```
