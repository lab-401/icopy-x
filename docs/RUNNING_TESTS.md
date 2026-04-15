# Running Tests

## UI Unit Tests (fast, no QEMU needed)

```bash
# All UI tests
python3 -m pytest tests/ui/ -q

# Stop on first failure
python3 -m pytest tests/ui/ -q -x

# Verbose output with short tracebacks
python3 -m pytest tests/ui/ -v --tb=short

# Widget tests only
python3 -m pytest tests/ui/widgets/

# Activity tests only
python3 -m pytest tests/ui/activities/

# Renderer/engine tests only
python3 -m pytest tests/ui/renderer/

# Framework tests only
python3 -m pytest tests/ui/framework/

# Integration tests only
python3 -m pytest tests/ui/integration/

# Single test file
python3 -m pytest tests/ui/activities/test_backlight.py -v

# Single test by name
python3 -m pytest tests/ui/ -k "test_backlight_save" -v

# With coverage
python3 -m pytest tests/ui/ --cov=src/lib --cov-report=term-missing
```

## QEMU Flow Tests (original .so modules)

These run the real .so modules under QEMU with PM3 mock fixtures.
Requires QEMU rootfs mounted at `/mnt/sdcard/root{1,2}/` and Xvfb on `:99`.

```bash
# Prerequisites
sudo mount /dev/sdX1 /mnt/sdcard/root1
sudo mount /dev/sdX2 /mnt/sdcard/root2
Xvfb :99 -screen 0 240x240x24 &

# Run single flow test suite
bash tests/flows/backlight/test_backlight.sh
bash tests/flows/volume/test_volume.sh
bash tests/flows/diagnosis/test_diagnosis.sh
bash tests/flows/scan/test_scans.sh
bash tests/flows/read/test_reads.sh
bash tests/flows/write/test_writes.sh
bash tests/flows/erase/test_erase.sh
bash tests/flows/auto-copy/test_auto_copy.sh
bash tests/flows/simulate/test_simulate.sh
bash tests/flows/sniff/test_sniffs.sh
bash tests/flows/lua-script/test_lua.sh

# Run parallel variants (faster, uses multiple Xvfb displays)
bash tests/flows/scan/test_scans_parallel.sh
bash tests/flows/read/test_reads_parallel.sh
bash tests/flows/write/test_writes_parallel.sh
bash tests/flows/erase/test_erase_parallel.sh
bash tests/flows/auto-copy/test_auto_copy_parallel.sh
bash tests/flows/simulate/test_simulate_parallel.sh

# Settings tests in parallel (backlight + volume)
bash tests/flows/test_settings_parallel.sh
```

## QEMU Flow Tests (with new Python UI)

These run flow tests with our Python modules loaded instead of the original
.so modules. The `run_with_new_ui.sh` wrapper prepends `src/lib` to
PYTHONPATH so Python finds `.py` before `.so` for replaced modules.

```bash
# Run single flow test with new UI
./tools/run_with_new_ui.sh bash tests/flows/backlight/test_backlight.sh
./tools/run_with_new_ui.sh bash tests/flows/volume/test_volume.sh
./tools/run_with_new_ui.sh bash tests/flows/diagnosis/test_diagnosis.sh

# Run all flow tests with new UI
./tools/run_with_new_ui.sh bash tests/flows/scan/test_scans.sh
./tools/run_with_new_ui.sh bash tests/flows/read/test_reads.sh
# ... etc.
```

## IPK Validation

The IPK QEMU integration test validates file structure, module imports,
JSON schemas, QEMU boot, and runs flow test smoke checks.

```bash
# Test a specific IPK file
./tools/test_ipk_qemu.sh dist/icopy-x-oss.ipk

# Test src/ directory structure directly (no IPK needed)
./tools/test_ipk_qemu.sh

# With custom display
TEST_DISPLAY=:98 ./tools/test_ipk_qemu.sh
```

## Test Results

Flow test results are written to `tests/flows/_results/`:
```
tests/flows/_results/
  backlight/
    scenario_summary.txt        # Pass/fail summary
    scenarios/
      backlight_save_low_to_high/
        screenshots/            # Deduplicated state screenshots
        logs/scenario_log.txt   # QEMU boot + PM3 mock log
        result.txt              # PASS/FAIL with reason
        scenario_states.json    # Activity stack + canvas state per frame
  volume/
  diagnosis/
  scan/
  read/
  write/
  ...
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TEST_DISPLAY` | `:99` | X11 display for QEMU rendering |
| `BOOT_TIMEOUT` | `80` | Seconds to wait for QEMU boot |
| `PM3_DELAY` | `3.0` | Simulated PM3 command delay (seconds) |
| `CAPTURE_INTERVAL` | `0.1` | Screenshot capture interval (seconds) |
| `NO_CLEAN` | `0` | Set to `1` to keep previous results |
| `QEMU_TRACE` | (empty) | Set to `1` to enable activity/PM3 trace log |
| `QEMU_BIN` | Auto-detect | Path to `qemu-arm-static` |
