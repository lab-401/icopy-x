# Erase Flow -- UI Integration Specification

You are continuing work on the iCopy-X open-source firmware reimplementation.

## Your task
Integrate the **Erase Tag** flow -- `WipeTagActivity` erases MIFARE Classic (Gen1a magic + standard) and T5577 tags. The activity selects erase type, scans the tag, performs the erase via PM3 commands, and shows success/fail results.

**Current status:** `WipeTagActivity` exists in `src/lib/activity_main.py` (lines ~2370-2613) with 5 states and 2 erase types. The test suite has 11 scenarios (10 without the missing 11th). Your job is to run every test, visually audit screenshots against real device captures, and fix any failures or UI issues.

## CRITICAL -- DRM SMOKE TEST

**Before debugging ANY silent .so failure, ALWAYS check DRM first:**

```bash
# Check launcher log for this line:
[OK] tagtypes DRM passed natively: 40 readable types    # <- MUST see this
[WARN] tagtypes DRM failed -- falling back to bypass      # <- MODULES MAY FAIL
```

**Correct serial**: `02c000814dfb3aeb` (in `launcher_current.py` cpuinfo mock)

**Reference**: `docs/DRM-KB.md`, `docs/DRM-Issue.md`

## Essential reading (READ ALL BEFORE ACTING)

1. `docs/flows/write/ui-integration/README.md` -- **READ THIS FIRST.** Write flow post-mortem. DRM blocker, callback patterns, no-middleware rules. The Erase flow uses similar PM3 commands (`hf mf wrbl` for standard erase, `hf mf cwipe` for Gen1a, `lf t55xx wipe` for T5577).

2. `docs/flows/auto-copy/ui-integration/README.md` -- Auto-Copy post-mortem. scan.so predicates, ConsoleMixin, middleware removal lessons.

3. `docs/flows/simulate/ui-integration/README.md` -- Simulate post-mortem (when written). SimFields widget, pixel-perfect UI, FB capture methodology.

4. `docs/flows/read/ui-integration/README.md` -- Read flow post-mortem. Scanner/Reader API, template.so rendering.

5. `docs/flows/scan/ui-integration/README.md` -- Scan flow post-mortem. Scanner API, ground truth rules.

6. `docs/UI_Mapping/13_erase_tag/README.md` -- **Exhaustive UI specification** for WipeTagActivity. 5 states, 2 erase types, PM3 commands, key bindings, callback methods.

7. `docs/Real_Hardware_Intel/trace_erase_flow_20260330.txt` -- **THE KEY TRACE.** Complete erase flow: Gen1a `hf mf cwipe`, standard `hf mf fchk` + `hf mf wrbl`, T5577 `lf t55xx wipe`. Shows exact PM3 command sequence with timeouts and responses.

8. `docs/Real_Hardware_Intel/trace_erase_gen1a_and_standard.txt` -- Gen1a vs standard card erase comparison trace.

9. Real device screenshots:
    - `docs/Real_Hardware_Intel/Screenshots/erase_tag_menu_1.png` -- Type selection (2 items)
    - `docs/Real_Hardware_Intel/Screenshots/erase_tag_menu_2.png` -- Scanning state
    - `docs/Real_Hardware_Intel/Screenshots/erase_tag_menu_3.png` -- "ChkDIC" key check
    - `docs/Real_Hardware_Intel/Screenshots/erase_tag_menu_4-5.png` -- "Erasing 0%" progress
    - `docs/Real_Hardware_Intel/Screenshots/erase_tag_menu_6.png` -- Result with Erase/Erase buttons
    - `docs/Real_Hardware_Intel/Screenshots/erase_tag_scanning.png` -- Scanning progress bar
    - `docs/Real_Hardware_Intel/Screenshots/erase_tag_unknown_error.png` -- Error state

10. `docs/DRM-KB.md` and `docs/DRM-Issue.md` -- DRM mechanism, correct cpuinfo serial.

11. `docs/HOW_TO_RUN_LIVE_TRACES.md` -- Deploy tracer to real device if new traces needed.

12. Decompiled binary:
    - `decompiled/activity_main_ghidra_raw.txt` -- WipeTagActivity methods
    - `docs/v1090_strings/activity_main_strings.txt` -- WipeTagActivity symbols (lines 20574-23169)

13. `src/screens/erase_tag.json` -- JSON UI state machine (5 states: type_select, erasing, success, failed, no_keys)

14. `tools/launcher_current.py` -- Launcher with PM3 mock, DRM fix, state dump.

## Critical lessons from completed flows (DO NOT REPEAT)

### 1. No Middleware
Our Python is a thin UI shell. The .so modules handle ALL RFID logic. WipeTagActivity builds PM3 commands and calls `executor.startPM3Task()`. It does NOT parse PM3 responses to make tag-specific decisions. In the Simulate flow, we found and removed `_isLFTag()` (hardcoded type set), `showReadToast()` keyword matching, and a `_saveSniffData()` no-op.

### 2. Tests are IMMUTABLE
NEVER modify test files without explicit user permission. Present findings and ASK. In Simulate, 7 scenarios had wrong SIM_INDEX — we got permission before fixing.

### 3. No Blind Sleeps
Poll output every 10-30s. Catch crashes in seconds, not minutes. Use `for i in $(seq 1 N); do sleep 30; check; done` pattern.

### 4. No Fixture Guessing
Fix must come from: real trace, decompiled .so, or PM3 source.

### 5. Visual Pixel Matching
Every UI element must match real device framebuffer captures exactly. Compare side-by-side after EVERY change. In Simulate, we iterated 5+ times on SimFields rendering, page indicator position, and box dimensions before matching. Do NOT declare "close enough" — iterate until exact.

### 6. Framebuffer Captures for Ground Truth
Deploy `/dev/fb1` capture on real device (240x240 RGB565, 500ms). NO Python patches during FB capture (crashes). Convert RGB565->PNG, deduplicate by pixel hash, name by scenario. This was the most valuable ground truth technique.

### 7. Content Verification in Tests
After navigating to an activity, verify the expected content appears (e.g., tag type name, field labels). In Simulate, 7 scenarios silently went to wrong types because tests only checked state counts. Added `content:` trigger checks.

### 8. Device-Wide Constants
- Background: #F8FCF8 (all activities)
- Title font: mononoki 16pt at x=105
- Page indicator: 9pt superscript, positioned via bbox
- Select item highlight: #E8ECE8
- Disabled button text: #808080

### 9. actstack Callback is `onActivity()` not `onActivityResult()`

### 10. PM3 Commands on Background Threads
`executor.startPM3Task(cmd, timeout)` — positional args only, no `callback=` kwarg. Run on `threading.Thread(daemon=True)`. Call result handler after thread completes.

### 11. Validation Max = Field Digit Limit
For decimal fields, effective max = min(doc_max, 10^digits - 1). Where .so passes raw values, max = digit limit only. Always verify defaults don't exceed the max.

## Erase flow architecture

### Activity stack transitions

```
MainActivity
    | (user selects "Erase Tag" from main menu)
WipeTagActivity (stack depth 2)
    |-- TYPE_SELECT: 2-item list
    |   1. Erase MF1/L1/L2/L3
    |   2. Erase T5577
    |   M1/PWR: finish (back to main)
    |   M2/OK: select type -> start erase
    |
    |-- ERASING: "Processing..." toast, buttons disabled
    |   MF1 Gen1a: hf mf cwipe (timeout=28888)
    |   MF1 Standard: hf 14a info -> hf mf cgetblk 0 -> hf mf fchk -> hf mf wrbl x N
    |   T5577: lf t55xx wipe [p 20206666]
    |   PWR: cancel erase
    |
    |-- SUCCESS: toast "Erase successful!", M1="Erase", M2="Erase"
    |-- FAILED: toast "Erase failed!", M1="Erase", M2="Erase"
    '-- NO_KEYS: toast "No valid keys...", M1="Erase", M2="Erase"
```

**Ground Truth**: `trace_erase_flow_20260330.txt`, `docs/UI_Mapping/13_erase_tag/README.md`

### WipeTagActivity state machine

| State | M1 | M2/OK | PWR |
|-------|----|----|-----|
| TYPE_SELECT | finish | startErase | finish |
| ERASING | -- | -- | cancel/finish |
| SUCCESS | startErase (re-erase) | startErase | finish |
| FAILED | startErase (retry) | startErase | finish |
| NO_KEYS | startErase (retry) | startErase | finish |

### Erase algorithms

**MF1 Gen1a (magic card):**
1. `hf 14a info` -- detect tag
2. `hf mf cgetblk 0` -- test Gen1a magic commands
3. If Gen1a: `hf mf cwipe` (timeout=28888) -- single command wipe
4. Ground truth: `trace_erase_flow_20260330.txt` line 10

**MF1 Standard (non-magic):**
1. `hf 14a info` -- detect tag
2. `hf mf cgetblk 0` -- test Gen1a (fails for standard)
3. `hf mf fchk {type} /tmp/.keys/mf_tmp_keys` -- find keys
4. If no keys: show "no valid keys" toast
5. `hf mf wrbl {block} A {key} 00000000000000000000000000000000` -- zero each block
6. Ground truth: `trace_erase_flow_20260330.txt` lines 21-248

**T5577:**
1. `lf t55xx wipe` or `lf t55xx wipe p 20206666` -- wipe with/without password
2. Ground truth: `trace_erase_flow_20260330.txt` line 249

### PM3 command reference

- `hf mf cwipe` (timeout=28888) -- Gen1a magic wipe. Response: success/fail
- `hf mf cgetblk 0` (timeout=5888) -- Test Gen1a magic commands
- `hf mf fchk {type} {keyfile}` (timeout=600000) -- Find sector keys
- `hf mf wrbl {block} {keytype} {key} {data}` (timeout=5888) -- Write single block with zeros
- `lf t55xx wipe` (timeout=5000) -- T5577 wipe without password
- `lf t55xx wipe p 20206666` (timeout=5000) -- T5577 wipe with DRM password

PM3 source: `https://github.com/iCopy-X-Community/icopyx-community-pm3`

## Test infrastructure

### 11 test scenarios (10 confirmed)

| Scenario | Type | Expected Result |
|----------|------|----------------|
| erase_mf1_gen1a_success | MF1 Gen1a | Erase successful |
| erase_mf1_gen1a_fail | MF1 Gen1a | Erase failed |
| erase_mf1_1k_success | MF1 1K standard | Erase successful |
| erase_mf1_4k_success | MF1 4K standard | Erase successful |
| erase_mf1_no_keys | MF1 standard | No valid keys toast |
| erase_mf1_no_tag | MF1 | No tag detected |
| erase_mf1_wrbl_fail | MF1 standard | Block write failure |
| erase_t5577_drm_success | T5577 with password | Erase successful |
| erase_t5577_no_password_success | T5577 no password | Erase successful |
| erase_t5577_fail | T5577 | Erase failed |

### Running tests

```bash
# Single test
TEST_TARGET=current SCENARIO=erase_mf1_gen1a_success FLOW=erase \
  bash tests/flows/erase/scenarios/erase_mf1_gen1a_success/erase_mf1_gen1a_success.sh

# Full parallel suite on remote
sshpass -p proxmark rsync -az --exclude='.git' --exclude='tests/flows/_results' --exclude='__pycache__' \
  /home/qx/icopy-x-reimpl/ qx@178.62.84.144:/home/qx/icopy-x-reimpl/
sshpass -p proxmark ssh -o ServerAliveInterval=30 qx@178.62.84.144 \
  'cd ~/icopy-x-reimpl && TEST_TARGET=current bash tests/flows/erase/test_erase_parallel.sh 9'

# Retrieve results
rm -rf tests/flows/_results/current/erase/
sshpass -p proxmark rsync -az qx@178.62.84.144:/home/qx/icopy-x-reimpl/tests/flows/_results/current/erase/ \
  tests/flows/_results/current/erase/
```

### Framework constants

```
PM3_DELAY=0.5
BOOT_TIMEOUT=600
ERASE_TRIGGER_WAIT=120
```

## Environment

- Branch: `feat/ui-integrating`
- Remote: `qx@178.62.84.144` (password: `proxmark`, 48 cores, max 9 workers safe)
- Real device: `sshpass -p 'fa' ssh -p 2222 root@localhost` (tunnel must be up)
- PM3 source: `https://github.com/iCopy-X-Community/icopyx-community-pm3`

## Working flows (don't break these)

- Volume: 7/7 PASS
- Backlight: 7/7 PASS
- Scan: 45/45 PASS
- Read: 99/99 PASS
- Write: 61/61 PASS
- Auto-Copy: 52/52 PASS
- Simulate: 28/28 PASS

## Ground Truth Rules (ABSOLUTE)

**Only use ground-truth resources:**
1. The original decompiled .so files: `decompiled/*.txt`
2. Real activity traces: `docs/Real_Hardware_Intel/trace_erase*.txt`
3. Real screenshots: `docs/Real_Hardware_Intel/Screenshots/erase_tag_*.png`
4. UI Mapping: `docs/UI_Mapping/13_erase_tag/README.md`
5. **NEVER deviate.** Never invent. Never guess. Never "try something".
6. **ALL work must derive from these ground truths.**
7. **EVERY action** must cite its ground-truth reference.
8. **Before writing code:** Does this come from ground truth? If not, don't.
9. **After writing code:** Audit -- does this come from ground truth? If not, undo.
10. **Use existing launcher tools** -- `tools/launcher_current.py` -- Do not roll your own infrastructure.
11. **When .so modules fail silently -- ALWAYS smoke-test DRM first.**
12. **Visual pixel matching** -- compare screenshots with FB captures side-by-side.

If no ground truth exists, ask the user before proceeding.

## Definition of done

1. All erase test scenarios PASS with correct toast validation
2. UI matches real device screenshots at every state
3. Type selection list renders correctly (2 items)
4. "Processing..." toast during erase operation
5. Success/fail/no-keys toasts with correct text
6. Erase/Erase buttons on result screens
7. No regressions on scan/read/write/auto-copy/simulate flows
8. Every change cites ground-truth source

## Approach

1. **Run the full erase suite** on remote with 9 workers
2. **Bring results back locally** (clean first!)
3. **Visually audit** key scenarios -- compare with real device captures
4. **Check for UI issues**: type selection, progress display, toast messages, button labels
5. **Identify failures** -- tests failing on trigger or state count
6. **Fix issues one at a time** with ground-truth citations
7. **Run all suites** to verify no regressions
