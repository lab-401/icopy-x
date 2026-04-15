# Simulate Flow -- UI Integration Post-Mortem

## 1. Initial State

### What existed
`SimulationActivity` and `SimulationTraceActivity` in `src/lib/activity_main.py` (~400 lines). 16 simulation types across 4 pages, with 30 test scenarios. `SIM_MAP` table with PM3 command templates, `SIM_FIELDS` with per-type input definitions.

### What was broken -- Functionality

**HF trace capture not working (11 tests):**
`_on14ASimStop()` saved trace data internally and returned to sim UI. Should push `SimulationTraceActivity` and send `hf 14a list` to fetch trace from Proxmark3. Ground truth: `trace_scan_flow_20260331.txt` lines 74-77.

**LF simulation never executed (8 tests):**
`_startSim()` called `executor.startPM3Task(cmd, callback=self._onSim)` with a `callback=` kwarg that the PM3 mock doesn't accept. Silently caught by `except (ImportError, AttributeError)`. Fix: run PM3 on background thread with positional args.

**Validation not catching overflow (4 tests):**
`InputMethods.rollUp/rollDown` used full ASCII range (0x20-0x7E) for decimal fields. Digits rolled past '9' to ':' and past '0' to '/'. Fix: added `'dec'` format with 0-9 wrapping.

**Input format set to 'text' instead of 'dec':**
`_showSimUi()` set `fmt = 'hex' if input_type == 'hex' else 'text'`. Decimal fields got 'text' format, bypassing the 0-9 roll fix. Fix: `'dec' if input_type == 'dec'`.

**Field length truncation:**
`length = len(str(max_val))` for decimal fields. IO Prox CN default "65535" (5 digits) with max 999 gave length 3, truncating the value. Fix: `max(len(default), len(str(max_val)))`, later simplified to `len(default)`.

**OK key started simulation instead of editing:**
`_onKeySimUi` treated OK same as M2 (start sim). Test infrastructure uses OK to enter/exit field edit mode. Fix: OK toggles edit, M2 starts sim, M1 exits edit or returns to list.

**M1 stops simulation (not M2):**
`_onKeySimulating` had M2/PWR stopping. Real device M1="Stop" (active), M2="Start" (inactive). Fix: M1/PWR stop.

**7 scenarios navigated to wrong tag type:**
SIM_INDEX values for Jablotron/FDX-B/Nedap were swapped (12-15 mapped incorrectly). Fix: corrected all 7 fixture.py and .sh files, added content verification check.

### What was broken -- UI

**No page indicator on list view:**
Title showed "Simulation" without "X/4". Fix: `_updateTitle()` formats as `"Simulation X/4"`, rendered as separate superscript widget via `setTitle()`.

**No item numbering:**
List showed "M1 S50 1k" instead of "1. M1 S50 1k". Fix: prefix items in `_showListUI()`.

**No RIGHT/LEFT page navigation:**
List only handled UP/DOWN. Fix: added RIGHT/LEFT key handlers that jump by page size.

**No type name on sim UI:**
Missing "AWID ID" / "M1 S50 1k" blue text above fields. Fix: render type name in blue (#1C6AEB) centered.

**Individual cell rendering instead of Select Box + Input Field:**
Each digit was a separate bordered cell. Real device: gray Select Box (#D8D8D8) containing label + white Input Field (#F8FCF8) with dynamic width. Fix: new `SimFields` widget with nested box rendering.

**Wrong background color:**
Content area was #FFFFFF. Real device: #F8FCF8. Fix: device-wide `BG_COLOR` constant change.

**Wrong title font size:**
Was mononoki 18. Fix: reduced to 16pt, x-position shifted -15px.

---

## 2. Resources and Techniques

### Critical resources

| Resource | What it provided |
|----------|-----------------|
| `trace_scan_flow_20260331.txt` lines 71-84 | HF simulation trace: `hf 14a sim` -> `hf 14a list` -> SimulationTraceActivity |
| FB captures `simulation_20260403/` (74 states) | First capture session: M1 S50, Ultralight, Em410x, Ntag215, FDX-B flows |
| FB captures `simulation_multi_20260403/` (86 states) | Second session: Nedap, FDX-B Animal, AWID with detailed editing states |
| `docs/UI_Mapping/07_simulation/README.md` | 52 methods, state machine, field specs, PM3 commands |
| `activity_main_strings.txt` | Binary symbols: `parserHfTraceLen`, `text_processing`, validation functions |
| `sim_common.sh` lines 203-210 | QEMU-verified default values for all multi-field types |
| `/home/qx/compare.png` | User-provided pixel comparison for exact dimensions |

### Framebuffer capture technique
Deployed `/dev/fb1` capture script on real device (240x240 RGB565, 500ms intervals). NO Python patches during FB capture (crashes under resource contention). Converted RGB565 to PNG via PIL, deduplicated by MD5 pixel hash.

### Pixel measurement technique
Used PIL to sample exact RGB values from FB captures at specific coordinates. Measured box dimensions, gap sizes, font positions by scanning for color transitions row by row.

---

## 3. Solutions Implemented

### 3.1 SimFields Widget (`widget.py`)
New widget replacing InputMethods for simulation fields:

```python
class SimFields:
    SELECT_BG = '#D8D8D8'     # outer Select Box
    SELECT_PAD = 3
    INPUT_BG = '#F8FCF8'      # inner Input Field
    INPUT_PAD_X = 7
    INPUT_PAD_Y = 6

    def _redraw(self):
        for i, f in enumerate(self._fields):
            # Select Box (outer gray)
            self._canvas.create_rectangle(box_x, y, box_x + box_w, y + self.BOX_H,
                fill=self.SELECT_BG, outline='')
            # Label inside Select Box
            self._canvas.create_text(box_x + 8, y + self.BOX_H // 2,
                text=f['label'], ...)
            # Input Field (inner white, dynamic width)
            input_w = val_text_w + 2 * self.INPUT_PAD_X
            self._canvas.create_rectangle(input_x, input_y, ...)
            # Cursor highlight on active digit
            if is_editing:
                self._canvas.create_rectangle(cx, ..., fill='#C4C9C4')
```

Box width varies by field count: 219px (1 field), 179px (2), 159px (3+). Focus arrow "<" shown only for multi-field types.

### 3.2 HF Trace Flow
```python
def _on14ASimStop(self):
    # Push trace activity FIRST in loading state
    actstack.start_activity(SimulationTraceActivity,
        {'trace_data': None, 'trace_len': 0, 'loading': True})
    # Fetch trace
    executor.startPM3Task('hf 14a list', 18888)
    trace_text = executor.CONTENT_OUT_IN__TXT_CACHE
    # Update already-pushed trace activity
    top = actstack.get_current_activity()
    top._trace_len = trace_len
    top._showResult()
```

### 3.3 PM3 Execution on Background Thread
```python
def _startSim(self, cmd):
    timeout = -1  # both HF and LF
    def _run_sim():
        executor.startPM3Task(cmd, timeout)
        self._onSim()
    threading.Thread(target=_run_sim, daemon=True).start()
```

### 3.4 Validation Limits
Effective max = min(doc_max, 10^field_digits - 1). Where .so passes raw values, max = digit limit. Nedap Subtype: decimal max 15 (FB proof: state_032 "greater than 15").

### 3.5 Content Verification
Added to `sim_common.sh` after navigation:
```bash
local -a SIM_NAMES=("M1 S50 1k" "M1 S70 4k" ... "FDX-B Data")
local expected_name="${SIM_NAMES[$sim_idx]}"
if ! wait_for_ui_trigger "content:${expected_name}" 5 ...; then
    report_fail "Wrong tag type (expected '${expected_name}')"
fi
```

---

## 4. DRM

No new DRM issues. The DRM mechanism was already solved in the Write flow. `cpuinfo` serial `02c000814dfb3aeb` set in `launcher_current.py`. Simulation doesn't use write.so, so DRM doesn't gate simulation commands. However, the DRM smoke test habit was maintained throughout.

---

## 5. Test Results

### Simulate suite: 28/28 PASS (was 30, 2 removed)
```
TOTAL: 28  PASS: 28  FAIL: 0
```

Removed `sim_gprox_ii_validation_fail` and `sim_pyramid_validation_fail` (no fields can exceed digit-length limits after correction).

Corrected 7 scenario SIM_INDEX values (Jablotron/FDX-B/Nedap swapped).

### Regression suites: 0 regressions
| Suite | Result |
|-------|--------|
| Scan | 45/45 PASS |
| Read | 99/99 PASS |
| Write | 61/61 PASS |
| Auto-Copy | 52/52 PASS |

---

## 6. JSON UI Requirements

`src/screens/simulation.json` defines 3 states:
- `list_view`: 16-type list, no buttons, UP/DOWN/RIGHT/LEFT/M2/OK/PWR keys
- `sim_ui`: input fields, M1="Stop" (dimmed), M2="Start", OK=toggleEdit
- `simulating`: toast "Simulation in progress...", M1="Stop" (active), M2="Start" (dimmed #808080)

Updated during integration:
- Simulating buttons: Stop/Start (was Stop/Stop)
- Simulating keys: M1 stops (was M2)
- Sim UI keys: OK=toggleEdit, M2=startSim (was both OK+M2=startSim)

---

## 7. No-Middleware Rules

### Middleware found and removed

**1. `_isLFTag()` + `_onWriteComplete()` in AutoCopyActivity (audit finding 1+2):**
Hardcoded LF type set deciding auto-verify. Dead code after AutoCopy refactor. Removed entirely.

**2. `_saveSniffData()` no-op (audit finding 8):**
Showed "Trace file saved" toast without saving. Fixed to call `sniff.saveSniffData()`.

**3. `showReadToast()` keyword matching (audit finding 6):**
Parsed message strings for UI routing. Simplified to display-only.

### Validation limits corrected (NOT middleware, but wrong constraints)

Fields where defaults exceeded our max values indicated wrong limits:
- AWID CN default "13371337" > max 65535 -> max corrected to 99999999
- FDX-B ID default "112233445566" > max 4294967295 -> max corrected to 999999999999
- Multiple fields: max set to field-digit-limit instead of doc_max

### Field labels corrected from FB ground truth
- FDX-B Animal: removed "Animal" selector (real device has 2 fields only)
- FDX-B: "ID:" renamed to "NC:" (FB proof)
- FDX-B Data: "Ext:" renamed to "Animal Bit:" (FB proof)

---

## 8. Summary

### High-level problems and solutions

| Problem | Solution | Steps |
|---------|----------|-------|
| HF trace not captured | Push SimulationTraceActivity, send `hf 14a list` | Study trace lines 74-77, implement, verify |
| LF sim never ran | Background thread + positional args | Found `callback=` kwarg mismatch, removed |
| Decimal input rolling to non-digits | Added 'dec' format to InputMethods | Found '/' appearing, added 0-9 constraint |
| All fields individual cells | New SimFields widget | FB captures showed nested Select Box + Input Field |
| 7 wrong type navigations | Corrected SIM_INDEX values | Added content verification check |
| Validation limits too restrictive | Raised to field-digit-limit or removed | Audited each field against real device behavior |
| Pixel dimensions wrong | User-provided comparison image | Exact px values for font, gap, position, colors |
| Page indicator overlapping battery | bbox-based positioning + smaller font | Multiple iterations with visual comparison |

### What would have made this faster

1. **Framebuffer captures from the start.** I spent hours guessing UI dimensions before the user initiated FB captures. Having real device screenshots for EVERY state from day 1 would have eliminated all pixel-guessing iterations.

2. **The nested Select Box + Input Field structure documented explicitly.** I built a flat rendering first, then had to rewrite when the user showed the gray-box-with-white-inner-field structure. A wireframe diagram would have saved the rewrite.

3. **Correct SIM_INDEX values in test fixtures.** 7 scenarios had swapped indices between Jablotron/FDX-B/Nedap. These were pre-existing bugs that silently passed because tests didn't verify content. A content check from the start would have caught these immediately.

4. **"The .so passes raw values" documented per-field.** I set validation limits from the docs (e.g., AWID CN max 65535) but the .so doesn't actually validate some fields. The default "13371337" proved this. Knowing which fields the .so validates vs passes raw would have avoided multiple limit correction iterations.

5. **The cursor effect is a background highlight, not an underline.** I implemented a blue underline cursor. The real device uses #C4C9C4 background on the active digit. A screenshot of editing state from the start would have prevented the wrong implementation.

6. **Button active/inactive states during simulation.** M1="Stop" (active white), M2="Start" (inactive #808080). The dimmed button pattern applies to sim UI M1="Stop" as well. This wasn't clear until user pointed it out with specific FB references.

7. **The `edit_sim_fields` case numbers must match SIM_INDEX values.** When I fixed the SIM_INDEX values in fixtures, the case statement in sim_common.sh still used the OLD numbers. The editing dispatched to the wrong type's field pattern. This coupling wasn't obvious.
