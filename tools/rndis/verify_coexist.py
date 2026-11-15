#!/usr/bin/env python3
"""Check the RNDIS coexistence change, in a tree or on an installed device.

Default (behavioural, no root, no device):
  * upan_and_serial() empties the configfs UDC (with a newline) *before* it
    touches any gadget module;
  * kill_all_module() restarts rndis.service *after* reloading g_serial;
  * mirror_service releases/restores around its own gadget;
  * both helpers are silent no-ops when no RNDIS gadget is installed.

--installed DIR (static, read-only): the same ordering checked against the app
that is actually running, whether it carries the native helpers or the injected
``patch_stock_ipk.py`` blocks. Behavioural probing is not possible there: the
injected form hardcodes the live configfs path, so exercising it would detach
the real gadget — the network you are connected over.

Run:
  python3 tools/rndis/verify_coexist.py
  python3 tools/rndis/verify_coexist.py --installed /home/pi/ipk_app_main/lib
  python3 tools/rndis/verify_coexist.py --installed src/middleware src/lib
"""
import ast
import os
import re
import shutil
import sys
import tempfile

argv = sys.argv[1:]
INSTALLED = bool(argv) and argv[0] == '--installed'

if not INSTALLED:  # static mode needs neither the modules nor a source tree
    REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, os.path.join(REPO, 'src', 'middleware'))
    sys.path.insert(0, os.path.join(REPO, 'src', 'lib'))

    import gadget_linux  # noqa: E402
    import mirror_service  # noqa: E402

# Markers that mean "release the UDC" / "rebuild the RNDIS gadget", in both the
# native form (helpers in gadget_linux) and the injected form (post-patch).
RELEASE = ('release_rndis_udc(', 'UDC')
RESTORE = ('restore_rndis(', 'restart rndis.service')


def gadget_calls(source, func_name):
    """Gadget-related calls inside *func_name*, in source order."""
    tree = ast.parse(source)
    func = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            func = node
            break
    if func is None:
        return None
    calls = []
    for node in ast.walk(func):
        if isinstance(node, ast.Call):
            text = ' '.join((ast.get_source_segment(source, node) or '').split())
            if ('UDC' in text or 'modprobe' in text or 'rndis.service' in text
                    or 'release_rndis_udc' in text or 'restore_rndis' in text):
                calls.append((node.lineno, text))
    calls.sort()
    return calls


def is_release(text):
    return any(part in text for part in RELEASE)


def is_restore(text):
    return any(part in text for part in RESTORE)


def check_installed(dirs):
    """Static ordering check of an installed app tree (no import, no side effects).

    *dirs* may be one directory (the device keeps both modules in lib/) or
    several (a source tree splits them over middleware/ and lib/).
    """
    problems = []
    results = []

    def report(cond, msg):
        results.append((cond, msg))

    found = {}
    for name in ('gadget_linux.py', 'mirror_service.py'):
        for directory in dirs:
            candidate = os.path.join(directory, name)
            if os.path.isfile(candidate):
                with open(candidate) as f:
                    found[name] = f.read()
                break
    missing = [n for n in ('gadget_linux.py', 'mirror_service.py') if n not in found]
    if missing:
        print('cannot find %s in %s' % (', '.join(missing), ', '.join(dirs)))
        return False
    gl_src = found['gadget_linux.py']
    ms_src = found['mirror_service.py']

    native = 'def release_rndis_udc(' in gl_src
    print('== app tree: %s ==' % ', '.join(dirs))
    print('   form: %s' % ('native helpers' if native else 'injected post-patch'))

    # The only string-literal writes in these two modules are the UDC unbinds:
    # one in the native helper, one per module when the post-patch inlined it.
    writes = re.findall(r"write\(\s*'([^']*)'\s*\)", gl_src + ms_src)
    expected_writes = 1 if native else 2
    report(len(writes) == expected_writes and all(w == r'\n' for w in writes),
           "every UDC unbind writes '\\n' (%d site(s), configfs ignores a "
           "zero-length store)" % len(writes))

    upan = gadget_calls(gl_src, 'upan_and_serial')
    report(upan is not None, 'gadget_linux.upan_and_serial() exists')
    if upan:
        release_at = [i for i, (_, t) in enumerate(upan) if is_release(t)]
        teardown_at = [i for i, (_, t) in enumerate(upan) if 'modprobe -r' in t]
        report(bool(release_at) and bool(teardown_at) and release_at[0] < teardown_at[0],
               'PC mode releases the UDC before touching gadget modules')
        report(any('g_acm_ms' in t for _, t in upan), 'PC mode loads g_acm_ms')

    kill = gadget_calls(gl_src, 'kill_all_module')
    report(kill is not None, 'gadget_linux.kill_all_module() exists')
    if kill:
        restore_at = [i for i, (_, t) in enumerate(kill) if is_restore(t)]
        gserial_at = [i for i, (_, t) in enumerate(kill) if t.endswith("modprobe g_serial')")
                        or t.endswith('modprobe g_serial')]
        report(bool(restore_at) and bool(gserial_at) and restore_at[0] > gserial_at[0],
               'leaving PC mode rebuilds the network after reloading g_serial')
        report(any('&' in t for _, t in kill if is_restore(t)) or native,
               'the rebuild does not block the caller (backgrounded when injected)')

    load = gadget_calls(ms_src, '_load_gadget')
    report(load is not None, 'mirror_service._load_gadget() exists')
    if load:
        release_at = [i for i, (_, t) in enumerate(load) if is_release(t)]
        teardown_at = [i for i, (_, t) in enumerate(load) if 'modprobe -r' in t]
        report(bool(release_at) and bool(teardown_at) and release_at[0] < teardown_at[0],
               'mirroring releases the UDC before loading g_serial')

    unload = gadget_calls(ms_src, '_unload_gadget')
    report(unload is not None, 'mirror_service._unload_gadget() exists')
    if unload:
        restore_at = [i for i, (_, t) in enumerate(unload) if is_restore(t)]
        unload_at = [i for i, (_, t) in enumerate(unload) if 'modprobe -r g_serial' in t]
        report(bool(restore_at) and bool(unload_at) and restore_at[0] > unload_at[0],
               'mirroring restores the network after dropping g_serial')

    for cond, msg in results:
        print(('  ok   ' if cond else '  FAIL ') + msg)
        if not cond:
            problems.append(msg)
    print()
    if problems:
        print('%d FAILURE(S)' % len(problems))
        return False
    print('all checks passed')
    return True


if INSTALLED:
    if len(argv) < 2:
        print('usage: verify_coexist.py --installed DIR [DIR ...]')
        sys.exit(2)
    sys.exit(0 if check_installed(argv[1:]) else 1)

tmp = tempfile.mkdtemp(prefix='rndis-verify-')
gadget = os.path.join(tmp, 'usb_gadget', 'icopy')
os.makedirs(gadget)
udc_path = os.path.join(gadget, 'UDC')
with open(udc_path, 'w') as f:
    f.write('musb-hdrc.4.auto')

calls = []
gadget_linux.os.system = lambda cmd: calls.append(cmd) or 0

failures = []


def check(cond, msg):
    print(('  ok   ' if cond else '  FAIL ') + msg)
    if not cond:
        failures.append(msg)


print('== upan_and_serial() ==')
gadget_linux._RNDIS_GADGET = gadget
calls.clear()
gadget_linux.upan_and_serial()
with open(udc_path) as f:
    udc_now = f.read()
check(udc_now == '\n', 'UDC unbound with a newline (not a zero-length write)')
first = calls[0] if calls else ''
check(first.startswith('sudo modprobe -r'), 'module teardown runs first (%r)' % first)
check(any('g_acm_ms' in c and 'file=' in c for c in calls), 'g_acm_ms loaded with the upan partition')

print('== kill_all_module() ==')
with open(udc_path, 'w') as f:
    f.write('')  # pretend the app owns the UDC now
calls.clear()
gadget_linux.kill_all_module(auto_remount=False)
serial_at = [i for i, c in enumerate(calls) if c.strip() == 'sudo modprobe g_serial']
rndis_at = [i for i, c in enumerate(calls) if 'restart rndis.service' in c]
check(bool(rndis_at), 'rndis.service restarted')
check(bool(serial_at) and bool(rndis_at) and rndis_at[0] > serial_at[0],
      'rndis.service restarted after g_serial is reloaded')

print('== mirror_service handover ==')
gadget_linux._RNDIS_GADGET = gadget
with open(udc_path, 'w') as f:
    f.write('musb-hdrc.4.auto')
calls.clear()
svc = mirror_service.MirrorService.__new__(mirror_service.MirrorService)
svc._load_gadget()
with open(udc_path) as f:
    check(f.read() == '\n', 'mirror releases the configfs UDC before g_serial')
check(any(c.strip() == 'sudo modprobe g_serial' for c in calls), 'mirror loads g_serial')
calls.clear()
svc._unload_gadget()
check(any('restart rndis.service' in c for c in calls), 'mirror restores the RNDIS gadget')

print('== no RNDIS gadget installed ==')
gadget_linux._RNDIS_GADGET = os.path.join(tmp, 'does-not-exist')
calls.clear()
check(gadget_linux.release_rndis_udc() is False, 'release_rndis_udc() is a no-op')
check(gadget_linux.restore_rndis() is False, 'restore_rndis() is a no-op')
check(calls == [], 'no commands issued when the gadget is absent')

shutil.rmtree(tmp, ignore_errors=True)
print()
if failures:
    print('%d FAILURE(S)' % len(failures))
    sys.exit(1)
print('all checks passed')
