# DRM Knowledge Base

## TL;DR

The iCopy-X DRM is **fully defeated** under QEMU by two changes:

1. **Real cpuinfo serial** in the subprocess mock: `02c000814dfb3aeb`
2. **Real PyCryptodome** (not the no-op shim that was in `tools/qemu_shims/Crypto/`)

All 6 DRM-gated modules now pass natively. No function-level bypasses needed.

---

## Device Identity

| Field | Value | Source |
|-------|-------|--------|
| Device Serial (software) | `02150004` | `version.SERIAL_NUMBER` (compiled constant in `version.so`) |
| CPU Serial (hardware) | `02c000814dfb3aeb` | `/proc/cpuinfo` on NanoPi NEO (sun8i / Allwinner H3) |
| Hardware | `sun8i` | `/proc/cpuinfo` Hardware field (NOT BCM2835 — this is not a Raspberry Pi) |
| Device Type | `iCopy-XS` | `version.TYP` |
| Firmware Version | `1.0.90` | `version.VERSION_STR` |
| License Blob | `version.UID` (88-char base64, 77 bytes decoded) | AES-encrypted license data |

The software serial (`02150004`) and CPU serial (`02c000814dfb3aeb`) are **different values** — one is assigned by the manufacturer, the other is the SoC's hardware serial. Both are used in DRM checks.

---

## DRM Mechanism

All DRM-gated modules use the same pattern:

```
1. subprocess.check_output(['cat', '/proc/cpuinfo'])
2. re.search(r'Serial\s*:\s*([a-fA-F0-9]+)', cpuinfo_output)
3. AES encrypt/decrypt using PyCryptodome (Crypto.Cipher.AES)
4. Compare derived value against version.UID or embedded license data
5. Return True/list (pass) or False (fail)
```

The AES operation is the critical step. The DRM derives a verification value from the cpuinfo serial using AES-128, then compares it against the pre-computed `version.UID` blob. Both the correct serial AND working AES are required.

### Why It Failed Under QEMU

Two independent failures:

1. **Wrong serial**: The subprocess mock returned `00000000deadbeef` (placeholder) or empty bytes instead of the real `02c000814dfb3aeb`
2. **Broken AES**: A stub `Crypto/` package in `tools/qemu_shims/` provided a no-op AES that returned input unchanged:
   ```python
   class _Cipher:
       def encrypt(self, data): return data  # ← identity function!
       def decrypt(self, data): return data
   ```

Both failures had to be fixed. The serial alone was not enough (AES was still broken), and working AES alone was not enough (wrong serial fed into derivation).

---

## Modules With DRM Checks

6 modules read `/proc/cpuinfo` and perform AES-based license verification:

| Module | DRM Functions | Status |
|--------|--------------|--------|
| `tagtypes.so` | `getReadable()`, `isTagCanRead()`, `isTagCanWrite()` | **PASSES** natively |
| `hfmfwrite.so` | `tagChk1(infos, file, newinfos)` — gates all MIFARE Classic write operations | **PASSES** natively |
| `hficlass.so` | iClass key blob decryption + license check | **PASSES** natively |
| `resources.so` | Unknown gated function | **PASSES** (imports OK) |
| `audio.so` | Unknown gated function | **PASSES** (imports OK) |
| `lft55xx.so` | LF T55XX write operations (likely has tagChk equivalent) | **PASSES** (imports OK) |

### Additional DRM (non-cpuinfo)

| Module | Mechanism | Status |
|--------|-----------|--------|
| `version.so` | OTA install verification — checks `SERIAL_NUMBER` against device | **PASSES** (using matching `version.so` from firmware package) |
| `hficlass.so` | Also checks `version.SERIAL_NUMBER` for key blob decryption | **PASSES** (matching version.so) |

---

## The Fix (Applied)

### 1. Removed fake Crypto shim

Deleted `tools/qemu_shims/Crypto/` (the no-op AES stub). The real PyCryptodome at `/mnt/sdcard/root2/root/home/pi/.local/lib/python3.8/site-packages/Crypto/` works perfectly under QEMU ARM user-mode emulation.

### 2. Updated cpuinfo mock

In `tools/minimal_launch_090.py`, the subprocess mock now returns the **real device cpuinfo** including:
- `Hardware: sun8i`
- `Serial: 02c000814dfb3aeb`

### 3. PYTHONPATH ordering

Site-packages must come before `tools/qemu_shims/` in PYTHONPATH so real PyCryptodome is found. Updated in:
- `tools/minimal_launch_090.py` (sys.path ordering)
- `tests/includes/common.sh` (PYTHONPATH env var)
- `tools/walkers/walk_write_scenarios.sh` (PYTHONPATH env var)

### 4. Removed tagtypes bypass

The hardcoded `getReadable()`/`isTagCanRead()`/`isTagCanWrite()` overrides in `minimal_launch_090.py` are no longer needed. The code now verifies DRM passes natively and only falls back to the bypass if it fails (defensive).

---

## Key Technical Details

### PyCryptodome Under QEMU

The real PyCryptodome (`_raw_aes.cpython-38-arm-linux-gnueabihf.so`) uses **standard ARM Thumb-2 instructions** for AES — no NEON, no ARMv8 crypto extensions. QEMU user-mode emulates these correctly. AES encrypt/decrypt produces correct, non-identity results.

### version.UID License Blob

```
G/5yMqW7SW5rSXdOQjYT53ofeumz+4A9PpBGN+OmWfFFSaOTcOW64JQitHeeXQJTi/jy/a6H0bCFXJpxSXxMKaORSxrFOOTYcIVbeic=
```

77 bytes when base64-decoded. AES-encrypted with a key derived from the cpuinfo serial. Each firmware build embeds a UID specific to the target device's CPU serial.

### AES Keys

From `aesutils.so` (referenced by DRM doc, not directly importable):
- `DEFAULTK = "QSVNi0joiAFo0o16"` (16 bytes, AES-128)
- `DEFAULTIV = "VB1v2qvOinVNIlv2"` (16 bytes)

These may or may not be the keys used for UID derivation — the exact algorithm is in the compiled .so modules.

### tagChk1 Signature

```python
hfmfwrite.tagChk1(infos, file, newinfos)
# infos: scan cache dict {'type': int, 'uid': str, 'atqa': str, 'sak': str, ...}
# file: dump file path (str)
# newinfos: new tag info dict (same structure as infos)
# Returns: True (write allowed) or False (write blocked by DRM)
```

Previously documented as taking 0 args — it actually takes 3. The DRM check is embedded within the function alongside the tag verification logic.

### Other tagChk Functions

```python
hfmfwrite.tagChk2(infos, newinfos)    # 2 args
hfmfwrite.tagChk3(infos, newinfos)    # 2 args
hfmfwrite.tagChk4(infos)              # 1 arg
```

---

## Real Device `/proc/cpuinfo`

```
processor	: 0
model name	: ARMv7 Processor rev 5 (v7l)
BogoMIPS	: 29.71
Features	: half thumb fastmult vfp edsp neon vfpv3 tls vfpv4 idiva idivt vfpd32 lpae evtstrm
CPU implementer	: 0x41
CPU architecture: 7
CPU variant	: 0x0
CPU part	: 0xc07
CPU revision	: 5

processor	: 1
model name	: ARMv7 Processor rev 5 (v7l)
(... 3 more identical cores ...)

Hardware	: sun8i
Revision	: 0000
Serial		: 02c000814dfb3aeb
```

The device is a **NanoPi NEO** with an Allwinner H3 SoC (sun8i), NOT a Raspberry Pi (BCM2835). The DRM doc previously assumed BCM2835 — this was incorrect but didn't matter because the .so modules only parse the `Serial` field via regex, not the `Hardware` field.

---

## Previous Failed Approaches

| Approach | Why It Failed |
|----------|--------------|
| `subprocess.check_output = lambda *a, **k: b''` | Returns empty bytes — no serial to extract |
| `mount --bind /tmp/fake_cpuinfo /proc/cpuinfo` | Requires root in QEMU; QEMU user-mode can't mount |
| `LD_PRELOAD` with `open()` hook | QEMU user-mode doesn't pass LD_PRELOAD to emulated processes |
| `lxcfs` FUSE mount | Same root/mount issue as above |
| Fake cpuinfo with `deadbeef` serial | Wrong serial → AES derivation produces wrong result |
| Fake Crypto shim with identity AES | AES must actually encrypt/decrypt for DRM verification |
| Function-level bypasses (`tagChk1 = lambda: True`) | Whack-a-mole; each new module needs its own bypass |

The correct fix was always: **give the DRM exactly what it expects** — the real cpuinfo serial + working AES crypto.
