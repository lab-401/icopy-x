# PM3 client and FPGA build contract

The Iceman client, PM3 ARM firmware and FPGA image must agree on the iCopy-X
platform (`PM3ICOPYX`, XC3S100E, bitstream part `3s100evq100`). Successful
compilation alone does not establish this agreement.

## Why v1.1.7 reports an FPGA chip mismatch

Upstream v4.23346 defines `ICOPYX` in `client/Makefile` but does not define
`XC3`. Its `common_fpga/fpga.h` consequently selects the legacy
`FPGA_TYPE` value `2s30vq100`. The firmware build supplies both definitions and
embeds the correct iCopy-X bitstream. The client's `hw version` compares these
identifiers and reports a mismatch.

Our original patch added `XC3`, but included trailing Makefile context that
changed upstream. Release build
[38370618121](https://github.com/lab-401/icopy-x/actions/runs/38370618121)
logged `Skipped: pm3_client_icopyx_xc3.patch` and continued successfully.
Commit `44a4e60` repaired the patch context. The remaining gaps were the silent
skip policy and companion-client jobs which never applied the correction.

Physical testing independently confirmed the diagnosis: the installed/release
client warned, the corrected client did not, and restoring the old client
restored the warning. PM3 OS and FPGA identities were unchanged in all three
observations. Flashing the FPGA is not the correction for this client defect.

## What CI builds

- A fresh clone at the resolved upstream tag supplies each job. The tag is
  resolved to a full commit once; every client and firmware checkout must match
  that commit, including companion clients. A tag moving during a run fails
  verification instead of silently mixing source revisions.
- The ARM device client compiles inside Ubuntu 16.04 for the device's glibc.
  Linux, Windows and macOS companion clients compile on their respective runners.
- The PM3 ARM `fullimage` compiles from source. Bootrom is not built or flashed.
- The build embeds the upstream **prebuilt** `fpga/fpga_icopyx_hf.bit` selected
  by `common_arm/Makefile.hal`. `make fullimage` compresses and incorporates
  this input; it does not run the Xilinx synthesis tools in `fpga/Makefile`.
  The bitstream part and input SHA-256 are recorded in the firmware manifest.
- Factory/no-flash clients and Lua are existing factory assets. This change
  does not replace them with Iceman outputs or claim to rebuild them.

Rebuilding the FPGA from Verilog would be a separate toolchain and hardware
acceptance project. Do not silently substitute a newly synthesized bitstream
for the upstream input. Matching a chip identifier is not proof that altered
FPGA logic works correctly.

## Required patches and failure behavior

`tools/pm3_build_contract.py prepare-client` declares required groups:

| Profile | Required groups |
| --- | --- |
| Device client | FPGA identifier; piped response delimiter; suppressed pipe spinners; visible card-selection diagnostics |
| Companion client | FPGA identifier |

For each group, exactly one patch variant must apply cleanly or pass Git's
reverse check as already present. No applicable variant, multiple variants,
missing patch files or a newly added unclassified `pm3_*.patch` stop the build
with the group name and Git diagnostics. Known legacy/modern selection patches
are alternatives, not patches to stack together.

The old readline patch is explicitly unused: the device build disables
readline and companion runners supply modern readline. Client-only patches
are not applied to the firmware checkout. Compiler-compatibility adjustments
remain limited to the old ARM client compiler; compilation must still succeed.

The standalone client Dockerfile uses the same helper and patch policy. Its
output metadata identifies the exact checkout used; package assembly checks
that identity against independently built firmware metadata.

## Checks on outputs

Each compiled Iceman client must contain the expected FPGA identifier and
must not contain either legacy identifier. This check catches the historical
bad binary independently of patch-application messages. Each firmware ELF
must identify exactly the expected iCopy-X FPGA design and part. The source
bitstream header and payload length are checked too.

Client build records include source commit/tag, platform, artifact SHA-256,
patch names/hashes/statuses and, for the device, the Lua archive SHA-256.
Package assembly requires client/firmware source identity, version and
platform to agree and validates the actual client, firmware and Lua bytes
against those records. The resulting manifest carries the combined identity.
Missing downloads or metadata fail rather than falling back to checked-in
build outputs. Both package-production jobs use this same verification.

These checks protect artifact identity and the known platform contract. They
do not certify all upstream behavior, RF protocols, USB operation, companion
DLL availability or firmware flashing. Host/QEMU and targeted physical
acceptance remain separate evidence.

## When upstream changes

1. Keep the failing run, selected tag/commit and named failed contract.
2. Inspect whether upstream adopted the same behavior, changed its location,
   or changed the protocol. Use a known patch alternative only when its
   semantics match; do not turn a required group into a best-effort skip.
3. Update the patch or verifier in a focused PR. Add a regression which fails
   on the unsupported input, then rebuild all affected client targets and both
   package variants. Old expected failures must remain failures.
4. Run host and QEMU acceptance. If protocol, FPGA contents or hardware-facing
   behavior changed, obtain the relevant physical evidence or record its gap.

Compiler errors, failed contracts and failed artifact checks produce failed
GitHub jobs and prevent the dependent release job from publishing. Maintainers
should enable GitHub notifications for failed workflow runs; no separate
notification service is required for this change.
