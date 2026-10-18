# Critical QEMU CI

This workflow runs the [small critical profile](QEMU_CRITICAL_FLOWS.md) against
both IPKs from one completed **Build iCopy-X IPK** run. The build workflow stays
unchanged. The QEMU workflow runs afterwards on a fresh GitHub-hosted Ubuntu
24.04 VM and publishes the commit status **QEMU critical flows**.

The main-branch rule requires that status and all three existing host-test jobs
(Linux Python 3.8/3.12 and Windows Python 3.8), with GitHub Actions as their
expected source. Branches must be up to date before merging. Administrators
retain an override for deliberate maintainer decisions; an override does not
turn missing or failed validation into passing evidence.

For PR builds, the controller checks the current PR head before downloading and
before reporting. It resolves missing fork associations through GitHub's commit
API. A moved or closed PR cannot receive a fresh passing status from an old run.
Missing, duplicate, expired or mismatched artifacts fail. Reports retain build
run/attempt, head SHA, artifact IDs and exact package hashes. GitHub PR builds
normally check out the merge ref; the head status identifies the PR candidate,
while the hashes identify the actual packages tested.

The workflow runs for every completed IPK build, including failed builds, which
receive a failure status. A successful build must pass the ARM runtime smoke,
both package profiles and every inventoried critical case. Cancellation, missing
runtime access and infrastructure errors do not become passes.

## Contributor workflow

Run the relevant host tests locally. No device, private image, SSH access or
bespoke QEMU installation is required to submit a PR. A QEMU failure links to
the Actions run. Download `critical-qemu-evidence` for per-variant case results,
wire commands, import provenance and guest logs. The evidence expires after
14 days; retain it separately when needed for a release or investigation.

Maintainers own the runtime and shared harness. Application changes are tested
against the trusted default-branch harness. A PR cannot weaken its own privileged
QEMU acceptance checks by editing fixtures or workflow code. Changes to the
harness itself receive unprivileged contract tests on the PR. A maintainer must
review an intentional expectation change and validate it from a trusted harness
revision before adopting it. For bootstrap or such reviewed changes, temporarily
allow a maintainer-controlled branch in the runtime environment, dispatch it
against a specific build run, then remove that branch exception.

```bash
gh workflow run qemu-critical.yml --ref main -f build_run_id=COMPLETED_BUILD_RUN_ID
```

Do not allow contributor branches or wildcard PR refs in that environment.
Do not regenerate fixtures from failing outputs just to obtain a pass.

## Execution boundary

`workflow_run` loads the controller from the default branch, without checking
out candidate source. The private runtime is downloaded and hash-verified
before candidate execution. Its download key is erased from temporary files
before the worker starts. The worker receives only the trusted harness, the
runtime, the IPKs and writable scratch directories.

Bubblewrap creates private mount, PID, network, IPC and UTS namespaces. Trusted
root setup invokes `setpriv` to drop to uid/gid 65534, remove supplementary groups
and clear all capability sets before starting Python or QEMU. No-new-privileges
prevents privilege recovery through setuid binaries. There is no host home,
host `/etc`, physical device, network or credential mount. A probe verifies these
properties before tests start. The guest shares the host kernel; this is a
disposable-worker boundary, not a claim of protection against every kernel bug.

A unique systemd scope bounds memory to 2 GiB, tasks to 128 and CPU to two cores.
The controller's default deadline is 300 seconds; files are limited to 64 MiB
and core dumps disabled. Scope/process cleanup targets this job only. Only a
bounded allowlist of regular report/log files is copied out, without following
guest symlinks or FIFOs. Runtime bundles, extracted applications and credentials
are not uploaded. Candidate output is not streamed as GitHub workflow commands.

Status publishing runs in a separate job with status-write permission. The
worker job has read-only repository/Actions permissions. No candidate code runs
on the shared SSH server; that server serves one static runtime file only.

## Runtime ownership and rotation

`tools/qemu_ci/runtime_pin.json` records the archive, manifest, factory-image and QEMU
digests and expected Python/Tcl/Tk versions. The private archive contains the
ARM interpreter, library/site-package dependencies, Tcl/Tk scripts and fonts.
It excludes the original application, credentials and card data. Before execution,
the worker checks the pinned manifest and every runtime file/link, rejecting
missing, additional or modified files even for direct lab calls. The runtime
exporter normalizes symlinks within the guest filesystem, omits dangling links
and records individual file hashes. The unpacker checks the archive digest
before bounded extraction and rejects unsafe paths, special files and hardlinks.

Export a replacement inside the trusted factory-image wrapper:

```bash
sudo bash tools/qemu_env.sh /srv/images/factory.img /srv/qemu-arm-static \
  "$PWD" /srv/runs/export-001 -- python3 "$PWD/tools/qemu_ci/export_runtime.py" \
  /srv/exports/runtime-001
```

Review the manifest and archive identity. Repeat runtime and both critical
profiles, plus failure/timeout cleanup checks, before changing the pin. Keep the
previous immutable bundle available until the new pin is accepted. A runtime
change is its own logical PR, not an incidental fixture update.

The environment **critical-qemu-runtime** must allow only `main` in normal
operation. Configure environment variables `QEMU_RUNTIME_HOST` and
`QEMU_RUNTIME_USER`, and environment secrets `QEMU_RUNTIME_KEY` and
`QEMU_RUNTIME_KNOWN_HOSTS`. Pin the verified SSH host key; do not use unchecked
`ssh-keyscan` output in CI.

Use a dedicated password-disabled account, no sudo membership, and a root-owned
home/authorized-keys file. Its key uses OpenSSH `restrict` and a root-owned forced
command which accepts only `fetch-<pinned digest>` and outputs the corresponding
read-only archive. It must reject arbitrary commands, shells, SFTP and forwarding.
Do not reuse a maintainer's development key. Rotate or revoke the download key
through this account and the GitHub environment together. No SSH daemon change
or additional listening service is needed.

## Activation and limits

The automatic `workflow_run` trigger becomes active only after this workflow is
on the default branch. After successful hosted runs, configure the exact status
**QEMU critical flows** as a required check in the repository's main-branch rule.
Use GitHub Actions as the expected status source. Verify a new PR receives the
check automatically before relying on branch protection. A passing status alone
does not enforce merge policy until the repository rule requires it.

This workflow does not intercept the existing tag-release publication job.
For release acceptance, validate a build-only candidate before creating the
release tag. Making publication depend on QEMU would be a separate build/release
workflow change requiring explicit review.

These tests are regression checks, not an attestation that deliberately hostile
application code cannot forge in-process test outcomes. Maintainer review and
the other CI checks remain necessary. Physical USB/RF, real reads/writes,
installation, flashing and an attached ICS Decoder remain separate acceptance
boundaries. The large legacy flow inventory is not silently promoted to this gate.

GitHub documents the privileged nature of
[workflow_run](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_run)
and [environment branch restrictions](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments).
Bubblewrap's [security model](https://github.com/containers/bubblewrap#sandbox-security)
depends on the caller's mount, namespace and capability policy.
