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

"""IPK Install Test launcher for QEMU ARM.

Based on launcher_original.py but with:
  - Tracing on os.listdir, os.path.exists, shutil, os.system for update paths
  - os.system passes through real commands (not mocked to 0) for install ops
  - All update/install module operations logged to /tmp/install_trace.log
  - Minimal patches — only what's needed to avoid crashes
  - Resources shim from tools/qemu_shims/

Prerequisites (run tools/setup_qemu_env.sh first):
  - SD card image mounted at /mnt/sdcard/root{1,2}/
  - Xvfb running on :99
  - qemu_shims/ directory populated

Usage:
  QEMU_LD_PREFIX=/mnt/sdcard/root2/root \
  QEMU_SET_ENV="LD_LIBRARY_PATH=..." \
  DISPLAY=:99 PYTHONPATH="<site-packages>" \
  PM3_SCENARIO_FILE="/path/to/mock.py" \
  qemu-arm-static python3.8 -u tools/minimal_launch_090.py
"""
import sys
import os
import types
import io
import threading
import builtins
import time

print('[BOOT] v1.0.90 minimal launcher', flush=True)

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

# Now add app paths — site-packages MUST come before shims for real PyCryptodome
# (the fake Crypto shim was removed; real PyCryptodome is needed for DRM AES checks)
SITE_PKGS = '/mnt/sdcard/root2/root/home/pi/.local/lib/python3.8/site-packages'
sys.path.insert(0, os.path.join(APP_DIR, 'main'))
sys.path.insert(0, os.path.join(APP_DIR, 'lib'))
sys.path.insert(0, SHIMS)
sys.path.insert(0, SITE_PKGS)  # Must be first for real PyCryptodome

sys.argv = [os.path.join(APP_DIR, 'app.py')]

# === Suppress exits ===
sys.exit = lambda *a: print('[EXIT] suppressed', flush=True)
builtins.exit = sys.exit
builtins.quit = sys.exit
os._exit = sys.exit

# === Install trace log ===
_install_trace = open('/tmp/install_trace.log', 'w')
def _itlog(msg):
    _install_trace.write('[%8.3f] %s\n' % (time.time() - _boot_t0, msg))
    _install_trace.flush()
    print('[INSTALL_TRACE] %s' % msg, flush=True)
_boot_t0 = time.time()
_itlog('=== INSTALL TRACE STARTED ===')

# === Traced os.system — runs real commands, logs everything ===
import subprocess as _real_sp
_real_sp_run = _real_sp.run
_real_os_system = os.system
def _traced_os_system(cmd):
    _itlog('OS.SYSTEM(%s)' % repr(cmd)[:200])
    cmd_str = str(cmd)
    # Commands that can't work under QEMU — return success
    if any(k in cmd_str for k in ('mount ', 'umount ', 'sudo service', 'reboot')):
        _itlog('OS.SYSTEM -> 0 (QEMU stub)')
        return 0
    # All other commands (chmod, cp, etc.) — run for real
    try:
        ret = _real_os_system(cmd)
        _itlog('OS.SYSTEM -> %d' % ret)
        return ret
    except Exception as e:
        _itlog('OS.SYSTEM -> EXCEPTION: %s' % e)
        return 1
os.system = _traced_os_system
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
        # Real device cpuinfo (NanoPi NEO / sun8i, serial 02150004)
        # This serial feeds AES-based DRM checks in tagtypes.so, hfmfwrite.so, etc.
        return b"""processor\t: 0
model name\t: ARMv7 Processor rev 5 (v7l)
BogoMIPS\t: 29.71
Features\t: half thumb fastmult vfp edsp neon vfpv3 tls vfpv4 idiva idivt vfpd32 lpae evtstrm
CPU implementer\t: 0x41
CPU architecture: 7
CPU variant\t: 0x0
CPU part\t: 0xc07
CPU revision\t: 5

Hardware\t: sun8i
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
                # Check key buffer FIRST — HMI key events take priority
                line = b''
                while True:
                    ch = _key_buf.read(1)
                    if not ch: break
                    line += ch
                    if ch == b'\n': break
                if line: return line
                # Then check command response buffer
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

# === Traced os.listdir ===
_orig_listdir = os.listdir
def _safe_listdir(path):
    try:
        result = _orig_listdir(path)
    except (FileNotFoundError, OSError) as e:
        if any(k in str(path) for k in ('upan', 'ipk', 'tmp')):
            _itlog('LISTDIR(%s) -> %s: %s' % (path, type(e).__name__, e))
        return []
    if any(k in str(path) for k in ('upan', 'ipk', 'tmp', 'font')):
        _itlog('LISTDIR(%s) -> %s' % (path, result))
    return result
os.listdir = _safe_listdir

# === Traced os.path.exists ===
_real_path_exists = os.path.exists
def _traced_exists(path):
    result = _real_path_exists(path)
    if any(k in str(path) for k in ('upan', 'ipk', 'version', 'install', 'app.py', 'unpkg', 'font')):
        _itlog('EXISTS(%s) -> %s' % (path, result))
    return result
os.path.exists = _traced_exists

# === Traced os.makedirs ===
_real_makedirs = os.makedirs
def _traced_makedirs(name, *args, **kwargs):
    _itlog('MAKEDIRS(%s)' % repr(name)[:200])
    try:
        result = _real_makedirs(name, *args, **kwargs)
        _itlog('MAKEDIRS -> OK')
        return result
    except Exception as e:
        _itlog('MAKEDIRS -> %s: %s' % (type(e).__name__, e))
        raise
os.makedirs = _traced_makedirs

# === Traced shutil ===
import shutil as _shutil_mod
for _sh_name in ('copy', 'copy2', 'copytree', 'move', 'rmtree'):
    if hasattr(_shutil_mod, _sh_name):
        _sh_orig = getattr(_shutil_mod, _sh_name)
        def _make_sh(name, fn):
            def wrapper(*a, **kw):
                _itlog('SHUTIL.%s(%s)' % (name, ', '.join(repr(x)[:80] for x in a)))
                try:
                    result = fn(*a, **kw)
                    _itlog('SHUTIL.%s -> OK' % name)
                    return result
                except Exception as e:
                    _itlog('SHUTIL.%s -> %s: %s' % (name, type(e).__name__, e))
                    raise
            return wrapper
        setattr(_shutil_mod, _sh_name, _make_sh(_sh_name, _sh_orig))

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

# === Traced zipfile.ZipFile for IPK extraction ===
import zipfile as _zipfile_mod
_real_ZipFile = _zipfile_mod.ZipFile
class _TracedZipFile(_real_ZipFile):
    def __init__(self, file, *args, **kwargs):
        _itlog('ZIPFILE.open(%s)' % repr(file)[:200])
        try:
            super().__init__(file, *args, **kwargs)
            _itlog('ZIPFILE.open -> OK (%d files)' % len(self.namelist()))
        except Exception as e:
            _itlog('ZIPFILE.open -> %s: %s' % (type(e).__name__, e))
            raise
    def extractall(self, path=None, *args, **kwargs):
        _itlog('ZIPFILE.extractall(%s)' % repr(path)[:200])
        try:
            result = super().extractall(path, *args, **kwargs)
            _itlog('ZIPFILE.extractall -> OK')
            return result
        except Exception as e:
            _itlog('ZIPFILE.extractall -> %s: %s' % (type(e).__name__, e))
            raise
    def extract(self, member, path=None, *args, **kwargs):
        _itlog('ZIPFILE.extract(%s, %s)' % (repr(member)[:80], repr(path)[:80]))
        try:
            result = super().extract(member, path, *args, **kwargs)
            return result
        except Exception as e:
            _itlog('ZIPFILE.extract -> %s: %s' % (type(e).__name__, e))
            raise
    def namelist(self):
        result = super().namelist()
        _itlog('ZIPFILE.namelist -> %d files' % len(result))
        return result
    def read(self, name, *args, **kwargs):
        _itlog('ZIPFILE.read(%s)' % repr(name)[:80])
        try:
            data = super().read(name, *args, **kwargs)
            _itlog('ZIPFILE.read -> %d bytes' % len(data))
            return data
        except Exception as e:
            _itlog('ZIPFILE.read -> %s: %s' % (type(e).__name__, e))
            raise
_zipfile_mod.ZipFile = _TracedZipFile

# === Traced imports for update modules (non-recursive) ===
_import_tracing = False
_real_builtins_import = builtins.__import__
def _traced_import(name, *args, **kwargs):
    global _import_tracing
    if _import_tracing or name not in ('update', 'activity_update', 'install'):
        return _real_builtins_import(name, *args, **kwargs)
    _import_tracing = True
    _itlog('IMPORT(%s)' % name)
    try:
        mod = _real_builtins_import(name, *args, **kwargs)
        _itlog('IMPORT(%s) -> OK from %s' % (name, getattr(mod, '__file__', '?')))
        return mod
    except Exception as e:
        _itlog('IMPORT(%s) -> %s: %s' % (name, type(e).__name__, e))
        raise
    finally:
        _import_tracing = False
builtins.__import__ = _traced_import

# === Global exception hook to catch silent failures ===
import traceback as _tb_mod
_real_excepthook = sys.excepthook
def _traced_excepthook(exc_type, exc_value, exc_tb):
    _itlog('UNHANDLED EXCEPTION: %s: %s' % (exc_type.__name__, exc_value))
    _itlog(''.join(_tb_mod.format_tb(exc_tb)))
    _real_excepthook(exc_type, exc_value, exc_tb)
sys.excepthook = _traced_excepthook

# Also catch threading exceptions
import threading
_real_excepthook_t = getattr(threading, 'excepthook', None)
def _traced_thread_except(args):
    _itlog('THREAD EXCEPTION in %s: %s: %s' % (args.thread, type(args.exc_value).__name__, args.exc_value))
    _itlog(''.join(_tb_mod.format_exception(type(args.exc_value), args.exc_value, args.exc_value.__traceback__)))
threading.excepthook = _traced_thread_except

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
except Exception as _e:
    print('[WARN] lfwrite import: %s' % _e, flush=True)
if isinstance(_readable, list) and len(_readable) > 0:
    print('[OK] tagtypes DRM passed natively: %d readable types' % len(_readable), flush=True)
else:
    print('[WARN] tagtypes DRM failed — falling back to bypass', flush=True)
    _tt.getReadable = lambda: [1, 42, 0, 41, 25, 26, 2, 3, 4, 5, 6, 7, 19, 46,
                               20, 21, 17, 18, 8, 9, 10, 11, 12, 13, 14, 15, 16,
                               28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 45, 23, 24]
    _tt.isTagCanRead = lambda typ, infos=None: _tt.types.get(typ, ('', False, False))[1]
    _tt.isTagCanWrite = lambda typ, infos=None: _tt.types.get(typ, ('', False, False))[2]

# === Import and patch actmain ===
import actmain
actmain.MainActivity.searchSerial = lambda self: ['/dev/ttyGS0']
actmain.MainActivity.startSerialListener = lambda self: None
actmain.MainActivity.stopSerialListener = lambda self: None
print('[OK] actmain patched', flush=True)

# Patch update.check_stm32/pm3/linux to not crash
# These crash with "argument of type 'int' is not iterable" because
# they filter file listings with a lambda but get unexpected types from mocks
# update.check_stm32/pm3/linux now work correctly because resources.get_fws()
# returns [] (empty list) instead of (8,17,14,28) which crashed the lambda filters.
# No patches needed — the real functions run and find no firmware files → no update.
print('[OK] update functions: no patches needed (get_fws fixed)', flush=True)

# === QEMU trace — same as real device tracer (module-level only) ===
# Enabled via QEMU_TRACE=1 env var. Logs to /tmp/qemu_trace.log
_QEMU_TRACE = os.environ.get('QEMU_TRACE', '')
if _QEMU_TRACE:
    import json as _trace_json
    _trace_t0 = time.time()
    _trace_log_path = '/tmp/qemu_trace.log'
    with open(_trace_log_path, 'w') as _f:
        _f.write('=== QEMU TRACE ===\n')
    def _tlog(msg):
        try:
            with open(_trace_log_path, 'a') as _f:
                _f.write('[%8.3f] %s\n' % (time.time() - _trace_t0, msg))
        except: pass

    import actstack
    _t_orig_start = actstack.start_activity
    def _t_start(*a, **kw):
        try: _tlog('START(%s)' % ', '.join(x.__name__ if hasattr(x, '__name__') else repr(x)[:80] for x in a))
        except: pass
        return _t_orig_start(*a, **kw)
    actstack.start_activity = _t_start
    _t_orig_finish = actstack.finish_activity
    def _t_finish(*a, **kw):
        try: _tlog('FINISH(top=%s d=%d)' % (type(actstack._ACTIVITY_STACK[-1]).__name__, len(actstack._ACTIVITY_STACK)))
        except: pass
        return _t_orig_finish(*a, **kw)
    actstack.finish_activity = _t_finish

    import scan as _t_scan
    _t_orig_setCache = _t_scan.setScanCache
    def _t_setCache(infos):
        try:
            if isinstance(infos, dict):
                _tlog('CACHE: %s' % _trace_json.dumps({k: repr(v)[:40] for k, v in infos.items()}))
        except: pass
        return _t_orig_setCache(infos)
    _t_scan.setScanCache = _t_setCache


    # Poller for stack state
    def _t_poll():
        prev = ''
        while True:
            try:
                names = [type(x).__name__ for x in actstack._ACTIVITY_STACK]
                cache = _t_scan.getScanCache()
                cs = ''
                if isinstance(cache, dict):
                    cs = 'type=%s uid=%s' % (cache.get('type', '?'), str(cache.get('uid', ''))[:16])
                line = 'stack=%s %s' % (names, cs)
                if line != prev:
                    _tlog('POLL %s' % line)
                    prev = line
            except: pass
            time.sleep(0.5)
    threading.Thread(target=_t_poll, daemon=True).start()
    print('[OK] QEMU trace enabled → %s' % _trace_log_path, flush=True)

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

_call_counts = {}  # Track call count per pattern for sequential responses

_pm3_n = 0
def _pm3_mock(cmd, timeout=5000, listener=None, rework_max=2):
    global _pm3_n
    _pm3_n += 1
    print('[PM3] %s' % cmd[:80], flush=True)
    print('[PM3-THREAD] %s' % threading.current_thread().name, flush=True)
    if _pm3_n > 19:
        import traceback
        print('[PM3-STACK] call %d: %s' % (_pm3_n, cmd[:40]), flush=True)
        for line in traceback.format_stack()[-6:-1]:
            print(line.rstrip(), flush=True)
    if _QEMU_TRACE:
        _tlog('PM3> %s (t=%d, thread=%s)' % (cmd[:100], timeout, threading.current_thread().name))
    time.sleep(_PM3_DELAY)
    # Handle 'data save f <path>' — PM3 auto-appends .pm3 extension
    # lf_wav_filter reads the .pm3 file and checks amplitude >= 90
    if cmd.startswith('data save f '):
        fpath = cmd[len('data save f '):].strip()
        if fpath:
            pm3_path = fpath + '.pm3'  # PM3 appends .pm3!
            try:
                # Write LF trace data with amplitude > 90 (threshold for T55XX detection)
                with open(pm3_path, 'w') as f:
                    for i in range(256):
                        val = 120 if (i // 8) % 2 == 0 else -120  # amplitude=240, well above 90
                        f.write('%d\n' % val)
                print('[PM3] Created %s (256 samples, amplitude=240)' % pm3_path, flush=True)
            except Exception as e:
                print('[PM3] Failed to create trace file: %s' % e, flush=True)
    # Handle 'lf em 4x05_dump f <path>' — PM3 creates .bin file
    # write_dump_em4x05() opens this file and writes each block via lf em 4x05_write
    # dump4X05() extracts DUMP_TEMP path via getContentFromRegex from the PM3 response text —
    # the response MUST include the actual .bin path: '[+] saved 64 bytes to binary file <path>'
    _em4x05_dump_bin_path = None
    if 'lf em 4x05_dump' in cmd and ' f ' in cmd:
        fpath = cmd[cmd.index(' f ') + 3:].strip()
        if fpath:
            bin_path = fpath if fpath.endswith('.bin') else fpath + '.bin'
            _em4x05_dump_bin_path = bin_path
            try:
                os.makedirs(os.path.dirname(bin_path), exist_ok=True)
                # EM4305 dump: 16 blocks × 4 bytes = 64 bytes (word-based)
                # Fill with non-zero data so write_dump_em4x05 has blocks to write
                dump_data = b'\x60\x01\x50\xE0'  # block 0 = ConfigWord
                for i in range(1, 14):
                    dump_data += b'\x00\x00\x00' + bytes([i])  # blocks 1-13: minimal non-zero
                dump_data += b'\xAA\xBB\xCC\xDD'  # block 14 = serial placeholder
                dump_data += b'\x00\x00\x00\x00'  # block 15 = reserved
                # Create file at multiple paths — .so may use any of these:
                # 1. <path>.bin (PM3 standard)
                # 2. <path> (base path from command)
                # 3. <path>.bin.bin (if .so appends .bin to already .bin path)
                for p in [bin_path, fpath, bin_path + '.bin']:
                    with open(p, 'wb') as f:
                        f.write(dump_data)
                print('[PM3] Created EM4305 dump %s (64 bytes, 3 copies)' % bin_path, flush=True)
            except Exception as e:
                print('[PM3] Failed to create EM4305 dump: %s' % e, flush=True)
    # Handle 'hf 15 dump f <path>' — PM3 creates .bin file
    # hf15write.so restore uses this file path for 'hf 15 restore f <path>.bin'
    # Without the file, the write phase has no data to restore.
    if 'hf 15 dump' in cmd and ' f ' in cmd:
        fpath = cmd[cmd.index(' f ') + 3:].strip()
        if fpath:
            bin_path = fpath if fpath.endswith('.bin') else fpath + '.bin'
            try:
                os.makedirs(os.path.dirname(bin_path), exist_ok=True)
                # ISO15693 dump: 14 blocks × 8 bytes = 112 bytes (typical ICODE)
                # Block 0 contains the UID (8 bytes, reversed)
                dump_data = b'\x00' * 112
                # Try to extract UID from scan cache / fixture responses
                for rpat, rval in _RESPONSES.items():
                    if 'hf sea' in rpat:
                        resp_text = rval[1] if isinstance(rval, tuple) else str(rval)
                        import re as _re
                        m = _re.search(r'UID:\s*([0-9A-Fa-f ]+)', resp_text)
                        if m:
                            uid_hex = m.group(1).replace(' ', '')
                            uid_bytes = bytes.fromhex(uid_hex)
                            # ISO15693 stores UID in block 0
                            dump_data = uid_bytes.ljust(8, b'\x00') + b'\x00' * (112 - 8)
                            break
                for p in [bin_path, fpath]:
                    with open(p, 'wb') as f:
                        f.write(dump_data)
                print('[PM3] Created ISO15693 dump %s (112 bytes)' % bin_path, flush=True)
            except Exception as e:
                print('[PM3] Failed to create ISO15693 dump: %s' % e, flush=True)
    # Handle 'hf mfu dump f <path>' — PM3 creates .bin file
    # hfmfuwrite.so restore uses this file path
    if 'hf mfu dump' in cmd and ' f ' in cmd:
        fpath = cmd[cmd.index(' f ') + 3:].strip()
        if fpath:
            bin_path = fpath if fpath.endswith('.bin') else fpath + '.bin'
            try:
                os.makedirs(os.path.dirname(bin_path), exist_ok=True)
                # Ultralight dump: 16 pages × 4 bytes = 64 bytes minimum
                dump_data = b'\x04\xA1\xB2\xC3' + b'\x00' * 60
                with open(bin_path, 'wb') as f:
                    f.write(dump_data)
                print('[PM3] Created MFU dump %s (64 bytes)' % bin_path, flush=True)
            except Exception as e:
                print('[PM3] Failed to create MFU dump: %s' % e, flush=True)
    # Handle 'hf iclass dump k <key> f <path>' — PM3 creates .bin file
    # iclasswrite.so reads block data from this dump file during write phase.
    # Without the file, getNeedWriteBlock / write() will error → "Write failed!" with no PM3 commands.
    if 'hf iclass dump' in cmd and ' f ' in cmd:
        fpath = cmd[cmd.index(' f ') + 3:].strip()
        # Strip trailing ' e' elite flag — hficlass.so appends 'e' as a PM3 flag
        # but the stored dump path (used by iclasswrite.so) does NOT include it
        if fpath.endswith(' e'):
            fpath = fpath[:-2]
        if fpath:
            bin_path = fpath if fpath.endswith('.bin') else fpath + '.bin'
            try:
                os.makedirs(os.path.dirname(bin_path), exist_ok=True)
                # iCLASS dump: 19 blocks × 8 bytes = 152 bytes
                # Block layout:
                #   0: CSN (Card Serial Number)
                #   1: Configuration
                #   2: ePurse
                #   3: Key (Kd - debit key)
                #   4: Key (Kc - credit key)
                #   5: Application Issuer Area
                #   6-18: Application data blocks (user data)
                # Blocks 6+ contain application data that will be compared
                # with tag blocks during write. We fill with non-zero data
                # so getNeedWriteBlock detects differences from tag (which
                # returns error/zeros under mock).
                blocks = [b'\x00' * 8] * 19
                blocks[0] = bytes.fromhex('000B0FFFF7FF12E0')  # CSN from fixture
                blocks[1] = bytes.fromhex('12FFFFFF7F1FFF3C')  # Config block
                blocks[2] = bytes.fromhex('FEFFFFFFFFFFFFFF')  # ePurse
                blocks[3] = bytes.fromhex('AEA684A6DAB21232')  # Kd (debit key)
                blocks[4] = bytes.fromhex('AEA684A6DAB21232')  # Kc (credit key)
                blocks[5] = bytes.fromhex('FFFFFFFFFFFFF3FF')  # App issuer
                # Blocks 6-18: application data — use distinct values so
                # iclasswrite detects them as "different from tag" and writes
                for i in range(6, 19):
                    blocks[i] = bytes([i, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07])
                dump_data = b''.join(blocks)
                with open(bin_path, 'wb') as f:
                    f.write(dump_data)
                # Also create .eml text version (hex per 8-byte block)
                eml_path = bin_path.replace('.bin', '.eml')
                with open(eml_path, 'w') as f:
                    for i in range(0, len(dump_data), 8):
                        f.write(dump_data[i:i+8].hex().upper() + '\n')
                print('[PM3] Created iCLASS dump %s (152 bytes, 19 blocks)' % bin_path, flush=True)
            except Exception as e:
                print('[PM3] Failed to create iCLASS dump: %s' % e, flush=True)
    # Handle 'lf t55xx dump f <path>' — PM3 creates .bin and .eml files
    # The .so passes this file path to WarningWriteActivity and verify needs it
    if 'lf t55xx dump' in cmd and ' f ' in cmd:
        fpath = cmd[cmd.index(' f ') + 3:].strip()
        if fpath:
            bin_path = fpath if fpath.endswith('.bin') else fpath + '.bin'
            try:
                os.makedirs(os.path.dirname(bin_path), exist_ok=True)
                # T55XX dump: 12 blocks × 4 bytes = 48 bytes (page 0 = 8 blocks, page 1 = 4 blocks)
                # Extract block data from fixture responses if available
                blocks = [b'\x00\x00\x00\x00'] * 12
                for bpat, bval in _RESPONSES.items():
                    if bpat.startswith('lf t55xx read b'):
                        bval_resp = bval[1] if isinstance(bval, tuple) else (bval[-1][1] if isinstance(bval, list) else str(bval))
                        import re as _re
                        m = _re.search(r'\|\s*([0-9A-Fa-f]{8})\s*\|', bval_resp)
                        if m:
                            hex_data = m.group(1)
                            # Determine block number from the response
                            bm = _re.search(r'(\d+)\s*\|', bval_resp)
                            if bm:
                                blk_num = int(bm.group(1))
                                if 0 <= blk_num < 12:
                                    blocks[blk_num] = bytes.fromhex(hex_data)
                dump_data = b''.join(blocks)
                with open(bin_path, 'wb') as f:
                    f.write(dump_data)
                # Also create .eml text version
                eml_path = bin_path.replace('.bin', '.eml')
                with open(eml_path, 'w') as f:
                    for i in range(0, len(dump_data), 4):
                        f.write(dump_data[i:i+4].hex().upper() + '\n')
                print('[PM3] Created T55XX dump %s (48 bytes)' % bin_path, flush=True)
            except Exception as e:
                print('[PM3] Failed to create T55XX dump: %s' % e, flush=True)
    # Handle 'hf mf csave <type> o <path>' — Gen1a magic card dump
    # readIfIsGen1a() in hfmfread.so sends this; it expects PM3 to create the .bin file.
    # Without the file, the read phase silently fails and M2:Write never appears.
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
                # Determine size from type parameter: csave <1|4> o <path>
                # type 1 = 1K (64 blocks × 16 bytes = 1024), type 4 = 4K (256 blocks × 16 = 4096)
                csave_type = 1
                for p in parts:
                    if p in ('1', '4'):
                        csave_type = int(p)
                        break
                num_blocks = 256 if csave_type == 4 else 64
                block_size = 16
                dump_size = num_blocks * block_size
                # Build dump with proper structure (block 0 has UID, sector trailers have keys)
                dump_data = bytearray(dump_size)
                # Extract UID from cgetblk response if available
                uid_bytes = bytes.fromhex('11223344')  # default
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
                # Block 0: UID + BCC + SAK + ATQA
                bcc = 0
                for b in uid_bytes:
                    bcc ^= b
                dump_data[0:4] = uid_bytes
                dump_data[4] = bcc
                dump_data[5] = 0x08 if csave_type == 1 else 0x18
                dump_data[6] = 0x04
                dump_data[7] = 0x00
                # Sector trailers: default keys FF...FF, access bits FF078069
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
                # Also create .eml text version
                eml_path = bin_path.replace('.bin', '.eml')
                with open(eml_path, 'w') as f:
                    for i in range(0, len(dump_data), block_size):
                        f.write(dump_data[i:i+block_size].hex().upper() + '\n')
                # Also create at base path (without .bin) — .so may open either
                if fpath and fpath != bin_path:
                    with open(fpath, 'wb') as f:
                        f.write(dump_data)
                print('[PM3] Created MFC Gen1a dump %s (%d bytes, %d blocks)' % (bin_path, dump_size, num_blocks), flush=True)
            except Exception as e:
                print('[PM3] Failed to create MFC csave dump: %s' % e, flush=True)
    for pat, val in sorted(_RESPONSES.items(), key=lambda kv: len(kv[0]), reverse=True):
        if pat in cmd:
            # Sequential responses: list of (ret, resp) tuples — advance per call, stay at last
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
            # Invoke listener callback with each line (used by _test_voltage.newlines etc.)
            if resp and listener:
                for _line in resp.split('\n'):
                    if _line.strip():
                        try: listener(_line)
                        except Exception: pass
            # Feed PM3 output to registered console callbacks (ConsolePrinterActivity)
            if resp: _invoke_task_callbacks(resp)
            # EM4305 dump: override response to include the actual bin path.
            # dump4X05() calls getContentFromRegex to extract DUMP_TEMP from the response text.
            # Fixture response has a placeholder; replace with real path so DUMP_TEMP is populated.
            if _em4x05_dump_bin_path and 'lf em 4x05_dump' in cmd:
                executor.CONTENT_OUT_IN__TXT_CACHE = '[+] saved 64 bytes to binary file %s\n' % _em4x05_dump_bin_path
            executor.LABEL_PM3_CMD_TASK_RUNNING = False
            executor.LABEL_PM3_CMD_TASK_STOP = True
            # startPM3Task returns 1=completed, -1=error
            result = ret if ret == -1 else 1
            if _QEMU_TRACE:
                _tlog('PM3< ret=%s seq=%d %s' % (result, _call_counts.get(pat, 0), (executor.CONTENT_OUT_IN__TXT_CACHE or '')[:150].replace('\n', '\\n')))
            return result
    executor.LABEL_PM3_CMD_TASK_RUNNING = False
    executor.LABEL_PM3_CMD_TASK_STOP = True
    # EM4305 dump fallback: even on DEFAULT_RETURN path, inject bin path into response
    if _em4x05_dump_bin_path and 'lf em 4x05_dump' in cmd:
        executor.CONTENT_OUT_IN__TXT_CACHE = '[+] saved 64 bytes to binary file %s\n' % _em4x05_dump_bin_path
    if _QEMU_TRACE:
        _tlog('PM3< DEFAULT ret=%s' % _DEFAULT_RET)
    return _DEFAULT_RET

executor.startPM3Task = _pm3_mock
executor.connect2PM3 = lambda *a, **k: True
executor.reworkPM3All = lambda: None

# Mock startPM3Ctrl (non-blocking sim/sniff commands) — same as startPM3Task
# SimulationActivity.startSim() uses startPM3Ctrl for long-running sim commands.
def _pm3_ctrl_mock(cmd, timeout=5000, listener=None, rework_max=2):
    print('[PM3-CTRL] %s' % cmd[:80], flush=True)
    return _pm3_mock(cmd, timeout=timeout, listener=listener, rework_max=rework_max)
executor.startPM3Ctrl = _pm3_ctrl_mock

# Mock stopPM3Task — sets STOP flag, used by SimulationActivity.stopSim()
def _pm3_stop_mock():
    print('[PM3-STOP]', flush=True)
    executor.LABEL_PM3_CMD_TASK_RUNNING = False
    executor.LABEL_PM3_CMD_TASK_STOP = True
executor.stopPM3Task = _pm3_stop_mock

# --- Executor task_call callback mechanism for ConsolePrinterActivity ---
# The real executor.so maintains a list of callbacks registered via add_task_call().
# When PM3 output arrives, each callback is invoked with the output line.
# ConsolePrinterActivity.on_exec_print uses this to display real-time PM3 output.
# We wrap add_task_call/del_task_call to track callbacks in Python, then invoke
# them from _pm3_mock after setting CONTENT_OUT_IN__TXT_CACHE.
_exec_task_callbacks = []
_orig_add_task_call = getattr(executor, 'add_task_call', None)
_orig_del_task_call = getattr(executor, 'del_task_call', None)

def _mock_add_task_call(callback):
    if callback not in _exec_task_callbacks:
        _exec_task_callbacks.append(callback)
    if _orig_add_task_call:
        try:
            _orig_add_task_call(callback)
        except Exception:
            pass

def _mock_del_task_call(callback):
    if callback in _exec_task_callbacks:
        _exec_task_callbacks.remove(callback)
    if _orig_del_task_call:
        try:
            _orig_del_task_call(callback)
        except Exception:
            pass

def _invoke_task_callbacks(text):
    """Feed PM3 output to all registered ConsolePrinterActivity callbacks.
    Each line is sent separately, matching real executor behavior."""
    if not _exec_task_callbacks or not text:
        return
    for line in text.split('\n'):
        if not line.strip():
            continue
        for cb in list(_exec_task_callbacks):
            try:
                cb(line)
            except Exception:
                pass

executor.add_task_call = _mock_add_task_call
executor.del_task_call = _mock_del_task_call

# --- Thread exception hook for debugging silent .so failures ---
import threading as _thr
def _thread_excepthook(args):
    print('[THREAD_EXCEPTION] %s: %s' % (args.exc_type.__name__, args.exc_value), flush=True)
    import traceback as _tb
    _tb.print_exception(args.exc_type, args.exc_value, args.exc_tb)
_thr.excepthook = _thread_excepthook

# --- hasKeyword/getContentFromRegex tracing (enabled via QEMU_TRACE) ---
if _QEMU_TRACE:
    _orig_hk = executor.hasKeyword
    def _traced_hk(keyword, content=None):
        result = _orig_hk(keyword, content)
        cached = getattr(executor, 'CONTENT_OUT_IN__TXT_CACHE', '<UNSET>')
        _tlog('HK(%s, c=%s) → %s  CACHE=%s' % (repr(keyword), repr(content)[:60] if content else 'None', result, repr(cached)[:100]))
        return result
    executor.hasKeyword = _traced_hk

    _orig_gr = executor.getContentFromRegex
    def _traced_gr(pattern, content=None):
        result = _orig_gr(pattern, content)
        cached = getattr(executor, 'CONTENT_OUT_IN__TXT_CACHE', '<UNSET>')
        _tlog('GR(%s, c=%s) → %s  CACHE=%s' % (repr(pattern), repr(content)[:60] if content else 'None', repr(result)[:100], repr(cached)[:80]))
        return result
    executor.getContentFromRegex = _traced_gr

    if hasattr(executor, 'getPrintContent'):
        _orig_gp = executor.getPrintContent
        def _traced_gp(content=None):
            result = _orig_gp(content)
            _tlog('GP(c=%s) → %s' % (repr(content)[:60] if content else 'None', repr(result)[:100]))
            return result
        executor.getPrintContent = _traced_gp

# HK/GR/GG tracing disabled in production — enable via QEMU_TRACE=1 env var
# The tracing changes function identity which breaks Cython module propagation detection

# Propagate PM3 mock to ALL modules that cache startPM3Task via 'from executor import startPM3Task'.
# Cython modules cache the function pointer at import time — patching executor alone is not enough.
# DRM (tagChk1 etc.) passes natively now — no bypasses needed. See docs/DRM-KB.md.
def _propagate_pm3_mock():
    for _mod_name in list(sys.modules.keys()):
        _mod = sys.modules.get(_mod_name)
        if _mod and _mod is not executor:
            if hasattr(_mod, 'startPM3Task') and getattr(_mod, 'startPM3Task') is not _pm3_mock:
                setattr(_mod, 'startPM3Task', _pm3_mock)
                print('[OK] Propagated PM3 mock → %s' % _mod_name, flush=True)
            if hasattr(_mod, 'startPM3Ctrl') and getattr(_mod, 'startPM3Ctrl') is not _pm3_ctrl_mock:
                setattr(_mod, 'startPM3Ctrl', _pm3_ctrl_mock)
                print('[OK] Propagated PM3 ctrl mock → %s' % _mod_name, flush=True)
            if hasattr(_mod, 'stopPM3Task') and getattr(_mod, 'stopPM3Task') is not _pm3_stop_mock:
                setattr(_mod, 'stopPM3Task', _pm3_stop_mock)
                print('[OK] Propagated PM3 stop mock → %s' % _mod_name, flush=True)
_propagate_pm3_mock()

_write_traced = False
def _trace_write_so():
    global _write_traced
    if _write_traced:
        return
    _wmod = sys.modules.get('write')
    if not _wmod or not hasattr(_wmod, 'write'):
        return
    if getattr(_wmod.write, '_traced', False):
        _write_traced = True
        return
    _ow = _wmod.write
    _ov = _wmod.verify
    def _tw(*a, **kw):
        for i, x in enumerate(a):
            if hasattr(x, '__self__'):
                print('[WRITE.write] arg%d: bound_method %s of %s' % (i, getattr(x, '__name__', '?'), type(x.__self__).__name__), flush=True)
                print('[WRITE.write] arg%d.__self__.bundle = %r' % (i, getattr(x.__self__, 'bundle', '??')), flush=True)
            elif isinstance(x, dict):
                print('[WRITE.write] arg%d: dict %r' % (i, x), flush=True)
            elif isinstance(x, str):
                print('[WRITE.write] arg%d: str=%r' % (i, x[:120]), flush=True)
            else:
                print('[WRITE.write] arg%d: %s=%r' % (i, type(x).__name__, str(x)[:80]), flush=True)
        return _ow(*a, **kw)
    _tw._traced = True
    _wmod.write = _tw
    def _tv(*a, **kw):
        for i, x in enumerate(a):
            if hasattr(x, '__self__'):
                print('[WRITE.verify] arg%d: bound_method %s of %s' % (i, getattr(x, '__name__', '?'), type(x.__self__).__name__), flush=True)
            elif isinstance(x, dict):
                print('[WRITE.verify] arg%d: dict keys=%s' % (i, list(x.keys())[:15]), flush=True)
            elif isinstance(x, str):
                print('[WRITE.verify] arg%d: str=%r' % (i, x[:120]), flush=True)
            else:
                print('[WRITE.verify] arg%d: %s=%r' % (i, type(x).__name__, str(x)[:80]), flush=True)
        return _ov(*a, **kw)
    _wmod.verify = _tv
    _write_traced = True
    print('[OK] write.so traced', flush=True)

def _pm3_propagation_loop():
    while True:
        time.sleep(2)
        _propagate_pm3_mock()
        try:
            _trace_write_so()
        except Exception:
            pass
threading.Thread(target=_pm3_propagation_loop, daemon=True).start()
print('[OK] Executor mocked (with propagation)', flush=True)

# === Key injection + GOTO support ===
_main_activity = None
_tk_root = None

_orig_ma_init = actmain.MainActivity.init
def _capture_init(self):
    global _main_activity
    _main_activity = self
    print('[GOTO] Captured MainActivity', flush=True)
    return _orig_ma_init(self)
actmain.MainActivity.init = _capture_init

import tkinter as tk
_orig_tk_init = tk.Tk.__init__
def _capture_tk(self, *a, **k):
    global _tk_root
    _orig_tk_init(self, *a, **k)
    _tk_root = self
    print('[OK] Tk root captured', flush=True)

    # Add TOAST_CANCEL command support
    # The toast adds a full-screen mask (rectangle with stipple), an inner box,
    # an icon/image, and text. All drawn ON TOP of the result content.
    # Strategy: find the canvas, get all items, identify and delete the toast layer.
    # The toast items are drawn AFTER the activity content, so they have the
    # highest item IDs. We delete from the top down until we hit content items.
    def _cancel_toast():
        """Cancel toast by finding and deleting toast canvas items.

        Toast items are tagged as '<object_id>:mask_layer', '<object_id>:text_bg',
        '<object_id>:text', '<object_id>:icon'. We find items whose tags contain
        'mask_layer' and extract the object_id prefix, then delete ALL items
        with that prefix.
        """
        try:
            for child in self.winfo_children():
                if not hasattr(child, 'find_all') or not hasattr(child, 'gettags'):
                    continue
                # Find the toast object ID by looking for mask_layer items
                toast_ids = set()
                for item in child.find_all():
                    try:
                        tags = child.gettags(item)
                        for tag in tags:
                            if ':mask_layer' in tag or ':text_bg' in tag:
                                obj_id = tag.split(':')[0]
                                toast_ids.add(obj_id)
                    except: pass

                if toast_ids:
                    # Delete ALL items belonging to these toast objects
                    deleted = 0
                    for item in list(child.find_all()):
                        try:
                            tags = child.gettags(item)
                            for tag in tags:
                                if any(tag.startswith(tid + ':') for tid in toast_ids):
                                    child.delete(item)
                                    deleted += 1
                                    break
                        except: pass
                    print('[TOAST_CANCEL] Deleted %d items from %d toast(s)' % (deleted, len(toast_ids)), flush=True)
                else:
                    print('[TOAST_CANCEL] No toast items found', flush=True)
        except Exception as e:
            print('[TOAST_CANCEL] Error: %s' % e, flush=True)
    # Store for use by key reader
    builtins._cancel_toast = _cancel_toast

    # Bind HMI key callbacks after 3s
    def _bind_keys():
        try:
            import hmi_driver, keymap
            bound = 0
            for ks in hmi_driver.SerialKeyCode:
                if hmi_driver.SerialKeyCode[ks]['meth'] is None:
                    hmi_driver.SerialKeyCode[ks]['meth'] = keymap.key.onKey
                    bound += 1
            print('[HMI] Bound %d key callbacks' % bound, flush=True)
        except Exception as e:
            print('[HMI] Error: %s' % e, flush=True)
    self.after(3000, _bind_keys)

    # Canvas state polling — periodically dump all text items to trace
    # when Decoding/TraceLen items appear and disappear.
    if _QEMU_TRACE:
        _prev_canvas_texts = [set()]
        def _poll_canvas_state():
            try:
                for child in self.winfo_children():
                    canvas = None
                    if hasattr(child, 'find_all'):
                        canvas = child
                    else:
                        for sub in child.winfo_children():
                            if hasattr(sub, 'find_all'):
                                canvas = sub; break
                    if canvas:
                        texts = set()
                        for item in canvas.find_all():
                            if canvas.type(item) == 'text':
                                txt = canvas.itemcget(item, 'text') or ''
                                if 'Decoding' in txt or 'TraceLen' in txt or 'UID' in txt or 'Key' in txt:
                                    coords = canvas.coords(item)
                                    fill = canvas.itemcget(item, 'fill')
                                    texts.add('id=%s %r xy=(%.0f,%.0f) fill=%s' % (
                                        item, txt[:40], coords[0] if coords else 0, coords[1] if len(coords)>1 else 0, fill))
                        if texts != _prev_canvas_texts[0]:
                            added = texts - _prev_canvas_texts[0]
                            removed = _prev_canvas_texts[0] - texts
                            if added: _tlog('CANVAS+ %s' % added)
                            if removed: _tlog('CANVAS- %s' % removed)
                            _prev_canvas_texts[0] = texts
            except: pass
            self.after(100, _poll_canvas_state)  # poll every 100ms
        self.after(4000, _poll_canvas_state)

tk.Tk.__init__ = _capture_tk

def _inject_key(name):
    # PWR while console is showing: hide the console Frame, consume the key.
    # On the real device, ReadListActivity.onKeyEvent checks console_activity.is_showing()
    # and calls console_activity.hidden() when PWR is pressed. In QEMU, this check in the
    # .so binary sometimes fails to propagate because the console is an embedded overlay
    # (not a separate activity on the stack). We replicate the real device behavior by
    # detecting the console Frame in the tkinter widget tree and hiding it.
    if name == 'PWR' and _tk_root:
        try:
            import tkinter
            # Walk ALL widgets recursively looking for a Frame with a Text child
            def _find_console_frame(parent, depth=0):
                for child in parent.winfo_children():
                    ctype = type(child).__name__
                    if depth == 0:
                        print('[PWR-SCAN] d%d %s bg=%s children=%d' % (
                            depth, ctype,
                            child.cget('bg') if hasattr(child, 'cget') else '?',
                            len(child.winfo_children())
                        ), flush=True)
                    if isinstance(child, tkinter.Frame):
                        for sub in child.winfo_children():
                            if isinstance(sub, tkinter.Text):
                                # Found console Frame+Text pair.
                                # Destroy the Frame entirely (removes from display).
                                # Schedule on main thread for proper tkinter handling.
                                _fref = child
                                def _hide_console(f=_fref):
                                    try:
                                        f.place_forget()
                                        f.destroy()
                                    except Exception:
                                        pass
                                _tk_root.after(0, _hide_console)
                                print('[KEY] PWR → console destroy scheduled bg=%s' % child.cget('bg'), flush=True)
                                return True
                    # Recurse into children
                    if _find_console_frame(child, depth + 1):
                        return True
                return False
            if _find_console_frame(_tk_root):
                return  # Consumed — don't propagate PWR
            print('[KEY] PWR → no console Frame found, propagating', flush=True)
        except Exception as e:
            print('[KEY] PWR console check error: %s' % e, flush=True)

    key = ('%s_PRES!\r\n' % name).encode()
    with _lk:
        p = _key_buf.tell(); _key_buf.seek(0, 2); _key_buf.write(key); _key_buf.seek(p)

# === State dump — extracts full UI + cache state as JSON ===
import json as _json

_state_dump_counter = 0
STATE_DUMP_DIR = os.environ.get('STATE_DUMP_DIR', '/tmp/state_dumps')

def _dump_state():
    """Dump complete application state to a JSON file.

    Extracts from the LIVE running app (not OCR):
    - Activity stack (class names, lifecycle)
    - Canvas text items by tag (title, M1, M2, content, toast)
    - Scan cache (scan.getScanCache())
    - Executor state (PM3 task state, last content)
    - All canvas items with coordinates, types, tags, text
    """
    global _state_dump_counter
    _state_dump_counter += 1
    os.makedirs(STATE_DUMP_DIR, exist_ok=True)
    outpath = os.path.join(STATE_DUMP_DIR, 'state_%03d.json' % _state_dump_counter)

    state = {
        'seq': _state_dump_counter,
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
            # Stack may contain dicts or activity objects
            if isinstance(top, dict):
                state['current_activity'] = top.get('class', top.get('__class__', type(top).__name__))
            else:
                state['current_activity'] = top.__class__.__name__

            # Get canvas — try activity methods, then _tk_root children
            canvas = None
            if not isinstance(top, dict):
                try: canvas = top.getCanvas()
                except:
                    try: canvas = top._canvas
                    except: pass
            if canvas is None and _tk_root:
                # Get the LAST (topmost/active) canvas, not the first
                for child in _tk_root.winfo_children():
                    if hasattr(child, 'find_all') and hasattr(child, 'find_withtag'):
                        canvas = child

            if canvas:
                # Tag format in the real .so: "ID:{uid}-title", "{uid}:text", etc.
                # Classify items by their tag patterns
                title_ids = set()
                btn_left_ids = set()
                btn_right_ids = set()
                btn_bg_ids = set()
                toast_obj_ids = set()

                for item in canvas.find_all():
                    tags = canvas.gettags(item)
                    for tag in tags:
                        tl = tag.lower()
                        if '-title' in tl or tl == 'tags_title':
                            title_ids.add(item)
                        elif '-btnleft' in tl or tl == 'tags_btn_left':
                            btn_left_ids.add(item)
                        elif '-btnright' in tl or tl == 'tags_btn_right':
                            btn_right_ids.add(item)
                        elif '-btnbg' in tl or tl == 'tags_btn_bg':
                            btn_bg_ids.add(item)
                        elif ':mask_layer' in tag or ':text_bg' in tag:
                            toast_obj_ids.add(tag.split(':')[0])

                # Title
                for item in title_ids:
                    if canvas.type(item) == 'text':
                        state['title'] = canvas.itemcget(item, 'text')

                # M1 (left button) — also check by coords (y > 200, x < 120)
                for item in btn_left_ids:
                    if canvas.type(item) == 'text':
                        t = canvas.itemcget(item, 'text')
                        if t: state['M1'] = t
                if not state['M1']:
                    for item in canvas.find_all():
                        if canvas.type(item) == 'text':
                            coords = canvas.coords(item)
                            if coords and len(coords) >= 2 and coords[1] >= 200 and coords[0] < 120:
                                t = canvas.itemcget(item, 'text')
                                if t and item not in title_ids:
                                    state['M1'] = t
                                    btn_left_ids.add(item)
                                    break

                # M2 (right button) — also check by coords (y > 200, x >= 120)
                for item in btn_right_ids:
                    if canvas.type(item) == 'text':
                        t = canvas.itemcget(item, 'text')
                        if t: state['M2'] = t
                if not state['M2']:
                    for item in canvas.find_all():
                        if canvas.type(item) == 'text':
                            coords = canvas.coords(item)
                            if coords and len(coords) >= 2 and coords[1] >= 200 and coords[0] >= 120:
                                t = canvas.itemcget(item, 'text')
                                if t and item not in title_ids and item not in btn_left_ids:
                                    state['M2'] = t
                                    btn_right_ids.add(item)
                                    break

                # Button visibility — derived from whether text items exist.
                state['M1_visible'] = bool(state['M1'])
                state['M2_visible'] = bool(state['M2'])

                # Button active state — derived from canvas fill color.
                # The .so modules render inactive buttons with grey (#808080).
                # Default is True (active); only set False if fill is dimmed.
                _DIMMED = {'#808080', 'grey', '#808088', 'gray'}
                for item in btn_left_ids:
                    if canvas.type(item) == 'text':
                        fill = (canvas.itemcget(item, 'fill') or '').lower()
                        if fill in _DIMMED:
                            state['M1_active'] = False
                        break
                for item in btn_right_ids:
                    if canvas.type(item) == 'text':
                        fill = (canvas.itemcget(item, 'fill') or '').lower()
                        if fill in _DIMMED:
                            state['M2_active'] = False
                        break

                # Toast — items belonging to toast object IDs
                toast_item_ids = set()
                toast_text_parts = []
                if toast_obj_ids:
                    for item in canvas.find_all():
                        for tag in canvas.gettags(item):
                            if any(tag.startswith(tid + ':') for tid in toast_obj_ids):
                                toast_item_ids.add(item)
                                if canvas.type(item) == 'text':
                                    toast_text_parts.append(canvas.itemcget(item, 'text'))
                if toast_text_parts:
                    state['toast'] = '\n'.join(toast_text_parts)

                # Content text — everything except title, buttons, toast, battery
                skip = title_ids | btn_left_ids | btn_right_ids | btn_bg_ids | toast_item_ids
                for item in canvas.find_all():
                    if item in skip: continue
                    if canvas.type(item) == 'text':
                        txt = canvas.itemcget(item, 'text')
                        if txt:
                            coords = canvas.coords(item)
                            y = coords[1] if len(coords) > 1 else 0
                            # Skip battery text (top-right, small font)
                            if y < 35 and coords[0] > 170: continue
                            state['content_text'].append({
                                'text': txt,
                                'x': coords[0] if coords else 0,
                                'y': y,
                                'fill': canvas.itemcget(item, 'fill'),
                                'font': canvas.itemcget(item, 'font'),
                            })

                # Full canvas item dump
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
        cache = scan.getScanCache()
        if cache is not None:
            # Convert to JSON-safe dict
            if isinstance(cache, dict):
                state['scan_cache'] = {str(k): repr(v) for k, v in cache.items()}
            else:
                state['scan_cache'] = repr(cache)
    except Exception as e:
        state['_scan_cache_error'] = str(e)

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
        print('[STATE_DUMP] #%d → %s' % (_state_dump_counter, outpath), flush=True)
    except Exception as e:
        print('[STATE_DUMP] Error writing: %s' % e, flush=True)


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
                                _tk_root.after(0, lambda p=pos: _main_activity.gotoActByPos(p))
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
                                _tk_root.after(0, _dump_state)
                        else:
                            _inject_key(k)
                            print('[KEY] %s' % k, flush=True)
                    last_pos = f.tell()
        except Exception: pass
        time.sleep(0.2)

threading.Thread(target=_key_reader, daemon=True).start()
print('[OK] Key injection ready (%s)' % KEYFILE, flush=True)

# === Launch ===
print('[START] application.startApp()', flush=True)
import application
application.startApp()
