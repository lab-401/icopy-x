import importlib.util
import io
from pathlib import Path
import tarfile

import pytest


spec = importlib.util.spec_from_file_location('runtime_archive', Path(__file__).resolve().parents[2] / 'tools/qemu_ci/unpack_runtime.py')
bundle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bundle)


def archive(tmp_path, entries):
    path = tmp_path / 'test.tar.gz'
    with tarfile.open(path, 'w:gz') as output:
        for name, kind, value in entries:
            item = tarfile.TarInfo(name)
            item.type = kind
            if kind == tarfile.REGTYPE:
                item.size = len(value)
                output.addfile(item, io.BytesIO(value))
            else:
                item.linkname = value
                output.addfile(item)
    return path


def test_bad_digest_does_not_create_output(tmp_path):
    path = archive(tmp_path, [('runtime/file', tarfile.REGTYPE, b'data')])
    with pytest.raises(ValueError, match='digest'):
        bundle.unpack(path, tmp_path / 'out', '0' * 64)
    assert not (tmp_path / 'out').exists()


@pytest.mark.parametrize('entries', [
    [('../escape', tarfile.REGTYPE, b'data')],
    [('/runtime/file', tarfile.REGTYPE, b'data')],
    [('runtime/fifo', tarfile.FIFOTYPE, '')],
    [('runtime/hard', tarfile.LNKTYPE, '/etc/passwd')],
    [('runtime/link', tarfile.SYMTYPE, '/etc/passwd')],
    [('runtime/link', tarfile.SYMTYPE, '../../escape')],
    [('runtime/link', tarfile.SYMTYPE, 'dir'), ('runtime/link/file', tarfile.REGTYPE, b'data')],
    [('runtime/file', tarfile.REGTYPE, b'one'), ('runtime/file', tarfile.REGTYPE, b'two')],
])
def test_unsafe_archive_rejected_before_extracting(tmp_path, entries):
    path = archive(tmp_path, entries)
    with pytest.raises(ValueError):
        bundle.unpack(path, tmp_path / 'out', bundle.sha256(path))
    assert list((tmp_path / 'out').iterdir()) == []


def test_regular_archive_and_existing_output_rejection(tmp_path):
    path = archive(tmp_path, [('runtime/file', tarfile.REGTYPE, b'data')])
    output = tmp_path / 'out'
    assert (bundle.unpack(path, output, bundle.sha256(path)) / 'file').read_bytes() == b'data'
    with pytest.raises(FileExistsError):
        bundle.unpack(path, output, bundle.sha256(path))
