##########################################################################
# Required Notice: Copyright ETOILE401 SAS (http://www.lab401.com)
#
# Copyright (c) 2026: ETOILE401 SAS & https://github.com/quantum-x/
#
# This software is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this software for commercial purposes.
#
# A copy of the license is available at:
# https://polyformproject.org/licenses/noncommercial/1.0.0
#
# This entire header "Required Notice" must remain in place.
##########################################################################

"""Launcher for the Open-Source Python UI under QEMU ARM.

Boots the OSS Python UI (src/lib/) directly — does NOT use application.so.
Middleware .so modules (executor, scan, read, write, etc.) still load from
the rootfs and are mocked for PM3 commands via PM3_SCENARIO_FILE.

All QEMU boilerplate (mock serial, mock subprocess, exit suppression, etc.)
is identical to launcher_original.py.  The difference is the final section:
instead of `application.startApp()`, we directly initialise actstack, create
the Tk root, and push MainActivity ourselves.

Prerequisites: same as launcher_original.py (QEMU rootfs, Xvfb, shims).
"""
import sys
import os
import types
import io
import threading
import builtins
import time

print('[BOOT] OSS Python UI launcher', flush=True)

os.environ.setdefault('DISPLAY', ':99')
APP_DIR = '/mnt/sdcard/root2/root/home/pi/ipk_app_main'
PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHIMS = os.path.join(PROJECT, 'tools', 'qemu_shims')
IMG_OVERLAY = os.path.join(PROJECT, 'tools', 'qemu_img_overlay')

os.chdir(APP_DIR)

# Import real pygame BEFORE lib/ goes on path (lib/audio.so shadows pygame internals)
sys.path.insert(0, SHIMS)
import pygame
print('[OK] Real pygame %s' % pygame.ver, flush=True)

# App paths — site-packages first for real PyCryptodome (DRM AES checks)
SITE_PKGS = '/mnt/sdcard/root2/root/home/pi/.local/lib/python3.8/site-packages'
sys.path.insert(0, os.path.join(APP_DIR, 'main'))
sys.path.insert(0, os.path.join(APP_DIR, 'lib'))
sys.path.insert(0, SHIMS)
sys.path.insert(0, SITE_PKGS)

# OSS Python UI: src/lib MUST be first so our .py modules shadow the .so modules
# src/middleware/ holds RFID middleware reimplementations (erase, future write/scan/etc.)
_src_lib = os.path.join(PROJECT, 'src', 'lib')
_src = os.path.join(PROJECT, 'src')
_src_mw = os.path.join(PROJECT, 'src', 'middleware')
_src_main = os.path.join(PROJECT, 'src', 'main')
_test_target = os.environ.get('TEST_TARGET', 'current')

if _test_target == 'current':
    # Dev mode: src/ modules shadow original .so from rootfs
    # src/main shadows main.so + rftask.so, src/middleware shadows middleware .so,
    # src/lib shadows UI .so (actmain, application, etc.)
    sys.path.insert(0, _src)
    sys.path.insert(0, _src_main)
    sys.path.insert(0, _src_mw)
    sys.path.insert(0, _src_lib)
    print('[TARGET] current — src/lib + src/middleware + src/main shadow .so', flush=True)
else:
    # original_current_ui: only our UI, original .so middleware stays
    sys.path.insert(0, _src_lib)
    print('[TARGET] %s — src/lib only, original middleware .so' % _test_target, flush=True)

sys.argv = [os.path.join(APP_DIR, 'app.py')]

# === Suppress exits ===
sys.exit = lambda *a: print('[EXIT] suppressed', flush=True)
builtins.exit = sys.exit
builtins.quit = sys.exit
os._exit = sys.exit

# === Mock subprocess ===
import subprocess as _real_sp
_real_sp_run = _real_sp.run
os.system = lambda cmd: 0
def _mock_sp_run(cmd, *a, **kw):
    cmd_str = ' '.join(cmd) if isinstance(cmd, (list, tuple)) else str(cmd)
    if 'import' in cmd_str and '-display' in cmd_str:
        return _real_sp_run(cmd, *a, **kw)
    return type('CP', (), {'returncode': 1, 'stdout': b'', 'stderr': b'', 'args': cmd})()
import subprocess
subprocess.run = _mock_sp_run
def _mock_check_output(cmd, *a, **k):
    cmd_str = ' '.join(cmd) if isinstance(cmd, (list, tuple)) else str(cmd)
    if 'cpuinfo' in cmd_str:
        return b"""processor\t: 0
model name\t: ARMv7 Processor rev 5 (v7l)
BogoMIPS\t: 29.71
Features\t: half thumb fastmult vfp edsp neon vfpv3 tls vfpv4 idiva idivt vfpd32 lpae evtstrm
CPU implementer\t: 0x41
CPU architecture: 7
CPU variant\t: 0x0
CPU part\t: 0xc07
CPU revision\t: 5

Hardware\t: Allwinner sun8i Family
Revision\t: 0000
Serial\t\t: 02c000814dfb3aeb
"""
    return b''
subprocess.check_output = _mock_check_output

# === Mock glob for ttyGS ===
import glob as _gmod
_orig_glob = _gmod.glob
_gmod.glob = lambda p, **kw: ['/dev/ttyGS0'] if 'ttyGS' in p else _orig_glob(p, **kw)

# === Mock serial ===
_buf = io.BytesIO()       # Command responses (battery, version, etc.)
_key_buf = io.BytesIO()   # HMI key events — checked FIRST by readline()
_lk = threading.Lock()

class MockSerial:
    is_open = True
    port = '/dev/ttyS0'
    baudrate = 57600
    def __init__(self, *a, **k): pass
    def write(self, d):
        r = b'-> OK\r\n'
        if b'pctbat' in d: r = b'#batpct:100\r\n-> OK\r\n'
        elif b'charge' in d: r = b'#charge:0\r\n-> OK\r\n'
        elif b'volbat' in d: r = b'#batvol:4200\r\n-> OK\r\n'
        elif b'version' in d: r = b'#version:1.4\r\n-> OK\r\n'
        elif b'idid' in d: r = b'#theid:DEADBEEF01020304\r\n-> OK\r\n'
        elif b'givemetime' in d: r = b'#rtctime:1679500000\r\n-> OK\r\n'
        with _lk:
            p = _buf.tell(); _buf.seek(0, 2); _buf.write(r); _buf.seek(p)
        return len(d)
    def readline(self, size=-1):
        for _ in range(20):
            with _lk:
                line = b''
                while True:
                    ch = _key_buf.read(1)
                    if not ch: break
                    line += ch
                    if ch == b'\n': break
                if line: return line
                line = b''
                while True:
                    ch = _buf.read(1)
                    if not ch: break
                    line += ch
                    if ch == b'\n': break
                if line: return line
            time.sleep(0.05)
        return b''
    def read(self, n=1):
        with _lk: return _buf.read(n)
    def close(self): pass
    def flush(self): pass
    def flushInput(self): pass
    def flushOutput(self): pass
    @property
    def in_waiting(self):
        with _lk:
            p1 = _key_buf.tell(); _key_buf.seek(0, 2); e1 = _key_buf.tell(); _key_buf.seek(p1)
            p2 = _buf.tell(); _buf.seek(0, 2); e2 = _buf.tell(); _buf.seek(p2)
            return (e1 - p1) + (e2 - p2)

sm = types.ModuleType('serial')
sm.Serial = MockSerial
sm.SerialException = Exception
sm.EIGHTBITS = 8; sm.PARITY_NONE = 'N'; sm.STOPBITS_ONE = 1
sys.modules['serial'] = sm
builtins._early_serial = MockSerial()

# === Mock pygame.mixer only (keep real pygame for fonts) ===
class _MMix:
    Sound = type('S', (), {
        '__init__': lambda s, *a, **k: None, 'play': lambda s, *a, **k: None,
        'stop': lambda s: None, 'set_volume': lambda s, v: None,
        'get_length': lambda s: 0.1})
    init = staticmethod(lambda *a, **k: None)
    quit = staticmethod(lambda: None)
    stop = staticmethod(lambda: None)
    get_init = staticmethod(lambda: (22050, -16, 2))
    set_num_channels = staticmethod(lambda n: None)
    get_num_channels = staticmethod(lambda: 8)
    fadeout = staticmethod(lambda ms: None)
    class music:
        load = play = stop = pause = unpause = staticmethod(lambda *a, **k: None)
        set_volume = staticmethod(lambda v: None)
        get_busy = staticmethod(lambda: False)
pygame.mixer = _MMix
sys.modules['pygame.mixer'] = _MMix
sys.modules['pygame.mixer.music'] = _MMix.music

# === Mock psutil (with subscript support for check_disk_space) ===
class _DiskUsage:
    def __init__(self):
        self.total = 11e9; self.used = 2e9; self.free = 9e9; self.percent = 18.0
    def __getitem__(self, k):
        if isinstance(k, int): return [self.total, self.used, self.free, self.percent][k]
        return getattr(self, k, 0)

ps = types.ModuleType('psutil')
ps.disk_usage = lambda p: _DiskUsage()
ps.virtual_memory = lambda: type('VM', (), {
    'total': 256e6, 'available': 128e6, 'percent': 50.0, 'used': 128e6, 'free': 128e6})()
ps.cpu_percent = lambda interval=None: 15.0
ps.Process = lambda pid=None: type('Pr', (), {
    'memory_info': lambda s: type('MI', (), {'rss': 50e6, 'vms': 100e6})(),
    'cpu_percent': lambda s, interval=None: 3.0})()
sys.modules['psutil'] = ps

# === Safe os.listdir (check_fw_update crashes on missing dirs) ===
_orig_listdir = os.listdir
def _safe_listdir(path):
    try: return _orig_listdir(path)
    except (FileNotFoundError, OSError): return []
os.listdir = _safe_listdir

# === Image overlay for missing PNGs ===
os.makedirs(IMG_OVERLAY, exist_ok=True)
_orig_open = builtins.open
def _patched_open(file, *args, **kwargs):
    if isinstance(file, str) and '/res/img/' in file:
        basename = os.path.basename(file)
        overlay = os.path.join(IMG_OVERLAY, basename)
        if not os.path.exists(overlay):
            try:
                from PIL import Image as _I, ImageDraw as _D
                img = _I.new('RGBA', (24, 24), (255, 255, 255, 0))
                _D.Draw(img).rectangle([2, 2, 21, 21], outline=(100, 100, 100), width=1)
                img.save(overlay)
            except Exception: pass
        if os.path.exists(overlay):
            return _orig_open(overlay, *args, **kwargs)
    return _orig_open(file, *args, **kwargs)
builtins.open = _patched_open

print('[OK] All mocks ready', flush=True)

# === Verify tagtypes DRM (should pass with real cpuinfo serial + real PyCryptodome) ===
import tagtypes as _tt
_readable = _tt.getReadable()

# Pre-import lfwrite to ensure maps are initialized before any write flow
try:
    import lfwrite as _lfw
    print('[OK] lfwrite: B0=%d PAR=%d RAW=%d DUMP=%d types' % (
        len(getattr(_lfw, 'B0_WRITE_MAP', {})),
        len(getattr(_lfw, 'PAR_CLONE_MAP', {})),
        len(getattr(_lfw, 'RAW_CLONE_MAP', {})),
        len(getattr(_lfw, 'DUMP_WRITE_MAP', {})),
    ), flush=True)
except Exception as e:
    print('[WARN] lfwrite import: %s' % e, flush=True)

if isinstance(_readable, (list, tuple)) and len(_readable) >= 30:
    print('[OK] tagtypes DRM passed natively: %d readable types' % len(_readable), flush=True)
elif _readable:
    print('[OK] tagtypes DRM passed (returned %s)' % type(_readable).__name__, flush=True)
else:
    print('[WARN] tagtypes DRM failed — falling back to bypass', flush=True)
    _tt.getReadable = lambda: [1, 42, 0, 41, 25, 26, 2, 3, 4, 5, 6, 7, 19, 46,
                               20, 21, 17, 18, 8, 9, 10, 11, 12, 13, 14, 15, 16,
                               28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 45, 23, 24]
    _tt.isTagCanRead = lambda typ, infos=None: _tt.types.get(typ, ('', False, False))[1]
    _tt.isTagCanWrite = lambda typ, infos=None: _tt.types.get(typ, ('', False, False))[2]
# Patch update.check_stm32/pm3/linux to not crash
print('[OK] update functions: no patches needed (get_fws fixed)', flush=True)

# === Mock executor with PM3 scenario support ===
import executor

_RESPONSES = {}
_DEFAULT_RET = -1
_PM3_DELAY = float(os.environ.get('PM3_MOCK_DELAY', '3.0'))
_sf = os.environ.get('PM3_SCENARIO_FILE', '')
if _sf and os.path.exists(_sf):
    try:
        ns = {}
        exec(open(_sf).read(), ns)
        _RESPONSES = ns.get('SCENARIO_RESPONSES', {})
        _DEFAULT_RET = ns.get('DEFAULT_RETURN', -1)
        print('[OK] PM3 mock: %d responses' % len(_RESPONSES), flush=True)
    except Exception as e:
        print('[WARN] PM3 mock load failed: %s' % e, flush=True)

_call_counts = {}

def _pm3_mock(cmd, timeout=5000, listener=None, rework_max=2):
    print('[PM3] cmd=%s cache_before=%r thread=%s' % (cmd[:60], (getattr(executor, 'CONTENT_OUT_IN__TXT_CACHE', '') or '')[:80], threading.current_thread().name), flush=True)
    time.sleep(_PM3_DELAY)
    # Handle 'data save f <path>' — PM3 auto-appends .pm3 extension
    if cmd.startswith('data save f '):
        fpath = cmd[len('data save f '):].strip()
        if fpath:
            pm3_path = fpath + '.pm3'
            try:
                with open(pm3_path, 'w') as f:
                    for i in range(256):
                        val = 120 if (i // 8) % 2 == 0 else -120
                        f.write('%d\n' % val)
                print('[PM3] Created %s (256 samples, amplitude=240)' % pm3_path, flush=True)
            except Exception as e:
                print('[PM3] Failed to create trace file: %s' % e, flush=True)
    # Handle 'lf em 4x05_dump f <path>'
    _em4x05_dump_bin_path = None
    if 'lf em 4x05_dump' in cmd and ' f ' in cmd:
        fpath = cmd[cmd.index(' f ') + 3:].strip()
        if fpath:
            bin_path = fpath if fpath.endswith('.bin') else fpath + '.bin'
            _em4x05_dump_bin_path = bin_path
            try:
                os.makedirs(os.path.dirname(bin_path), exist_ok=True)
                dump_data = b'\x60\x01\x50\xE0'
                for i in range(1, 14):
                    dump_data += b'\x00\x00\x00' + bytes([i])
                dump_data += b'\xAA\xBB\xCC\xDD'
                dump_data += b'\x00\x00\x00\x00'
                for p in [bin_path, fpath, bin_path + '.bin']:
                    with open(p, 'wb') as f:
                        f.write(dump_data)
                print('[PM3] Created EM4305 dump %s (64 bytes)' % bin_path, flush=True)
            except Exception as e:
                print('[PM3] Failed to create EM4305 dump: %s' % e, flush=True)
    # Handle 'hf 15 dump f <path>'
    if 'hf 15 dump' in cmd and ' f ' in cmd:
        fpath = cmd[cmd.index(' f ') + 3:].strip()
        if fpath:
            bin_path = fpath if fpath.endswith('.bin') else fpath + '.bin'
            try:
                os.makedirs(os.path.dirname(bin_path), exist_ok=True)
                dump_data = b'\x00' * 112
                for rpat, rval in _RESPONSES.items():
                    if 'hf sea' in rpat:
                        resp_text = rval[1] if isinstance(rval, tuple) else str(rval)
                        import re as _re
                        m = _re.search(r'UID:\s*([0-9A-Fa-f ]+)', resp_text)
                        if m:
                            uid_hex = m.group(1).replace(' ', '')
                            uid_bytes = bytes.fromhex(uid_hex)
                            dump_data = uid_bytes.ljust(8, b'\x00') + b'\x00' * (112 - 8)
                            break
                for p in [bin_path, fpath]:
                    with open(p, 'wb') as f:
                        f.write(dump_data)
                print('[PM3] Created ISO15693 dump %s (112 bytes)' % bin_path, flush=True)
            except Exception as e:
                print('[PM3] Failed to create ISO15693 dump: %s' % e, flush=True)
    # Handle 'hf mfu dump f <path>'
    if 'hf mfu dump' in cmd and ' f ' in cmd:
        fpath = cmd[cmd.index(' f ') + 3:].strip()
        if fpath:
            bin_path = fpath if fpath.endswith('.bin') else fpath + '.bin'
            try:
                os.makedirs(os.path.dirname(bin_path), exist_ok=True)
                dump_data = b'\x04\xA1\xB2\xC3' + b'\x00' * 60
                with open(bin_path, 'wb') as f:
                    f.write(dump_data)
                print('[PM3] Created MFU dump %s (64 bytes)' % bin_path, flush=True)
            except Exception as e:
                print('[PM3] Failed to create MFU dump: %s' % e, flush=True)
    # Handle 'hf iclass dump k <key> f <path>'
    if 'hf iclass dump' in cmd and ' f ' in cmd:
        fpath = cmd[cmd.index(' f ') + 3:].strip()
        if fpath.endswith(' e'):
            fpath = fpath[:-2]
        if fpath:
            bin_path = fpath if fpath.endswith('.bin') else fpath + '.bin'
            try:
                os.makedirs(os.path.dirname(bin_path), exist_ok=True)
                blocks = [b'\x00' * 8] * 19
                blocks[0] = bytes.fromhex('000B0FFFF7FF12E0')
                blocks[1] = bytes.fromhex('12FFFFFF7F1FFF3C')
                blocks[2] = bytes.fromhex('FEFFFFFFFFFFFFFF')
                blocks[3] = bytes.fromhex('AEA684A6DAB21232')
                blocks[4] = bytes.fromhex('AEA684A6DAB21232')
                blocks[5] = bytes.fromhex('FFFFFFFFFFFFF3FF')
                for i in range(6, 19):
                    blocks[i] = bytes([i, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07])
                dump_data = b''.join(blocks)
                with open(bin_path, 'wb') as f:
                    f.write(dump_data)
                eml_path = bin_path.replace('.bin', '.eml')
                with open(eml_path, 'w') as f:
                    for i in range(0, len(dump_data), 8):
                        f.write(dump_data[i:i+8].hex().upper() + '\n')
                print('[PM3] Created iCLASS dump %s (152 bytes, 19 blocks)' % bin_path, flush=True)
            except Exception as e:
                print('[PM3] Failed to create iCLASS dump: %s' % e, flush=True)
    # Handle 'lf t55xx dump f <path>'
    if 'lf t55xx dump' in cmd and ' f ' in cmd:
        fpath = cmd[cmd.index(' f ') + 3:].strip()
        if fpath:
            bin_path = fpath if fpath.endswith('.bin') else fpath + '.bin'
            try:
                os.makedirs(os.path.dirname(bin_path), exist_ok=True)
                blocks = [b'\x00\x00\x00\x00'] * 12
                for bpat, bval in _RESPONSES.items():
                    if bpat.startswith('lf t55xx read b'):
                        bval_resp = bval[1] if isinstance(bval, tuple) else (bval[-1][1] if isinstance(bval, list) else str(bval))
                        import re as _re
                        m = _re.search(r'\|\s*([0-9A-Fa-f]{8})\s*\|', bval_resp)
                        if m:
                            hex_data = m.group(1)
                            bm = _re.search(r'(\d+)\s*\|', bval_resp)
                            if bm:
                                blk_num = int(bm.group(1))
                                if 0 <= blk_num < 12:
                                    blocks[blk_num] = bytes.fromhex(hex_data)
                dump_data = b''.join(blocks)
                with open(bin_path, 'wb') as f:
                    f.write(dump_data)
                eml_path = bin_path.replace('.bin', '.eml')
                with open(eml_path, 'w') as f:
                    for i in range(0, len(dump_data), 4):
                        f.write(dump_data[i:i+4].hex().upper() + '\n')
                print('[PM3] Created T55XX dump %s (48 bytes)' % bin_path, flush=True)
            except Exception as e:
                print('[PM3] Failed to create T55XX dump: %s' % e, flush=True)
    # Handle 'hf mf csave <type> o <path>'
    if 'hf mf csave' in cmd and ' o ' in cmd:
        parts = cmd.split()
        try:
            o_idx = parts.index('o')
            fpath = parts[o_idx + 1] if o_idx + 1 < len(parts) else ''
        except (ValueError, IndexError):
            fpath = ''
        if fpath:
            bin_path = fpath if fpath.endswith('.bin') else fpath + '.bin'
            try:
                os.makedirs(os.path.dirname(bin_path) or '/tmp', exist_ok=True)
                csave_type = 1
                for p in parts:
                    if p in ('1', '4'):
                        csave_type = int(p)
                        break
                num_blocks = 256 if csave_type == 4 else 64
                block_size = 16
                dump_size = num_blocks * block_size
                dump_data = bytearray(dump_size)
                uid_bytes = bytes.fromhex('11223344')
                for rpat, rval in _RESPONSES.items():
                    if 'cgetblk' in rpat:
                        resp_text = rval[1] if isinstance(rval, tuple) else str(rval)
                        import re as _re
                        m = _re.search(r'Block 0:\s*([0-9A-Fa-f ]+)', resp_text)
                        if m:
                            hex_str = m.group(1).replace(' ', '')[:32]
                            if len(hex_str) >= 8:
                                uid_bytes = bytes.fromhex(hex_str[:8])
                            break
                bcc = 0
                for b in uid_bytes:
                    bcc ^= b
                dump_data[0:4] = uid_bytes
                dump_data[4] = bcc
                dump_data[5] = 0x08 if csave_type == 1 else 0x18
                dump_data[6] = 0x04
                dump_data[7] = 0x00
                trailer = bytes.fromhex('FFFFFFFFFFFF') + bytes.fromhex('FF078069') + bytes.fromhex('FFFFFFFFFFFF')
                if csave_type == 4:
                    for s in range(32):
                        t_blk = s * 4 + 3
                        dump_data[t_blk*16:(t_blk+1)*16] = trailer
                    for s in range(32, 40):
                        t_blk = 128 + (s - 32) * 16 + 15
                        dump_data[t_blk*16:(t_blk+1)*16] = trailer
                else:
                    for s in range(16):
                        t_blk = s * 4 + 3
                        dump_data[t_blk*16:(t_blk+1)*16] = trailer
                with open(bin_path, 'wb') as f:
                    f.write(dump_data)
                eml_path = bin_path.replace('.bin', '.eml')
                with open(eml_path, 'w') as f:
                    for i in range(0, len(dump_data), block_size):
                        f.write(dump_data[i:i+block_size].hex().upper() + '\n')
                if fpath and fpath != bin_path:
                    with open(fpath, 'wb') as f:
                        f.write(dump_data)
                print('[PM3] Created MFC Gen1a dump %s (%d bytes, %d blocks)' % (bin_path, dump_size, num_blocks), flush=True)
            except Exception as e:
                print('[PM3] Failed to create MFC csave dump: %s' % e, flush=True)
    for pat, val in sorted(_RESPONSES.items(), key=lambda kv: len(kv[0]), reverse=True):
        if pat in cmd:
            if isinstance(val, list):
                idx = _call_counts.get(pat, 0)
                entry = val[min(idx, len(val) - 1)]
                _call_counts[pat] = idx + 1
                ret, resp = entry if isinstance(entry, tuple) else (0, str(entry))
            elif isinstance(val, tuple):
                ret, resp = val
            else:
                ret, resp = (0, str(val))
            if resp: executor.CONTENT_OUT_IN__TXT_CACHE = resp
            if resp and listener:
                for _line in resp.split('\n'):
                    if _line.strip():
                        try: listener(_line)
                        except Exception: pass
                # Hold BG thread briefly so test polling can capture
                # intermediate states (e.g. Decoding screen during
                # hf list parse).  Original .so streams lines over TCP
                # with natural latency; mock delivers synchronously.
                time.sleep(0.8)
            if resp: _invoke_task_callbacks(resp)
            if _em4x05_dump_bin_path and 'lf em 4x05_dump' in cmd:
                executor.CONTENT_OUT_IN__TXT_CACHE = '[+] saved 64 bytes to binary file %s\n' % _em4x05_dump_bin_path
            executor.LABEL_PM3_CMD_TASK_RUNNING = False
            executor.LABEL_PM3_CMD_TASK_STOP = True
            result = ret if ret == -1 else 1
            return result
    executor.LABEL_PM3_CMD_TASK_RUNNING = False
    executor.LABEL_PM3_CMD_TASK_STOP = True
    if _em4x05_dump_bin_path and 'lf em 4x05_dump' in cmd:
        executor.CONTENT_OUT_IN__TXT_CACHE = '[+] saved 64 bytes to binary file %s\n' % _em4x05_dump_bin_path
    return _DEFAULT_RET

executor.startPM3Task = _pm3_mock
executor.connect2PM3 = lambda *a, **k: True
executor.reworkPM3All = lambda: None

def _pm3_ctrl_mock(cmd, timeout=5000, listener=None, rework_max=2):
    print('[PM3-CTRL] %s' % cmd[:80], flush=True)
    return _pm3_mock(cmd, timeout=timeout, listener=listener, rework_max=rework_max)
executor.startPM3Ctrl = _pm3_ctrl_mock

def _pm3_stop_mock():
    print('[PM3-STOP]', flush=True)
    executor.LABEL_PM3_CMD_TASK_RUNNING = False
    executor.LABEL_PM3_CMD_TASK_STOP = True
executor.stopPM3Task = _pm3_stop_mock

# --- Executor task_call callback mechanism for ConsolePrinterActivity ---
_exec_task_callbacks = []
_orig_add_task_call = getattr(executor, 'add_task_call', None)
_orig_del_task_call = getattr(executor, 'del_task_call', None)

def _mock_add_task_call(callback):
    if callback not in _exec_task_callbacks:
        _exec_task_callbacks.append(callback)
    if _orig_add_task_call:
        try: _orig_add_task_call(callback)
        except Exception: pass

def _mock_del_task_call(callback):
    if callback in _exec_task_callbacks:
        _exec_task_callbacks.remove(callback)
    if _orig_del_task_call:
        try: _orig_del_task_call(callback)
        except Exception: pass

def _invoke_task_callbacks(text):
    if not _exec_task_callbacks or not text:
        return
    for line in text.split('\n'):
        if not line.strip():
            continue
        for cb in list(_exec_task_callbacks):
            try: cb(line)
            except Exception: pass

executor.add_task_call = _mock_add_task_call
executor.del_task_call = _mock_del_task_call

# --- Thread exception hook for debugging ---
import threading as _thr
def _thread_excepthook(args):
    print('[THREAD_EXCEPTION] %s: %s' % (args.exc_type.__name__, args.exc_value), flush=True)
    import traceback as _tb
    tb = getattr(args, 'exc_traceback', None) or getattr(args, 'exc_tb', None)
    _tb.print_exception(args.exc_type, args.exc_value, tb)
_thr.excepthook = _thread_excepthook

# Propagate PM3 mock to ALL modules that cache startPM3Task at import time
def _propagate_pm3_mock():
    for _mod_name in list(sys.modules.keys()):
        _mod = sys.modules.get(_mod_name)
        if _mod and _mod is not executor:
            if hasattr(_mod, 'startPM3Task') and getattr(_mod, 'startPM3Task') is not _pm3_mock:
                setattr(_mod, 'startPM3Task', _pm3_mock)
            if hasattr(_mod, 'startPM3Ctrl') and getattr(_mod, 'startPM3Ctrl') is not _pm3_ctrl_mock:
                setattr(_mod, 'startPM3Ctrl', _pm3_ctrl_mock)
            if hasattr(_mod, 'stopPM3Task') and getattr(_mod, 'stopPM3Task') is not _pm3_stop_mock:
                setattr(_mod, 'stopPM3Task', _pm3_stop_mock)
_propagate_pm3_mock()

def _pm3_propagation_loop():
    while True:
        time.sleep(2)
        _propagate_pm3_mock()
        try:
            _trace_write_module()
        except Exception:
            pass
threading.Thread(target=_pm3_propagation_loop, daemon=True).start()
print('[OK] Executor mocked (with propagation)', flush=True)

# NOTE: Do NOT patch write.write/write.verify — it breaks internal Cython closures.
# write.so's run() uses module-level references to call_on_state/call_on_finish
# which must remain unpatched for the background thread to work correctly.
def _trace_write_module():
    pass

# =====================================================================
# KEY INJECTION + STATE DUMP
# =====================================================================
# These are the test harness features that flow tests depend on.
# They are launcher-agnostic: same key file protocol, same state dump
# JSON format, same GOTO/FINISH/TOAST_CANCEL/STATE_DUMP commands.
# =====================================================================

_main_activity = None
_tk_root = None

def _inject_key(name):
    """Dispatch a key press to the running app via keymap.key.onKey."""
    # PWR while console is showing: destroy the console Frame
    if name == 'PWR' and _tk_root:
        try:
            import tkinter
            def _find_console_frame(parent, depth=0):
                for child in parent.winfo_children():
                    if isinstance(child, tkinter.Frame):
                        for sub in child.winfo_children():
                            if isinstance(sub, tkinter.Text):
                                _fref = child
                                def _hide_console(f=_fref):
                                    try:
                                        f.place_forget()
                                        f.destroy()
                                    except Exception: pass
                                _tk_root.after(0, _hide_console)
                                print('[KEY] PWR -> console destroy scheduled', flush=True)
                                return True
                    if _find_console_frame(child, depth + 1):
                        return True
                return False
            if _find_console_frame(_tk_root):
                return
        except Exception as e:
            print('[KEY] PWR console check error: %s' % e, flush=True)

    # Dispatch key on main tkinter thread via after(0, ...).
    # The key reader thread must stay free to process STATE_DUMP commands
    # while startBGTask parse threads run concurrently.
    try:
        import keymap
        keycode = '%s_PRES!' % name
        _tk_root.after(0, lambda kc=keycode: keymap.key.onKey(kc))
        print('[KEY] %s' % name, flush=True)
    except Exception as e:
        print('[KEY] Error dispatching %s: %s' % (name, e), flush=True)


# === State dump — extracts full UI + cache state as JSON ===
import json as _json

_state_dump_counter = 0
STATE_DUMP_DIR = os.environ.get('STATE_DUMP_DIR', '/tmp/state_dumps')

def _dump_state(raw_frame=None):
    """Dump complete application state to a JSON file."""
    global _state_dump_counter
    _state_dump_counter += 1
    os.makedirs(STATE_DUMP_DIR, exist_ok=True)
    outpath = os.path.join(STATE_DUMP_DIR, 'state_%03d.json' % _state_dump_counter)

    state = {
        'seq': _state_dump_counter,
        'raw_frame': raw_frame,
        'timestamp': time.time(),
        'activity_stack': [],
        'current_activity': None,
        'title': None,
        'M1': None,
        'M2': None,
        'M1_active': True,
        'M2_active': True,
        'M1_visible': True,
        'M2_visible': True,
        'content_text': [],
        'toast': None,
        'scan_cache': None,
        'executor': {},
        'canvas_items': [],
    }

    try:
        import actstack
        stack = None
        try:
            stack = actstack.get_activity_pck()
        except Exception as e:
            state['_stack_error'] = 'get_activity_pck: %s' % e
        if not stack:
            try:
                stack = actstack._ACTIVITY_STACK
            except Exception as e:
                state['_stack_error2'] = '_ACTIVITY_STACK: %s' % e
        if not stack:
            stack = []

        state['activity_stack'] = []
        for i, act in enumerate(stack):
            entry = {'index': i, 'class': act.__class__.__name__}
            try:
                lc = act.life
                entry['lifecycle'] = {
                    'created': bool(lc.created),
                    'resumed': bool(lc.resumed),
                    'paused': bool(lc.paused),
                    'destroyed': bool(lc.destroyed),
                }
            except: pass
            state['activity_stack'].append(entry)

        if stack:
            top = stack[-1]
            if isinstance(top, dict):
                state['current_activity'] = top.get('class', top.get('__class__', type(top).__name__))
            else:
                state['current_activity'] = top.__class__.__name__

            # Expose activity state (e.g. 'scanning', 'reading', 'read_success')
            try:
                state['activity_state'] = str(getattr(top, 'state', ''))
            except Exception:
                pass

            canvas = None
            if not isinstance(top, dict):
                try: canvas = top.getCanvas()
                except:
                    try: canvas = top._canvas
                    except: pass
            if canvas is None and _tk_root:
                for child in _tk_root.winfo_children():
                    if hasattr(child, 'find_all') and hasattr(child, 'find_withtag'):
                        canvas = child

            if canvas:
                title_ids = set()
                btn_left_ids = set()
                btn_right_ids = set()
                btn_bg_ids = set()
                toast_obj_ids = set()
                toast_item_ids = set()
                toast_text_parts = []

                for item in canvas.find_all():
                    tags = canvas.gettags(item)
                    for tag in tags:
                        tl = tag.lower()
                        # Title bar: matches 'ID:NNN-title' and 'tags_title'/'tags_title_text'
                        # Does NOT match template headers ('tpl_title', 'NNN:title')
                        if '-title' in tl or tl in ('tags_title', 'tags_title_text'):
                            title_ids.add(item)
                        elif '-btnleft' in tl or tl == 'tags_btn_left':
                            btn_left_ids.add(item)
                        elif '-btnright' in tl or tl == 'tags_btn_right':
                            btn_right_ids.add(item)
                        elif '-btnbg' in tl or tl in ('tags_btn_bg', 'button_bar'):
                            btn_bg_ids.add(item)
                        elif ':mask_layer' in tag or ':text_bg' in tag:
                            toast_obj_ids.add(tag.split(':')[0])

                # Extract text from classified items
                for item in title_ids:
                    if canvas.type(item) == 'text':
                        t = canvas.itemcget(item, 'text')
                        if t:
                            state['title'] = t
                for item in btn_left_ids:
                    if canvas.type(item) == 'text':
                        t = canvas.itemcget(item, 'text')
                        if t:
                            state['M1'] = t
                for item in btn_right_ids:
                    if canvas.type(item) == 'text':
                        t = canvas.itemcget(item, 'text')
                        if t:
                            state['M2'] = t

                # Button active/inactive/visible flags from activity
                try:
                    state['M1_active'] = bool(getattr(top, '_m1_active', True))
                    state['M2_active'] = bool(getattr(top, '_m2_active', True))
                    state['M1_visible'] = bool(getattr(top, '_m1_visible', True))
                    state['M2_visible'] = bool(getattr(top, '_m2_visible', True))
                except Exception:
                    pass

                if toast_obj_ids:
                    for item in canvas.find_all():
                        for tag in canvas.gettags(item):
                            if any(tag.startswith(tid + ':') for tid in toast_obj_ids):
                                toast_item_ids.add(item)
                                if canvas.type(item) == 'text':
                                    toast_text_parts.append(canvas.itemcget(item, 'text'))
                if toast_text_parts:
                    state['toast'] = ' '.join(toast_text_parts)

                skip = title_ids | btn_left_ids | btn_right_ids | btn_bg_ids | toast_item_ids
                for item in canvas.find_all():
                    if item in skip: continue
                    if canvas.type(item) == 'text':
                        txt = canvas.itemcget(item, 'text')
                        if txt:
                            coords = canvas.coords(item)
                            y = coords[1] if len(coords) > 1 else 0
                            if y < 35 and coords[0] > 170: continue
                            state['content_text'].append({
                                'text': txt,
                                'x': coords[0] if coords else 0,
                                'y': y,
                                'fill': canvas.itemcget(item, 'fill'),
                                'font': canvas.itemcget(item, 'font'),
                            })

                try:
                    for item in canvas.find_all():
                        itype = canvas.type(item)
                        tags = list(canvas.gettags(item))
                        coords = canvas.coords(item)
                        entry = {
                            'id': int(item),
                            'type': itype,
                            'tags': tags,
                            'coords': [round(c, 1) for c in coords],
                        }
                        if itype == 'text':
                            entry['text'] = canvas.itemcget(item, 'text')
                            entry['fill'] = canvas.itemcget(item, 'fill')
                            entry['font'] = canvas.itemcget(item, 'font')
                            entry['anchor'] = canvas.itemcget(item, 'anchor')
                        elif itype == 'rectangle':
                            entry['fill'] = canvas.itemcget(item, 'fill')
                            entry['outline'] = canvas.itemcget(item, 'outline')
                            entry['stipple'] = canvas.itemcget(item, 'stipple')
                        elif itype == 'image':
                            entry['image'] = str(canvas.itemcget(item, 'image'))
                        state['canvas_items'].append(entry)
                except: pass
    except Exception as e:
        state['_activity_error'] = str(e)

    # Scan cache
    try:
        import scan
        state['scan_cache'] = scan.getScanCache()
    except: pass

    # Executor state
    try:
        state['executor'] = {
            'pm3_running': bool(getattr(executor, 'LABEL_PM3_CMD_TASK_RUNNING', False)),
            'pm3_stopped': bool(getattr(executor, 'LABEL_PM3_CMD_TASK_STOP', False)),
            'last_content': (getattr(executor, 'CONTENT_OUT_IN__TXT_CACHE', '') or '')[:500],
        }
    except: pass

    try:
        with _orig_open(outpath, 'w') as f:
            _json.dump(state, f, indent=2, default=str)
        print('[STATE_DUMP] #%d -> %s' % (_state_dump_counter, outpath), flush=True)
    except Exception as e:
        print('[STATE_DUMP] Error writing: %s' % e, flush=True)


# === Key reader thread ===
KEYFILE = os.environ.get('ICOPY_KEY_FILE', '/tmp/icopy_keys_090.txt')

def _key_reader():
    last_pos = 0
    while True:
        try:
            if os.path.exists(KEYFILE):
                sz = os.path.getsize(KEYFILE)
                if sz < last_pos: last_pos = 0
                with open(KEYFILE) as f:
                    f.seek(last_pos)
                    for line in f:
                        k = line.strip()
                        if not k: continue
                        if k.startswith('GOTO:'):
                            pos = int(k.split(':')[1])
                            if _main_activity and _tk_root:
                                def _do_goto(p=pos):
                                    try:
                                        _main_activity.gotoActByPos(p)
                                    except Exception as e:
                                        print('[GOTO] Error at pos %d: %s' % (p, e), flush=True)
                                        import traceback; traceback.print_exc()
                                _tk_root.after(0, _do_goto)
                            print('[GOTO] %d' % pos, flush=True)
                        elif k == 'FINISH':
                            if _main_activity and _tk_root:
                                _tk_root.after(0, lambda: _main_activity.finish())
                            print('[FINISH]', flush=True)
                        elif k == 'TOAST_CANCEL':
                            if _tk_root and hasattr(builtins, '_cancel_toast'):
                                _tk_root.after(0, builtins._cancel_toast)
                            print('[TOAST_CANCEL]', flush=True)
                        elif k.startswith('STATE_DUMP'):
                            if _tk_root:
                                # Parse optional frame index: STATE_DUMP:42
                                _rf = None
                                if ':' in k:
                                    try: _rf = int(k.split(':',1)[1])
                                    except: pass
                                _tk_root.after(0, lambda rf=_rf: _dump_state(raw_frame=rf))
                        else:
                            _inject_key(k)
                    last_pos = f.tell()
        except Exception: pass
        time.sleep(0.2)

threading.Thread(target=_key_reader, daemon=True).start()
print('[OK] Key injection ready (%s)' % KEYFILE, flush=True)

# =====================================================================
# LAUNCH — Direct boot of the OSS Python UI
# =====================================================================
# Instead of application.so → actmain.MainActivity.init(), we directly:
#   1. Create Tk root (240x240)
#   2. Initialise actstack with the root
#   3. Push MainActivity onto the stack (triggers onCreate → renders UI)
#   4. Bind HMI key callbacks
#   5. Register TOAST_CANCEL handler
#   6. Enter mainloop
# =====================================================================

import tkinter as tk

print('[START] Creating Tk root', flush=True)
root = tk.Tk()
root.title('iCopy-X OSS')
root.geometry('240x240')
root.resizable(False, False)
root.configure(bg='#F8FCF8')  # real device FB background (248,252,248)
_tk_root = root
print('[OK] Tk root created', flush=True)

# Register TOAST_CANCEL handler on root
def _cancel_toast():
    """Remove toast overlay items from the top canvas."""
    try:
        for child in root.winfo_children():
            if hasattr(child, 'find_withtag'):
                canvas = child
                # Toast items have 'toast' in their tags
                for item in canvas.find_all():
                    tags = canvas.gettags(item)
                    for tag in tags:
                        if 'toast' in tag.lower():
                            canvas.delete(item)
                            break
    except Exception as e:
        print('[TOAST_CANCEL] Error: %s' % e, flush=True)
builtins._cancel_toast = _cancel_toast

# Initialise the activity stack with our Tk root
import actstack
actstack.init(root)
print('[OK] actstack initialised', flush=True)

# Push MainActivity — this calls .start() → .onCreate() → renders the main menu
import actmain
_main_activity = actstack.start_activity(actmain.MainActivity)
print('[OK] MainActivity pushed: %s' % _main_activity.__class__.__name__, flush=True)

# Wire keymap target to the top activity on the stack.
# The original application.so does this internally; we must do it explicitly.
import keymap

def _update_key_target():
    """Set keymap target to the current top-of-stack activity."""
    try:
        if actstack._ACTIVITY_STACK:
            top = actstack._ACTIVITY_STACK[-1]
            keymap.key.bind(top)
    except Exception as e:
        print('[HMI] target update error: %s' % e, flush=True)

# Patch start_activity and finish_activity to update key target automatically
_orig_start_activity = actstack.start_activity
def _patched_start_activity(*a, **kw):
    result = _orig_start_activity(*a, **kw)
    _update_key_target()
    return result
actstack.start_activity = _patched_start_activity

_orig_finish_activity = actstack.finish_activity
def _patched_finish_activity(*a, **kw):
    result = _orig_finish_activity(*a, **kw)
    _update_key_target()
    return result
actstack.finish_activity = _patched_finish_activity

# Set initial target to MainActivity
_update_key_target()
print('[HMI] keymap target: %s' % type(keymap.key._target).__name__, flush=True)
print('[HMI] Bound (auto-updates on stack changes)', flush=True)

print('[START] Entering mainloop', flush=True)
root.mainloop()
