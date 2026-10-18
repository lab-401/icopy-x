# QEMU flow runner

The canonical runner executes the existing scenario scripts directly. The old
suite summaries could hide failures, omit missing results and count console
cases twice. A pass now requires a zero scenario exit status and exactly one
fresh `PASS: ...` result. Timeouts, missing/malformed results and unexecuted
cases cannot pass. JSON results distinguish application FAIL, infrastructure
ERROR and INCOMPLETE.

Run in an isolated Linux QEMU environment with the expected ARM rootfs, QEMU,
Xvfb and ImageMagick. The runner does not provision these dependencies.

```bash
TEST_TARGET=current bash tests/flows/run_all_flows.sh --list
TEST_TARGET=current bash tests/flows/run_all_flows.sh --flow read --case 'read/*console*'
TEST_TARGET=current bash tests/flows/run_all_flows.sh --timeout 600
```

`tests/test_all_flows.sh` delegates to the same runner. Specify `current` or
`original` explicitly; there is no implicit original-firmware target. These
are source-mode profiles, not proof of executing a built IPK. The mixed
`original_current_ui` launcher mode is not an accepted package validation mode.

Runs use a new directory under `tests/flows/_results/run-*`, or a new path
supplied with `--results`. Existing output directories are rejected. The frozen
case inventory, results and remaining incomplete cases appear in
`master_summary.json`; individual scenarios retain screenshots and logs.
Missing scenario entrypoints, empty selected flows and unmatched filters are
errors. Install scenarios are not in this general-purpose suite; they need a
separate, disposable installer environment and acceptance profile.

Scenarios run serially because their helpers share device filesystem paths.
The former worker-count argument accepts only `1`; greater values fail rather
than introducing concurrent filesystem interference. Xvfb allocates a free
display for each case. Cleanup targets owned process groups, not other QEMU or
Xvfb jobs by process name. The existing per-flow parallel scripts remain legacy
development tools and are not used as the authoritative aggregate gate.

This runner fixes execution/accounting, not every scenario assertion or the
PM3 mocking boundary. A green result still needs the scenario and fixture audit
required by the boundaries in [HOST_TESTS.md](HOST_TESTS.md). Run harness contracts
without a device or rootfs using `python -m pytest tests/qemu_runner`.

## Isolated factory-image environment

`tools/qemu_env.sh` is a maintainer-operated Linux wrapper for **trusted** test
commands. It needs sudo, util-linux (`unshare`, `mount`, `findmnt`, `sfdisk`),
Python 3, overlayfs, a factory SD image and an explicitly selected static ARM
QEMU binary. Runtime/flow tests also need Xvfb; flow screenshots use ImageMagick.
It is ARM user-mode emulation: no device kernel, USB hardware or RF is emulated.
This is not a security sandbox for contributor code: the non-root test account
still has its normal host filesystem and network access. CI needs a disposable
worker without credentials or physical-device access.

Use a clean checkout (a Git worktree is supported), with inputs and a new output
directory outside `/mnt` and `/tmp`. The output parent must already exist.
Paths containing mount-option separators (comma, colon, backslash or newline)
are rejected. Run from the non-root account that will own test results:

```bash
sudo bash tools/qemu_env.sh /srv/images/factory.img /usr/bin/qemu-arm-static \
  "$PWD" /srv/runs/runtime-001 -- /usr/bin/python3 "$PWD/tools/qemu_runtime_smoke.py"

sudo bash tools/qemu_env.sh /srv/images/factory.img /usr/bin/qemu-arm-static \
  "$PWD" /srv/runs/scan-001 -- /usr/bin/python3 "$PWD/tests/flows/run_all_flows.py" \
  --target current --flow scan --case scan/scan_no_tag \
  --results /srv/runs/scan-001/results/flows
```

The wrapper validates the image's Linux root partitions, mounts them using
read-only auto-clearing loop devices with journal replay disabled, then creates
separate writable overlays. Its mount/PID namespaces hide the host's `/mnt`
and `/tmp`; `/mnt/upan` is new scratch data, not the host's shared directory.
Only the command runs as the original sudo user. Namespace termination kills
remaining descendants; normal cleanup unmounts the owned mounts in reverse order.
Signals INT, TERM and HUP sent to the wrapper terminate its owned namespace and
record `INTERRUPTED`. Killing only the outer shell with SIGKILL cannot run this
handler: a supervisor must terminate the owned process group for forced stops.
There are no package installations or edits to the original image/checkout.

The overlays deliberately use `xino=off`: with encoded 64-bit overlay inodes,
the old 32-bit ARM font stack failed to enumerate device fonts and could crash
Tk font measurement. A private Fontconfig file selects the image's real fonts.
The runtime smoke requires actual mononoki enumeration, measurement and canvas
rendering, and rejects Python/Tcl callback errors. It does not mock fonts.

Each run retains `environment.json` (image/QEMU hashes, versions, source commit,
dirty status/diff hash, wrapper hash, command and exit status), guest input hashes,
`command.log`, writable overlay state and `results/`. A command exit of zero is
reported as `COMMAND_COMPLETED`, not an application test pass: inspect its test
report. A dirty checkout is visible but is not fully reproducible from its commit;
untracked inputs must be retained separately. Use clean revisions for acceptance.
Image hashing can take several minutes before the command starts.

Validated lab inputs: factory image SHA-256
`345114e012aa5e6fedd9d33821dd864ff3800cb657665247760770c0215369e6`,
QEMU 7.2.0 SHA-256
`9f07762a3cd0f8a199cb5471a92402a4765f8e2fcb7fe91a87ee75da9616a806`,
ARM Python 3.8.0 and Tcl/Tk 8.6.5. The image was verified against a streaming
extraction of the supplied factory archive. Image assets are not redistributed
by this repository. Record your own image and emulator identities; the example
`/usr/bin` path is not a version guarantee.

Run the runtime smoke twice with new directories before diagnosing application
failures. The legacy `tools/setup_qemu_env.sh` changes shared machine state and
is not part of this isolated workflow. Existing flow fixtures still need audit;
the new environment does not make their expectations authoritative.

## Built IPK smoke test

`tools/test_ipk_qemu.sh` now requires an explicit package and variant. It reads
the project's ZIP-format IPKs and runs the **extracted package** under ARM
Python, with no checkout or original application directories on `sys.path`.
Missing QEMU prerequisites fail; they cannot be counted as successful skips.

```bash
sudo bash tools/qemu_env.sh /srv/images/factory.img /usr/bin/qemu-arm-static \
  "$PWD" /srv/runs/package-001 -- bash "$PWD/tools/test_ipk_qemu.sh" \
  /srv/artifacts/icopy-x-noflash.ipk --variant noflash
```

Run flash and no-flash artifacts separately, using exact candidate CI outputs.
Each result retains the IPK digest, extracted-file digests, harness digests,
PM3/client/Lua/firmware asset digests, imported application module paths/hashes,
dependency paths and guest logs. Unsafe archive paths, special files, duplicate
entries, missing/empty required files and incorrect firmware presence fail.
Asset hashes record identity; they do not alone prove a compatible client/Lua
pair. Keep the existing build/content checks and configuration-specific tests.

The guest compiles every packaged Python file with device Python 3.8, imports
core UI/middleware/startup modules, renders the main menu, enters the Read Tag
type list through activity key dispatch, returns and checks teardown callbacks.
Tk, Pillow, pygame and fonts are real. It redirects `config._CONF_PATH` to the
extracted package's data only; it does not mock activity decisions, cryptography,
process exits or hardware responses. Imported application files must hash-match
the archive. Runtime dependencies come from the pinned image.

This is a **module/rendering smoke test**, not application startup or installation
acceptance. It bypasses `app.py`, `main.main()` and `application.startApp()`,
does not initiate scans or writes, and does not run the packaged PM3 client or
flash firmware. These remaining boundaries need separate tests. A selected
package variant describes its contents, not an emulated PM3 firmware version.
The legacy source-flow launcher remains a different, heavily mocked profile.

## Contribution and maintenance policy

The [critical flow profile](QEMU_CRITICAL_FLOWS.md) extends the built-IPK smoke
with eight bounded scan/UI/accessory-absent cases for each firmware configuration.
It uses real translation and parsing with explicitly documented transport
fixtures. It is separate from the unaudited legacy scenario inventory.

Contributors do not need a device, a factory image or a QEMU server to submit a
fix. Start with the commands in [HOST_TESTS.md](HOST_TESTS.md); add a focused
host regression test for the behavior being changed when it can be exercised
there. Describe any remaining ARM, packaging or hardware boundary in the PR.
The [critical QEMU workflow](QEMU_CI.md) runs both candidate CI-built IPKs on
disposable hosted workers. Maintainers run additional relevant lab checks.
Do not create a separate emulator setup or bespoke shell harness for each PR.

The layers have different responsibilities:

| Layer | Responsibility | Current execution |
|---|---|---|
| Host and package checks | Fast logic, translation and flash/no-flash content regressions | Existing GitHub Actions workflows |
| QEMU harness contracts | Missing results, nonzero exits, timeouts, stale output and invalid archives must fail | Linux host CI; `python -m pytest tests/qemu_runner` |
| Real ARM runtime, IPK smoke and critical flows | Device Python, imports, real Tk/fonts, package navigation and bounded scan/UI contracts | Disposable hosted CI; the same profile can run in the lab |
| Legacy source scenarios | Candidate behavior checks with mocked PM3 responses | Exploratory until each scenario and fixture is audited |
| Physical acceptance | USB, RF, accessory behavior, firmware and installation on hardware | Selected checks for the changed hardware boundary |

Passing harness contracts is not an emulation run: the separate **QEMU critical
flows** status requires both real ARM runs. See [activation and repository-rule
requirements](QEMU_CI.md#activation-and-limits). The legacy inventory of 417 scenarios is not 417
validated behaviors: sampled cases contained stale expectations and incorrect
menu navigation. Do not make that entire suite a required gate or weaken its
assertions merely to obtain a green result.

Repository maintainers own the shared environment, image/emulator identities,
helpers and acceptance profiles. Contributors own the intended behavior and
regression evidence for their change; a maintainer can supply the lab execution.
Keep future scenario additions small and reuse shared helpers. Prefer observable
results and exact command/response expectations over private implementation
details, arbitrary sleeps or screenshot counts. Screenshots remain diagnostics.

Before promoting a scenario to a required check, record its purpose, supported
configuration, fixture provenance and maintained entry point. Review where it
mocks hardware: bypassing the command translation layer cannot validate that
layer. Confirm the test passes repeatedly from clean state and fails when the
targeted behavior is deliberately broken. Intentional differences from factory
firmware need explicit expectations; factory parity is not always the goal.

For acceptance runs, retain source/harness revisions, exact IPK and environment
hashes, case selection, logs and all failures or skips. Changes to the environment
need repeat runtime smoke runs plus failure/interruption cleanup checks; changes
to the package harness need both variants and a deliberately broken package.
Review changed expectations in the same PR as an intentional behavior change,
explaining why. Do not automatically regenerate expected outputs to match failures.

Keep the required set small and reliable. A flaky check needs a tracked issue,
an accountable maintainer and a review deadline; removing it from the gate must
leave the coverage gap visible. Repair, replace or explicitly retire obsolete
tests. Revisit the matrix when supported firmware, runtime dependencies or build
contents change. Unavailable hardware remains pending, not passed.

The hosted workflow uses a pinned environment and exact build artifacts, with
candidate execution isolated from credentials and device access. Keep this
required profile small; reserve broader audited scenarios for affected areas
and scheduled regression runs.
Do not execute unreviewed PR code with sudo on the shared SSH lab. A model review
can flag missing coverage and scope creep, but cannot substitute for these checks.
