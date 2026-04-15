# iCopy-X Open Source UI Framework Replacement Plan

## Context

The iCopy-X RFID copier runs 62 Cython-compiled .so modules on ARM Linux (240x240 display). We have exhaustive documentation (decompiled source, UI specs, string tables, 337+ QEMU flow tests). The goal is to replace the UI framework with pure Python while keeping the original middleware .so modules for RFID logic.

A prototype UI exists at `/home/qx/archive/ui/` (built against v1.0.3). It serves as reference only — we build clean from spec.

## Architecture: Declarative JSON UI + Flat Module Layout

### Core Architecture: JSON-Driven Screens

Instead of hardcoding UI in activity classes, screens are **declared in JSON** and consumed by a **renderer engine**. This is defined in `docs/UI_JSON_SCHEMA.md` and prototyped in `/home/qx/archive/ui/screens/` (11 JSON files).

**How it works:**
1. Each activity's screens are defined in a JSON file with content type, buttons, keys, and state machine transitions
2. A single **renderer engine** reads JSON and draws to tkinter Canvas (dispatches by `content.type`: list, template, progress, text, input, empty)
3. A **state machine engine** manages transitions between states (`on_result.found==true` → `found` state)
4. Activities become **thin middleware bridges** — they load JSON, call .so middleware on `run:` actions, feed results back to the state machine
5. **PWR always exits** — enforced by renderer, stripped from all JSON key bindings
6. **Plugin contract** — plugins use the same JSON schema, renderer enforces constraints

**Content types (6):**
- `list` — Scrollable items with styles: menu (icons), radio, checklist, plain
- `template` — Tag info with header/subheader/field rows, `{variable}` placeholders
- `progress` — Progress bar + message (fixed at y=100)
- `text` — Multi-line text (About, warnings)
- `input` — Hex/text character entry
- `empty` — Blank (toast-only screens)

### Flat Module Layout

**Critical constraint:** The original .so modules use bare imports (`import actbase`, `import widget`). The kept middleware modules (e.g., `executor.so` imports `hmi_driver`) require our replacements to be importable as flat module names on `sys.path`.

```
src/lib/              # Flat layout — each file replaces one .so module
├── _constants.py         # PRIVATE: colors, layout, key constants
├── _renderer.py          # NEW: JSON screen → Canvas renderer engine
├── _state_machine.py     # NEW: state machine engine for multi-state flows
├── _variable_resolver.py # NEW: {placeholder} resolution from middleware results
├── actbase.py            # Replaces actbase.so (BaseActivity, uses renderer)
├── actmain.py            # Replaces actmain.so (MainActivity + SleepMode + WarningDiskFull)
├── actstack.py           # Replaces actstack.so (Activity, LifeCycle, stack mgmt)
├── activity_main.py      # Replaces activity_main.so (~30 activity classes, JSON-driven)
├── activity_tools.py     # Replaces activity_tools.so (DiagnosisActivity + 6 test activities)
├── activity_update.py    # Replaces activity_update.so (UpdateActivity)
├── batteryui.py          # Replaces batteryui.so (BatteryBar with polling)
├── hmi_driver.py         # Replaces hmi_driver.so (serial driver)
├── images.py             # Replaces images.so (icon loading)
├── keymap.py             # Replaces keymap.so (KeyEvent + key constants)
├── resources.py          # Replaces resources.so (StringEN, DrawParEN, get_str, get_font)
└── widget.py             # Replaces widget.so (ListView, ProgressBar, Toast, etc.)

src/screens/          # JSON screen definitions (one per activity/flow)
├── main_menu.json        # 14 items, 3 pages, icons
├── scan_tag.json         # State machine: idle→scanning→found/not_found/multi/wrong_type
├── read_tag.json         # State machine: type_list→scanning→reading→result/fail/warning
├── write_tag.json        # State machine: confirm→writing→verify→done/fail
├── autocopy.json         # Pipeline: scan→read→swap_prompt→write→verify→done
├── sniff.json            # 5 protocols, step-by-step
├── simulation.json       # Type select→UID input→simulating
├── erase_tag.json        # Scan→confirm→erasing→done
├── backlight.json        # Radio list (Low/Mid/High)
├── volume.json           # Radio list (Off/Low/Mid/High)
├── diagnosis.json        # Checklist + sub-test screens
├── about.json            # Version info text
├── time_settings.json    # 6-field cursor editor
├── lua_script.json       # File list→console output
├── pc_mode.json          # USB bridge instructions
├── dump_files.json       # File browser→detail→write/sim
├── warning_write.json    # Pre-write confirmation
├── warning_m1.json       # Missing keys options (4 pages)
└── console_printer.json  # Monospace scrolling output
```

### How Activities Use JSON

Activities become thin middleware bridges:
```
JSON defines:  WHAT the screen looks like + WHEN to transition
Renderer does: HOW to draw it on canvas
Activity does: HOW to call middleware + feeds results back to state machine
```

Example — ScanActivity is ~30 lines of Python (not 1000+):
- Loads `scan_tag.json` state machine
- On `run:scan.scan_all_synchronous` action → calls real scan.so
- Feeds scan result back → state machine transitions to found/not_found
- Renderer draws the new state's screen definition

**Import resolution:** `PYTHONPATH=src/lib:...:orig_so/lib` — Python finds our `.py` before the `.so` for replaced modules. Middleware `.so` modules (scan, read, write, executor, etc.) load from `orig_so/lib` as-is.

## What We Replace vs Keep

| Replace (Python) | Keep (original .so) |
|---|---|
| actbase, actstack, widget, batteryui | executor, scan, read, write, sniff |
| hmi_driver, keymap, resources, images | tagtypes, container, mifare, template |
| actmain, activity_main, activity_tools | hfmfread, hfmfwrite, hfmfkeys, hfmfuread |
| activity_update | lft55xx, lfread, lfwrite, hficlass, etc. |
| | appfiles, commons, audio, config, debug |

## Testing Strategy

### New pytest Suite: `tests/ui/`

```
tests/ui/
├── conftest.py                    # --target option, MockCanvas, fixtures
├── renderer/
│   ├── test_renderer.py           # 25 tests — renders each content type, validates canvas items
│   ├── test_state_machine.py      # 20 tests — transitions, on_enter, on_result conditions
│   ├── test_variable_resolver.py  # 10 tests — {placeholder} resolution, priority
│   └── test_json_validation.py    # 15 tests — schema lint, id uniqueness, target existence
├── widgets/
│   ├── test_listview.py           # 35 tests
│   ├── test_progress_bar.py       # 18 tests
│   ├── test_toast.py              # 15 tests
│   ├── test_battery_bar.py        # 16 tests
│   ├── test_checked_listview.py   # 10 tests
│   ├── test_page_indicator.py     # 8 tests
│   ├── test_console_view.py       # 8 tests
│   └── test_input_methods.py      # 10 tests
├── framework/
│   ├── test_base_activity.py      # 25 tests
│   ├── test_activity_stack.py     # 20 tests
│   └── test_key_dispatch.py       # 12 tests
├── activities/
│   ├── test_main_menu.py          # 30 tests
│   ├── test_scan_tag.py           # 35 tests
│   ├── test_read_tag.py           # 50 tests
│   ├── test_write_tag.py          # 30 tests
│   ├── test_auto_copy.py          # 45 tests
│   ├── test_sniff.py              # 25 tests
│   ├── test_simulation.py         # 35 tests
│   ├── test_erase_tag.py          # 35 tests
│   ├── test_backlight.py          # 12 tests
│   ├── test_volume.py             # 12 tests
│   ├── test_diagnosis.py          # 30 tests
│   ├── test_about.py              # 18 tests
│   ├── test_time_settings.py      # 12 tests
│   ├── test_lua_script.py         # 12 tests
│   ├── test_pc_mode.py            # 15 tests
│   ├── test_dump_files.py         # 20 tests
│   └── test_hidden_activities.py  # 25 tests
└── integration/
    ├── test_navigation.py         # 20 tests
    ├── test_pwr_always_exits.py   # 37 tests (parametrized over all activities)
    ├── test_screen_rendering.py   # 15 tests
    └── test_state_dump_parity.py  # 10 tests
```

**Estimated total: ~790 pytest tests** (720 + 70 renderer/schema tests)

### --target System

```python
# conftest.py
def pytest_addoption(parser):
    parser.addoption("--target", default="current", choices=["current", "original"])
```

- `--target=current` (default): Tests our Python UI directly. Fast, no QEMU.
- `--target=original`: Tests real .so via QEMU bridge. Slow, validates parity.

### MockCanvas (core test fixture)

In-memory canvas tracking all create_text/create_rectangle/delete/itemconfig calls. Same API as tkinter.Canvas. Allows testing without X11/Xvfb.

### Existing Flow Tests (337+ scenarios)

Immutable. Must still pass after UI swap. Validated via QEMU with `src/lib` on PYTHONPATH before `orig_so/lib`.

---

## Execution Plan

### Phase 1: Project Setup & Constants (3 tasks)

| ID | Task | Output | Sources |
|----|------|--------|---------|
| P1-1 | Create directory structure + pytest config + conftest.py with MockCanvas | `src/lib/`, `tests/ui/conftest.py`, `conftest.py` | UI_SPEC.md for canvas dimensions |
| P1-2 | `_constants.py` — ALL colors, layout dims, key constants | `src/lib/_constants.py` | UI_SPEC.md, decompiled/actbase.c |
| P1-3 | `resources.py` — StringEN, DrawParEN, get_str(), get_font(), get_xy() | `src/lib/resources.py` | tools/qemu_shims/resources.py, resources_ghidra_raw.txt |

**Verification:** `resources.get_str('read_tag')` returns `"Read Tag"`. All color hex values match UI_SPEC.md.

### Phase 2: Renderer Engine & Widget Library (11 tasks)

#### Renderer Engine (3 tasks — the architectural core)

| ID | Task | Deps | Complexity | Description |
|----|------|------|------------|-------------|
| P2-R1 | **_renderer.py** — JSON screen → Canvas renderer | P1-2 | HIGH | Single module that dispatches by `content.type` (list, template, progress, text, input, empty). Draws title bar (#7C829A), content area, button bar. ~500 lines. |
| P2-R2 | **_state_machine.py** — Multi-state flow engine | P1-2 | MEDIUM | Manages `initial_state`, `on_enter` actions, `transitions` (on_result, on_error, on_timeout). Resolves `set_state:`, `push:`, `finish`, `run:` actions. |
| P2-R3 | **_variable_resolver.py** — `{placeholder}` resolution | P1-3 | LOW | Resolves `{uid}`, `{tag_type_name}`, `{scan_progress}` etc from middleware result dicts. Priority: middleware result → activity state → global device state. |

#### Widget Library (8 tasks)

| ID | Task | Deps | Complexity | Key Specs |
|----|------|------|------------|-----------|
| P2-1 | **ListView** — items, selection (#EEEEEE bg, black text), pagination (4 items/page), icons, callbacks, BigTextListView | P1-2 | HIGH | Item height: 40px, text x=19 (no icon) / x=50 (icon), content y=40-200 |
| P2-2 | **ProgressBar** — fill (#1C6AEB), bg (#eeeeee), message, **FIXED position y=100** | P1-2 | LOW | Bar at (20,100)→(220,120). Message at (120,98) anchor='s'. Position is FIXED — never moves with text content. |
| P2-3 | **Toast** — MASK_CENTER, MASK_FULL, MASK_TOP_CENTER, auto-dismiss, icon | P1-2 | MEDIUM | Overlay on canvas, timer thread, multiline text |
| P2-4 | **BatteryBar** — external rect (208,15)-(230,27), fill colors (green>50, yellow>20, red<20), charging icon | P1-2 | MEDIUM | Contact pip, level-proportional fill width |
| P2-5 | **CheckedListView** — extends ListView, check marks, getCheckPosition() | P2-1 | LOW | Green checkmark at x=5 |
| P2-6 | **PageIndicator** — up/down arrows, page position in title bar | P1-2 | LOW | Arrows shown based on current page |
| P2-7 | **ConsoleView** — monospace scrolling text, auto-scroll | P1-2 | MEDIUM | mononoki 8px, white on #222222 |
| P2-8 | **InputMethods** — hex/text per-character focus, roll selection | P1-2 | MEDIUM | bakcolor=#ffffff, datacolor=#000000 |

**Verification:** Each widget renders to MockCanvas. Coordinates/colors match UI_SPEC.md exactly. Screenshot comparison for ListView and ProgressBar.

### Phase 3: Framework (5 tasks)

| ID | Task | Deps | Complexity | Key API |
|----|------|------|------------|---------|
| P3-1 | **actstack.py** — Activity class, LifeCycle (RLock-protected states), start_activity(), finish_activity(), activity stack list | P2-1 | HIGH | New Canvas per activity, lifecycle callbacks |
| P3-2 | **keymap.py** — KeyEvent singleton, bind/unbind, onKey dispatch, PWR → finish_activity() | P1-2 | LOW | `key` module-level singleton, _compat() for HMI codes |
| P3-3 | **actbase.py** — BaseActivity(Activity), setTitle (#7C829A bg), setLeftButton (15,228), setRightButton (225,228), busy state, battery bar | P3-1, P2-4 | HIGH | Thread-safe _setbusy(), canvas tag management |
| P3-4 | **hmi_driver.py** — Serial /dev/ttyS0 @57600, key events, battery poll, backlight, PM3 control | P3-2 | HIGH | executor.so imports this — must be API-compatible |
| P3-5 | **images.py** — Icon loading from res/img/, recolor for selection state | P1-2 | LOW | load(name, rgb=None), PhotoImage cache |

**Verification:** Framework boots, displays title bar + battery + buttons, accepts key events, pushes/pops activities. PWR always exits.

### Phase 4: JSON Screen Definitions + Activities (25 tasks)

Each activity has TWO deliverables:
1. **JSON screen definition** in `src/screens/` — declares all states, screens, keys, transitions
2. **Activity Python class** in `src/lib/` — thin middleware bridge (~30-100 lines each, NOT 1000+)

The JSON defines the UI. The Python handles middleware calls. Activities are dramatically simpler than the original .so implementations because rendering is handled by the engine.

Ordered by complexity tier.

#### Tier 1: Simple Settings (3 tasks)

| ID | Activity | States | Deps | Sources |
|----|----------|--------|------|---------|
| A-1 | BacklightActivity + `backlight.json` | 2 (list, toast) | P3-3, P2-5, P2-R1 | docs/UI_Mapping/08_backlight/ |
| A-2 | VolumeActivity + `volume.json` | 2 (list, toast) | P3-3, P2-5, P2-R1 | docs/UI_Mapping/10_volume/ |
| A-3 | SleepModeActivity | 2 | P3-3 | decompiled/SUMMARY.md |

**Existing tests:** 7 backlight + 7 volume scenarios (all passing)

#### Tier 2: Simple Display (2 tasks)

| ID | Activity | States | Deps |
|----|----------|--------|------|
| A-4 | AboutActivity | 2 (info list, update prompt) | P3-3, P2-1 |
| A-5 | WarningDiskFullActivity | 1 | P3-3 |

#### Tier 3: Main Menu & Medium (3 tasks)

| ID | Activity | States | Deps |
|----|----------|--------|------|
| A-6 | **MainActivity** | 4 (14 items, 3 pages, icons) | P3-3, P2-1, P2-6, P3-5 |
| A-7 | DiagnosisActivity + 6 test sub-activities | 12 | P3-3, P2-5 |
| A-8 | PCModeActivity | 4 | P3-3 |

**Existing tests:** 4 diagnosis scenarios (all passing)

#### Tier 4: Medium+ (3 tasks)

| ID | Activity | States | Deps |
|----|----------|--------|------|
| A-9 | TimeSyncActivity | 3 (editor cursor) | P3-3, P2-8 |
| A-10 | ConsolePrinterActivity | 2 (scrolling output) | P3-3, P2-7 |
| A-11 | LUAScriptCMDActivity | 3 (file list + console) | A-10 |

#### Tier 5: Complex RFID Flows (4 tasks)

| ID | Activity | States | Deps | Existing Tests |
|----|----------|--------|------|----------------|
| A-12 | **ScanActivity** | 6 (idle, scanning, found, not_found, wrong_type, multi) | P3-3, P2-2, P2-3 | 45 scenarios |
| A-13 | ReadListActivity | 5 (type list, navigation) | P3-3, P2-1 | — |
| A-14 | **WipeTagActivity** (Erase) | 12 (scan + erase + confirm) | A-12 | 10 scenarios |
| A-15 | SniffActivity + sub-activities | 6 | P3-3, P2-1 | 16 scenarios |

#### Tier 6: Very Complex (4 tasks)

| ID | Activity | States | Deps | Existing Tests |
|----|----------|--------|------|----------------|
| A-16 | **ReadActivity** | 13 (key recovery, progress, console, warnings) | A-12, A-10 | 99 scenarios |
| A-17 | **WriteActivity** | 8 (write + verify + rewrite) | P3-3, P2-2 | 61 scenarios |
| A-18 | WarningWriteActivity | 2 | P3-3 | — |
| A-19 | WarningM1Activity | 4 pages | P3-3, P2-1 | — |

#### Tier 7: Pipeline (2 tasks)

| ID | Activity | States | Deps | Existing Tests |
|----|----------|--------|------|----------------|
| A-20 | **AutoCopyActivity** | 16 (scan→read→write pipeline) | A-12, A-16, A-17 | 54 scenarios |
| A-21 | SimulationActivity + trace | 14 | P3-3, P2-8, P2-1 | 30 scenarios |

#### Tier 8: Specialized (4 tasks)

| ID | Activity | States | Deps |
|----|----------|--------|------|
| A-22 | CardWalletActivity (Dump Files) | 5 | A-13 |
| A-23 | InputMethodsActivity (KeyEnterM1) | 3 | P3-3, P2-8 |
| A-24 | UpdateActivity / OTAActivity | 4 | P3-3, P2-2 |
| A-25 | Hidden activities (Snake, Wearable, AutoExceptCatch, factory tests) | ~20 | Various |

### Phase 5: Integration & Validation (5 tasks)

| ID | Task | Description |
|----|------|-------------|
| I-1 | Full-stack boot test | app.py → main menu → navigate all 14 items |
| I-2 | QEMU parity regression | Run 337+ existing flow tests with src/lib on PYTHONPATH |
| I-3 | Screenshot regression | Render every screen, compare to docs/screenshots/orig_*.png |
| I-4 | State dump parity | Our state extraction matches QEMU _dump_state() format exactly |
| I-5 | Fix regressions | Iterate until ALL tests pass |

### Phase 6: IPK Build & Deploy (4 tasks)

| ID | Task | Description |
|----|------|-------------|
| B-1 | Update tools/build_ipk.py | Include src/lib/*.py, exclude replaced .so files |
| B-2 | Update .github/workflows/build-ipk.yml | Add pytest stage, flow test stage |
| B-3 | QEMU end-to-end IPK test | Install IPK, boot, navigate, validate |
| B-4 | Real hardware preparation | Document test procedure, prepare test IPK |

---

## Multi-Agent Workflow Per Task

Every task (P1-1, P2-1, A-1, etc.) follows this 4-agent pipeline:

```
Agent 1 (Implementer):
  - Reads decompiled .so + UI_SPEC.md + UI_Mapping docs
  - Writes Python module matching spec exactly
  - NEVER guesses — ALL info is in the docs
  - NO logic in UI — .so modules ARE the logic

Agent 2 (Clean-Room Reviewer):
  - Reads ONLY the written code first
  - Builds understanding of what the code does
  - THEN reads the spec
  - Compares: does code match spec? All states? All branches?
  - If mismatch → iterate with Agent 1

Agent 3 (Test Writer):
  - Writes pytest tests for every public method/state
  - Enumerates ALL states (happy + fail + edge)
  - Uses MockCanvas, MockHMI, MockExecutor fixtures
  - Reuses existing flow test fixture data where applicable
  - Tests organized in tests/ui/ mirroring src/lib/

Agent 4 (Test Runner):
  - Runs all tests: pytest tests/ui/
  - If failures → all agents iterate
  - Records pass/fail
```

## Dependency Graph (Critical Path)

```
P1-1,P1-2,P1-3 (Setup + Constants + Resources)
    ↓
P2-R1 (Renderer) ← P2-1 (ListView), P2-2 (ProgressBar), P2-3 (Toast), P2-4 (Battery)
P2-R2 (StateMachine) ← P2-R3 (VarResolver)
    ↓
P2-1 (ListView) → P2-5 (CheckedListView)
P2-2 (ProgressBar)    ↘
P2-3 (Toast)           → P3-1 (actstack) → P3-3 (actbase) → JSON Screens + Activities
P2-4 (BatteryBar)     ↗                                    ↓
P2-6 (PageIndicator)                                    A-1..A-8 (simple: Backlight, Volume, About...)
P2-7 (ConsoleView)                                         ↓
P2-8 (InputMethods)                                     A-6 (MainActivity)
    ↓                                                      ↓
P3-2 (keymap)                                          A-12 (Scan) → A-14 (Erase)
P3-4 (hmi_driver)                                         ↓
P3-5 (images)                                          A-16 (Read) → A-17 (Write) → A-20 (AutoCopy)
                                                                                       ↓
                                                                                   I-1..I-5 → B-1..B-4
```

**The Renderer (P2-R1) is on the critical path** — it must be built and validated early because all activities depend on it to render their JSON screen definitions.

## Existing JSON Screen References

11 prototype JSON screens exist at `/home/qx/archive/ui/screens/` (built against v1.0.3, need updating for v1.0.90):
- `main_menu.json` — 14 items with icons and push actions
- `scan_tag.json` — State machine: scanning→found/not_found/multi_tags
- `settings.json` — Multi-screen: volume, backlight, diagnosis
- `autocopy.json`, `simulation.json`, `sniff.json`, `erase_tag.json`
- `dump_files.json`, `lua_script.json`, `time_settings.json`, `watch_copy.json`

The JSON schema spec is at `docs/UI_JSON_SCHEMA.md` (409 lines). It defines content types, toast overlay, button bar, key bindings, state machine transitions, variable resolution, and plugin contract.

## Key Ground-Truth Sources Per Phase

| Phase | Primary Source | Location |
|-------|---------------|----------|
| JSON Schema | UI_JSON_SCHEMA.md | docs/UI_JSON_SCHEMA.md |
| JSON Prototypes | Existing screen defs (v1.0.3, ref only) | /home/qx/archive/ui/screens/*.json |
| Renderer | JSON schema + widget API | docs/UI_JSON_SCHEMA.md + decompiled/widget_ghidra_raw.txt |
| Constants | UI_SPEC.md | docs/UI_SPEC.md |
| Resources | QEMU shim (working) | tools/qemu_shims/resources.py |
| Widgets | widget.so decompilation | decompiled/widget_ghidra_raw.txt |
| Framework | actbase.c, actstack.c | decompiled/actbase.c, actstack.c |
| Activities | activity_main decompilation + UI mapping | decompiled/ + docs/UI_Mapping/ |
| HMI | hmi_driver.c + real device traces | decompiled/hmi_driver.c + docs/traces/ |
| String tables | v1090_strings/ | docs/v1090_strings/ |

## Key Rules for All Agents

1. **NEVER guess or invent** — ALL information is in the documentation
2. **NO logic in tests or UI** — .so modules handle ALL decisions
3. **ALL states must be covered** — happy path, fail states, edge cases, every permutation
4. **Fixtures are DATA ONLY** — no decisions, no branching, no function calls
5. **ProgressBar at FIXED y=100** — never moves with text content (original bug in prototype)
6. **PWR is ALWAYS exit** — framework-level intercept, no screen can override
7. **Drop-in replacement** — pixel-perfect match to original
8. **Flat module names** — `import actbase`, not `from src.framework import actbase`
