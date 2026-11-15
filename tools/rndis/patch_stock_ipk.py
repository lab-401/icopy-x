#!/usr/bin/env python3
"""Re-apply the RNDIS-coexistence patch to an *installed stock* iCopy-X app.

The fix lives in ``src/middleware/gadget_linux.py`` and ``src/lib/mirror_service.py``,
so any IPK built from this tree already has it.  An IPK built upstream (or the
factory image) does not — this script injects the same logic into the installed
copy at ``/home/pi/ipk_app_main`` so the USB network survives PC mode and screen
mirroring without rebuilding the package.

Run at boot before ``icopy.service`` (see ``icopy-postpatch.service``).

Properties:
  * Idempotent — marker-tagged blocks are inserted at most once, and files that
    already contain the native implementation (``release_rndis_udc``) are left
    alone, so shipping an IPK built from this tree does not double-apply.
  * Fail-safe — syntax is validated with ``compile()`` before writing (the
    device's ``python3 -m py_compile`` is broken), the pristine file is kept as
    ``*.prepostpatch``, and no error can block boot.
"""
import os
import shutil
import sys
import time
import traceback

# install layout on the device; overridable so the patch can be exercised on a
# copy of that tree (tests, staging).
APP = os.environ.get('ICOPY_APP_DIR', '/home/pi/ipk_app_main')
GL = os.path.join(APP, 'lib', 'gadget_linux.py')
MS = os.path.join(APP, 'lib', 'mirror_service.py')

MARK_REL = '# OSS patch: rndis coexist'
MARK_RES = '# OSS patch: rndis restore'
# Present once the tree-level fix is installed — never patch those files.
NATIVE = 'def release_rndis_udc('

log_lines = []


def log(msg):
    log_lines.append(msg)
    print(msg, flush=True)


def apply(path, anchor, body, mark):
    """Insert *body* after *anchor* once. Validates syntax before committing."""
    if not os.path.isfile(path):
        log('SKIP missing %s' % path)
        return 'missing'
    src = open(path).read()
    if NATIVE in src:
        log('ok   native implementation present: %s' % os.path.basename(path))
        return 'native'
    if mark in src:
        log('ok   already patched: %s' % os.path.basename(path))
        return 'present'
    if anchor not in src:
        log('WARN anchor not found in %s (upstream changed?)' % os.path.basename(path))
        return 'anchor-missing'
    new = src.replace(anchor, anchor + body, 1)
    try:
        compile(new, path, 'exec')
    except SyntaxError as e:
        log('FAIL syntax after patch %s: %s' % (path, e))
        return 'syntax-error'
    if not os.path.exists(path + '.prepostpatch'):
        shutil.copy2(path, path + '.prepostpatch')
    open(path, 'w').write(new)
    log('PATCHED %s' % os.path.basename(path))
    return 'patched'


def main():
    log('--- iCopy-X OSS post-patch %s' % time.strftime('%Y-%m-%d %H:%M:%S'))

    apply(GL,
          '    logger.debug("gadget_linux: upan_and_serial()")\n',
          '    # OSS patch: rndis coexist (release UDC for PC mode / mirror)\n'
          '    try:\n'
          "        open('/sys/kernel/config/usb_gadget/icopy/UDC', 'w').write('\\n')\n"
          '    except Exception:\n'
          '        pass\n',
          MARK_REL)

    apply(GL,
          '    # Factory: reload g_serial as baseline gadget so USB controller is not\n'
          '    # left orphaned. See audit \u00a74/\u00a75 cited above.\n'
          '    try:\n'
          "        os.system('sudo modprobe g_serial')\n"
          '    except Exception:\n'
          '        pass\n',
          '    # OSS patch: rndis restore (bring the USB network back after PC mode)\n'
          '    try:\n'
          "        os.system('sudo systemctl restart rndis.service >/dev/null 2>&1 &')\n"
          '    except Exception:\n'
          '        pass\n',
          MARK_RES)

    apply(MS,
          '    def _load_gadget(self):\n',
          '        # OSS patch: rndis coexist (release UDC for screen mirror)\n'
          '        try:\n'
          "            open('/sys/kernel/config/usb_gadget/icopy/UDC', 'w').write('\\n')\n"
          '        except Exception:\n'
          '            pass\n',
          MARK_REL)

    apply(MS,
          '    def _unload_gadget(self):\n'
          "        os.system('sudo modprobe -r g_serial 2>/dev/null')\n",
          '        # OSS patch: rndis restore\n'
          "        os.system('sudo systemctl restart rndis.service >/dev/null 2>&1 &')\n",
          MARK_RES)

    # sanity: the modules must still compile
    for mod in ('gadget_linux', 'mirror_service'):
        path = os.path.join(APP, 'lib', mod + '.py')
        try:
            compile(open(path).read(), path, 'exec')
            log('syntax ok: %s' % mod)
        except Exception as e:
            log('SYNTAX BROKEN: %s %s' % (mod, e))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        log('UNEXPECTED: ' + traceback.format_exc(limit=3))

    try:
        with open('/var/log/icopy-postpatch.log', 'a') as f:
            f.write('\n'.join(log_lines) + '\n')
    except Exception:
        pass
    sys.exit(0)
