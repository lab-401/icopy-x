"""The static verifier must accept a correct tree and reject a broken one.

tools/rndis/verify_coexist.py --installed is what confirms a *deployed* device,
where behavioural probing is impossible (the injected post-patch hardcodes the
live configfs path). A verifier that always prints "ok" would be worthless, so
each check below is paired with a mutation it has to catch.
"""
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'tools/rndis/verify_coexist.py'
SOURCES = (ROOT / 'src/middleware/gadget_linux.py', ROOT / 'src/lib/mirror_service.py')


@pytest.fixture
def tree(tmp_path):
    """Copy of the two modules the verifier inspects."""
    for source in SOURCES:
        shutil.copy2(source, tmp_path / source.name)
    return tmp_path


def verify(tree):
    return subprocess.run([sys.executable, str(SCRIPT), '--installed', str(tree)],
                          capture_output=True, text=True, timeout=120)


def edit(path, old, new):
    text = path.read_text()
    assert old in text, old[:40]
    path.write_text(text.replace(old, new, 1))


def test_a_correct_tree_passes(tree):
    result = verify(tree)
    assert result.returncode == 0, result.stdout
    assert 'all checks passed' in result.stdout
    assert 'FAIL' not in result.stdout


def test_a_zero_length_unbind_is_rejected(tree):
    """configfs ignores a zero-length store — this is the defect the fix exists for."""
    edit(tree / 'gadget_linux.py', "            f.write('\\n')", "            f.write('')")

    result = verify(tree)
    assert result.returncode == 1
    assert 'FAIL every UDC unbind writes' in result.stdout


def test_releasing_after_the_teardown_is_rejected(tree):
    """The UDC must be free *before* g_acm_ms is loaded, or it parks as pending."""
    edit(tree / 'gadget_linux.py',
         '    logger.debug("gadget_linux: upan_and_serial()")\n    release_rndis_udc()\n',
         '    logger.debug("gadget_linux: upan_and_serial()")\n')

    result = verify(tree)
    assert result.returncode == 1
    assert 'FAIL PC mode releases the UDC before touching gadget modules' in result.stdout


def test_a_mirror_without_the_restore_is_rejected(tree):
    edit(tree / 'mirror_service.py',
         '        self._restore_rndis()\n', '')

    result = verify(tree)
    assert result.returncode == 1
    assert 'FAIL mirroring restores the network' in result.stdout


def test_missing_modules_are_reported_not_swallowed(tmp_path):
    result = verify(tmp_path)
    assert result.returncode == 1
    assert 'cannot find' in result.stdout
