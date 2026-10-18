"""Fault injection must stay finite and cannot forgive extra commands."""
import importlib.util
from pathlib import Path
import socket
import sys
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1] / 'qemu_artifact'
spec = importlib.util.spec_from_file_location('strict_transport', ROOT / 'strict_transport.py')
transport = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transport)
spec = importlib.util.spec_from_file_location('recovery_transport', ROOT / 'recovery_transport.py')
recovery = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, strict_transport=transport):
    spec.loader.exec_module(recovery)


def test_truncation_then_exact_sync():
    wire = recovery.RecoveryTranscript([
        dict(command='old', response='partial', truncated=True),
        dict(control='sync', response='READY\nNikola.D: 0\n'),
    ])
    wire.sendall(b'Nikola.D.CMD = old\n')
    assert wire.recv(1024) == b'partial'
    assert wire.recv(1024) == b''
    wire.close()
    wire.sendall(b'Nikola.D.CTL = sync\n')
    assert wire.recv(1024) == b'READY\nNikola.D: 0\n'
    wire.verify()
    with pytest.raises(AssertionError):
        wire.sendall(b'Nikola.D.CMD = surprise\n')


def test_command_cannot_replace_required_sync():
    wire = recovery.RecoveryTranscript([dict(control='sync', response='READY\nNikola.D: 0\n')])
    with pytest.raises(AssertionError):
        wire.sendall(b'Nikola.D.CMD = sync\n')
    with pytest.raises(AssertionError):
        wire.verify()


def test_delayed_reply_is_not_released_by_a_recv_timeout():
    wire = recovery.RecoveryTranscript([dict(command='old', response='END\n', delay=10)])
    wire.sendall(b'Nikola.D.CMD = old\n')
    wire.settimeout(.001)
    with pytest.raises(socket.timeout):
        wire.recv(1024)
    assert wire.pending == b'END\n'
    with pytest.raises(AssertionError):
        wire.close()
