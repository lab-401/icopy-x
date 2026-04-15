# Install Flow Test Suite — Handover

## Current State: 4/13 PASS (original target)

### Passing scenarios
| Scenario | Flow |
|----------|------|
| `install_ready_cancel` | About→Update(stk=3)→M1→About |
| `install_success_with_fonts` | About→Update(stk=3)→OK→(install runs) |
| `install_ready_pwr` | Passed in isolation, needs timing fix for sequential |
| `install_success_minimal` | Passed in isolation, fails in sequential (isolation issue) |

### Failure Categories

#### Category 1: Test isolation — IPK from prior test pollutes next test
**Affected:** `install_no_ipk`, `install_success_minimal`
**Symptom:** `install_no_ipk` reaches Update(stk=3) despite NONE fixture — leftover IPK from prior test. `install_success_minimal` gets inline 0x03 when it should reach Update.
**Root cause:** The original firmware moves processed IPKs. Even with `find -delete`, timing gaps between cleanup and QEMU boot allow stale state. Sequential tests share `/mnt/upan/`.
**Fix:** Run `install_no_ipk` FIRST (before any IPK-placing test). Consider a pre-boot verification step that confirms the IPK state matches expectations before starting QEMU.

#### Category 2: Toast not captured — install runs but toast appears briefly
**Affected:** `install_checkpkg_invalid_zip`, `install_checkpkg_no_install`, `install_checkpkg_no_version`, `install_install_exception`, `install_error_dismiss_ok`, `install_error_dismiss_pwr`
**Symptom:** Reaches Update(stk=3) then next state shows `?(0)` — QEMU crashed or toast was too brief to capture. The `SLEEP:5` before toast gate wasn't enough.
**Root cause:** Under QEMU, the install pipeline runs fast. The background thread finishes, shows the toast, but the toast may auto-dismiss before the next state dump captures it. Also, `?(0)` empty states suggest QEMU process died (possibly from `restart_app()` calling `os.system("sudo service icopy restart &")`).
**Fix:** Need to either (a) increase capture frequency during install, (b) use a QEMU_TRACE flag to log toast events, or (c) accept that install.so's `restart_app()` kills the QEMU process and treat that as expected behavior.

#### Category 3: DRM check runs inline
**Affected:** `install_checkver_fail`
**Symptom:** Shows `Install failed, code = 0x04` inline at About(stk=2), BUT most recent run shows it DID reach Update(stk=3) at state 4 — inconsistent between runs.
**Root cause:** The original firmware's checkUpdate() sometimes runs checkVer inline, sometimes launches UpdateActivity first. Depends on whether the IPK was previously processed (checkVer cached result?).
**Fix:** Accept both inline and sub-activity paths. Gate should be: `toast:Install failed` OR `title:Update|KEY:OK|toast:Install failed`.

#### Category 4: checkPkg failure path different than expected
**Affected:** `install_checkpkg_no_app`
**Symptom:** Gets inline `Install failed, code = 0x03` at About(stk=2), NOT reaching Update. The IPK without app.py causes checkPkg to fail inline.
**Root cause:** The original firmware's checkPkg runs in AboutActivity BEFORE launching UpdateActivity. If checkPkg fails, it shows the error inline without launching Update.
**Fix:** This scenario's gate should expect the inline error: `toast:Install failed` (not `title:Update`).

### Key Findings from QEMU Testing

1. **OK only triggers checkUpdate from page 2** — must navigate DOWN first
2. **The original firmware has TWO install paths:**
   - **Inline** (stack=2): checkPkg or checkVer fails → toast on About → no UpdateActivity
   - **Sub-activity** (stack=3): IPK passes validation → launches UpdateActivity with READY screen
3. **install.so's `restart_app()` kills the QEMU process** — `sudo service icopy restart &` under QEMU attempts to restart the host service, crashing the test
4. **Toast timing is critical** — the install pipeline runs in a background thread, toasts can appear and dismiss between state dumps
5. **The `?(0)` empty states** indicate the QEMU process crashed, likely from `restart_app()`

### Files
- Fixture generator: `tests/flows/install/fixtures/build_fixtures.py`
- 8 IPK fixtures: `tests/flows/install/fixtures/*.ipk`
- Common infrastructure: `tests/flows/install/includes/install_common.sh`
- 13 scenarios: `tests/flows/install/scenarios/install_*/`
- Parallel runner: `tests/flows/install/test_install_parallel.sh`
- UI mapping: `docs/UI_Mapping/19_install/README.md`
- Real device trace: `docs/Real_Hardware_Intel/trace_update_flow_20260410.txt`
- Real device analysis: `docs/Real_Hardware_Intel/trace_update_flow_analysis_20260410.md`
- Framebuffer captures: `docs/Real_Hardware_Intel/framebuffer_captures/update_flow/png/deduped/`
- install.so analysis: `docs/v1090_strings/install_so_analysis.md`
- install.so decompiled: `decompiled/install_ghidra_raw.txt`
