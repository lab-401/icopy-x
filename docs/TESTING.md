# Testing

Two test categories exist: **UI tests** (fast, headless, pytest) and
**flow tests** (QEMU-based, end-to-end, bash scripts).

## UI Tests

Located in `tests/ui/`. These test individual activities, widgets, the JSON
renderer, the plugin system, and the PM3 compatibility layer. They use a
`MockCanvas` (in-memory tkinter replacement) so no X display or Tk mainloop
is required at the unit level. Integration tests that create real Tk windows
need Xvfb.

### Running

```bash
# Set PYTHONPATH so imports resolve correctly
export PYTHONPATH=src/lib:src:src/middleware

# Start a virtual framebuffer (needed for integration tests)
Xvfb :99 -screen 0 320x240x24 &
export DISPLAY=:99

# Run all UI tests
python3 -m pytest tests/ui/ -v --tb=short

# Run a single test file
python3 -m pytest tests/ui/activities/test_scan_tag.py -v

# Run tests matching a pattern
python3 -m pytest tests/ui/ -k "test_pm3_compat" -v
```

### Test Structure

```
tests/ui/
  conftest.py             # MockCanvas, shared fixtures
  activities/             # Per-activity tests (scan, read, write, etc.)
  framework/              # Activity stack, lifecycle, state machine tests
  integration/            # Full-stack tests with real Tk windows
  renderer/               # JSON renderer tests
  widgets/                # Widget-level tests
  test_plugin_*.py        # Plugin system tests
  test_pm3_compat.py      # PM3 command translation tests
  test_pm3_flash.py       # PM3 firmware flash safety tests
```

The top-level `conftest.py` configures `sys.path` so that `src/lib/`,
`src/`, and `src/middleware/` are on the import path. It supports a
`--target` flag (`current` or `original`) to switch between the open-source
Python modules and the original `.so` binaries.

### Parallelism

UI tests are stateless and can run in parallel:

```bash
python3 -m pytest tests/ui/ -n auto  # requires pytest-xdist
```

## Flow Tests

Located in `tests/flows/`. These run the full application under QEMU
(emulating the ARM binary environment), inject PM3 fixture responses, send
key events, and validate UI state via screenshots and state dumps.

### Prerequisites

- `qemu-arm-static` (QEMU user-mode ARM emulation)
- iCopy-X rootfs mounted at `/mnt/sdcard/root2/root/`
- Xvfb for display
- PIL/Pillow for screenshot validation

### Running

Each flow has a runner script and scenario subdirectories:

```bash
# Run all scan scenarios
bash tests/flows/scan/test_scans.sh

# Run a single scenario
SCENARIO=scan_em410x bash tests/flows/scan/scenarios/scan_em410x/scan_em410x.sh

# Run all flows
bash tests/test_all_flows.sh

# Run on a remote QEMU server (for large test suites)
bash tests/run_full_suite_remote.sh qx@178.62.84.144 9
```

### Flow Test Structure

```
tests/flows/
  scan/
    includes/scan_common.sh     # Shared scan test infrastructure
    scenarios/
      scan_em410x/
        scan_em410x.sh          # Scenario runner
        fixture.py              # PM3 response fixtures
        expected.json           # Expected UI states
      scan_hid_prox/
        ...
    test_scans.sh               # Run all scan scenarios
    test_scans_parallel.sh      # Parallel variant
  read/
  write/
  erase/
  auto-copy/
  ...
  _results/                     # Test output (screenshots, logs, summaries)
```

Shared infrastructure lives in `tests/includes/common.sh`. It handles QEMU
boot, display setup, fixture injection, key event sending, and screenshot
capture.

### Parallelism

Flow tests that use QEMU need separate X displays to avoid conflicts.
The infrastructure supports this via `TEST_DISPLAY`:

```bash
TEST_DISPLAY=:99 bash tests/flows/scan/scenarios/scan_em410x/scan_em410x.sh &
TEST_DISPLAY=:100 bash tests/flows/scan/scenarios/scan_hid_prox/scan_hid_prox.sh &
```

Parallel runners (`test_scans_parallel.sh`) handle display allocation
automatically. However, flows that share mutable state (backlight and volume
both write to `conf.ini`) **must run sequentially**.

### Test Targets

The `TEST_TARGET` environment variable controls which implementation is
tested:

| Target | Description |
|--------|-------------|
| `original` | Boots via `application.so`, uses original `.so` modules |
| `current` | Boots via `launcher_current.py`, uses open-source Python modules |

Results land in `tests/flows/_results/{target}/` so original and current
results never overlap.

## Adding New Tests

### New UI Test

1. Create `tests/ui/activities/test_my_activity.py`
2. Import `MockCanvas` from the `conftest` fixtures
3. Instantiate the activity with a mock canvas
4. Call lifecycle methods (`onCreate`, `onResume`) and key events
5. Assert canvas state using `MockCanvas` introspection methods

```python
def test_my_screen_renders_title(mock_canvas):
    activity = MyActivity()
    activity._canvas = mock_canvas
    activity.onCreate(bundle={})
    activity.onResume()
    # Check that title text was drawn
    items = mock_canvas.find_withtag("title_text")
    assert len(items) > 0
```

### New Flow Test

1. Create `tests/flows/{flow}/scenarios/{scenario}/`
2. Add `fixture.py` with PM3 response data (constants only, no logic)
3. Add `expected.json` with expected UI states to validate
4. Add `{scenario}.sh` that sources the common infrastructure and runs
5. Register the scenario in the flow's `test_{flow}s.sh` runner

Fixtures must be pure data -- string responses that the PM3 client would
return for specific commands. Never put branching logic or function calls
in fixture files.

## Coverage

```bash
python3 -m pytest tests/ui/ --cov=src/lib --cov-report=term-missing
```

The `verify_coverage.py` tool reports PM3 command coverage per middleware
module:

```bash
python3 tools/verify_coverage.py --scope all
```
