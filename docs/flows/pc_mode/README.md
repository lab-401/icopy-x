# PC Mode Flow -- Specification & Integration Guide

You are continuing work on the iCopy-X open-source firmware reimplementation.

## Your task

Build **Phase 1** (flow scenarios validated against original firmware) and **Phase 2** (open-source Python UI layer) for the **PC Mode** flow (`PCModeActivity`). This is a system UI flow for USB mass storage. The activity manages USB gadget kernel modules -- **NO PM3 TAG COMMANDS**, but it DOES interact with `gadget_linux.so`, `hmi_driver.so`, and `executor.so` for USB/PM3 plumbing.

---

## TWO ABSOLUTE LAWS

### LAW 1: NO MIDDLEWARE
PCModeActivity is a **USB gadget controller**. It toggles kernel modules (`g_mass_storage`) and bridges the PM3 serial connection via socat. It does NOT send PM3 RFID commands (`hf`, `lf`, etc.). The `.so` modules (`gadget_linux`, `hmi_driver`, `executor`) handle ALL USB plumbing.

If you find yourself writing PM3 scan/read/write commands, RFID protocol logic, or tag-specific code -- **STOP. You are violating Law 1.**

Note: The Erase flow is the ONLY justified middleware exception in this project. See `docs/flows/dump_files/ui-integration/README.md` Section 6.3 for why Erase was an exception. PC Mode has NO such exception -- `gadget_linux.so` owns the USB gadget logic.

### LAW 2: NO CHANGING SCENARIOS (Phase 2)
Once Phase 1 scenarios pass with `--target=original`, they are **IMMUTABLE** for Phase 2.

---

## Essential reading (READ ALL BEFORE ACTING)

1. `docs/HOW_TO_BUILD_FLOWS.md` -- **READ FIRST.** Flow scenario methodology.
2. `docs/HOW_TO_INTEGRATE_A_FLOW.md` -- Integration methodology, JSON UI system.
3. `docs/flows/dump_files/README.md` -- **MODEL SPEC.** Complete handover format.
4. `docs/flows/dump_files/ui-integration/README.md` -- **POST-MORTEM.** QEMU LD_PREFIX, per-gate validation, no-middleware rules.
5. `docs/UI_Mapping/08_pcmode/README.md` -- UI specification for PC Mode.
6. Real device screenshot:
   - `docs/Real_Hardware_Intel/Screenshots/pc_mode.png` -- IDLE state

---

## Activity Overview

| Property | Value |
|----------|-------|
| Activity class | `PCModeActivity` |
| ACT_NAME | `'pcmode'` |
| Menu position | Index 6 (`GOTO:6`) |
| Binary source | `activity_main.so` (13 methods decompiled) |
| PM3 tag commands | **NONE** |
| External modules | `gadget_linux.so` (USB gadget), `hmi_driver.so` (PM3 HW), `executor.so` (PM3 ctrl) |

---

## State Machine (from decompiled binary + real device screenshot)

### State: IDLE (initial)
- **Title:** `"PC-Mode"` (resources key: `pc-mode`)
- **Content:** BigTextListView with `"Please connect to\nthe computer.Then\npress start button"` (resources key: `connect_computer`)
- **Buttons:** M1="Start", M2="Start"
- **Keys:** M1/M2/OK = start PC mode (-> STARTING), PWR = finish()
- **Screenshot:** `pc_mode.png`

### State: STARTING (transient)
- **Toast:** `"Processing..."` (resources key: `processing`)
- **Buttons:** disabled (both hidden)
- **Keys:** ALL ignored (no user interaction during startup)
- **Background thread executes:**
  1. `gadget_linux.upan_and_serial()` -- set up USB mass storage + serial gadget
  2. `start_socat()` -- bridge `/dev/ttyGS0` to `TCP:localhost:18888`
  3. `wait_for_pm3_online()` -- poll until PM3 responds
  4. `hmi_driver.presspm3()` -- wake PM3 hardware
  5. `executor.startPM3Ctrl()` -- start PM3 control channel
- **On success:** -> RUNNING
- **On failure:** -> IDLE (with error handling)

### State: RUNNING
- **Title:** `"PC-Mode"` (unchanged)
- **Content:** unchanged (connection instructions still visible)
- **Toast:** `"PC-mode Running..."` (resources key: `pcmode_running`)
- **Buttons:** M1="Stop", M2="Button"
- **Keys:** M1/M2/PWR = stop PC mode (-> STOPPING)
- **Audio:** `audio.playPCModeRunning()` (best-effort)

### State: STOPPING (transient)
- **Buttons:** disabled (both hidden)
- **Keys:** ALL ignored
- **Background thread executes:**
  1. `stop_socat()` -- kill socat process
  2. `kill_child_processes()` -- enumerate and kill child PIDs
  3. `gadget_linux.kill_all_module()` -- tear down USB gadget
  4. `hmi_driver.restartpm3()` -- restart PM3
  5. `executor.reworkPM3All()` -- reinitialize PM3 connections
- **On completion:** -> finish() (exits activity entirely)

---

## Logic Tree

```
PCModeActivity
  |
  +-- IDLE state
  |     |-- Title: "PC-Mode"
  |     |-- Content: connection instructions
  |     |-- M1="Start", M2="Start"
  |     |-- M1/M2/OK -> STARTING
  |     +-- PWR -> finish()
  |
  +-- STARTING state (background thread)
  |     |-- Toast: "Processing..."
  |     |-- Buttons: disabled
  |     |-- Keys: all ignored
  |     +-- On complete -> RUNNING
  |
  +-- RUNNING state
  |     |-- Toast: "PC-mode Running..."
  |     |-- M1="Stop", M2="Button"
  |     |-- M1/M2 -> STOPPING
  |     +-- PWR -> STOPPING
  |
  +-- STOPPING state (background thread)
        |-- Buttons: disabled
        |-- Keys: all ignored
        +-- On complete -> finish()
```

---

## Proposed Scenarios

| # | Scenario | Tests | Min Triggers |
|---|----------|-------|-------------|
| 1 | `pcmode_idle` | IDLE state: title, content, buttons | title:PC-Mode, M1:Start, M2:Start, content:connect |
| 2 | `pcmode_pwr_exit` | PWR from IDLE exits | title:PC-Mode then finish |
| 3 | `pcmode_start` | M2 starts, shows Processing toast, transitions to RUNNING | toast:Processing, M1:Stop |
| 4 | `pcmode_start_m1` | M1 also starts (same as M2) | toast:Processing, M1:Stop |
| 5 | `pcmode_running` | RUNNING state: buttons Stop/Button, toast Running | M1:Stop, toast:Running |
| 6 | `pcmode_stop` | M1 from RUNNING stops and exits | M1:Stop then finish |
| 7 | `pcmode_stop_pwr` | PWR from RUNNING stops and exits | similar to stop |
| 8 | `pcmode_keys_ignored_starting` | Keys during STARTING are ignored | buttons disabled |
| 9 | `pcmode_keys_ignored_stopping` | Keys during STOPPING are ignored | buttons disabled |

### IMPORTANT: USB Gadget Mocking

Under QEMU, `gadget_linux.so` will fail (no USB gadget hardware). The test fixture must mock:
- `gadget_linux.upan_and_serial()` -- return success
- `gadget_linux.kill_all_module()` -- return success
- `hmi_driver.presspm3()` / `hmi_driver.restartpm3()` -- no-op
- `executor.startPM3Ctrl()` / `executor.reworkPM3All()` -- no-op
- `subprocess.Popen` for socat -- mock or no-op

---

## Validation Rules

Each scenario MUST validate at least 2 of:
- **Title** (`title:PC-Mode`)
- **Button text** (`M1:Start`, `M2:Start`, `M1:Stop`)
- **Button state** (active/inactive/visible)
- **Content text** (`content:connect`, `content:computer`)
- **Toast text** (`toast:Processing`, `toast:Running`)

State count is a SMOKE TEST only.

---

## Running tests

```bash
# Single scenario
TEST_TARGET=original SCENARIO=pcmode_idle FLOW=pc_mode \
  bash tests/flows/pc_mode/scenarios/pcmode_idle/pcmode_idle.sh

# Full suite
TEST_TARGET=original bash tests/flows/pc_mode/test_pc_mode_parallel.sh
```

---

## Key files

| File | Purpose |
|------|---------|
| `src/lib/activity_main.py` | PCModeActivity (L1384-1679) |
| `src/screens/pc_mode.json` | JSON UI state machine (to be created) |
| `src/lib/resources.py` | Strings: `pc-mode`, `start`, `stop`, `button`, `processing`, `pcmode_running`, `connect_computer` |

---

## Environment

- Branch: `feat/ui-integrating`
- Remote: `qx@178.62.84.144` (password: `proxmark`, 48 cores)
- GOTO index: `GOTO:6` (menu position for PC-Mode)
- Fixtures: Mock USB gadget modules (no real hardware under QEMU)
