# Read Flow UI Integration — Handover Prompt

Copy everything below this line into a new development tool session.

---

You are continuing work on the iCopy-X open-source firmware reimplementation.

## Your task
Integrate the **Read Tag** flow — `read.so` and related middleware must call back to our Python `ReadActivity` / `ReadListActivity`, displaying correct UI at every step.

## Essential reading (READ ALL BEFORE ACTING)

1. `docs/flows/scan/ui-integration/README.md` — **READ THIS FIRST.** Complete post-mortem of the Scan flow integration. Contains every lesson learned, every mistake to avoid, the correct architecture, and the ground truth rules. The Read flow follows the same patterns.

2. `docs/HOW_TO_INTEGRATE_A_FLOW.md` — Methodology, architecture, ground truth rules, JSON UI system, immutable laws.

3. `docs/Real_Hardware_Intel/full_read_write_trace_20260327.txt` — Real device trace of a complete Read→Write flow for MFC 1K. Shows exact PM3 command sequence, activity transitions, key cracking, block reads.

4. `docs/Real_Hardware_Intel/trace_scan_flow_20260331.txt` — Scan traces (Read starts after scan).

5. `docs/Real_Hardware_Intel/trace_iclass_scan_20260331.txt` — iCLASS scan trace.

6. `decompiled/activity_main_ghidra_raw.txt` — Decompiled activity_main.so. Search for `ReadListActivity`, `ReadActivity`, `onReading`, `onReadFinish`, `startRead`, `initList`.

7. `decompiled/read_ghidra_raw.txt` — Decompiled read.so (if exists, or check `docs/v1090_strings/read_strings.txt`).

8. `docs/v1090_strings/read_strings.txt` — All string literals from read.so.

9. `docs/v1090_strings/activity_main_strings.txt` — Activity class method names and string constants.

10. `docs/Real_Hardware_Intel/Screenshots/` — Real device screenshots (check MANIFEST.txt for read-related files).

11. `src/lib/activity_main.py` — Current activity implementations. ReadListActivity and ReadActivity exist but may not be wired correctly.

12. `src/lib/json_renderer.py` — JSON UI renderer for declarative screen definitions.

## Critical lessons from the Scan flow (DO NOT REPEAT THESE MISTAKES)

### 1. Scanner/Reader API Discovery
The scan.so `Scanner` class API was NOT what we expected. `scanForType(None, self)` did nothing. The correct pattern was:
```python
scanner = scan.Scanner()          # no args
scanner.call_progress = self.onScanning    # bound method, not self
scanner.call_resulted = self.onScanFinish  # bound method, not self
scanner.scan_all_asynchronous()   # no args
```
**Read.so will have its own Reader classes.** Do NOT assume the API. Probe it under QEMU first. Check `docs/v1090_strings/read_strings.txt` for class/method names, then test interactively.

### 2. template.so Renders Results — NOT Python
`template.so` owns ALL tag info display rendering. It has per-type draw functions. Call `template.draw(type, data, canvas)` — do NOT build display logic in Python. The `parent` argument is the **canvas**, not the activity (confirmed via traceback).

### 3. NEVER Invent Middleware
Every line of display code I wrote (`_FAMILY_MAP`, `_resolve_tag_display()`, frequency lookups, field formatting) was WRONG and had to be deleted. template.so does all of this. If you find yourself writing tag-specific display logic, STOP — it belongs in a .so module.

### 4. NEVER Mass-Modify Fixtures
I mass-modified 219 fixtures and broke ALL tests. The mock already handles return code conversion (`ret=0` → `return 1`). The `[usb] pm3 -->` prefix is expected by the .so parsers. Only fix fixtures that are SPECIFICALLY broken, and verify each fix individually.

### 5. Fixture Fixes Need Real Traces
The only 2 fixtures that genuinely needed fixing (scan_iclass, scan_fdxb) were fixed using real device traces and PM3 source code. If a fixture is broken, capture a real trace — don't guess the PM3 response format.

### 6. Parallel Tests Need Display Isolation
Each parallel test thread needs its own Xvfb display. Without this, screenshots cross-contaminate. The remote test runner at `/tmp/run_scan.sh` on `qx@178.62.84.144` has this fix (displays `:50` through `:58`).

### 7. PIL ImageFont.truetype Fails Under QEMU
`_imagingft` C module is not available. Use PIL for RGBA compositing (transparency, icons) and tkinter for text rendering (native mononoki font works fine).

### 8. Canvas Cleanup
When transitioning between states, clear ALL canvas items from previous states. The JSON renderer uses tags `_jr_content`, `_jr_content_bg`, `_jr_buttons`. template.so uses `template.dedraw(canvas)`.

## Ground Truth Rules (ABSOLUTE)

**Only use ground-truth resources:**
1. The original decompiled .so files: `decompiled/*.txt`
2. Real activity traces: `docs/Real_Hardware_Intel/trace_*.txt`
3. Real screenshots: `docs/Real_Hardware_Intel/Screenshots/*.png`
4. **NEVER deviate.** Never invent. Never guess. Never "try something".
5. **ALL work must derive from these ground truths.**
6. **EVERY action** must cite its ground-truth reference.
7. **Before writing code:** Does this come from ground truth? If not, don't.
8. **After writing code:** Audit — does this come from ground truth? If not, undo.

If no ground truth exists, ask the user before proceeding.

### Supplementary ground truth
- PM3 source: `https://github.com/iCopy-X-Community/icopyx-community-pm3` — use when trace responses are truncated
- QEMU API dump: `archive/root_old/qemu_api_dump_filtered.txt` — method signatures
- Live trace methodology: `docs/HOW_TO_RUN_LIVE_TRACES.md` — deploy tracer to real device (tunnel on port 2222, `root:fa`)

## Environment

- Branch: `feat/ui-integrating` at latest commit
- QEMU rootfs: `/mnt/sdcard/root2/root/`
- Remote QEMU server: `qx@178.62.84.144` (password: `proxmark`, sudo: `proxmark`, 48 cores)
- Real device SSH: `sshpass -p 'fa' ssh -p 2222 root@localhost` (tunnel must be established by user)
- Run single test: `TEST_TARGET=current SCENARIO=<name> FLOW=read bash tests/flows/read/scenarios/<name>/<name>.sh`
- Run parallel on remote: use `/tmp/run_scan.sh` pattern with per-thread Xvfb displays

## Working flows (don't break these)
- Volume: 7/7 PASS
- Backlight: 7/7 PASS
- Scan: 45/45 PASS (44 + 1 known `scan_no_console_on_right` flaky)

## What the Read flow involves

From `docs/v1090_strings/activity_main_strings.txt` and `read_strings.txt`:
- `ReadListActivity` — tag type selection list after scan
- `ReadActivity` — actual read operation with progress
- Key cracking: `hf mf fchk` (fast check), `hf mf nested`, `hf mf darkside`, `hf mf hardnested`
- Block reading: `hf mf rdsc`, `hf mf rdbl`, `hf mfu dump`, `hf iclass dump`
- Console output during read (PM3 command log visible to user)
- Multiple read paths per tag type (MFC key cracking, UL direct read, iCLASS key-based, LF clone-read, ISO15693 dump)
- Read result: file saved to `/mnt/upan/dump/`

## Definition of done
1. ReadListActivity correctly shows tag type list after scan
2. ReadActivity drives read.so which sends PM3 commands via mocked executor
3. Progress callbacks update UI during read
4. Read results display correctly via template.so
5. Console output shows during read (if applicable)
6. Read flow tests pass
7. Existing scan/volume/backlight tests still pass
