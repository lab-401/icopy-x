# DRM / License Check Issues Under QEMU

## Overview

The v1.0.90 `.so` modules contain multiple DRM/license checks. These checks read the Raspberry Pi's CPU serial number from `/proc/cpuinfo`, use AES key derivation to validate against embedded license data, and gate critical API functions. Under QEMU user-mode emulation on an x86 host, these checks fail because the host environment doesn't match the expected ARM hardware.

This document catalogs every known DRM check, its mechanism, its current bypass status, and what's needed to fix it properly.

---

## The Anti-Emulation Environment

The `.so` modules verify they're running on genuine hardware via multiple signals:

| Signal | Real Device | QEMU x86 Host | How `.so` Reads It |
|--------|-------------|----------------|-------------------|
| `/proc/cpuinfo` Serial | `00000000AABBCCDD` (16 hex digits) | No `Serial` field | `subprocess.check_output(['cat', '/proc/cpuinfo'])` → regex `Serial\s*:\s*([a-fA-F0-9]+)` |
| `/proc/cpuinfo` Hardware | `BCM2835` | `AuthenticAMD` / `GenuineIntel` | Same subprocess call |
| `version.so` SERIAL_NUMBER | `02150004` (compiled constant) | Same (loaded from SD card) | `import version; version.SERIAL_NUMBER` |
| AES keys | `DEFAULTK = "QSVNi0joiAFo0o16"`, `DEFAULTIV = "VB1v2qvOinVNIlv2"` | Same (in `aesutils.so`) | Used for key derivation from serial |
| PM3 `hw version` response | Real hardware version string | Empty (mocked PM3) | `executor.startPM3Task('hw version')` |

The cpuinfo Serial is the **primary key**. It feeds into AES derivation that gates multiple modules. The other signals (Hardware, PM3 version) are secondary checks in specific modules.

---

## Current Subprocess Mock

In `tools/minimal_launch_090.py`, line 68:
```python
subprocess.check_output = lambda *a, **k: b''
```

This returns **empty bytes** for ALL `subprocess.check_output` calls, including `cat /proc/cpuinfo`. Every module that reads the serial gets nothing → every DRM check fails.

### The Fix (Not Yet Applied)

Replace with a mock that returns real ARM cpuinfo with the device's actual Serial:

```python
def _mock_check_output(cmd, *a, **k):
    cmd_str = ' '.join(cmd) if isinstance(cmd, (list, tuple)) else str(cmd)
    if 'cpuinfo' in cmd_str:
        return b"processor\t: 0\nmodel name\t: ARMv7 Processor rev 4 (v7l)\n" \
               b"Hardware\t: BCM2835\nRevision\t: 9000c1\n" \
               b"Serial\t\t: <REAL_DEVICE_SERIAL>\n"
    return b''
subprocess.check_output = _mock_check_output
```

**What's needed**: The real device's `/proc/cpuinfo` output. Get it via:
```bash
ssh -p 2222 root@<device> 'cat /proc/cpuinfo'
```

---

## DRM Check #1: tagtypes.so — Tag Type Gating (SOLVED)

**Discovery**: RE_CHRONICLE Section 28 (ReadListActivity crash investigation)

**Module**: `tagtypes.so`

**Functions Gated**:
| Function | What It Controls | Behavior When DRM Fails |
|----------|-----------------|------------------------|
| `getReadable()` | List of tag type IDs for ReadListActivity UI | Returns `[]` (empty list) |
| `isTagCanRead(typ)` | Whether a scanned tag can enter read flow | Returns `False` for all types |
| `isTagCanWrite(typ)` | Whether a read tag can enter write flow | Returns `False` for all types |

**Mechanism**: AES-based license check using `/proc/cpuinfo` Serial as key material. Also calls `executor.startPM3Task('hw version')` at module init time and parses the PM3 response for a valid serial number string. Under QEMU, both checks fail — no ARM serial in cpuinfo, and `hw version` returns empty from the mock.

**Impact History**:
- **Section 19**: `getReadable()` returned `[]` → `ReadListActivity.initList()` received empty list → crash at `SetItem`. Fixed with `getReadable()` shim returning the real device order.
- **Section 28**: Even with `getReadable()` fixed, `isTagCanRead(1)` still returned `False` → scan detected tags but `onScanFinish()` silently skipped `startRead()`. This blocked ALL auto flows (Read, Write, AutoCopy, Erase).

**Key Insight**: The DRM only blocks *access*. The actual data is correct inside the module:
```python
>>> tagtypes.types[1]
('M1 S50 1K 4B', True, True)
#                 ^^^^  ^^^^
#                 readable  writable
```

**Current Bypass** (minimal_launch_090.py lines 204-218):
```python
import tagtypes as _tt
_tt.getReadable = lambda: [1, 42, 0, 41, 25, ...]  # Real device order (captured from device)
_tt.isTagCanRead  = lambda typ, infos=None: _tt.types.get(typ, ('', False, False))[1]
_tt.isTagCanWrite = lambda typ, infos=None: _tt.types.get(typ, ('', False, False))[2]
```

Reads directly from the module's own `types` dictionary. No invented values — the shims expose data the module already has.

**Status**: SOLVED. 44 scan + 82 read scenarios pass with this bypass.

---

## DRM Check #2: hficlass.so — iClass Key Blob Encryption (SOLVED)

**Discovery**: RE_CHRONICLE Section 23

**Module**: `hficlass.so`

**What's Protected**: The `KEYS_ICLASS_NIKOLA` blob — 13,072 bytes of AES-128-CFB encrypted iClass SE/Elite DES keys (1,634 unique 8-byte keys).

**Mechanism**: Module init performs a DRM license check tied to the device serial number (from `version.so` SERIAL_NUMBER). If the SN in `version.so` doesn't match the embedded license expectation, the module rejects with:
```
无法通过验证，禁止使用IClass的验证过程
(Unable to pass verification, forbidden to use iClass verification process)
```

**Key Insight**: This check uses `version.SERIAL_NUMBER` (compiled constant in `version.so`), NOT `/proc/cpuinfo`. The check compares the SN against what was licensed at build time.

**Resolution**: Use the MATCHING `version.so` and `hficlass.so` from the same firmware package (`02150004_1.0.90.ipk`). With matching SN, the license check passes. The encrypted key blob was decrypted using AES keys from `aesutils.so` (`DEFAULTK`/`DEFAULTIV`) under QEMU with the real ARM PyCrypto library.

**Status**: SOLVED. iClass keys are now open-source in PM3 RRG anyway — the encryption is moot.

---

## DRM Check #3: hfmfwrite.so tagChk1 — Write Authorization (UNSOLVED)

**Discovery**: Write flow testing, 2026-03-28

**Module**: `hfmfwrite.so`

**Function**: `tagChk1()`

**Mechanism**: Called at the start of every MIFARE Classic write operation via `write_common()`. The function:
1. Uses `subprocess.check_output(['cat', '/proc/cpuinfo'])` (confirmed in string table)
2. Parses with regex `Serial\s*:\s*([a-fA-F0-9]+)` (confirmed in string table)
3. Uses `__Pyx_PyUnicode_Equals` for string comparison (adjacent in Ghidra symbol table)
4. Returns `True` (write allowed) or `False` (write blocked)

**String Table Evidence** (from `hfmfwrite_strings.txt`):
```
cat /proc/cpuinfo          ← reads cpuinfo
Serial\s*:\s*([a-fA-F0-9]+) ← extracts serial
subprocess                 ← via subprocess module
check_output               ← via check_output()
__Pyx_PyUnicode_Equals     ← string comparison (adjacent to tagChk1 symbol)
```

**Call Chain**: `hfmfwrite.write()` → `write_common()` → `tagChk1()` → `False` → return `-9`

**Impact**: When `tagChk1()` returns `False`, `write_common()` returns `-9` immediately — no `hf mf fchk`, no `hf mf wrbl`, no blocks written. Toast shows "Write failed!" with zero PM3 write commands executed.

**What We Know From Instrumented QEMU Runs**:
- tagChk1 returns `False` immediately with NO PM3 calls, NO hasKeyword calls, NO getContentFromRegex calls
- It checks an in-memory value derived from cpuinfo (which is `b''` under current mock)
- Bypassing tagChk1 with `lambda: True` makes the ENTIRE write flow work — 87 wrbl commands, "Write successful!", "Verification successful!"
- The rest of `hfmfwrite.so` is fully functional under QEMU. tagChk1 is the sole blocker.

**Inner Function Structure**:
- `tagChk1.<locals>.init_tag` — tag initialization
- `tagChk1.<locals>.init_tag1` — variant initialization
- `tagChk1.<locals>.<lambda>` — inline comparison

**The Correct Fix**: Provide the real device's cpuinfo Serial in the subprocess mock AND use real PyCryptodome (not the fake shim).

**Status**: **SOLVED** (2026-03-28). Real cpuinfo serial `02c000814dfb3aeb` + real PyCryptodome. tagChk1 returns True natively.

---

## DRM Check #4: version.so — OTA Install Verification (SOLVED)

**Discovery**: RE_CHRONICLE Sections 6-7

**Module**: `version.so` + `install.so`

**Mechanism**: The OTA installer (`install.so`) loads `version.so` from the IPK package and compares `SERIAL_NUMBER` against the running device's serial. Mismatch → error 0x04.

**Resolution**: Ship the genuine `version.so` (82,856 bytes, SHA256 `c37ae1406614...`) from the device's own firmware package. The file contains the correct SN as a compiled constant. No bypass needed — just use the right file.

**Status**: SOLVED.

---

## Potential DRM in Other Modules

From string analysis, these modules reference DRM-related patterns:

| Module | References | Likely Mechanism | Status |
|--------|-----------|-----------------|--------|
| `container.so` | `AesEncryption` | May validate write targets against license | UNTESTED |
| `write.so` | Dispatches to `hfmfwrite`, `lfwrite`, etc. | May check before dispatch | LIKELY OK (no independent cpuinfo check) |
| `aesutils.so` | `DEFAULTK`, `DEFAULTIV` | Provides crypto primitives, not DRM itself | N/A |
| `lfwrite.so` | `check_detect`, `lft55xx` | May have its own tagChk equivalent for LF | UNTESTED |
| `resources.so` | cpuinfo + AES | Unknown gated function | **PASSES** (imports OK) |
| `audio.so` | cpuinfo + AES | Unknown gated function | **PASSES** (imports OK) |
| `lft55xx.so` | cpuinfo + AES | LF T55XX write operations | **PASSES** (imports OK) |

**Confirmed**: All DRM checks share the same cpuinfo Serial + AES mechanism. The real Serial + real PyCryptodome resolves ALL of them.

---

## Resolution (2026-03-28)

**ALL DRM CHECKS NOW PASS NATIVELY.** The fix had two parts:

### Root Cause 1: Fake PyCryptodome (the real blocker)

`tools/qemu_shims/Crypto/` contained a stub AES implementation where encrypt/decrypt were identity functions (`return data`). This meant ALL AES-based DRM derivations produced garbage. **Deleted the fake shim** — the real PyCryptodome from the SD card image works perfectly under QEMU ARM user-mode.

### Root Cause 2: Wrong cpuinfo Serial

The subprocess mock had `Serial: 00000000deadbeef` (placeholder). Updated to the real device serial `02c000814dfb3aeb` obtained via `ssh -p 2222 root@localhost 'cat /proc/cpuinfo'`.

### Changes Made

| File | Change |
|------|--------|
| `tools/qemu_shims/Crypto/` | **Deleted** — no-op AES stub was causing all DRM failures |
| `tools/minimal_launch_090.py` | Updated cpuinfo mock with real serial; removed hardcoded tagtypes bypass; added site-packages to sys.path before shims |
| `tests/includes/common.sh` | Reordered PYTHONPATH: site-packages before shims |
| `tools/walkers/walk_write_scenarios.sh` | Same PYTHONPATH fix |

### Verification

- `tagtypes.getReadable()` returns 40 types (was returning `False`)
- `tagtypes.isTagCanRead(1)` returns `True` (was returning `False`)
- `hfmfwrite.tagChk1(infos, file, newinfos)` returns `True` (was returning `False`)
- All 6 DRM-gated modules (tagtypes, hfmfwrite, hficlass, resources, audio, lft55xx) pass
- Read flow tests pass with no regressions

See `docs/DRM-KB.md` for the full technical deep-dive.
