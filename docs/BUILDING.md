# Building

## Prerequisites

- Python 3.8+ (3.12 recommended for development)
- `python3-tk` (tkinter, for UI rendering)
- `pytest` (test runner)
- `pycryptodome` (crypto operations for MIFARE/iCLASS)
- `pyserial` (serial communication with GD32 MCU)
- Docker (for cross-compiling the PM3 client)
- Xvfb (for headless UI test execution)

Install on Ubuntu/Debian:

```bash
sudo apt-get install python3-tk xvfb docker.io
pip install pytest pycryptodome pyserial
```

## Project Layout

```
src/
  app.py              # Entry point
  lib/                # UI layer (activities, renderer, widgets)
  middleware/          # PM3 command modules (scan, read, write, etc.)
  screens/            # JSON UI screen definitions
  main/               # Boot chain (main.py, rftask.py, install.py)
plugins/              # Bundled plugins (DOOM, HF Deep Scan, etc.)
res/                  # Runtime resources (audio, fonts, images, firmware)
data/                 # Configuration files (conf.ini)
tools/                # Build scripts, test tooling, Docker
build/                # Cross-compiled artifacts (PM3 binary, lua.zip)
```

## Building IPK Packages

The iCopy-X installs firmware updates as `.ipk` files (ZIP archives with a
specific layout). Two variants exist:

### Flash IPK (includes iceman PM3 client + firmware)

Includes a cross-compiled RRG/Iceman PM3 client binary, Lua 5.4 scripts,
and PM3 fullimage.elf for on-device firmware flashing.

```bash
# Step 1: Cross-compile PM3 client via Docker (see next section)
# Step 2: Build the IPK
python3 tools/build_ipk.py --sn UNIVERSAL --output icopy-x-flash.ipk
```

### No-Flash IPK (keeps existing PM3 firmware)

Replaces only the Python UI layer. Does not touch the PM3 client or firmware.
Safe for users who want to keep their factory PM3 version.

```bash
python3 tools/build_ipk.py --sn UNIVERSAL --no-flash --output icopy-x-noflash.ipk
```

### Build Options

```
--sn SERIAL      Serial number (default: UNIVERSAL)
--output FILE    Output path (default: icopy-x-oss.ipk)
--dry-run        Print manifest without creating the IPK
--no-flash       Exclude PM3 firmware files
--no-trojan      Exclude version.so/install.so (cannot install on factory FW)
--version VER    Override build version string (default: YYMMDD-H.M-Int)
```

The build script automatically excludes `.so` modules that have been replaced
by Python reimplementations and verifies no replaced `.so` leaked into the
final archive.

## Cross-Compiling the PM3 Client

The iCopy-X runs Ubuntu 16.04 (armhf, glibc 2.23). The PM3 client must be
built inside a matching container to produce a compatible binary.

### Using Docker (recommended)

```bash
# From the repository root:
docker build -f tools/docker/Dockerfile.pm3-client -t pm3-client-builder .
docker run --rm -v $(pwd)/build:/out pm3-client-builder
```

This produces two files in `build/`:
- `proxmark3` -- ARM cross-compiled PM3 client binary
- `lua.zip` -- iceman-compatible Lua 5.4 scripts and libraries

The Dockerfile uses `ubuntu:16.04` as the base image and installs the
`arm-linux-gnueabihf` cross-compilation toolchain. Build flags:
`PLATFORM=PM3ICOPYX`, `SKIPQT=1`, `SKIPPYTHON=1`, `SKIPREADLINE=1`.

Patches from `tools/patches/` are applied automatically:
- `pm3_14a_select_warning.patch`
- `pm3_eor_marker.patch`
- `pm3_readline_compat.patch`
- `pm3_suppress_inplace.patch`

### PM3 Firmware

The CI also builds PM3 firmware (`fullimage.elf`) using `gcc-arm-none-eabi`.
**Never build or flash the bootrom** -- the iCopy-X has no JTAG, so a bad
bootrom flash permanently bricks the device.

```bash
# Firmware build (CI does this automatically):
make -j$(nproc) fullimage PLATFORM=PM3ICOPYX SKIPREVENGTEST=1
```

## CI/CD Pipeline

GitHub Actions workflow: `.github/workflows/build-ipk.yml`

### Triggers

- Push to `main` branch
- Pull requests targeting `main`
- Git tags matching `v*` (releases)
- Manual dispatch (`workflow_dispatch`)

### Jobs

1. **test** -- Runs UI tests under Xvfb, verifies IPK build via `--dry-run`
2. **cross-compile-pm3** -- Builds the PM3 client binary inside `ubuntu:16.04`
   Docker container, uploads `proxmark3` + `lua.zip` as artifacts
3. **cross-compile-pm3-firmware** -- Builds `fullimage.elf` with
   `gcc-arm-none-eabi`, generates `pm3_manifest.json` with version/SHA256
4. **build-ipk** -- Downloads artifacts from jobs 2 and 3, builds both flash
   and no-flash IPK variants, uploads as artifacts
5. **release** -- Triggered only on `v*` tags. Creates a GitHub Release with
   both IPK files and installation instructions

### Installing on Device

1. Enter **PC-Mode** on the device to mount USB storage
2. Copy the `.ipk` to the root of the USB drive
3. Exit PC-Mode, navigate to **Settings > Install**
4. Select the IPK file and press OK
5. The device installs and restarts automatically
