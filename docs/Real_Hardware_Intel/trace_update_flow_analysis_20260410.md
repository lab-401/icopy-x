# Update Flow — Real Device Ground Truth (2026-04-10)

## Capture Method

- **Run 1**: Python instrumentation (actstack transitions, resources.get_str patch)
- **Run 2**: Framebuffer capture (240x240 RGB565 /dev/fb1, 500ms interval, 191 frames → 31 unique states)
- **Device**: Original firmware v1.0.90 (all .so modules)
- **IPK**: `02150004_1.0.90.ipk` (original firmware re-install)

## Activity Transition Trace

```
[  65.027] START(AboutActivity, None)              — About pushed, bundle=None
[  65.107] POLL stack=['dict', 'dict'] d=2          — Main + About
[  65.188] PM3> hw ver (timeout=6888)               — AboutActivity reads PM3 version
[  65.345] PM3< ret=1 (NIKOLA v3.1)                 — Version data returned
[  74.723] START(UpdateActivity, '/mnt/upan/ipk_old/9_02150004_1.0.90.ipk')
                                                     — UpdateActivity launched as SUB-ACTIVITY
                                                     — Bundle = IPK FILE PATH (string)
[  75.026] POLL stack=['dict', 'dict', 'dict'] d=3   — Main + About + Update
           === APP RESTART (install complete) ===
```

## Key Finding: Bundle is IPK Path

AboutActivity does NOT launch UpdateActivity with `bundle=None`. It first calls
`search()` to find the IPK, then passes the **IPK file path as the bundle string**
to `actstack.start_activity(UpdateActivity, ipk_path)`.

## Complete UI State Sequence (from framebuffer captures)

### Phase 1: Navigation to About

| State | Frame | Screen |
|-------|-------|--------|
| 0 | fb_0000 | Main Page 1/3 — Auto Copy, Dump Files, Scan Tag, Read Tag, Sniff TRF |
| 1-6 | fb_0081-0091 | Main Page 3/3 — scrolling to About (highlight moves) |
| 7 | fb_0092 | **About 1/2** — iCopy-XS, HW 1.7, HMI 1.4, OS 1.0.90, PM 3.1, SN 02150004 |
| 8 | fb_0098 | **About 2/2** — Firmware update instructions |

### Phase 2: UpdateActivity READY

| State | Frame | Screen |
|-------|-------|--------|
| 9 | fb_0107 | **Title: "Update"**, Content: "Press 'Start' to install", Buttons: **M1="Cancel"**, **M2="Start"** |
| 10 | fb_0116 | Same but buttons disappeared (busy state entered after pressing Start) |

### Phase 3: Install Progress (ProgressBar with setMessage)

| State | Frame | Message | Progress Bar |
|-------|-------|---------|-------------|
| 11-13 | fb_0133-0135 | **"No Font can install."** | ~25% filled |
| 14-15 | fb_0137-0138 | **"Permission Updating..."** | ~40% filled |
| 16-17 | fb_0141-0142 | **"LUA dep exists..."** | ~55% filled |
| 18-20 | fb_0144-0146 | **"App installed!"** | ~90% filled |
| 21-24 | fb_0148-0152 | **"App restarting..."** | ~95% filled |

### Phase 4: Restart

| State | Frame | Screen |
|-------|-------|--------|
| 25 | fb_0158 | Black screen (app killed) |
| 26-27 | fb_0171-0172 | Main Page with "Processing..." toast (fresh boot) |
| 28-30 | fb_0175-0190 | Main Page 1/3 — normal operation |

## Progress Bar Messages (Ground Truth)

These are the exact strings displayed by `onInstall(name, progress)` via
`self.progressbar.setMessage(name)`. They come from install.so's callback calls.

Source: `install.so` extracted from device, strings + Ghidra decompilation.
Full analysis: `docs/v1090_strings/install_so_analysis.md`

### Observed sequence (framebuffer capture):

| Step | install.so function | Callback message | Approx progress |
|------|-------------------|-----------------|----------------|
| 1 | `install_font()` | `"No Font can install."` | ~25% |
| 2 | `update_permission()` | `"Permission Updating..."` | ~40% |
| 3 | `install_lua_dep()` | `"LUA dep exists..."` | ~55% |
| 4 | `install_app()` | `"App installed!"` | ~90% |
| 5 | `restart_app()` | `"App restarting..."` | ~95% |

### ALL possible callback messages (from install.so binary strings):

| Function | Message | When |
|----------|---------|------|
| `install_font` | `" Font will install..."` | Fonts found, copying |
| `install_font` | `" Font installed."` | Fonts copied OK |
| `install_font` | `"No Font can install."` | No fonts in IPK |
| `update_permission` | `"Permission Updating..."` | chmod running |
| `install_lua_dep` | `"LUA dep installing..."` | Extracting lua.zip |
| `install_lua_dep` | `"LUA dep exists..."` | Lua deps already present |
| `install_lua_dep` | `"LUA dep install done."` | Extraction complete |
| `install_lua_dep` | `"lua.zip no found..."` | No lua.zip in IPK |
| `install_app` | `"App installing..."` | Moving files |
| `install_app` | `"App installed!"` | Files moved OK |
| `install_app` | `"copy files finished!"` | Copy complete |
| `restart_app` | `"App restarting..."` | Before service restart |

### Execution order (confirmed):
```
install() orchestrator calls:
  1. install_font(unpkg_path, callback)
  2. update_permission(unpkg_path, callback)
  3. install_lua_dep(unpkg_path, callback)
  4. install_app(unpkg_path, callback)
  5. restart_app(callback)
```

**NOTE**: The order differs from what DRM-Install-Analysis.md assumed:
- Actual order: font → permission → lua → app → restart
- DRM doc assumed: font → lua → permission → app → restart

**NOTE**: The message strings are NOT resource keys — they are literal English
strings hardcoded in install.so and passed directly to the callback. They are
NOT looked up via `resources.get_str()`.

**NOTE**: The leading space in `" Font will install..."` and `" Font installed."`
is intentional — it's in the binary.

## UpdateActivity UI Specification (Ground Truth)

### READY State
- **Title**: "Update"
- **Content**: "Press 'Start' to install" (blue text, Consolas 15 font)
- **M1 button**: "Cancel" (visible, white text)
- **M2 button**: "Start" (visible, white text)
- **Keys**: M2/OK = start install, M1/PWR = finish (back to About)

### INSTALLING State
- **Title**: "Update" (unchanged)
- **Content**: "Press 'Start' to install" (remains visible, unchanged)
- **Buttons**: HIDDEN (disappeared after Start pressed)
- **Progress Bar**: Bottom of screen, blue fill, with message text above
- **Keys**: ALL DISABLED

### Progress Bar Widget
- Position: bottom quarter of screen
- Blue filled bar progressing left to right
- Text message above the bar (the `name` parameter from callback)
- Messages update as each install step completes

### DONE State (not captured — app restarts immediately)
- After "App restarting..." the app is killed and reboots
- No "Update finish." toast was observed — the restart happens immediately

## Files

- Activity trace: `docs/Real_Hardware_Intel/trace_update_flow_20260410.txt`
- Framebuffer PNGs: `docs/Real_Hardware_Intel/framebuffer_captures/update_flow/png/deduped/`
