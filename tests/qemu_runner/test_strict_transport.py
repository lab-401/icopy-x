"""A fixture error must stay a failure even when application code catches it."""
import importlib.util
from pathlib import Path

import pytest

path = Path(__file__).resolve().parents[1] / 'qemu_artifact' / 'strict_transport.py'
spec = importlib.util.spec_from_file_location('strict_transport', path)
transport = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transport)


def transcript():
    return transport.Transcript([dict(command='hf 14a info', response='reply\nNikola.D: 0\n')])


def test_exact_command_and_fragmented_response():
    wire = transcript()
    wire.sendall(b'Nikola.D.CMD = hf 14a info\n')
    assert wire.recv(3) == b'rep'
    assert wire.recv(1024) == b'ly\nNikola.D: 0\n'
    wire.verify()


@pytest.mark.parametrize('command', [b'hf 14a info\n', b'Nikola.D.CMD = hf 14a info EXTRA\n',
                                     b'Nikola.D.CMD = lf sea\n'])
def test_caught_command_mismatch_cannot_become_a_pass(command):
    wire = transcript()
    with pytest.raises(AssertionError):
        wire.sendall(command)
    with pytest.raises(AssertionError):
        wire.verify()


def test_exhausted_transcript_does_not_repeat_its_last_response():
    wire = transcript()
    wire.sendall(b'Nikola.D.CMD = hf 14a info\n')
    wire.recv(1024)
    with pytest.raises(AssertionError, match='exhaustion'):
        wire.sendall(b'Nikola.D.CMD = hf 14a info\n')
    with pytest.raises(AssertionError):
        wire.verify()


def test_missing_commands_cannot_pass():
    with pytest.raises(AssertionError, match='not sent'):
        transcript().verify()


def test_unconsumed_response_cannot_pass():
    wire = transcript()
    wire.sendall(b'Nikola.D.CMD = hf 14a info\n')
    with pytest.raises(AssertionError, match='not consumed'):
        wire.verify()


def test_reading_past_response_is_recorded_even_if_caught():
    wire = transcript()
    wire.sendall(b'Nikola.D.CMD = hf 14a info\n')
    wire.recv(1024)
    with pytest.raises(AssertionError, match='beyond'):
        wire.recv(1024)
    with pytest.raises(AssertionError):
        wire.verify()


@pytest.mark.parametrize('violation', ['close', 'other_socket', 'closed_recv', 'closed_send'])
def test_separate_connections_reject_ownership_violations(violation):
    wire = transport.ConnectionTranscript([
        dict(command='first', response='first\nNikola.D: 0\n'),
        dict(command='second', response='second\nNikola.D: 0\n')])
    first, second = wire.new_socket(), wire.new_socket()
    first.sendall(b'Nikola.D.CMD = first\n')
    if violation.startswith('closed_'):
        first.recv(1024)
        first.close()
    with pytest.raises(AssertionError):
        if violation == 'close':
            first.close()
        elif violation == 'other_socket':
            second.sendall(b'Nikola.D.CMD = second\n')
        elif violation == 'closed_recv':
            first.recv(1024)
        else:
            first.sendall(b'Nikola.D.CMD = second\n')
    with pytest.raises(AssertionError):
        wire.verify()


def test_separate_connections_transfer_only_after_consumption():
    wire = transport.ConnectionTranscript([
        dict(command='first', response='old\nNikola.D: 0\n'),
        dict(command='second', response='new\nNikola.D: 0\n')])
    first = wire.new_socket()
    first.sendall(b'Nikola.D.CMD = first\n')
    assert first.recv(1024).startswith(b'old')
    first.close()
    second = wire.new_socket()
    second.sendall(b'Nikola.D.CMD = second\n')
    assert second.recv(1024).startswith(b'new')
    wire.verify()
