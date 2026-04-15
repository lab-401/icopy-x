# Tools Reference

## Walkers

| Tool | Purpose |
|------|---------|
| `walkers/walk_all_reads.py` | Read Tag parallel QEMU walker. 40/40 types, 400+ scenarios, 0 failures. |
| `walkers/walk_scan_scenarios.sh` | Scan Tag sequential walker. 44 scenarios. |
| `walkers/walk_scan_parallel.sh` | Scan Tag parallel walker (4 workers). |

## Fixtures & Verification

| Tool | Purpose |
|------|---------|
| `pm3_fixtures.py` | PM3 mock response fixtures. 52 scan + 73 read + 36 write + 5 erase + 7 autocopy + 3 diagnosis + 3 sniff = 179 total. |
| `verify_coverage.py` | **Step 4 verification.** Scoped .so string coverage checker. Categorizes strings (PM3_CMD, BRANCH, REGEX, UI_TEXT, INTERNAL), reports CRITICAL/WARNING/INFO gaps. |
| `xref_strings.py` | Legacy cross-reference tool (superseded by verify_coverage.py). |
| `read_list_map.json` | 40-item Read Tag list positions verified from real device. |

## QEMU Infrastructure

| Tool | Purpose |
|------|---------|
| `minimal_launch_090.py` | QEMU launcher. Executor mock, showScanToast bridge, key injection, _direct_read_flow. |
| `qemu_shims/` | Python shims for Cython modules under QEMU (resources, tagtypes, etc). |

## Usage

### Run Read walker
```bash
python3 tools/walkers/walk_all_reads.py --workers 8
python3 tools/walkers/walk_all_reads.py --workers 1 --filter "viking_id__success"
```

### Run Scan walker
```bash
bash tools/walkers/walk_scan_scenarios.sh       # sequential
bash tools/walkers/walk_scan_parallel.sh         # parallel (4 workers)
```

### Step 4 Verification (scoped string coverage)
```bash
python3 tools/verify_coverage.py --scope read    # Read Tag
python3 tools/verify_coverage.py --scope scan    # Scan Tag
python3 tools/verify_coverage.py --scope write   # Write Tag
python3 tools/verify_coverage.py --scope all     # All scopes
python3 tools/verify_coverage.py --scope read --json results.json  # Export
```

### Run on remote QEMU server
```bash
sshpass -p 'proxmark' ssh qx@104.248.162.214 \
  "cd ~/icopy-x-reimpl && python3 tools/walkers/walk_all_reads.py --workers 8"
```

## Walker Output

Each Read scenario produces in `docs/screenshots/Read/walker_v4/{name}/`:
- `pre_ok.png` — screenshot before pressing OK (entry verification)
- `state_NNN.png` — deduplicated unique frames during scan+read
- `final.png` — final screenshot after toast dismiss
- `log.txt` — QEMU process log with PM3 commands and toast hooks

Each Scan scenario produces in `docs/screenshots/Scan/scenarios/scan_{type}/`:
- `state_NNN.png` — deduplicated unique frames

## Verification Output

`verify_coverage.py` reports per scope:
- **PM3_CMD** — PM3 commands in .so vs fixtures (target: 100%)
- **BRANCH** — Branch-determining keywords in .so vs fixture responses (target: 100%)
- **REGEX** — Parsing patterns from .so (INFO — documented, not in fixtures)
- **CRITICAL** — Missed branch keywords that affect logic flow
- **Per-module** — Coverage breakdown per .so file

## Validation Levels (Walker)

| Status | Meaning |
|--------|---------|
| ELT (all caps) | Entry + Log + Toast all PASS |
| Elt, ELt, etc. | Lowercase = that check FAILED |
| BOOT_FAIL | QEMU didn't start |
