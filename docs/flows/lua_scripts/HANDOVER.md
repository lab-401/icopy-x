# LUA Scripts Flow — Handover for Next Agent

## Status

**Phase 1**: NOT STARTED — test scenarios need to be built and validated against `--target=original`.
**Phase 2**: NOT STARTED — blocked by Phase 1. However, a prototype JSON UI exists and was previously approved.

---

## What You Need to Do

### Phase 1: Build & Validate Test Scenarios

1. Read `docs/flows/lua_scripts/README.md` — the complete specification with logic tree, scenario definitions, and fixture designs.
2. Read `docs/HOW_TO_BUILD_FLOWS.md` — the Phase 1 methodology.
3. Build scenario scripts + fixtures for every leaf in the logic tree (~10 scenarios).
4. Run against `--target=original` until ALL pass.
5. Run >5 test runs on the remote QEMU server (`qx@178.62.84.144`, password: `proxmark`) to confirm stability.

### Phase 2: UI Integration

1. Read `docs/HOW_TO_INTEGRATE_A_FLOW.md` — the integration guide.
2. Run against `--target=current` and fix failures by modifying ONLY `src/lib/activity_main.py`.
3. **DO NOT modify scenarios.** If they fail on current, the bug is in your implementation.
4. **DO NOT write middleware.** The `.so` modules handle all PM3 logic.

---

## Key Resources

### Primary Specification
- `docs/flows/lua_scripts/README.md` — Logic tree, PM3 commands, screen specs, scenario table, fixture examples

### Ground Truth
- `docs/Real_Hardware_Intel/trace_misc_flows_20260330.txt` lines 41-55 — Real device LUA flow (cancel + retry + success)
- `docs/Real_Hardware_Intel/trace_misc_flows_session2_20260330.txt` lines 29-34 — Enhanced trace with full PM3 output
- `docs/UI_Mapping/15_lua_script/README.md` — 404-line UI spec with method inventory and key bindings
- FB screenshots: `docs/Real_Hardware_Intel/Screenshots/lua_script_*.png` (7 list screenshots), `lua_console_*.png` (10 console screenshots)
- `docs/Real_Hardware_Intel/Screenshots/v1090_captures/090-Lua.png` — Real device photo

### Existing Code
- `src/lib/activity_main.py` lines 1990-2150 — LUAScriptCMDActivity (file browser, mostly complete)
- `src/lib/activity_main.py` lines 733-828 — ConsolePrinterActivity (console display, missing PM3 task execution)

### Related Flows to Study
- `docs/flows/dump_files/README.md` — CardWalletActivity uses the same file-list browsing pattern. Study its scenario structure for the list/pagination/navigation scenarios.
- `docs/flows/sniff/ui-integration/README.md` — QEMU canvas tracing technique (Section 2.1). Critical when you need to match pixel positions or verify rendering against the original.

---

## Prototype JSON UI — Previously Approved

A prototype JSON UI definition was created and approved during earlier work. It is located at:

```
/home/qx/archive/ui/screens/lua_script.json
```

This defines two states:
- **`script_list`**: ListView with `page_size: 5`, no buttons, UP/DOWN/OK/PWR keys
- **`running`**: Console with auto-scroll, font zoom (M1/M2), scroll (UP/DOWN), PWR exits

This prototype was reviewed and approved by the user. Use it as a **solid base for Phase 2** — copy it to `src/screens/lua_script.json` and adapt as needed during integration. The key parameters (page_size, key bindings, console colors) match the ground truth from FB captures.

**NOTE**: The prototype uses `bg_color: "#000011"` and `text_color: "#00CCFF"` which are close to but may not exactly match the real device. Verify against `lua_console_*.png` FB captures during integration.

---

## Architecture Summary

```
Main Menu (pos 13)
    └─ GOTO:13
        └─ LUAScriptCMDActivity
            │ Title: "LUA Script X/Y"
            │ Content: ListView of .lua filenames (sorted, no extension)
            │ Source: /mnt/upan/luascripts/ (47 scripts)
            │ Buttons: NONE (invisible)
            │ Keys: UP/DOWN scroll, LEFT/RIGHT page, M2/OK run, PWR exit
            │
            └─ M2/OK → runScriptTask()
                │ cmd = "script run <filename>"
                │ bundle = {'cmd': cmd, 'title': 'LUA Script'}
                │
                └─ ConsolePrinterActivity
                    │ NO title bar, NO button bar
                    │ Full-screen black bg, monospace text
                    │ Executes: executor.startPM3Task(cmd, -1)
                    │ Displays: live polling of executor.CONTENT_OUT_IN__TXT_CACHE
                    │ Keys: UP/M2 zoom in, DOWN/M1 zoom out, LEFT/RIGHT scroll, PWR cancel+exit
                    │
                    └─ PWR or completion → finish() → back to script list
```

---

## Known Implementation Gap

**ConsolePrinterActivity does NOT execute the PM3 command from the bundle.**

Current code (`src/lib/activity_main.py` line 774-782) reads the executor cache on `onCreate` and starts polling, but never calls `executor.startPM3Task(bundle['cmd'], -1)`.

The trace proves the original `.so` executes the command:
```
PM3-TASK> script run hf_read timeout=-1
```

This is the critical gap for Phase 2. The command must be executed — likely via `startBGTask` to avoid blocking the UI thread.

---

## What This Flow Does NOT Have

Compared to other flows, LUA Scripts is simple:
- **No tag-specific logic** — no scan cache, no bundle routing, no type detection
- **No middleware needed** — the PM3 `script run` command handles everything
- **No save/delete** — scripts are read-only from `/mnt/upan/luascripts/`
- **No sub-activities beyond ConsolePrinterActivity** — no WarningWrite, no Simulation
- **Single PM3 command** — `script run <filename>` with `timeout=-1`

This makes it one of the simplest flows to implement. The main complexity is ensuring ConsolePrinterActivity correctly executes the PM3 task and displays live output.

---

## Test Infrastructure Pattern

Follow the pattern established by the Sniff flow:

```
tests/flows/lua_scripts/
├── includes/
│   └── lua_common.sh          # wait_for_ui_trigger, boot_qemu wrapper
├── scenarios/
│   ├── lua_list_display/
│   │   ├── lua_list_display.sh
│   │   └── fixture.py
│   ├── lua_run_success/
│   │   ├── lua_run_success.sh
│   │   └── fixture.py
│   └── ...
├── test_lua_parallel.sh        # Parallel runner (copy from test_sniff_parallel.sh)
└── test_lua.sh                 # Sequential runner (optional)
```

The `lua_common.sh` should source `tests/includes/common.sh` and define flow-specific helpers. Use `GOTO:13` to navigate to LUA Scripts.

---

## Lessons from Previous Flows

These were hard-won during the Sniff flow integration. Apply them here:

1. **QEMU canvas tracing** is your most powerful tool. Add a 100ms canvas poller to `launcher_original.py` to capture exact positions, colors, and creation/deletion timing.

2. **`parserTraceLen` does not exist** — always verify function names via QEMU attribute probe (`[a for a in dir(module)]`) before calling `.so` functions.

3. **The original `.so` never deletes canvas items** — stale items persist under new rendering. Don't rely on stale items for test gates; validate the RESULT state content directly.

4. **`startBGTask` vs direct call** — the original uses separate BG threads for PM3 tasks. Match the threading model to get correct state dump behavior.

5. **Empty states need negative assertions** — verify that content that should NOT be present is actually absent (e.g., no Decoding for empty traces).

6. **Test on the remote QEMU server** — local timing differs from remote. Always validate final results on `qx@178.62.84.144` with 3 workers.

7. **`scenario_states.json` is the reliable validation source**, not screenshots. Screenshots are visual confirmation only.

---

## Environment

- **Branch**: `feat/ui-integrating`
- **Remote QEMU**: `qx@178.62.84.144` (password: `proxmark`, use `sshpass`)
- **Script directory**: `/mnt/upan/luascripts/` (47 `.lua` files)
- **Main menu position**: 13 (`GOTO:13`)
- **Prototype JSON UI**: `/home/qx/archive/ui/screens/lua_script.json` (approved)
