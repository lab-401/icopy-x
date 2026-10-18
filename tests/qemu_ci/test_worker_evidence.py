import importlib.util
import os
from pathlib import Path

import pytest


pytest.importorskip('resource', reason='Worker runs on Linux')
spec = importlib.util.spec_from_file_location('worker', Path(__file__).resolve().parents[2] / 'tools/qemu_ci/run_worker.py')
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


def test_regular_bounded_evidence(tmp_path):
    (tmp_path / 'report').write_bytes(b'PASS')
    assert worker.read_guest_file(tmp_path, 'report', 4) == b'PASS'
    with pytest.raises(ValueError):
        worker.read_guest_file(tmp_path, 'report', 3)


@pytest.mark.parametrize('relative', ['../report', '/etc/passwd', ''])
def test_invalid_evidence_path(tmp_path, relative):
    with pytest.raises(ValueError):
        worker.read_guest_file(tmp_path, relative)


def test_symlink_leaf_parent_and_fifo_rejected(tmp_path):
    root = tmp_path / 'guest'
    root.mkdir()
    (tmp_path / 'secret').write_text('host-only')
    (root / 'leaf').symlink_to(tmp_path / 'secret')
    (root / 'parent').symlink_to(tmp_path, target_is_directory=True)
    os.mkfifo(root / 'pipe')
    for name in ('leaf', 'parent/secret', 'pipe'):
        with pytest.raises((OSError, ValueError)):
            worker.read_guest_file(root, name)
