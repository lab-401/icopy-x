# UpdateActivity — Exhaustive UI Mapping

**Source module:** `activity_update.so` (separate Cython module)
**Decompiled reference:** `decompiled/activity_update_ghidra_raw.txt` (17,057 lines)
**Class:** `UpdateActivity(BaseActivity)`
**Launched from:** `AboutActivity.checkUpdate()` via `actstack.start_activity(UpdateActivity, ipk_path)`
**Install engine:** `main/install.so` (bundled inside IPK package)
**Install engine decompiled:** `decompiled/install_ghidra_raw.txt` (12,572 lines)
**Install engine strings:** `docs/v1090_strings/install_strings.txt`

---

## 1. Activity Identity

### Module Audit (V1090_MODULE_AUDIT.txt lines 2912-2961)

```
MODULE: activity_update

class UpdateActivity(BaseActivity):
    __init__(self, canvas: tkinter.Canvas)
    search(path, name)              — static method, finds .ipk files
    checkPkg(self, file)            — validates ZIP structure
    checkVer(self, path)            — DRM serial number check
    unpkg(self, file)               — extracts IPK to temp dir
    install(self, file)             — orchestrates install pipeline
    onInstall(self, name, progress) — progress callback from install.so
    onKeyEvent(self, event)         — key handler
    onCreate(self)                  — lifecycle: setup UI
    onData(self, bundle)            — receives data from parent
    onResume(self)                  — lifecycle: resume
    onPause(self)                   — lifecycle: pause
    onDestroy(self)                 — lifecycle: cleanup
    path_import(file)               — loads .so/.py module from path
    showErr(self, code)             — displays error toast
    showTips(self, enable, text)    — shows/hides tip text
    showBtns(self, enable)          — shows/hides buttons
    finish(self, bundle)            — exits activity

IMPORTS: actbase, gadget_linux, importlib, keymap, os, resources,
         shutil, sys, time, tkinter, version, widget, zipfile
```

### Decompiled Functions (activity_update_ghidra_raw.txt)

| Function | Address | Lines |
|----------|---------|-------|
| `__init__` | 0x0001e798 | 12507-13020 |
| `onCreate` | 0x00018824 | 7123-7578 |
| `onKeyEvent` | 0x0001bb48 | 10004-10550 |
| `onData` | 0x0001a240 | 8596-9080 |
| `onInstall` | 0x000173c0 | 5930-6171 |
| `search` | 0x00018fc8 | 7580-8457 |
| `checkPkg` | 0x0001d7b8 | 11602-12505 |
| `checkVer` | 0x0001c4e4 | 10552-11600 |
| `unpkg` | 0x0002056c | 14106-14811 |
| `install` | 0x000212b0 | 14813-16300 |
| `path_import` | 0x0001f10c | 13022-14104 |
| `showErr` | 0x0001aabc | 9082-9617 |
| `showBtns` | 0x0001b4a0 | 9619-10002 |
| `showTips` | 0x00022bf0 | 16302-17037 |
| `install.callback` | 0x00017c48 | 6478-6696 (closure inside install) |
| `onKeyEvent.lambda1` | 0x0001844c | 6910-7121 |
| `onData.lambda` | 0x00018074 | 6698-6908 |

---

## 2. Screen Layout

### STATE: READY (initial)

```
+--------------------------------------+
|  Title Bar (0,0)-(240,40)            |
|  "Update"                            |
|  Font: Consolas 18, white on #788098 |
+--------------------------------------+
|  Content Area (0,40)-(240,190)       |
|                                      |
|  "Press 'Start' to install"          |
|  (blue text, Consolas 15 font)       |
|  (resources key: start_install_tips) |
|                                      |
+--------------------------------------+
|  Button Bar (0,215)-(240,240)        |
|  M1 = "Cancel"    M2 = "Start"      |
|  (white text on grey bar)            |
+--------------------------------------+
```

**Title citation:** resources.py StringEN.title: `'update': 'Update'`
**Content citation:** resources.py StringEN.tipsmsg: `'start_install_tips': "Press 'Start' to install"`
**M1 citation:** Framebuffer capture `fb_0107.png` (2026-04-10): M1 shows "Cancel"
**M2 citation:** Framebuffer capture `fb_0107.png`: M2 shows "Start"; resources.py: `'start': 'Start'`
**Font citation:** activity_update.so string table: `STR@0x00024414: Consolas 15`

### STATE: INSTALLING (after Start pressed)

```
+--------------------------------------+
|  Title Bar (0,0)-(240,40)            |
|  "Update"                            |
+--------------------------------------+
|  Content Area (0,40)-(240,190)       |
|                                      |
|  "Press 'Start' to install"          |
|  (text remains, unchanged)           |
|                                      |
+--------------------------------------+
|  Progress Area (0,190)-(240,230)     |
|                                      |
|  "{message}"          (Consolas 15)  |
|  [████████░░░░░░░░░░░] (ProgressBar) |
|  x=20..219 (200px total width)       |
|  Blue fill, light background         |
+--------------------------------------+
```

**Buttons:** HIDDEN (dismissed after Start pressed)
**Widget:** `ProgressBar` from `widget` module (`STR@0x00024408`)
**Message method:** `progressbar.setMessage(name)` (`STR@0x00024420`)
**Progress method:** `progressbar.setProgress(value)` (`STR@0x000243a8`)
**Citation:** Framebuffer captures `fb_0116.png` through `fb_0152.png`

### STATE: ERROR (install failed)

```
+--------------------------------------+
|  Title Bar: "Update"                 |
+--------------------------------------+
|  Content Area                        |
|                                      |
|  Toast (MASK_TOP_CENTER):            |
|  "Install failed, code = {N}"       |
|                                      |
+--------------------------------------+
```

**Toast position:** `MASK_TOP_CENTER` (`STR@0x000241ec`)
**Toast string:** resources.py: `'install_failed': 'Install failed, code = {}'`
**Error code format:** Hex (e.g., `0x03`, `0x04`, `0x05`)
**Citation:** activity_update.so string `install_failed` at `STR@0x0002424c`

### STATE: NO_UPDATE (no IPK found)

```
+--------------------------------------+
|  Toast (MASK_TOP_CENTER):            |
|  "No update available"              |
+--------------------------------------+
```

**Toast string:** resources.py: `'update_unavailable': 'No update available'`
**Behavior:** Toast shown, then `finish()` called automatically

### STATE: SUCCESS (install complete)

```
+--------------------------------------+
|  Toast (MASK_TOP_CENTER):            |
|  "Update finish."                    |
+--------------------------------------+
```

**Toast string:** resources.py: `'update_finish': 'Update finish.'`
**NOTE:** In practice, `restart_app()` calls `sudo service icopy restart &` which kills the app before this toast is visible. Framebuffer capture confirms the screen goes black immediately after "App restarting..." without showing "Update finish."

---

## 3. Key Bindings

### onKeyEvent (activity_update_ghidra_raw.txt line 10004)

The function takes `(self, event)`. Decompiled at line 10004-10550.

The key handler checks `self.can_click` attribute first (`STR@0x000244cc`). When `can_click` is False (during INSTALLING), all keys are ignored.

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| READY | no-op | no-op | no-op | no-op | start install | finish() | start install | finish() |
| INSTALLING | ignored | ignored | ignored | ignored | ignored | ignored | ignored | ignored |
| ERROR | finish() | finish() | finish() | finish() | finish() | finish() | finish() | finish() |

**READY detail:**
- OK/M2: Calls `self.install(bundle_path)` via `startBGTask()`. Sets `can_click = False`. Calls `showBtns(False)` to hide buttons. Starts background install thread.
- M1/PWR: Calls `self.finish()` — returns to AboutActivity.

**INSTALLING detail:**
- `can_click` is False. The `onKeyEvent.lambda1` closure (line 6910) wraps the install dispatch. All keys return early.

**ERROR/SUCCESS detail:**
- Any key calls `self.finish()`.

**Citation:** Decompiled `onKeyEvent` at line 10004. `can_click` attribute at `STR@0x000244cc`. `showBtns` at `STR@0x00024040`. `onKeyEvent.lambda1` closure at line 6910.

---

## 4. Methods — Detailed

### onCreate (line 7123)

```python
def onCreate(self):
    super().onCreate()
    self.setTitle(resources.get_str('update'))       # "Update"
    self.setLeftButton(resources.get_str('cancel'))   # "Cancel" (STR: cancel @0x2469c)
    self.setRightButton(resources.get_str('start'))   # "Start"
    self.showTips(True, resources.get_str('start_install_tips'))
    # Creates ProgressBar widget (hidden initially)
    # self.progressbar = ProgressBar(canvas, ...)
    self.can_click = True
```

**Citation:** String references: `start_install_tips` @0x24158, `start` @0x246f0, `cancel` @0x2469c, `update` @0x24608.
Framebuffer capture `fb_0107.png` confirms "Cancel" and "Start" buttons.

### onData (line 8596)

```python
def onData(self, bundle):
    # Receives IPK path from AboutActivity
    # Stores for later use by install()
    # The bundle is the IPK file path string
```

**Citation:** Instrumentation trace (2026-04-10): `START(UpdateActivity, '/mnt/upan/ipk_old/9_02150004_1.0.90.ipk')` — the bundle IS the IPK path.

### search (line 7580, static method)

```python
@staticmethod
def search(path, name):
    # Scans path for .ipk files
    # Returns list of found .ipk paths
    # String references: 'search' @0x24618, 'infolist' @0x2453c
```

**Citation:** `UpdateActivity.search` @0x240d0. Called by AboutActivity before launching UpdateActivity.

### checkPkg (line 11602)

```python
def checkPkg(self, file):
    # Validates ZIP structure
    # Required: app.py, lib/version.so, main/install.so
    # String references: 'infolist' @0x2453c, 'ver_info_file' @0x2428c
    # Uses zipfile.ZipFile to inspect contents
```

**Required files (from string table):**
- `lib/version.so` (`STR@0x0002423c`)
- `main/install.so` (`STR@0x000241bc`)
- Presence of `app.py` (implied by `MAIN_APP_SCRIPT` @0x241fc)

**Citation:** activity_update.so strings `lib/version.so` @0x2423c, `main/install.so` @0x241bc.

### checkVer (line 10552) — DRM CHECK

```python
def checkVer(self, path):
    # 1. path_import('version', 'lib/version.so') from unpacked IPK
    # 2. Read module.SERIAL_NUMBER
    # 3. Compare against running device's version.SERIAL_NUMBER
    # 4. MISMATCH → return error (code 0x04)
    # 5. MATCH → return success
```

**String references:** `SERIAL_NUMBER` @0x242fc, `VERSION_SCRIPT` @0x2426c, `ver_info_file` @0x2428c.
**Citation:** DRM-Install-Analysis.md lines 22-32.

### path_import (line 13022)

```python
def path_import(file):
    # Uses importlib.machinery.ExtensionFileLoader to load .so modules
    # String: ' path_import(): ' @0x242d8
    # String: 'ExtensionFileLoader' @0x24144
    # String: 'EXTENSION_SUFFIXES' @0x24180
    # String: 'module_from_spec' @0x24194
    # String: 'exec_module' @0x243e4
```

**CRITICAL:** This can ONLY load compiled `.so` files, NOT `.py` files. Confirmed by QEMU testing (DRM-Install-Analysis.md line 36: "ExtensionFileLoader CANNOT load .py files — returns 'invalid ELF header'").

### unpkg (line 14106)

```python
def unpkg(self, file):
    # Extracts IPK ZIP to TMP_OUT_DIR
    # String: 'TMP_OUT_DIR' @0x243fc — /tmp/.ipk/unpkg
    # String: 'unpack_archive' @0x241ec (note: also matches MASK_TOP_CENTER offset)
    # Uses shutil.unpack_archive or zipfile extraction
```

### install (line 14813) — ORCHESTRATOR

```python
def install(self, file):
    # 1. Creates internal callback closure
    # 2. path_import('install', 'main/install.so') from unpacked IPK
    # 3. Calls install.install(unpkg_path, callback)
    #    → install.so orchestrator calls in order:
    #       a. install_font(unpkg_path, callback)
    #       b. update_permission(unpkg_path, callback)
    #       c. install_lua_dep(unpkg_path, callback)
    #       d. install_app(unpkg_path, callback)
    #       e. restart_app(callback)
    # 4. On success: show "Update finish." toast
    # 5. On exception: call showErr(code)
```

**install.callback closure** (line 6478): Wraps `self.onInstall(name, progress)` for thread-safe UI updates.

**Citation:** `install.install` string @0x25a34. `installer_so` @0x2432c. `install_app` @0x24250.

### onInstall (line 5930)

```python
def onInstall(self, name, progress):
    # Called by install.so's callback function
    # 1. self.progressbar.setMessage(name)   — updates text above bar
    # 2. self.progressbar.setProgress(progress) — updates bar fill
```

**Widget methods:** `setMessage` @0x24420, `setProgress` @0x243a8.
**Widget attribute:** `progressbar` @0x243b4.
**Citation:** Decompiled lines 5930-6171.

### showErr (line 9082)

```python
def showErr(self, code):
    # Creates Toast with error message
    # text = resources.get_str('install_failed').format(code)
    # Toast position: MASK_TOP_CENTER
    # Sets can_click = True (allows key dismissal)
```

**Citation:** `install_failed` @0x2424c, `text_install_failed` @0x24732, `Toast` @0x24720, `MASK_TOP_CENTER` @0x241ec.

### showTips (line 16302)

```python
def showTips(self, enable=True, text=None):
    # Shows or hides the tip text in the content area
    # Creates canvas text with Consolas 15 font
    # When enable=False, hides/deletes the text
```

**Citation:** `showTips` @0x244d8, `Consolas 15` @0x24414.

### showBtns (line 9619)

```python
def showBtns(self, enable):
    # Shows or hides M1/M2 buttons
    # enable=True: state='normal' → buttons visible
    # enable=False: state='hidden' → buttons invisible
    # Also controls can_click attribute
```

**State strings:** `normal` @0x24630, `hidden` @0x2466c.
**Citation:** `showBtns` @0x24040.

---

## 5. Install Engine (install.so) — Complete Callback Map

Source: `main/install.so` from IPK package (98,188 bytes).
Decompiled: `decompiled/install_ghidra_raw.txt`.
Strings: `docs/v1090_strings/install_strings.txt`.

### Function Signatures

| # | Function | Address | Signature |
|---|----------|---------|-----------|
| 1 | `install_font` | 0x000166e4 | `install_font(unpkg_path, callback)` |
| 2 | `update_permission` | 0x00015cbc | `update_permission(unpkg_path, callback)` |
| 3 | `install_lua_dep` | 0x00019768 | `install_lua_dep(unpkg_path, callback)` |
| 4 | `install_app` | 0x0001b348 | `install_app(unpkg_path, callback)` |
| 5 | `restart_app` | 0x0001541c | `restart_app(callback)` |
| 6 | `install` | 0x0001d370 | `install(unpkg_path, callback)` — orchestrator |

### Execution Order (confirmed by framebuffer capture 2026-04-10)

```
install(unpkg_path, callback):
    install_font(unpkg_path, callback)
    update_permission(unpkg_path, callback)
    install_lua_dep(unpkg_path, callback)
    install_app(unpkg_path, callback)
    restart_app(callback)
```

### Complete Callback Message Table

All strings extracted from `install.so` binary. Each function calls
`callback(message_string, progress_int)` at various stages.

#### Step 1: install_font(unpkg_path, callback)

Copies `.ttf` files from `{unpkg_path}/res/font/` to device font directory.
Runs `sudo fc-cache -fsv` after copying.

| Branch | Callback message | Meaning |
|--------|-----------------|---------|
| Fonts found, starting copy | `" Font will install..."` | (note leading space) |
| Fonts copied successfully | `" Font installed."` | (note leading space) |
| No font files in IPK | `"No Font can install."` | Skip font step |

**Internal variables:** `source_font_path`, `target_font_path`, `source_font_file`, `old_fonts`, `new_fonts`, `new_font`, `font_suffix` (`.ttf`), `font_no_install_list`, `font_install`.
**System command:** `sudo fc-cache -fsv` (font cache refresh).

#### Step 2: update_permission(unpkg_path, callback)

Sets permissions on extracted files.

| Branch | Callback message | Meaning |
|--------|-----------------|---------|
| Running chmod | `"Permission Updating..."` | chmod in progress |

**System command:** `chmod 777 -R {unpkg_path}` (via `os.system(format(...))`).

#### Step 3: install_lua_dep(unpkg_path, callback)

Extracts `lua.zip` and copies lua libraries + scripts.

| Branch | Callback message | Meaning |
|--------|-----------------|---------|
| Starting extraction | `"LUA dep installing..."` | Extracting lua.zip |
| Lua deps already present | `"LUA dep exists..."` | Skip extraction |
| Extraction complete | `"LUA dep install done."` | Success |
| lua.zip not found | `"lua.zip no found..."` | (sic — original typo) |

**Internal variables:** `path_lua_zip`, `path_lua_libs`, `path_lua_scripts`, `dir_lualibs`, `dir_luascripts`.
**File:** `lua.zip` (searched in `/mnt/upan/` aka `path_upan`).

#### Step 4: install_app(unpkg_path, callback)

Moves unpacked files to `/home/pi/ipk_app_new`.

| Branch | Callback message | Meaning |
|--------|-----------------|---------|
| Starting file move | `"App installing..."` | Moving files |
| Move complete | `"App installed!"` | Files in place |
| Copy fallback done | `"copy files finished!"` | Used if move fails |

**Internal variables:** `target_path`, `target_path_new_pkg` (`ipk_app_new`), `target_path_unpkg`.
**Operations:** `shutil.move()` or `shutil.copy()` + `shutil.rmtree()`.

#### Step 5: restart_app(callback)

Restarts the iCopy service.

| Branch | Callback message | Meaning |
|--------|-----------------|---------|
| Before restart | `"App restarting..."` | About to restart |

**System command:** `sudo service icopy restart &` (backgrounded).
**NOTE:** After this call, the app process is killed. No further UI updates occur.

---

## 6. Full Logic Tree

```
AboutActivity
  │
  ├── checkUpdate()
  │     │
  │     ├── search('/mnt/upan/', ...) → finds .ipk files
  │     │     │
  │     │     ├── No .ipk found
  │     │     │     └── Toast: "No update available" (update_unavailable)
  │     │     │         └── return (stay on AboutActivity)
  │     │     │
  │     │     └── .ipk found → ipk_path
  │     │           └── actstack.start_activity(UpdateActivity, ipk_path)
  │     │
  │     └── UpdateActivity launched
  │
  └── UpdateActivity
        │
        ├── onCreate()
        │     ├── setTitle("Update")
        │     ├── setLeftButton("Cancel")
        │     ├── setRightButton("Start")
        │     ├── showTips(True, "Press 'Start' to install")
        │     ├── Create ProgressBar (hidden)
        │     └── can_click = True
        │
        ├── STATE: READY
        │     │
        │     ├── [M1 or PWR pressed]
        │     │     └── finish() → back to AboutActivity
        │     │
        │     └── [M2 or OK pressed]
        │           ├── can_click = False
        │           ├── showBtns(False) → hide Cancel/Start
        │           ├── setbusy() → show busy indicator
        │           └── startBGTask(install_pipeline)
        │
        ├── STATE: INSTALLING (background thread)
        │     │
        │     ├── All keys IGNORED (can_click = False)
        │     │
        │     ├── checkPkg(ipk_path)
        │     │     │
        │     │     ├── FAIL: missing app.py / lib/version.so / main/install.so
        │     │     │     └── showErr(0x05) → "Install failed, code = 0x05"
        │     │     │         └── goto STATE: ERROR
        │     │     │
        │     │     └── PASS → continue
        │     │
        │     ├── unpkg(ipk_path)
        │     │     │
        │     │     ├── FAIL: extraction error
        │     │     │     └── showErr(0x02) → "Install failed, code = 0x02"
        │     │     │         └── goto STATE: ERROR
        │     │     │
        │     │     └── PASS → files in /tmp/.ipk/unpkg/
        │     │
        │     ├── checkVer(unpkg_path)  ← DRM CHECK
        │     │     │
        │     │     ├── path_import('version', 'lib/version.so')
        │     │     │     │
        │     │     │     ├── FAIL: can't load version.so
        │     │     │     │     └── showErr(0x04) → "Install failed, code = 0x04"
        │     │     │     │
        │     │     │     └── PASS → module loaded
        │     │     │
        │     │     ├── Compare SERIAL_NUMBER
        │     │     │     │
        │     │     │     ├── MISMATCH
        │     │     │     │     └── showErr(0x04) → "Install failed, code = 0x04"
        │     │     │     │         └── goto STATE: ERROR
        │     │     │     │
        │     │     │     └── MATCH → continue
        │     │     │
        │     │     └── (our OSS firmware skips this check entirely)
        │     │
        │     ├── path_import('install', 'main/install.so')
        │     │     │
        │     │     ├── FAIL: can't load install module
        │     │     │     └── showErr(0x03) → "Install failed, code = 0x03"
        │     │     │         └── goto STATE: ERROR
        │     │     │
        │     │     └── PASS → install module loaded
        │     │
        │     └── install.install(unpkg_path, callback)
        │           │
        │           │  callback = self.onInstall(name, progress)
        │           │  → progressbar.setMessage(name)
        │           │  → progressbar.setProgress(progress)
        │           │
        │           ├── Step 1: install_font(unpkg_path, callback)
        │           │     │
        │           │     ├── Fonts found in {unpkg}/res/font/*.ttf
        │           │     │     ├── callback(" Font will install...", ?)
        │           │     │     ├── Copy fonts to target_font_path
        │           │     │     ├── os.system("sudo fc-cache -fsv")
        │           │     │     └── callback(" Font installed.", ?)
        │           │     │
        │           │     └── No fonts in IPK
        │           │           └── callback("No Font can install.", ?)
        │           │
        │           ├── Step 2: update_permission(unpkg_path, callback)
        │           │     └── os.system("chmod 777 -R {unpkg_path}")
        │           │           └── callback("Permission Updating...", ?)
        │           │
        │           ├── Step 3: install_lua_dep(unpkg_path, callback)
        │           │     │
        │           │     ├── lua.zip found on USB
        │           │     │     ├── Lua dirs don't exist yet
        │           │     │     │     ├── callback("LUA dep installing...", ?)
        │           │     │     │     ├── Extract lua.zip → lualibs + luascripts
        │           │     │     │     └── callback("LUA dep install done.", ?)
        │           │     │     │
        │           │     │     └── Lua dirs already exist
        │           │     │           └── callback("LUA dep exists...", ?)
        │           │     │
        │           │     └── lua.zip NOT found
        │           │           └── callback("lua.zip no found...", ?)
        │           │
        │           ├── Step 4: install_app(unpkg_path, callback)
        │           │     ├── callback("App installing...", ?)
        │           │     ├── shutil.move(unpkg → /home/pi/ipk_app_new)
        │           │     │     OR shutil.copy + rmtree (fallback)
        │           │     │     └── callback("copy files finished!", ?)
        │           │     └── callback("App installed!", ?)
        │           │
        │           └── Step 5: restart_app(callback)
        │                 ├── callback("App restarting...", ?)
        │                 ├── time.sleep(?) — brief delay
        │                 └── os.system("sudo service icopy restart &")
        │                       └── APP PROCESS KILLED
        │                           (device reboots with new firmware)
        │
        ├── STATE: ERROR
        │     │
        │     ├── Toast displayed: "Install failed, code = {0xNN}"
        │     ├── can_click = True (re-enabled)
        │     └── [ANY key pressed] → finish() → back to AboutActivity
        │
        └── STATE: SUCCESS (rarely reached — restart kills app first)
              │
              ├── Toast displayed: "Update finish."
              ├── can_click = True
              └── [ANY key pressed] → finish() → back to AboutActivity
```

---

## 7. Error Code Table

| Code | Hex | Cause | Stage |
|------|-----|-------|-------|
| 1 | 0x01 | No .ipk file found | search() |
| 2 | 0x02 | IPK extraction failed | unpkg() |
| 3 | 0x03 | Install module load/execution failed | install() exception |
| 4 | 0x04 | Serial number mismatch (DRM) | checkVer() |
| 5 | 0x05 | IPK package validation failed | checkPkg() |

**Citation:** DRM-Install-Analysis.md, flow spec docs/flows/about/README.md lines 132-134, test scenario `about_update_install_fail`.

---

## 8. String Resources (activity_update.so)

### From resources module (looked up via get_str)

| Key | Category | Value | Used in |
|-----|----------|-------|---------|
| `update` | title | `"Update"` | onCreate → setTitle |
| `start` | button | `"Start"` | onCreate → setRightButton |
| `cancel` | button | `"Cancel"` | onCreate → setLeftButton |
| `start_install_tips` | tipsmsg | `"Press 'Start' to install"` | onCreate → showTips |
| `installation` | tipsmsg | `"During installation\ndo not turn off\n or power off..."` | (tip during install) |
| `install_tips` | tipsmsg | (install instructions) | (additional tips) |
| `install_failed` | toastmsg | `"Install failed, code = {}"` | showErr |
| `update_finish` | toastmsg | `"Update finish."` | success toast |
| `update_unavailable` | toastmsg | `"No update available"` | AboutActivity (no IPK) |

### From install.so (hardcoded callback strings)

| String | Function | Meaning |
|--------|----------|---------|
| `" Font will install..."` | install_font | Copying fonts |
| `" Font installed."` | install_font | Fonts copied OK |
| `"No Font can install."` | install_font | No fonts in IPK |
| `"Permission Updating..."` | update_permission | chmod running |
| `"LUA dep installing..."` | install_lua_dep | Extracting lua.zip |
| `"LUA dep exists..."` | install_lua_dep | Already present |
| `"LUA dep install done."` | install_lua_dep | Extraction done |
| `"lua.zip no found..."` | install_lua_dep | No lua.zip (sic) |
| `"App installing..."` | install_app | Moving files |
| `"App installed!"` | install_app | Files moved |
| `"copy files finished!"` | install_app | Copy fallback done |
| `"App restarting..."` | restart_app | Before service restart |

**NOTE:** The leading space in `" Font will install..."` and `" Font installed."` is present in the binary and displayed as-is. This is NOT a transcription error.

---

## 9. Widget Details

### ProgressBar

Created from `widget.ProgressBar` module. Located at bottom of content area.

| Property | Value | Citation |
|----------|-------|---------|
| Widget class | `ProgressBar` | STR@0x24408 |
| Position | Bottom of screen, y≈196-225 | Framebuffer captures |
| Total width | 200px (x=20 to x=219) | Pixel analysis |
| Height | ~29px | Pixel analysis |
| Fill color | Solid blue (R<50, G<130, B>200) | Pixel analysis |
| Background | Light blue/white | Pixel analysis |
| Text position | Above bar fill area | Framebuffer captures |
| Text font | Consolas 15 | STR@0x24414 |
| setMessage(text) | Updates text label | STR@0x24420 |
| setProgress(value) | Updates fill percentage | STR@0x243a8 |

### Toast

Used for error and success messages.

| Property | Value | Citation |
|----------|-------|---------|
| Widget class | `Toast` | STR@0x24720 |
| Position | `MASK_TOP_CENTER` | STR@0x241ec |

---

## 10. Ground Truth Checklist

| Property | Value | Source |
|----------|-------|--------|
| Title | "Update" | resources.py, fb_0107.png |
| M1 label (READY) | "Cancel" | fb_0107.png |
| M2 label (READY) | "Start" | fb_0107.png, resources.py |
| Content text | "Press 'Start' to install" | fb_0107.png, resources.py |
| Content font | Consolas 15 | activity_update.so STR@0x24414 |
| Buttons hidden during install | Yes | fb_0116.png |
| Progress widget | ProgressBar | activity_update.so STR@0x24408 |
| Progress messages | 12 unique strings | install.so binary extraction |
| Install order | font→perm→lua→app→restart | Framebuffer sequence 2026-04-10 |
| Bundle type | IPK file path (string) | Instrumentation trace 2026-04-10 |
| Launched via | actstack.start_activity | Instrumentation trace 2026-04-10 |
| Stack depth | 3 (Main + About + Update) | Instrumentation trace 2026-04-10 |
| Error format | "Install failed, code = 0x{NN}" | activity_update.so, test scenario |
| App restart cmd | `sudo service icopy restart &` | install.so STR@0x1efbc |
| DRM check | checkVer compares SERIAL_NUMBER | activity_update.so, DRM-Install-Analysis.md |

---

## 11. Real Device Evidence

| Artifact | Location |
|----------|----------|
| Instrumentation trace | `docs/Real_Hardware_Intel/trace_update_flow_20260410.txt` |
| Full analysis | `docs/Real_Hardware_Intel/trace_update_flow_analysis_20260410.md` |
| Framebuffer PNGs (31 unique) | `docs/Real_Hardware_Intel/framebuffer_captures/update_flow/png/deduped/` |
| install.so binary | `decompiled/install.so` |
| install.so decompiled | `decompiled/install_ghidra_raw.txt` |
| install.so strings | `docs/v1090_strings/install_strings.txt` |
| install.so analysis | `docs/v1090_strings/install_so_analysis.md` |
| About page 1 screenshot | `docs/Real_Hardware_Intel/Screenshots/about_1_2.png` |
| About page 2 screenshot | `docs/Real_Hardware_Intel/Screenshots/about_2_2.png` |

---

## Corrections Applied

| Date | Correction | Evidence |
|------|-----------|----------|
| 2026-04-10 | M1 button is "Cancel" (not empty/hidden) in READY state | Framebuffer capture fb_0107.png |
| 2026-04-10 | Install execution order is font→permission→lua→app→restart (not font→lua→permission→app→restart as DRM doc stated) | Framebuffer capture sequence |
| 2026-04-10 | UpdateActivity receives IPK path as bundle string (not None or dict) | Instrumentation trace: `START(UpdateActivity, '/mnt/upan/...')` |
| 2026-04-10 | "Update finish." toast is never visible in practice — restart_app kills app first | Framebuffer capture shows black screen after "App restarting..." |
| 2026-04-10 | install.so callback messages are hardcoded English strings, not resource keys | Binary string extraction from install.so |
| 2026-04-10 | Leading space in " Font will install..." and " Font installed." is intentional — present in binary | install.so string table |
