"""The stock-app post-patch must inject the RNDIS handover exactly once.

tools/rndis/patch_stock_ipk.py runs at boot before the app, against an
installed tree that cannot be rebuilt. It therefore has to be idempotent and
must never leave a file that fails to compile.
"""
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'tools/rndis/patch_stock_ipk.py'

GADGET = '''import os

logger = None


def upan_and_serial():
    logger.debug("gadget_linux: upan_and_serial()")
    os.system('sudo modprobe g_acm_ms')


def kill_all_module(auto_remount=True):
    # Factory: reload g_serial as baseline gadget so USB controller is not
    # left orphaned. See audit \u00a74/\u00a75 cited above.
    try:
        os.system('sudo modprobe g_serial')
    except Exception:
        pass
'''

MIRROR = '''import os


class MirrorService:
    def _load_gadget(self):
        os.system('sudo modprobe g_serial')

    def _unload_gadget(self):
        os.system('sudo modprobe -r g_serial 2>/dev/null')
'''


@pytest.fixture
def tree(tmp_path):
    """A miniature copy of the installed app layout."""
    lib = tmp_path / 'ipk_app_main' / 'lib'
    lib.mkdir(parents=True)
    (lib / 'gadget_linux.py').write_text(GADGET)
    (lib / 'mirror_service.py').write_text(MIRROR)
    return tmp_path / 'ipk_app_main'


def run(tree):
    env = dict(os.environ, ICOPY_APP_DIR=str(tree))
    return subprocess.run([sys.executable, str(SCRIPT)], capture_output=True,
                          text=True, env=env, timeout=60)


def test_injects_the_handover_into_both_modules(tree):
    result = run(tree)
    assert result.returncode == 0, result.stderr
    # two anchors per file: release before the app's gadget, restore after it
    assert result.stdout.count('PATCHED') == 4, result.stdout

    gadget = (tree / 'lib/gadget_linux.py').read_text()
    mirror = (tree / 'lib/mirror_service.py').read_text()
    for source in (gadget, mirror):
        assert 'usb_gadget/icopy/UDC' in source      # releases the UDC
        assert 'systemctl restart rndis.service' in source
        compile(source, 'patched', 'exec')            # still valid python
    assert (tree / 'lib/gadget_linux.py.prepostpatch').read_text() == GADGET


def test_second_boot_does_not_patch_twice(tree):
    assert run(tree).returncode == 0
    first = (tree / 'lib/gadget_linux.py').read_text()

    second = run(tree)
    assert second.returncode == 0
    assert 'already patched' in second.stdout
    assert (tree / 'lib/gadget_linux.py').read_text() == first
    patched = (tree / 'lib/gadget_linux.py').read_text()
    assert patched.count('# OSS patch: rndis coexist') == 1
    assert patched.count('# OSS patch: rndis restore') == 1


def test_native_implementation_is_left_alone(tree):
    """An IPK built from the tree already has the fix: do not double-apply."""
    path = tree / 'lib/gadget_linux.py'
    native = GADGET + '\n\ndef release_rndis_udc():\n    return False\n'
    path.write_text(native)

    result = run(tree)
    assert result.returncode == 0
    assert 'native implementation present' in result.stdout
    assert path.read_text() == native


def test_unknown_layout_never_blocks_boot(tree):
    path = tree / 'lib/gadget_linux.py'
    path.write_text('import os\n')            # anchors gone: upstream moved them

    result = run(tree)
    assert result.returncode == 0, 'a failed patch must not stop the device booting'
    assert 'anchor not found' in result.stdout
    assert path.read_text() == 'import os\n'


def _load_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location('rndis_postpatch', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_broken_injection_is_rejected_before_writing(tmp_path):
    """The device's py_compile is broken, so the in-process compile() is the gate."""
    module = _load_module()
    path = tmp_path / 'module.py'
    path.write_text('import os\n')

    outcome = module.apply(str(path), 'import os\n', '\n  def broken(:\n', '# mark')

    assert outcome == 'syntax-error'
    assert path.read_text() == 'import os\n', 'a failed patch must not touch the file'
