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

"""Diagnostic script: probe scan.so under QEMU to understand its API.

Runs under QEMU with the same mocks as launcher_current.py.
Goal: figure out why scan.scanForType(None, self) doesn't fire PM3 commands.

Usage:
    DISPLAY=:99 /home/qx/.local/bin/qemu-arm-static \
        /mnt/sdcard/root2/root/usr/local/python-3.8.0/bin/python3.8 \
        /home/qx/icopy-x-reimpl/tools/diag_scan.py
"""
import sys
import os
import types
import io
import threading
import builtins
import time
import traceback

# =====================================================================
# ENVIRONMENT SETUP (mirrors launcher_current.py)
# =====================================================================

os.environ.setdefault('DISPLAY', ':99')
APP_DIR = '/mnt/sdcard/root2/root/home/pi/ipk_app_main'
PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHIMS = os.path.join(PROJECT, 'tools', 'qemu_shims')

os.chdir(APP_DIR)

# Import real pygame BEFORE lib/ goes on path
sys.path.insert(0, SHIMS)
import pygame

# App paths
SITE_PKGS = '/mnt/sdcard/root2/root/home/pi/.local/lib/python3.8/site-packages'
sys.path.insert(0, os.path.join(APP_DIR, 'main'))
sys.path.insert(0, os.path.join(APP_DIR, 'lib'))
sys.path.insert(0, SHIMS)
sys.path.insert(0, SITE_PKGS)

# Do NOT put src/lib on path — we want the REAL .so modules, not our Python shadows
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
Serial\t\t: 02150004f4584d53
"""
    return b''
subprocess.check_output = _mock_check_output

# === Mock glob for ttyGS ===
import glob as _gmod
_orig_glob = _gmod.glob
_gmod.glob = lambda p, **kw: ['/dev/ttyGS0'] if 'ttyGS' in p else _orig_glob(p, **kw)

# === Mock serial ===
_buf = io.BytesIO()
_key_buf = io.BytesIO()
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

# === Mock pygame.mixer ===
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

# === Mock psutil ===
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

# === Safe os.listdir ===
_orig_listdir = os.listdir
def _safe_listdir(path):
    try: return _orig_listdir(path)
    except (FileNotFoundError, OSError): return []
os.listdir = _safe_listdir

print('[SETUP] All mocks ready', flush=True)

# =====================================================================
# LOGGING INFRASTRUCTURE
# =====================================================================

_log = []
_thread_log = []
_pm3_log = []
_callback_log = []
_attr_log = []
_exception_log = []

def log(tag, msg):
    line = '[%s] %s' % (tag, msg)
    _log.append(line)
    print(line, flush=True)

# =====================================================================
# MONKEY-PATCH threading.Thread to log all thread creations
# =====================================================================

_OrigThread = threading.Thread
class _LoggingThread(_OrigThread):
    def __init__(self, *args, **kwargs):
        target = kwargs.get('target') or (args[1] if len(args) > 1 else None)
        name = kwargs.get('name', '') or (args[0] if args else '')
        info = 'Thread(name=%r, target=%r, args=%r)' % (
            name,
            getattr(target, '__qualname__', getattr(target, '__name__', repr(target))),
            kwargs.get('args', ())[:3] if kwargs.get('args') else ()
        )
        _thread_log.append(info)
        log('THREAD', info)
        super().__init__(*args, **kwargs)

    def run(self):
        try:
            super().run()
        except Exception as e:
            info = 'Thread %r exception: %s: %s' % (self.name, type(e).__name__, e)
            _exception_log.append(info)
            log('THREAD_EXC', info)
            traceback.print_exc()

threading.Thread = _LoggingThread

# =====================================================================
# IMPORT EXECUTOR AND MOCK PM3
# =====================================================================

log('IMPORT', 'Loading executor...')
import executor

def _pm3_mock(cmd, timeout=5000, listener=None, rework_max=2):
    info = 'startPM3Task(cmd=%r, timeout=%s)' % (cmd[:120], timeout)
    _pm3_log.append(info)
    log('PM3', info)

    # Create .pm3 file for data save commands (lf_wav_filter needs this)
    if cmd.startswith('data save f '):
        fpath = cmd[len('data save f '):].strip()
        if fpath:
            pm3_path = fpath + '.pm3'
            try:
                with open(pm3_path, 'w') as f:
                    for i in range(256):
                        val = 120 if (i // 8) % 2 == 0 else -120
                        f.write('%d\n' % val)
                log('PM3', 'Created trace file %s' % pm3_path)
            except Exception as e:
                log('PM3', 'Failed to create trace: %s' % e)

    executor.LABEL_PM3_CMD_TASK_RUNNING = False
    executor.LABEL_PM3_CMD_TASK_STOP = True
    executor.CONTENT_OUT_IN__TXT_CACHE = ''
    return 1  # 1 = completed

executor.startPM3Task = _pm3_mock
executor.connect2PM3 = lambda *a, **k: True
executor.reworkPM3All = lambda: None
executor.startPM3Ctrl = lambda cmd, **kw: (_pm3_log.append('startPM3Ctrl(%r)' % cmd), log('PM3-CTRL', cmd), 1)[-1]
executor.stopPM3Task = lambda: log('PM3', 'stopPM3Task()')

# Propagate to all loaded modules
def _propagate():
    for name in list(sys.modules.keys()):
        mod = sys.modules.get(name)
        if mod and mod is not executor:
            if hasattr(mod, 'startPM3Task'):
                setattr(mod, 'startPM3Task', _pm3_mock)
_propagate()

# =====================================================================
# IMPORT TAGTYPES (needed by scan.so)
# =====================================================================

log('IMPORT', 'Loading tagtypes...')
try:
    import tagtypes as _tt
    _readable = _tt.getReadable()
    if isinstance(_readable, (list, tuple)) and len(_readable) >= 30:
        log('DRM', 'tagtypes OK: %d readable types' % len(_readable))
    else:
        log('DRM', 'tagtypes bypass needed (got %s)' % type(_readable).__name__)
        _tt.getReadable = lambda: [1, 42, 0, 41, 25, 26, 2, 3, 4, 5, 6, 7, 19, 46,
                                   20, 21, 17, 18, 8, 9, 10, 11, 12, 13, 14, 15, 16,
                                   28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 45, 23, 24]
except Exception as e:
    log('DRM', 'tagtypes import failed: %s' % e)

# =====================================================================
# IMPORT scan.so
# =====================================================================

log('IMPORT', 'Loading scan.so...')
try:
    import scan
    log('IMPORT', 'scan.so loaded OK')
except Exception as e:
    log('IMPORT', 'scan.so import FAILED: %s' % e)
    traceback.print_exc()
    scan = None

# =====================================================================
# PROBE 1: List all public attributes
# =====================================================================

if scan:
    log('PROBE', '=== dir(scan) ===')
    attrs = sorted(dir(scan))
    for a in attrs:
        try:
            val = getattr(scan, a)
            typename = type(val).__name__
            if callable(val):
                log('ATTR', '  %s -> %s (callable)' % (a, typename))
            else:
                log('ATTR', '  %s -> %s = %r' % (a, typename, val))
        except Exception as e:
            log('ATTR', '  %s -> ERROR: %s' % (a, e))

    # Check specific expected functions
    for fn_name in ['scanForType', 'scan_all_asynchronous', 'scan_stop',
                    'getScanCache', 'setScanCache', 'Scanner',
                    'lf_wav_filter']:
        has = hasattr(scan, fn_name)
        log('CHECK', '%s: %s' % (fn_name, 'EXISTS' if has else 'MISSING'))

# =====================================================================
# PROBE 2: Build a comprehensive mock listener
# =====================================================================

class DiagListener:
    """Mock listener that logs every callback scan.so makes."""

    def __init__(self, name='DiagListener'):
        self._name = name
        self._calls = []

    def __getattr__(self, name):
        """Catch-all for ANY attribute access scan.so might do."""
        if name.startswith('_'):
            raise AttributeError(name)
        def _handler(*args, **kwargs):
            info = '%s.%s(%s%s)' % (
                self._name, name,
                ', '.join(repr(a)[:200] for a in args),
                (', ' + ', '.join('%s=%r' % (k, v) for k, v in kwargs.items())) if kwargs else ''
            )
            self._calls.append(info)
            _callback_log.append(info)
            log('CALLBACK', info)
            return None
        log('ATTR_ACCESS', '%s.%s accessed' % (self._name, name))
        return _handler

    def __setattr__(self, name, value):
        if name.startswith('_'):
            super().__setattr__(name, value)
            return
        info = '%s.%s = %r' % (self._name, name, value)
        _attr_log.append(info)
        log('SETATTR', info)
        super().__setattr__(name, value)

    # Explicitly define known callbacks to avoid __getattr__ masking issues
    def onScanFinish(self, result):
        info = '%s.onScanFinish(%r)' % (self._name, result)
        self._calls.append(info)
        _callback_log.append(info)
        log('CALLBACK', info)

    def onScanning(self, progress):
        info = '%s.onScanning(%r)' % (self._name, progress)
        self._calls.append(info)
        _callback_log.append(info)
        log('CALLBACK', info)

    def onAutoScan(self, *args):
        info = '%s.onAutoScan(%s)' % (self._name, ', '.join(repr(a) for a in args))
        self._calls.append(info)
        _callback_log.append(info)
        log('CALLBACK', info)

    def how2Scan(self, *args):
        info = '%s.how2Scan(%s)' % (self._name, ', '.join(repr(a) for a in args))
        self._calls.append(info)
        _callback_log.append(info)
        log('CALLBACK', info)

    def canidle(self):
        log('CALLBACK', '%s.canidle()' % self._name)
        _callback_log.append('%s.canidle()' % self._name)
        return False  # Not idle

    def getManifest(self):
        log('CALLBACK', '%s.getManifest()' % self._name)
        _callback_log.append('%s.getManifest()' % self._name)
        return None

    def playScanning(self):
        log('CALLBACK', '%s.playScanning()' % self._name)
        _callback_log.append('%s.playScanning()' % self._name)

    def showButton(self, *args):
        info = '%s.showButton(%s)' % (self._name, ', '.join(repr(a) for a in args))
        self._calls.append(info)
        _callback_log.append(info)
        log('CALLBACK', info)

    def showScanToast(self, *args, **kwargs):
        info = '%s.showScanToast(%s)' % (self._name, ', '.join(repr(a) for a in args))
        self._calls.append(info)
        _callback_log.append(info)
        log('CALLBACK', info)

    def setScanCache(self, *args):
        info = '%s.setScanCache(%s)' % (self._name, ', '.join(repr(a)[:200] for a in args))
        self._calls.append(info)
        _callback_log.append(info)
        log('CALLBACK', info)


# =====================================================================
# PROBE 3: Try scanForType(None, listener) — "scan all" mode
# =====================================================================

if scan and hasattr(scan, 'scanForType'):
    log('TEST', '=== scanForType(None, listener) ===')
    listener1 = DiagListener('L1-scanForType-None')
    try:
        # Re-propagate PM3 mock right before call
        _propagate()
        result = scan.scanForType(None, listener1)
        log('TEST', 'scanForType(None, listener) returned: %r' % (result,))
    except Exception as e:
        log('TEST', 'scanForType(None, listener) EXCEPTION: %s: %s' % (type(e).__name__, e))
        traceback.print_exc()

    log('TEST', 'Waiting 10s for async callbacks...')
    time.sleep(10)
    _propagate()
    log('TEST', 'After 10s: %d PM3 calls, %d callbacks, %d threads' % (
        len(_pm3_log), len(_callback_log), len(_thread_log)))

    # Check if scan.so cached startPM3Task before we mocked it
    log('CHECK', 'executor.startPM3Task is our mock: %s' % (executor.startPM3Task is _pm3_mock,))
    if hasattr(scan, 'startPM3Task'):
        log('CHECK', 'scan.startPM3Task exists: %r' % (scan.startPM3Task,))
        log('CHECK', 'scan.startPM3Task is our mock: %s' % (scan.startPM3Task is _pm3_mock,))
    else:
        log('CHECK', 'scan module has no startPM3Task attribute')

    # Check executor module attributes that scan.so reads
    for attr_name in ['CONTENT_OUT_IN__TXT_CACHE', 'LABEL_PM3_CMD_TASK_RUNNING',
                      'LABEL_PM3_CMD_TASK_STOP', 'hasKeyword', 'getContentFromRegex',
                      'getPrintContent']:
        val = getattr(executor, attr_name, 'MISSING')
        log('EXECUTOR', '%s = %r' % (attr_name, val if not callable(val) else '<callable>'))
else:
    log('TEST', 'SKIP scanForType — not available')

# =====================================================================
# PROBE 4: Try scanForType(0, listener) — "scan type 0" mode
# =====================================================================

if scan and hasattr(scan, 'scanForType'):
    log('TEST', '=== scanForType(0, listener) ===')
    _pm3_log_before = len(_pm3_log)
    _callback_log_before = len(_callback_log)
    listener2 = DiagListener('L2-scanForType-0')
    try:
        _propagate()
        result = scan.scanForType(0, listener2)
        log('TEST', 'scanForType(0, listener) returned: %r' % (result,))
    except Exception as e:
        log('TEST', 'scanForType(0, listener) EXCEPTION: %s: %s' % (type(e).__name__, e))
        traceback.print_exc()

    log('TEST', 'Waiting 10s for async callbacks...')
    time.sleep(10)
    _propagate()
    new_pm3 = len(_pm3_log) - _pm3_log_before
    new_cb = len(_callback_log) - _callback_log_before
    log('TEST', 'After 10s: %d new PM3 calls, %d new callbacks' % (new_pm3, new_cb))

# =====================================================================
# PROBE 5: Try scan.Scanner() and scan_all_asynchronous
# =====================================================================

if scan and hasattr(scan, 'Scanner'):
    log('TEST', '=== scan.Scanner() ===')
    try:
        scanner = scan.Scanner()
        log('TEST', 'Scanner() created: %r' % (scanner,))
        log('TEST', 'Scanner dir: %s' % sorted(dir(scanner)))
    except Exception as e:
        log('TEST', 'Scanner() EXCEPTION: %s: %s' % (type(e).__name__, e))
        traceback.print_exc()
elif scan:
    log('TEST', 'SKIP Scanner — not in dir(scan)')

if scan and hasattr(scan, 'scan_all_asynchronous'):
    log('TEST', '=== scan.scan_all_asynchronous(listener) ===')
    _pm3_log_before = len(_pm3_log)
    _callback_log_before = len(_callback_log)
    listener3 = DiagListener('L3-scan_all_async')
    try:
        _propagate()
        result = scan.scan_all_asynchronous(listener3)
        log('TEST', 'scan_all_asynchronous(listener) returned: %r' % (result,))
    except Exception as e:
        log('TEST', 'scan_all_asynchronous(listener) EXCEPTION: %s: %s' % (type(e).__name__, e))
        traceback.print_exc()

    log('TEST', 'Waiting 10s for async callbacks...')
    time.sleep(10)
    _propagate()
    new_pm3 = len(_pm3_log) - _pm3_log_before
    new_cb = len(_callback_log) - _callback_log_before
    log('TEST', 'After 10s: %d new PM3 calls, %d new callbacks' % (new_pm3, new_cb))
elif scan:
    log('TEST', 'SKIP scan_all_asynchronous — not in dir(scan)')

# =====================================================================
# PROBE 6: Check how scan.so accesses executor
# =====================================================================

if scan:
    log('PROBE', '=== How scan.so accesses executor ===')
    # Check if scan.so has its own reference to executor functions
    for attr in ['startPM3Task', 'connect2PM3', 'CONTENT_OUT_IN__TXT_CACHE',
                 'LABEL_PM3_CMD_TASK_RUNNING', 'hasKeyword', 'getContentFromRegex',
                 'getPrintContent']:
        if hasattr(scan, attr):
            val = getattr(scan, attr)
            log('SCAN_ATTR', 'scan.%s = %r (is our mock: %s)' % (
                attr, val if not callable(val) else '<callable>',
                val is _pm3_mock if attr == 'startPM3Task' else 'N/A'))

    # Check the scan module's __dict__ for any executor-related refs
    for key, val in sorted(scan.__dict__.items()) if hasattr(scan, '__dict__') else []:
        if 'executor' in str(key).lower() or 'pm3' in str(key).lower() or 'task' in str(key).lower():
            log('SCAN_DICT', 'scan.__dict__[%r] = %r' % (key, val))

# =====================================================================
# PROBE 7: Inspect executor module as scan.so sees it
# =====================================================================

log('PROBE', '=== executor module state ===')
exec_mod = sys.modules.get('executor')
if exec_mod:
    for attr in sorted(dir(exec_mod)):
        if attr.startswith('_'):
            continue
        try:
            val = getattr(exec_mod, attr)
            if callable(val):
                is_mock = val is _pm3_mock
                log('EXEC_ATTR', '%s -> callable%s' % (attr, ' (OUR MOCK)' if is_mock else ''))
            else:
                log('EXEC_ATTR', '%s = %r' % (attr, val))
        except Exception as e:
            log('EXEC_ATTR', '%s -> ERROR: %s' % (attr, e))

# =====================================================================
# PROBE 8: Check active threads
# =====================================================================

log('PROBE', '=== Active threads ===')
for t in threading.enumerate():
    log('THREAD', 'alive: %s (daemon=%s, target=%s)' % (
        t.name, t.daemon, getattr(t, '_target', None)))

# =====================================================================
# SUMMARY
# =====================================================================

print('\n' + '=' * 70, flush=True)
print('DIAGNOSTIC SUMMARY', flush=True)
print('=' * 70, flush=True)
print('scan.so loaded:        %s' % (scan is not None), flush=True)
if scan:
    print('scan attributes:       %s' % sorted(a for a in dir(scan) if not a.startswith('_')), flush=True)
print('Total PM3 commands:    %d' % len(_pm3_log), flush=True)
for cmd in _pm3_log:
    print('  %s' % cmd, flush=True)
print('Total callbacks:       %d' % len(_callback_log), flush=True)
for cb in _callback_log:
    print('  %s' % cb, flush=True)
print('Total threads created: %d' % len(_thread_log), flush=True)
for t in _thread_log:
    print('  %s' % t, flush=True)
print('Attribute sets:        %d' % len(_attr_log), flush=True)
for a in _attr_log:
    print('  %s' % a, flush=True)
print('Exceptions:            %d' % len(_exception_log), flush=True)
for e in _exception_log:
    print('  %s' % e, flush=True)
print('=' * 70, flush=True)

if not _pm3_log:
    print('\nDIAGNOSIS: No PM3 commands fired!', flush=True)
    print('Possible causes:', flush=True)
    print('  1. scan.so caches executor.startPM3Task at import time', flush=True)
    print('     -> Fix: mock executor BEFORE importing scan.so', flush=True)
    print('  2. scan.so uses Cython direct C-call to executor (not Python attr lookup)', flush=True)
    print('     -> Fix: must replace at C level or use scenario file approach', flush=True)
    print('  3. scanForType is async and thread died silently', flush=True)
    print('     -> Check thread exceptions above', flush=True)
    print('  4. scan.so needs additional setup (connect2PM3, etc.)', flush=True)
    print('     -> Check attribute access log above', flush=True)
else:
    print('\nPM3 commands were fired! The mock is working.', flush=True)

print('\nDone.', flush=True)
