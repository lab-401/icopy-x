import importlib.util
import json
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


def test_runtime_tampering_missing_and_extra_files_rejected(tmp_path):
    data = tmp_path / 'library'
    data.write_bytes(b'factory')
    manifest = dict(source_image_sha256='image', qemu_sha256='emulator',
                    files={'library': dict(bytes=7, sha256=worker.sha256(data))})
    record = tmp_path / 'runtime.json'
    record.write_text(json.dumps(manifest))
    pin = dict(source_image_sha256='image', qemu_sha256='emulator',
               manifest_sha256=worker.sha256(record))
    assert worker.verify_runtime(tmp_path, pin) == manifest
    data.write_bytes(b'changed')
    with pytest.raises(ValueError, match='digest'):
        worker.verify_runtime(tmp_path, pin)
    data.unlink()
    with pytest.raises(ValueError, match='Missing or extra'):
        worker.verify_runtime(tmp_path, pin)
    data.write_bytes(b'factory')
    (tmp_path / 'extra').write_bytes(b'code')
    with pytest.raises(ValueError, match='Missing or extra'):
        worker.verify_runtime(tmp_path, pin)
