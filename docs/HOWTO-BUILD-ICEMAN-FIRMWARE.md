# How to Build the Iceman PM3 Client for iCopy-X

## Overview

The iCopy-X ships with a Proxmark3 module running RRG/Iceman firmware. We build the PM3 **client binary** from the official RRG source with iCopy-X-specific patches applied.

**Key constraint:** The iCopy-X runs Ubuntu 16.04 (Xenial) with glibc 2.23. The PM3 client MUST be cross-compiled inside a matching `ubuntu:16.04` Docker container. Building on a modern host produces glibc 2.38+ binaries that crash on the device with `GLIBC_2.xx not found`.

## Quick Start (Local Build)

```bash
# From the repo root:
mkdir -p build

sudo docker run --rm \
  -v $(pwd)/build:/out \
  -v $(pwd)/tools/patches:/patches:ro \
  ubuntu:16.04 bash -c '
  set -e
  cat > /etc/apt/sources.list << EOF
deb [arch=amd64] http://archive.ubuntu.com/ubuntu/ xenial main restricted universe
deb [arch=amd64] http://archive.ubuntu.com/ubuntu/ xenial-updates main restricted universe
deb [arch=armhf] http://ports.ubuntu.com/ubuntu-ports/ xenial main restricted universe
deb [arch=armhf] http://ports.ubuntu.com/ubuntu-ports/ xenial-updates main restricted universe
EOF
  dpkg --add-architecture armhf && apt-get update -qq
  apt-get install -y -qq gcc-arm-linux-gnueabihf g++-arm-linux-gnueabihf \
    make pkg-config git libbz2-dev:armhf zlib1g-dev:armhf liblz4-dev:armhf \
    libreadline-dev:armhf

  git clone --depth 1 --branch v4.21128 \
    https://github.com/RfidResearchGroup/proxmark3.git /tmp/pm3
  cd /tmp/pm3

  for p in /patches/pm3_*.patch; do
    [ -f "$p" ] || continue
    git apply --check "$p" 2>/dev/null && git apply "$p" && echo "Applied: $(basename $p)"
  done

  export PKG_CONFIG_PATH=/usr/lib/arm-linux-gnueabihf/pkgconfig
  export PKG_CONFIG_LIBDIR=/usr/lib/arm-linux-gnueabihf/pkgconfig

  make -j$(nproc) client \
    PLATFORM=PM3ICOPYX \
    CC=arm-linux-gnueabihf-gcc CXX=arm-linux-gnueabihf-g++ \
    LD=arm-linux-gnueabihf-ld "AR=arm-linux-gnueabihf-ar rcs" \
    RANLIB=arm-linux-gnueabihf-ranlib cpu_arch=arm \
    SKIPQT=1 SKIPPYTHON=1 SKIPREVENGTEST=1 SKIPGD=1 SKIPBT=1

  cp client/proxmark3 /out/proxmark3
'

# Verify
file build/proxmark3
# Expected: ELF 32-bit LSB executable, ARM, EABI5, dynamically linked, glibc 2.23

# Build IPK (picks up build/proxmark3 automatically)
python3 tools/build_ipk.py --sn UNIVERSAL -o icopy-x-oss.ipk
```

## Build Output

The Docker container writes to `/out`, which is mounted to the repo's `build/` directory. `build_ipk.py` checks `build/proxmark3` first, then falls back to `device_so/proxmark3` (legacy).

`build/` is gitignored — it contains only build artifacts.

## CI/CD Pipeline

GitHub Actions workflow: `.github/workflows/build-ipk.yml`

The pipeline has four jobs:

| Job | Purpose | Runs on |
|-----|---------|---------|
| `test` | Run pytest UI tests + IPK dry-run | ubuntu-latest |
| `cross-compile-pm3` | Docker cross-compile PM3 client | ubuntu-latest + ubuntu:16.04 container |
| `cross-compile-pm3-firmware` | Build fullimage.elf (ARM firmware) | ubuntu-latest + arm-none-eabi toolchain |
| `build-ipk` | Assemble final IPK package | ubuntu-latest (after all three above) |

### Triggers

- Push to `main` or any `v*` tag
- Pull requests against `main`
- Manual dispatch (`workflow_dispatch`)

### Tagged releases

Pushing a `v*` tag triggers the `release` job, which creates a GitHub Release with the IPK and standalone PM3 client binary attached.

### Environment Variables

Defined at the top of `build-ipk.yml`:

| Variable | Value | Purpose |
|----------|-------|---------|
| `PM3_REPO` | `https://github.com/RfidResearchGroup/proxmark3.git` | Upstream RRG source |
| `PM3_TAG` | `v4.21128` | Pinned firmware/client version |
| `PM3_CLIENT_PLATFORM` | `PM3ICOPYX` | Client build platform flag |
| `PM3_FW_PLATFORM` | `PM3RDV4` | Firmware build platform flag |

**Why different platforms?** The PM3 client uses `PM3ICOPYX` for the iCopy-X flash guard magic values. The firmware uses `PM3RDV4` because the iCopy-X has a Spartan-II XC2S30 FPGA (not the XC3S100E that `PM3ICOPYX` targets for FPGA bitstreams). Verified on real device 2026-04-12.

## Patching Mechanism

Patches live in `tools/patches/` as standard `git diff` unified diffs. They are applied automatically during the Docker build, both locally and in CI.

### Current Patches

| Patch | File Modified | Purpose |
|-------|---------------|---------|
| `pm3-client-piped-stdin-eor-marker.patch` | `client/src/proxmark3.c` | Emit `pm3 -->` end-of-response marker when stdin is piped. The iCopy-X RTM needs a delimiter to detect when command output is complete. |
| `pm3_suppress_inplace.patch` | `client/src/ui.c` | Suppress `PrintAndLogEx(INPLACE)` when `stdinOnTTY` is false. INPLACE uses `\r` carriage returns for terminal spinners — produces garbage on the TCP/pipe transport. |
| `pm3_readline_compat.patch` | `client/src/ui.c` | Stub `rl_clear_visible_line()` for readline 6.3 (Xenial). This function was added in readline 8.0. The PM3 client runs as a daemon, not interactively, so the visible-line redraw is unnecessary. |

### How Patching Works

The patch loop (identical in Dockerfile and CI workflow):

```bash
for p in /patches/pm3_*.patch; do
    [ -f "$p" ] || continue
    if git apply --check "$p" 2>/dev/null; then
        git apply "$p" && echo "Applied: $(basename $p)"
    else
        echo "Skipped (already applied or N/A): $(basename $p)"
    fi
done
```

- `git apply --check` does a dry run first — if the patch doesn't apply cleanly, it's skipped
- Patches are applied in alphabetical order (shell glob)
- Failed patches are logged but don't break the build (allows version skew)

### Adding a New Patch

1. Clone the PM3 source at the target tag:
   ```bash
   git clone --depth 1 --branch v4.21128 \
     https://github.com/RfidResearchGroup/proxmark3.git /tmp/pm3_patch
   ```

2. Make your changes in `/tmp/pm3_patch/`

3. Generate the patch:
   ```bash
   cd /tmp/pm3_patch
   git diff > /path/to/repo/tools/patches/pm3_my_change.patch
   ```

4. Name it `pm3_*.patch` — the glob pattern in the build scripts only picks up files matching this pattern

5. Test locally with the Docker build command above

## Build Flags Explained

| Flag | Why |
|------|-----|
| `PLATFORM=PM3ICOPYX` | Sets iCopy-X-specific defines (`-DICOPYX`) |
| `SKIPQT=1` | No GUI — headless device |
| `SKIPPYTHON=1` | No Python scripting in PM3 client |
| `SKIPREVENGTEST=1` | Skip reverse engineering tests |
| `SKIPGD=1` | No libgd (image processing) |
| `SKIPBT=1` | No Bluetooth |
| `SKIPREADLINE=1` | **Only use if readline build fails.** Preferred: include readline with the `pm3_readline_compat.patch` stub. Without readline, the PM3 client's stdin pipe handling may break the RTM bridge. |

## Dockerfile

`tools/docker/Dockerfile.pm3-client` provides a reproducible build environment:

```bash
# Build the Docker image (from repo root)
docker build -f tools/docker/Dockerfile.pm3-client -t pm3-client-builder .

# Run the build
docker run --rm -v $(pwd)/build:/out pm3-client-builder
```

The Dockerfile `COPY`s patches from `tools/patches/` into the image at build time. If you add new patches, rebuild the Docker image.

Override the PM3 version: `docker run --rm -e PM3_TAG=v4.22000 -v $(pwd)/build:/out pm3-client-builder`

## Safety Rules

1. **NEVER flash PM3 bootrom.** The iCopy-X has no JTAG. Flashing bootrom = permanent brick. The firmware job builds `fullimage` only — never `bootrom`.

2. **NEVER build with the host toolchain.** Always use the Docker `ubuntu:16.04` container for glibc 2.23 compatibility.

3. **NEVER deploy binaries directly to the device.** Always package in an IPK and install through the device UI (About > Update).

## Updating the PM3 Version

1. Update `PM3_TAG` in:
   - `.github/workflows/build-ipk.yml` (line 13)
   - `tools/docker/Dockerfile.pm3-client` (line 45)

2. Test patches still apply against the new tag (they may need rebasing)

3. Update `res/firmware/pm3/manifest.json` with the new version string

4. Rebuild locally, test on device, then push

## Binary Dependencies (on device)

The cross-compiled binary links against these shared libraries (all present on the iCopy-X):

```
libbz2.so.1.0
liblz4.so.1
libreadline.so.6  (when built with readline)
libstdc++.so.6
libm.so.6
libc.so.6
libdl.so.2
libpthread.so.0
```

Verify with: `ldd build/proxmark3`
