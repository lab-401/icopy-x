# Scan Flow UI Integration — Post-Mortem & Guide

## Branch: `feat/ui-integrating`
## Date: 2026-03-31
## Status: 45/45 scan scenarios PASS, screenshots verified correct

---

## 1. Initial State — What Was Broken

### 1.1 Functionality: scan.so Not Calling Back

`scan.scanForType(None, self)` was called in `ScanActivity.onCreate()` but:
- Zero PM3 commands were sent
- `onScanFinish()` was never called
- UI stuck at "Scanning... 0%"

The real device trace (`docs/Real_Hardware_Intel/trace_scan_flow_20260331.txt` line 4-5) proved scan.so DOES send PM3 commands immediately after activity start:
```
[ 189.572] START(ScanActivity, None)
[ 189.636] PM3> hf 14a info (timeout=5000)
```

### 1.2 UI: Wrong Colors, Positions, Icons

| Element | Was | Should Be (Ground Truth) |
|---------|-----|--------------------------|
| Button bar BG | `#FFFFFF` (white) | `#222222` (dark) — `actbase_strings.txt` line 1228 |
| Button text | `#333333` (dark grey) | `white` — `actbase_strings.txt` line 1230 |
| Progress bar Y | `y=100` (middle) | `y=210` (bottom) — `scan_tag_scanning_2.png` pixel measurement |
| Progress % counter | Always shown | Never shown (only in Erase flow) — `scan_tag_scanning_2.png` |
| Icon recolor | Grey→White (invisible on white bg) | Grey→Dark grey — `main_page_1_3_1.png` |
| Button bar on main menu | Always drawn | Only when buttons have text — `main_page_1_3_1.png` |

### 1.3 UI: Scan Result Display

The result screen was implemented with invented Python middleware (`_FAMILY_MAP`, `_resolve_tag_display()`) that hardcoded family names, frequency lookups, and field formatting. This was 100% wrong — `template.so` owns ALL scan result rendering.

---

## 2. Ground Truth Resources — What Was Vital

### 2.1 Decompiled .so Files

| File | What It Provided |
|------|-----------------|
| `decompiled/scan_ghidra_raw.txt` | Scanner class API: `Scanner()` no-args, `call_progress`/`call_resulted`/`call_exception` properties, `scan_all_asynchronous()` no-args |
| `decompiled/activity_main_ghidra_raw.txt` | `ScanActivity.onScanFinish`, `ScanActivity.onScanning` callback names, `showButton(self, found, cansim=False)` signature |
| `decompiled/widget_ghidra_raw.txt` | Toast `_showMask` uses `create_image` with RGBA PhotoImage (tags_mask_layer) |
| `docs/v1090_strings/actbase_strings.txt` | `#222222` (button bar BG, line 1228), `white` (button text, line 1230) |
| `docs/v1090_strings/scan_strings.txt` | `scanForType`, `Scanner`, `setScanCache`, `getScanCache` — public API |
| `docs/v1090_strings/template_strings.txt` | ALL display strings: `MIFARE`, `FDX-B`, `Animal ID`, `UID: {}`, `SAK: {} {}: {}`, `Frequency: {}`, `13.56MHZ`, `125KHZ` |
| `docs/v1090_strings/hfsearch_strings.txt` | `Valid iCLASS tag` — keyword that triggers iCLASS detection |
| `docs/v1090_strings/lfsearch_strings.txt` | `Valid FDX-B ID`, `REGEX_ANIMAL` — FDX-B detection keywords |

### 2.2 Real Device Traces

| Trace | Content | Key Findings |
|-------|---------|--------------|
| `trace_scan_flow_20260331.txt` | 6 mixed scans (MFC, UL, ISO15693, Indala, FDX-B) | PM3 command sequence, `hf 14a info` returns `ret=1 \n` for no-tag, scan cache format |
| `trace_lf_scan_flow_20260331.txt` | 15 LF badge scans (AWID, EM410x, FDX-B, Gallagher, IO Prox, Indala, Jablotron, Keri, NexWatch, PAC, Paradox, Pyramid, Viking + no-tag + MFC) | Every PM3 command returns `ret=1`, no `[usb]` prefix in responses, T55xx detection sequence |
| `trace_iclass_scan_20260331.txt` | 3 HF scans (iCLASS Legacy, iCLASS Elite, ISO15693) | Full iCLASS PM3 command chain: `hf sea` → `hf iclass rdbl` (key attempts) → `hf iclass info` (CSN extraction) |

### 2.3 Real Device Screenshots

| Screenshot | What It Proved |
|-----------|---------------|
| `scan_tag_scanning_2.png` | Progress bar at y=210, no % counter, "Scanning..." text above bar |
| `scan_tag_scanning_5.png` | Result layout: header y=52, subheader y=86, fields y=110/132/155, bold fonts, field spacing |
| `scan_tag_no_tag_found_2.png` | No-tag state: M1="Rescan", M2="Rescan", dark button bar |
| `scan_tag_no_tag_found_3.png` | Toast overlay: semi-transparent, PNG icon left of text, content visible underneath |
| `main_page_1_3_1.png` | Main menu: dark grey icons on light bg, no button bar when buttons empty |

### 2.4 QEMU API Dump (from archive)

| File | What It Provided |
|------|-----------------|
| `archive/root_old/qemu_api_dump_filtered.txt` line 223 | `showButton(self, found, cansim=False)` — exact method signature |

### 2.5 PM3 Source Code

| File | What It Provided |
|------|-----------------|
| `icopyx-community-pm3/client/src/cmdlffdx.c` lines 285-290 | Exact PM3 output format for FDX-B: `Animal ID  %04u-%012PRIu64` |
| `icopyx-community-pm3/client/src/cmdhficlass.c` lines 896-898 | `hf iclass reader` output: `CSN: %s`, `Config: %s` |
| `icopyx-community-pm3/client/src/cmdhf.c` line 136 | `hf search` iCLASS detection: `Valid iCLASS tag / PicoPass tag found` |

**When to use PM3 source:** When real device trace responses are truncated (the tracer had a 150-char limit, later fixed to unlimited). The PM3 source provides the complete output format that the truncated trace cuts off.

---

## 3. Solutions Implemented

### 3.1 scan.so Call Pattern (The Critical Discovery)

**Problem:** `scan.scanForType(None, self)` returned None with zero threads created.

**Discovery method:** Systematic probing under QEMU (adding instrumentation to `_startScan`).

**Ground truth:** Probing `scan.Scanner()` under QEMU revealed:
- `Scanner()` takes NO args (not the listener)
- `Scanner.call_progress`, `call_resulted`, `call_exception` are properties set to bound methods
- `scan_all_asynchronous()` takes NO args

**Correct pattern:**
```python
import scan
self._scanner = scan.Scanner()
self._scanner.call_progress = self.onScanning    # bound method
self._scanner.call_resulted = self.onScanFinish   # bound method
self._scanner.call_exception = self.onScanFinish  # bound method
self._scanner.scan_all_asynchronous()
```

**Why `scanForType(None, self)` failed:** The `None` type argument caused the function to skip scanning entirely. And even with a type ID, `scanForType` creates zero threads — it has a different internal flow.

### 3.2 Callback Signatures

**Ground truth:** `decompiled/activity_main_ghidra_raw.txt` symbols:
- `__pyx_pw_13activity_main_12ScanActivity_5onScanning`
- `__pyx_pw_13activity_main_12ScanActivity_7onScanFinish`

**`onScanning(self, progress)`** — receives a tuple `(current, max)`:
```python
def onScanning(self, progress):
    if isinstance(progress, (list, tuple)) and len(progress) >= 2:
        pct = int(progress[0] * 100 / max(progress[1], 1))
```

**`onScanFinish(self, result)`** — receives a dict or string:
```python
# Dict: {'found': True, 'uid': '2CADC272', 'type': 1, 'sak': '08', ...}
# String: traceback text (on error)
# Int: error code
```

### 3.3 Result Display — template.so

**Problem:** Invented `_FAMILY_MAP` and `_resolve_tag_display()` produced wrong displays for many tag types.

**Solution:** Delete ALL invented display logic. Call `template.draw(type, result, canvas)`.

```python
def _showFoundState(self, result):
    tag_type = result.get('type', -1)
    canvas = self.getCanvas()
    if canvas is not None:
        try:
            import template
            template.draw(tag_type, result, canvas)
        except Exception as e:
            print('[TEMPLATE] draw failed: %s' % e, flush=True)
```

**Ground truth for template.so API:**
- `docs/v1090_strings/template_strings.txt` — all display strings
- `template.draw(typ, data, parent)` — confirmed via QEMU probing
- `parent` = canvas (not activity) — confirmed via traceback: `template.__drawFinal` calls `parent.create_text()`
- `template.dedraw(canvas)` — cleanup

**Critical timing insight:** `template.draw()` reads `executor.CONTENT_OUT_IN__TXT_CACHE` for the display data. This works because `onScanFinish` runs on the scan thread synchronously — the cache still contains the relevant PM3 response.

### 3.4 Toast — PIL RGBA Overlay + Tkinter Text

**Ground truth:** `decompiled/widget_ghidra_raw.txt` — `Toast._showMask` uses `create_image` with `tags_mask_layer` tag.

**Implementation:** PIL creates a transparent RGBA image (20% dim + 50% toast box + PNG icon), placed on canvas with `create_image`. Text rendered by tkinter's native mononoki font (PIL's `ImageFont.truetype` fails under QEMU — no `_imagingft`).

```python
# PIL for mask layer (transparency + icon)
mask = Image.new('RGBA', (W, H), (0, 0, 0, 0))
dim = Image.new('RGBA', (W, H), (0, 0, 0, 51))    # 20% dim
mask = Image.alpha_composite(mask, dim)
# ... toast box at 50% black, icon paste ...
self._tk_mask = ImageTk.PhotoImage(mask)
self._canvas.create_image(0, 0, image=self._tk_mask, anchor='nw', tags=self._tag_mask)

# Tkinter for text (native mononoki works under QEMU)
self._canvas.create_text(cx, cy, text=message, fill='white',
                         font=('mononoki', 18, 'bold'), anchor='center', tags=self._tag_text)
```

### 3.5 Canvas Cleanup

**Problem:** "Scanning..." text bled through on result screens.

**Root cause:** `_clearContent()` cleared widget objects and template.so items but not the JSON renderer's canvas items (tags `_jr_content`, `_jr_content_bg`, `_jr_buttons`).

```python
def _clearContent(self):
    # ... widget cleanup ...
    canvas = self.getCanvas()
    if canvas is not None:
        canvas.delete('_jr_content')
        canvas.delete('_jr_content_bg')
        canvas.delete('_jr_buttons')
        try:
            import template
            template.dedraw(canvas)
        except Exception:
            pass
```

---

## 4. JSON UI System

Activities define UI declaratively via JSON screen definitions. The `JsonRenderer` (`src/lib/json_renderer.py`) translates these into canvas draw calls.

### 4.1 Schema

```json
{
    "content": {
        "type": "progress|template|list|text|empty",
        "message": "Scanning...",
        "value": 0,
        "max": 100
    },
    "buttons": {
        "left": "Rescan",
        "right": "Simulate"
    }
}
```

### 4.2 Content Types

| Type | Use | Rendered By |
|------|-----|-------------|
| `progress` | Scanning phase | JsonRenderer (progress bar at y=210) |
| `template` | Tag result display | **template.so** (NOT JsonRenderer) |
| `list` | Tag type selection | JsonRenderer |
| `text` | Warnings, info | JsonRenderer |
| `empty` | Toast-only screens | Nothing |

### 4.3 Key Rule: template.so Renders Results

The JSON renderer handles progress bars and button bars. But scan result display (the tag info template) is rendered by `template.so` — it has per-type draw functions (`__drawM1`, `__drawMFU`, `__drawID`, etc.) that know exactly which fields to show and how to format them. The JSON renderer's `_render_template` method exists but is NOT used for scan results.

---

## 5. NO MIDDLEWARE — Violations Found & Corrected

### Rule: Our Python code must NOT contain RFID logic. The .so middleware does ALL logic.

### 5.1 `_FAMILY_MAP` — DELETED

A 30-entry hardcoded dictionary mapping type name prefixes to display family names (`'M1': 'MIFARE'`, `'FDXB': 'FDX-B'`, etc.). This reimplemented `template.so`'s `TYPE_TEMPLATE` lookup.

### 5.2 `_resolve_tag_display()` — DELETED

Function that resolved tag type IDs to `(family, subheader, frequency)` tuples. Three separate middleware violations:
- Family name resolution (prefix matching — template.so uses integer lookup)
- Subheader formatting (`"M1 S50 1K 4B" → "M1 S50 1K (4B)"` — template.so stores pre-formatted strings)
- Frequency resolution (hardcoded type ID sets — template.so stores frequency per type)

### 5.3 `_canSimulate()` — DELETED

Function that decided which tag types support simulation using invented type ID sets. Replaced with `_SIMULATE_TYPES` frozenset sourced from `archive/ui/activities/scan.py` `_can_simulate()` (extracted from `activity_main.so` `simulate_map`).

**Note:** `_SIMULATE_TYPES` is still technically middleware — it should ideally come from the running `activity_main.so`. However, `activity_main.so` cannot be fully imported under QEMU (init crashes). This is an accepted deviation with user confirmation.

### 5.4 Mass Fixture Modification — REVERTED

219 fixtures across all flows were mass-modified to change return codes `(0,...)` → `(1,...)` and remove `[usb] pm3 -->` prefixes. This broke ALL tests because:
- The mock already converted `ret=0` to `return 1` internally (`launcher_current.py` line 489: `result = ret if ret == -1 else 1`)
- The `[usb] pm3 -->` prefix was part of the response format that scan.so's parsers expected

**Lesson:** NEVER mass-modify working fixtures. Fix ONLY what is specifically broken, verify each fix individually.

### 5.5 Fixtures That Genuinely Needed Fixing

Only 2 out of 336 fixture files required modification:

| Fixture | Problem | Fix | Ground Truth |
|---------|---------|-----|-------------|
| `scan_iclass` | Missing `Valid iCLASS tag` keyword in `hf sea` response, causing scan.so to fall through to LF detection | Added full `hf sea` response with keyword + CSN/Config output, plus `hf iclass rdbl` and `hf iclass info` responses | `trace_iclass_scan_20260331.txt` lines 4-22, `cmdhf.c` line 136, `cmdhficlass.c` lines 896-898 |
| `scan_fdxb` | Invented PM3 response format (`[+] Animal ID: 999-00001234567`) that `lfsearch.so` couldn't parse | Correct PM3 format from `cmdlffdx.c` lines 285-290: `[+] Animal ID  0999-000001234567` with full demod output | `trace_lf_scan_flow_20260331.txt` line 44, `cmdlffdx.c` |

---

## 6. PM3 Source Code Reference

Repository: `https://github.com/iCopy-X-Community/icopyx-community-pm3`

### When to Use

When real device trace responses are truncated. The tracer originally truncated PM3 responses at 150 chars (now fixed to unlimited in `docs/HOW_TO_RUN_LIVE_TRACES.md`). The PM3 source provides the complete `PrintAndLogEx` output format.

### Key Files

| PM3 Source File | Tag Type | Output Format |
|----------------|----------|---------------|
| `client/src/cmdlffdx.c` lines 285-290 | FDX-B | `[+] Animal ID  %04u-%012PRIu64` |
| `client/src/cmdhficlass.c` lines 896-898 | iCLASS | `CSN: %s`, `Config: %s` |
| `client/src/cmdhf.c` line 136 | iCLASS detection | `Valid iCLASS tag / PicoPass tag found` |
| `client/src/cmdlfem4x.c` lines 253-292 | EM410x | `EM TAG ID: %010PRIX64` + de-scramble |
| `client/src/cmdlfhid.c` ~line 202 | HID Prox | `HID Prox - %x%08x%08x (%u)` |
| `client/src/cmdlfpyramid.c` line 184 | Pyramid | `Pyramid - len: %d, FC: %d Card: %d` |

---

## 7. Summary

### 7.1 High-Level Problems & Solutions

| # | Problem | Root Cause | Solution | Steps |
|---|---------|-----------|----------|-------|
| 1 | scan.so silent — no PM3 commands | Wrong call pattern: `scanForType(None, self)` | Discovered `Scanner()` API via QEMU probing | Probe module attrs → try call patterns → trace threads → find working pattern |
| 2 | Callbacks not firing | `Scanner.call_progress` set to `self` (not callable) | Set to bound methods (`self.onScanning`) | Decompiled `_call_progress_method` checks `tp_call` → realized it needs a callable |
| 3 | Result screen wrong content | Invented `_FAMILY_MAP` middleware | Delegate to `template.so` via `template.draw(type, result, canvas)` | Found `template.so` in string tables → probed API → confirmed `parent` = canvas via traceback |
| 4 | Toast wrong style | Unicode glyphs, wrong position, no transparency | PIL RGBA overlay + tkinter text, matching widget.so `_showMask` pattern | Read decompiled widget.so → found `create_image` + `mask_layer` → PIL for mask, tkinter for text |
| 5 | Button bar on main menu | `_setupButtonBg` called for empty buttons | Only draw bar when button text is non-empty | Real screenshot `main_page_1_3_1.png` shows no bar |
| 6 | Progress bar position | `y=100` (invented) | `y=210` (bottom-anchored) | Pixel measurement of `scan_tag_scanning_2.png` |
| 7 | FDX-B empty UID | Fixture PM3 format wrong | Correct format from PM3 source `cmdlffdx.c` | Real trace showed `lfsearch.so` uses `REGEX_ANIMAL` → checked PM3 source for format |
| 8 | iCLASS shows "Jablotron" | Fixture missing `Valid iCLASS tag` keyword | Added keyword + full command chain from real trace | Captured `trace_iclass_scan_20260331.txt` → showed exact PM3 sequence |
| 9 | Mass fixture modification broke everything | Blanket changes to 219 working fixtures | Reverted all, fixed only 2 that were actually broken | Lesson: NEVER mass-modify working fixtures |
| 10 | Remote test screenshots cross-contaminated | 9 parallel tests sharing single Xvfb display | Per-thread Xvfb displays (`:50` through `:58`) | Diagnosed by comparing state JSON (correct) vs screenshots (wrong) |

### 7.2 What Would Have Made This Faster

1. **Knowing the `Scanner()` API from the start.** The `scanForType` vs `Scanner` distinction cost hours. A document listing "scan.so public API: `Scanner()` no-args, set `call_progress`/`call_resulted`/`call_exception` to bound methods, call `scan_all_asynchronous()` no-args" would have saved the entire probing phase.

2. **Knowing `template.so` exists and owns result rendering.** I built 120 lines of invented display code before discovering `template.so`. A module inventory with "template.so: renders scan/read result screens, API: `template.draw(type, data, canvas)`" would have prevented all middleware violations.

3. **Knowing the tracer truncates at 150 chars.** The iCLASS `hf sea` response was truncated, hiding the `Valid iCLASS tag` keyword. I spent time debugging before realizing the trace was incomplete. The tracer should have been unlimited from the start.

4. **Knowing the mock already converts ret=0 to 1.** `launcher_current.py` line 489: `result = ret if ret == -1 else 1`. The fixtures' `(0, ...)` return codes were already correct. Understanding this would have prevented the disastrous mass fixture modification.

5. **Per-thread Xvfb display isolation in the parallel test runner.** This is standard parallel test infrastructure but was missing, causing hours of debugging "wrong screenshots" that were actually cross-contamination.

6. **A complete list of `.so` modules and their roles.** Something like:
   - `scan.so` — scan pipeline, creates Scanner, sends PM3 commands
   - `template.so` — renders tag info on canvas (TYPE_TEMPLATE dict)
   - `lfsearch.so` — parses LF PM3 responses (REGEX_ANIMAL, etc.)
   - `hfsearch.so` — parses HF PM3 responses (Valid iCLASS tag, etc.)
   - `hf14ainfo.so` — parses hf 14a info response (UID, SAK, ATQA)
   - `executor.so` — PM3 communication (startPM3Task, getContentFromRegex, CONTENT_OUT_IN__TXT_CACHE)

---

## 8. Ground Truth Rules — Enforced

**Only use ground-truth resources:**

1. The original decompiled .so files: `decompiled/*.txt`
2. Real activity traces from real actions on the real device: `docs/Real_Hardware_Intel/trace_*.txt`
3. Real screenshots from the real device: `docs/Real_Hardware_Intel/Screenshots/*.png`
4. **NEVER deviate** from these resources. Never invent. Never guess. Never "try something".
5. **ALL your work must derive from these ground truths.**
6. **EVERY action that you perform**, you will provide the reference to the ground-truth upon which you justify your action.
7. **Before you write ANY code**, ask yourself: Does this come directly from a ground-truth? If not, don't do it.
8. **AFTER you have written code**, audit it and ask yourself: Does this come directly from a ground-truth? If not, undo it.

If there is NO way around this, or if you're given a task that requires deviating, ask explicit confirmation from the User.

### PM3 Source as Supplementary Ground Truth

Repository: `https://github.com/iCopy-X-Community/icopyx-community-pm3`

Use ONLY when real device trace responses are truncated. The PM3 source provides the complete `PrintAndLogEx` output format. Always verify against a real trace first — the PM3 source shows what the output SHOULD look like, the trace shows what it ACTUALLY looks like.

---

## 9. Files Modified

| File | Changes |
|------|---------|
| `src/lib/activity_main.py` | ScanActivity: Scanner API, onScanning/onScanFinish callbacks, template.draw() for results, _clearContent canvas cleanup |
| `src/lib/widget.py` | Toast: PIL RGBA mask + tkinter text, ProgressBar: y=210 no %, icon recolor constants |
| `src/lib/actbase.py` | Button bar only drawn when text present |
| `src/lib/_constants.py` | BTN_BAR_BG=#222222, BTN_TEXT_COLOR=white, PROGRESS_Y=210, ICON_RECOLOR_NORMAL |
| `src/lib/resources.py` | get_bold_font() for template header/subheader |
| `src/lib/json_renderer.py` | NEW: JSON schema → canvas renderer |
| `src/screens/scan_tag.json` | NEW: declarative scan flow screen definitions |
| `tools/launcher_current.py` | Thread exception hook fix, PM3 mock cache tracing |
| `tests/flows/scan/scenarios/scan_iclass/fixture.py` | Full iCLASS PM3 command chain from real trace |
| `tests/flows/scan/scenarios/scan_fdxb/fixture.py` | Correct PM3 output format from cmdlffdx.c |
| `res/font/mononoki-Bold.ttf` | NEW: bold font for template headers |
| `docs/HOW_TO_INTEGRATE_A_FLOW.md` | Ground Truth Rules, JSON UI System documentation |
| `docs/HOW_TO_RUN_LIVE_TRACES.md` | Removed 150-char truncation from PM3 response logging |
