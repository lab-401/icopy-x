# Console During-Read Handover — 5 failing tests

## What we're trying to achieve

The Read flow has an inline **console view** (ConsolePrinterActivity on the real device, but implemented as a view mode within ReadActivity — NOT a separate activity). The console shows raw PM3 command output (`executor.CONTENT_OUT_IN__TXT_CACHE`).

**Functional requirements:**
1. During reading or on the result screen, pressing **RIGHT** opens the console (full-screen black background with white monospace text)
2. Console keys: UP/M2=zoom in, DOWN/M1=zoom out, LEFT/RIGHT=hscroll, **PWR=back to ReadActivity view**
3. PWR in console mode hides the console and **returns to the ReadActivity screen** (template, buttons, toast if applicable)
4. The console is always the **highest layer** — if a toast fires on ReadActivity while the console is showing (e.g., read completes), the toast must NOT display over the console. Instead, the result is deferred until the user exits the console.
5. When the user presses PWR to exit the console, the deferred toast and buttons appear on the ReadActivity screen.

**5 failing tests** — all `console_during_read`:
- `read_em410x_console_during_read`
- `read_iclass_console_during_read`
- `read_mf1k_console_during_read`
- `read_t5577_console_during_read`
- `read_ultralight_console_during_read`

All fail with: `trigger 'toast:File saved' not reached after console exit`

The `console_on_result` and `console_on_success/failure` tests (4 tests) **PASS**. The `console_during_read` tests fail because the read completes WHILE the console is open, and the deferred toast never appears after console exit.

## Current state: what's happening

The console view IS working:
- RIGHT opens it (full-screen black + PM3 text)
- Zoom gates work (9/9 in on_result tests)
- Scrollbar renders
- Autofit font calculates correct size

The PWR exit does NOT work for `during_read`:
- The read completion dict fires with `success=True` while the console is showing
- `_showReadSuccess()` detects `_console_showing=True` and stores `_pending_result = ('success', partial)`
- The user presses PWR to exit the console
- `_hideConsole()` is supposed to be called, which hides the console and shows the deferred toast
- **BUT `_hideConsole()` is never called** — the state dump after PWR shows a black screen

## Root cause analysis

**PWR key dispatch is broken.** The previous agent identified two issues and attempted fixes, but the problem persists:

### Issue 1: keymap.py PWR shortcut
`src/lib/keymap.py` had `if logical == POWER: self._run_shutdown(); return` which called `actstack.finish_activity()` directly, bypassing `onKeyEvent`. The previous agent removed this to let PWR go through `onKeyEvent`. **Verify this change is correct and complete.**

### Issue 2: Launcher PWR interception
`tools/launcher_current.py` lines 586-608 has SPECIAL PWR handling:
```python
def _inject_key(name):
    if name == 'PWR' and _tk_root:
        # Searches for tkinter Frame containing Text widget
        # If found: destroys it and RETURNS (no key dispatch)
        if _find_console_frame(_tk_root):
            return
```
This searches for a tkinter Frame/Text widget (an old ConsoleView pattern). Our ConsoleView uses Canvas items, not Frame/Text, so this check should fail and PWR should be dispatched normally. **But verify this isn't interfering.**

### Issue 3: Possible state corruption
The previous agent made MANY changes to `activity_read.py` and `widget.py` during this session. Some changes may have introduced bugs:
- The `_pending_result` mechanism stores deferred toast data but `_hideConsole` may not properly consume it
- The `_console_showing` flag may not be in sync with actual console state
- The `onReading` completion handler's interaction with the deferred mechanism needs auditing

**AUDIT THE PREVIOUS AGENT'S CHANGES WITH INTENSE SKEPTICISM.** The agent was iterating rapidly under context pressure and may have introduced logic errors. Read every line of `activity_read.py` and `widget.py` fresh.

## Files modified (by previous agent)

| File | What changed | Risk |
|------|-------------|------|
| `src/lib/activity_read.py` | Major rewrite: console inline view, deferred results, return code mapping, RIGHT key handler | HIGH — many interleaved changes |
| `src/lib/widget.py` | ConsoleView: zoom, hscroll, scrollbar, autofit. Toast: auto-wrap with font reduction | MEDIUM — widget changes |
| `src/lib/keymap.py` | Removed PWR→finish_activity shortcut | HIGH — affects ALL activities |
| `src/lib/actbase.py` | Page indicator tag fix | LOW |
| `src/lib/actstack.py` | Added _result passing from finish to parent via onActivity() | MEDIUM |
| `src/lib/activity_main.py` | ConsolePrinterActivity rewrite, WarningM1Activity fix, ReadListActivity buttons/keys | MEDIUM |
| `src/lib/json_renderer.py` | Extended _render_text with color, y, tag | LOW |
| `tests/flows/read/includes/read_common.sh` | TRIGGER_WAIT 180→45 | LOW |
| Various fixture files | iCLASS elite, EM4305 lf sea responses | LOW |

## Ground truth resources

### Real device traces (AUTHORITATIVE)
- `docs/Real_Hardware_Intel/trace_console_flow_20260401.txt` — **THE KEY TRACE**: user opened/closed console multiple times during a successful MFC read. Shows: **NO activity stack changes**. Console is purely a view toggle within ReadListActivity. Stack stays at `['dict', 'dict']` throughout.
- `docs/Real_Hardware_Intel/trace_read_flow_20260401.txt` — Successful MFC read (no console)
- `docs/Real_Hardware_Intel/trace_fail_read_flow_20260401.txt` — Failed LF read showing WarningT5XActivity push

### Screenshots
- `docs/Real_Hardware_Intel/Screenshots/lua_console_*.png` (10 files) — Real device console appearance: full-screen black bg, white monospace text, NO title bar, NO button bar

### Test infrastructure
- `tests/flows/read/includes/read_console_common.sh` — Complete console test flow with 9 key gates
- Lines 27-35: Key handling spec: `UP/M2=zoom in, DOWN/M1=zoom out, RIGHT=hscroll right, LEFT=hscroll left, PWR=exit`

### Decompiled binary
- `docs/v1090_strings/activity_main_strings.txt` — ConsolePrinterActivity symbols: show, hidden, is_showing, textfontsizeup, textfontsizedown, updatefontinfo, updatetextfont, add_text, clear, on_exec_print

## Immutable rules

1. **Tests are immutable** — NEVER modify test scripts (exception already made for 2 timeout scripts)
2. **No middleware** — ConsolePrinterActivity is pure UI, no RFID logic
3. **Ground truth only** — every change must cite a trace, screenshot, or test expectation
4. **Fixtures immutable** unless you have real trace evidence AND explicit user confirmation
5. **The .so modules are the logic** — our Python is a thin UI shell
6. **94/99 tests currently pass** — do NOT regress them

## Testing

### Run locally (single test)
```bash
TEST_TARGET=current SCENARIO=read_ultralight_console_during_read FLOW=read \
  bash tests/flows/read/scenarios/read_ultralight_console_during_read/read_ultralight_console_during_read.sh
```

### Run full parallel suite on remote (48-core server)
```bash
sshpass -p proxmark rsync -az --exclude='.git' --exclude='tests/flows/_results' --exclude='__pycache__' \
  /home/qx/icopy-x-reimpl/ qx@178.62.84.144:/home/qx/icopy-x-reimpl/

sshpass -p proxmark ssh -o ServerAliveInterval=30 qx@178.62.84.144 \
  'cd ~/icopy-x-reimpl && TEST_TARGET=current bash tests/flows/read/test_reads_parallel.sh 16'
```
Results: `tests/flows/_results/current/read/scenario_summary.txt` on the remote server.

### Scan regression
```bash
sshpass -p proxmark ssh qx@178.62.84.144 \
  'cd ~/icopy-x-reimpl && TEST_TARGET=current bash tests/flows/scan/test_scan_parallel.sh 16'
```
Must stay 45/45.

## Overall context

We're finishing the **Read flow UI integration** on branch `feat/ui-integrating`. The session went from 52/99 → 94/99 read tests passing. The 5 remaining are all `console_during_read`. The scan flow (45/45), volume (7/7), and backlight (7/7) all pass.

The previous agent was at 65% context usage and making rapid iterative changes. The keymap.py PWR change and the deferred-toast mechanism need fresh-eyes auditing against the ground truth.
