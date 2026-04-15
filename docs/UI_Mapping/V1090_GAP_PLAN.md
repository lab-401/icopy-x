# v1.0.90 Feature Gap — Complete Plan

## The Problem

We built the UI map from v1.0.3 because it had no aes.so dependency issue.
v1.0.90 is the LATEST firmware and has significant additional features.
These must ALL be implemented in iCopy-X Open.

## New Features in v1.0.90 (not in v1.0.3)

### 1. Dump Files (Menu Item 2 — "Dump Files")
Entire new activity for browsing, viewing, and writing saved tag dumps.

**Screens:**
- Dump Files list, organised by card type groups (Mifare Classic, T5577, etc.)
- Per-type file list with pagination (e.g., "Dump Files 1/5")
- File detail view ("Tag Info") showing card type, frequency, UID, SAK, ATQA
- Disabled action support: "Simulate" greyed out when not supported for file type
- "Write" action triggers standard [WRITE] flow with dump file

**Flow:**
```
Main Menu → Dump Files → Type List → File List → File Info
                                                    ├── Simulate (if supported)
                                                    └── Write → [WRITE flow]
```

**New UI concepts:**
- Disabled/greyed-out action buttons (M1 does nothing when label is grey)
- File browser with type grouping

### 2. Erase Tag (Menu Page 3)
Wipe tags to factory state.

**Screens:**
- Erase type selection ("Erase MF1/L1/L2/L3", "Erase T5577")
- Scanning progress (reuses scan UI)
- Success/failure toasts

**Flow:**
```
Main Menu → Erase Tag → Type Select → [SCAN] → Erase progress → Success/Fail
```

### 3. Time Settings (Menu Page 3)
RTC date/time editor with cursor-based field selection.

**Screens:**
- Time display: YYYY-MM-DD / HH:MM:SS in boxed fields
- Edit mode: cursor (▲) tracks selected field, UP/DOWN changes value
- LEFT/RIGHT moves cursor between fields
- Save/Cancel buttons

**New UI concepts:**
- Cursor-based field editor (new content type needed in JSON schema)
- Boxed numeric fields with selection indicator

### 4. LUA Script (Menu Page 3)
Execute Lua scripts from /mnt/upan/luas/.

**Screens:**
- Script list with pagination ("LUA Script 1/10")
- Live PM3 console output (blue/cyan text on black background)

**Flow:**
```
Main Menu → LUA Script → Script List → OK → Live Console
```

### 5. Live PM3 Console (GLOBAL — accessible from any PM3 operation)
**THIS IS A MAJOR FEATURE.** Available during ANY [READ/WRITE/SIMULATE/SCAN] flow
by pressing RIGHT arrow.

**Behaviour:**
- Shows real-time PM3 serial output (scrolling console)
- Auto-scrolls to follow latest line
- UP/DOWN: manual scroll through console history
- M1: zoom out (decrease font size)
- M2: zoom in (increase font size)
- PWR: exit back to the activity that launched it
- Blue/cyan text on black background (terminal style)

**New UI concepts:**
- Console/terminal content type (monospace, auto-scroll, variable font size)
- Global overlay accessible from any PM3 operation
- This is NOT a separate activity — it's accessible via RIGHT arrow from within
  any running scan/read/write/simulate operation

### 6. Menu Structure Change
v1.0.90 has 3 pages (not 2):

**Page 1:** Auto Copy, Dump Files, Scan Tag, Read Tag, Sniff TRF
**Page 2:** Simulation, PC-Mode, Backlight, Diagnosis, Volume
**Page 3:** About, Erase Tag, Time Settings, LUA Script

(vs v1.0.3: Page 1 had Auto Copy, Scan, Read, Sniff, Simulation. Page 2 had PC-Mode, Backlight, Diagnosis, Volume, About)

## Plan to Fill the Gap

### TWO PARALLEL TRACKS (both required for 100% coverage)

**Track 1: QEMU UI Navigation** — Run v1.0.90 under QEMU, navigate every screen, capture every state with rapid-fire screenshots. This gives us the visual reference.

**Track 2: Binary Reverse Engineering** — Extract ALL UI logic, screen text, string resources, function signatures, widget types, and flow connections from the v1.0.90 .so modules (Ghidra decompilation + QEMU function calls). This is the same approach that produced the 56 transliterated modules from v1.0.3, but now targeting the NEW modules in v1.0.90.

Track 2 is critical because:
- The photos will miss details (edge cases, error states, conditional text)
- The .so modules contain the EXACT text strings, layout parameters, and flow logic
- It tells us HOW to connect what we see in the UI (which middleware functions are called, with what parameters)
- It will reveal NEW widgets/content types we haven't seen in the photos

**NOTE: Watch for new UI widgets, content types, or rendering patterns in the v1.0.90 binaries that don't exist in v1.0.3. Document any discoveries immediately.**

### Phase A: Run v1.0.90 under QEMU

1. Check if v1.0.90 binary exists on the device image
2. The only blocker was aes.so — our transliterated aesutils.py should work
3. Inject aesutils.py into the PYTHONPATH (same approach as before)
4. Run v1.0.90 with patched_launch.py adapted for the new binary
5. Use the same rapid-fire capture system to screenshot every screen

### Phase A2: Reverse Engineer v1.0.90 Binaries

Parallel to QEMU navigation. For EACH new .so module in v1.0.90:

1. **Identify new/changed modules** — diff the v1.0.90 lib/ against v1.0.3 lib/
   - New modules (dump browser, erase, time settings, lua executor, console)
   - Changed modules (activity_main.so — new menu items, new activities)

2. **For each new module:**
   - Load under QEMU, enumerate all exported functions
   - Call each function with test inputs, capture outputs
   - Extract string constants (UI text, error messages, labels)
   - Map function call graphs (which calls which)
   - Identify widget types used (list, template, console, time_editor, etc.)

3. **For activity_main.so (changed):**
   - Extract the new activity registrations (Dump Files, Erase, Time, LUA)
   - Map key handlers per activity (which keys do what in which state)
   - Extract the Live Console implementation (how it taps PM3 output)
   - Document disabled button logic (when is Simulate greyed out?)

4. **Transliterate new modules** into readable Python
   - Same methodology as Phase 1: decompile → understand → translate → verify
   - The output is additional .py files in lib_transliterated/

5. **Document ALL new UI patterns** — any widget, layout, or interaction
   not seen in v1.0.3 gets documented with exact parameters

### Phase B: Build missing JSON screen definitions

From the real device photos + QEMU captures:

1. **dump_files.json** — Multi-state: type_list → file_list → file_info
2. **erase_tag.json** — Multi-state: type_select → scanning → result
3. **time_settings.json** — Multi-state: display → edit (new cursor content type)
4. **lua_script.json** — Multi-state: script_list → console
5. **pm3_console.json** — Global overlay (new content type: terminal)

### Phase C: Extend JSON schema

New content types needed:

1. **`console`** — Terminal-style scrolling text
   ```json
   {
     "type": "console",
     "lines": [],
     "auto_scroll": true,
     "font_size": 10,
     "bg_color": "#000011",
     "text_color": "#00CCFF"
   }
   ```

2. **`time_editor`** — Boxed fields with cursor
   ```json
   {
     "type": "time_editor",
     "fields": ["year","month","day","hour","minute","second"],
     "values": [1970, 2, 12, 3, 38, 42],
     "cursor": 0
   }
   ```

3. **Disabled button support** — Extend button spec:
   ```json
   {
     "left": {"text": "Simulate", "enabled": false},
     "right": "Write"
   }
   ```

### Phase D: Update main menu

Change from 2-page (v1.0.3) to 3-page (v1.0.90) menu structure.
Add new items: Dump Files, Erase Tag, Time Settings, LUA Script.

### Phase E: Implement middleware

1. **Erase middleware** — transliterate from v1.0.90 .so modules
   - `lfwipe.py` for T5577 erase
   - `hfmfwipe.py` for MIFARE erase (write all zeros + default keys)

2. **File browser middleware** — `appfiles.get_card_list()` already exists

3. **Time settings middleware** — `hmi_driver.givemetime()` / `hmi_driver.settime()`

4. **LUA executor middleware** — subprocess call to PM3 with `script run <name>`

5. **PM3 console middleware** — tap into executor's TCP stream for real-time output

### Phase F: Test everything

Run the full test suite on v1.0.90 under QEMU with all new activities.

## Priority

This is HIGH priority — these features are expected by users.
The Live PM3 Console in particular is a power-user feature that
differentiates iCopy-X from other RFID tools.

## Estimated Scope

- 5 new JSON screen definitions
- 2 new content types in the renderer (console, time_editor)
- 1 new button feature (disabled state)
- 4 new middleware modules
- ~15 new screens to render
- Update main menu from 10 to 14 items (3 pages)
