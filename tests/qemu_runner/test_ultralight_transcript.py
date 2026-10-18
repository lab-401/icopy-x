"""Wrong commands and wrong files must not satisfy the ARM MFU cases."""
import importlib.util
from pathlib import Path
import sys
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1] / 'qemu_artifact'
spec = importlib.util.spec_from_file_location('strict_transport', ROOT/'strict_transport.py')
transport = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transport)
spec = importlib.util.spec_from_file_location('ultralight_cases', ROOT/'ultralight_cases.py')
cases = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, strict_transport=transport):
    spec.loader.exec_module(cases)


@pytest.mark.parametrize('firmware,flag', [('original', 'f'), ('iceman', '-f')])
def test_dump_written_only_for_exact_final_command(tmp_path, firmware, flag):
    wire, partial = cases.prepare('mfu_read_success', firmware, tmp_path)
    steps = list(wire.steps)
    assert not partial and (' '+flag+' ') in steps[-1]['command']
    for step in steps:
        assert not wire.path.exists()
        wire.sendall(('Nikola.D.CMD = '+step['command']+'\n').encode())
        while wire.pending:
            wire.recv(17)
    wire.verify()
    assert wire.path.read_bytes() == cases.binary(16)


def test_mismatched_dump_command_cannot_create_file(tmp_path):
    wire, _ = cases.prepare('mfu_read_success', 'iceman', tmp_path)
    with pytest.raises(AssertionError):
        wire.sendall(b'Nikola.D.CMD = hf mfu dump -f wrong-path\n')
    assert not wire.path.exists()
    with pytest.raises(AssertionError):
        wire.verify()
