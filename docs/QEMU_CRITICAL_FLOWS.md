# Critical ARM/Tk flows

`critical-v4` is a small package acceptance profile intended for PR CI and
release-candidate validation. Run it for **both** flash and no-flash IPKs using
the same entry point as the [package smoke test](QEMU_TESTS.md):

```bash
sudo bash tools/qemu_env.sh /srv/images/factory.img /usr/bin/qemu-arm-static \
  "$PWD" /srv/runs/critical-001 -- python3 "$PWD/tools/qemu_artifact_smoke.py" \
  /srv/artifacts/icopy-x-noflash.ipk --variant noflash --profile critical
```

Use a new run directory for each execution. The default `smoke` profile remains
available. `critical` includes its package, imports, main-menu and Read Tag menu
checks, then runs the ordered inventory in
[`critical_cases.json`](../tests/qemu_artifact/critical_cases.json).

| Case | Observable contract |
|---|---|
| No card and rescan | All six scan stages finish, show no card, and M2 repeats once |
| Collision | The collision warning appears and no Reader starts |
| Single tag | Exactly one Reader receives the parsed UID/type and normal-read flag |
| Cancel before parsing | PWR exits during a blocked response; the late empty result is ignored |
| Cancel after UID parsing | PWR exits during the Gen1 probe; the late found result is ignored |
| Exit and re-enter | After the old worker finishes, a new activity scans successfully |
| Console round trip | PWR first closes the console without exiting the reading screen |
| Decoder absent | Real discovery with no serial ports reports absence and allows exit |
| Reader success | EM410x scan, real Reader, protocol parser, dump file and success UI agree on the identity |
| Queued Reader completion | The real worker finishes while Tk is paused; PWR discards its queued completion |
| Reader cancellation | PWR exits during a held LF read response; after worker completion, a fresh activity reads successfully |
| Reader failure and retry | An LF reply without tag data saves no dump and offers rescan; the next read succeeds |
| Reader cancellation with overlap | PWR returns while the old response is held; re-entry waits without blocking Tk or replacing the socket, then reads successfully |
| Ultralight full read | Real Reader validates the simulated client file, UID, header and page count before full success |
| Ultralight partial read | Valid partial data is retained and visibly identified as partial |
| Ultralight missing/empty/truncated file | Three cases reject invalid output despite plausible response text and clear the stale write path |
| Ultralight empty response | A completed command without data or a file displays read failure |
| Auto Copy partial Ultralight | The real callback carries partial status to Auto Copy while preserving its path-shaped write bundle |

## What executes and what is substituted

The candidate IPK supplies every application module. Device ARM Python 3.8,
Tcl/Tk, fonts, Pillow and pygame run under QEMU. Scanner worker threads,
executor connection/reset logic, command translation, response parsers, activity
decisions, key dispatch and Tk callbacks execute normally.

The TCP socket is a finite transcript: every wire command must match exactly,
every response must be consumed, and every expected command must occur. A
transport mismatch remains a failure even if application code catches it.
The declared firmware profile is supplied to the translator. The original scan
cases observe Reader dispatch. The five `reader_*` cases run the packaged
Reader, EM410x scan/read parsers, dump saving and ReadActivity through real
threads and Tk callbacks. Dump files go into the disposable worker's `/mnt/upan`.
Audio is silent; HMI abort releases the held response except in the overlap
case, where the harness deliberately holds it across exit/re-entry. That case
uses distinct socket buffers and rejects premature close or overlapping
commands across connections. Unexpected serial opens,
restarts and process execution fail.
The decoder test substitutes an empty port inventory only.

The seven `mfu_*` cases execute the packaged Ultralight reader and simulate the
client-created binary only after the exact dump command matches. Both firmware
profiles use the verified 56-byte header layout. See [ULTRALIGHT_DUMPS.md](ULTRALIGHT_DUMPS.md)
for provenance, capacity/partial rules and the physical failure that remains open.

The successful Iceman response comes from the repository's existing captured
response fixture. Factory-format success, no-card replies and the legacy
collision literal are **synthetic contracts**, identified in `transcripts.json`.
The EM410x cases also use explicitly synthetic, firmware-specific responses.
The collision case protects the UI's handling of `found=True` with the collision
return code; it does not establish that current firmware emits that literal.

These checks do **not** validate RF, actual card reads/writes, the PM3 executable,
firmware detection/flashing, installed startup, the USB stack, or an attached
ICS Decoder. The overlap case establishes scan/read ownership with a held,
complete reply, not remote-daemon recovery after a truncated reply or timeout.
Those boundaries need focused tests and, where relevant, physical acceptance.

`Reader` and `Scanner` hold executor ownership across protocol commands and
parsing of the shared response cache. Cancellation unwinds at executor boundaries,
including after the in-flight call returns, without retrying or starting the
next protocol command. Cancelled workers waiting for ownership can exit without
waiting for the active owner. ReadActivity invalidates callbacks before requesting
hardware abort, requests executor cancellation without waiting on Tk, drops queued
callbacks from old reads, and drains current callbacks on Tk without worker calls to Tk.
An already-running receive retains ownership until it returns; software cancellation
alone cannot guarantee a prompt hardware abort. Files already saved are not rolled back.
Host tests additionally cover late success/failure/progress/exception callbacks,
retry identity, exception classification, and the legacy completion poll.

Host concurrency regressions also cover cancellation before the next protocol
command, separate Readers parsing their own responses, Reader/Scanner overlap,
cancelled waiters, stop before thread entry, and exception/listener cleanup.
Public executor socket/reset/restart entry points serialize with these owners;
legacy callers outside Scanner/Reader do not yet own entire multi-command
protocols or their parsing gaps. This profile does not establish that broader guarantee.

Still pending: reconnect after a partial response or timeout, ownership scopes for
other multi-command operations, and the separate Auto Copy activity's callback
lifecycle. The legacy completion
fallback still infers success from progress when no result callback arrives;
these tests do not establish that inference as proof of a valid card dump.
The bound callback's `__self__` is preserved, but these packages execute Python
`read.py`; direct callbacks from an original binary `read.so` are not validated.

## Maintaining the profile

Contributors run `python -m pytest tests/qemu_runner` and the relevant host tests.
They do not need to provision QEMU or possess the factory image. Maintainers own
the shared runtime and profile; CI supplies execution against built packages.
The [maintenance policy](QEMU_TESTS.md#contribution-and-maintenance-policy) applies.

For a behavior change, describe the expected result and add a host regression
where possible. Extend this profile only when the ARM/runtime or integration
boundary provides additional coverage. Reuse its transport and event-loop
helpers. Change an expectation only with an explained behavior change. A test
must fail when the protected behavior is deliberately broken before it is
accepted as a gate; a passing baseline alone is insufficient.

Each run records case results, wire commands, connection attempts, scan results,
reader dispatches, fixture provenance, substitutions, failures and teardown
errors in `critical.json`. `report.json` also records package/harness hashes and
import provenance. Missing cases, timeouts, pending callbacks or worker errors
cannot pass. Keep failed evidence as well as passing reports.

Automatic worker integration is separate from this profile. Adding these cases
does not by itself activate a required GitHub check or gate release publication.
