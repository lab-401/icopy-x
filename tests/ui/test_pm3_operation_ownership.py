"""Deterministic worker races through the real executor and socket boundary."""
import threading
from unittest.mock import Mock

import pytest

import executor
import read
import scan


@pytest.fixture
def wire(monkeypatch):
    commands, violations, sockets = [], [], []
    entered, release = threading.Event(), threading.Event()

    class Socket:
        def __init__(self, *args):
            self.pending = b''
            self.command = None
            sockets.append(self)

        def connect(self, address):
            assert address == ('127.0.0.1', 8888)

        def settimeout(self, timeout):
            pass

        def sendall(self, data):
            if self.pending:
                violations.append('overlapping commands on one socket')
            self.command = data.decode().strip().split(' = ', 1)[1]
            commands.append(self.command)
            self.pending = (self.command + '\nNikola.D: 0\n').encode()

        def recv(self, size):
            if self.command == 'held':
                entered.set()
                assert release.wait(3), 'test did not release held response'
            response, self.pending = self.pending[:size], self.pending[size:]
            return response

        def close(self):
            if self.pending:
                violations.append('socket closed while response was owned')

    monkeypatch.setattr(executor.socket, 'socket', Socket)
    monkeypatch.setattr(executor, 'pm3_compat', None)
    monkeypatch.setattr(executor, 'pm3_localize', None)
    monkeypatch.setattr(executor, '_socket_instance', None)
    monkeypatch.setattr(executor, '_pipeline_needs_cleanup', False)
    monkeypatch.setattr(executor, '_pipeline_uncertain', False)
    monkeypatch.setattr(executor, '_consecutive_reworks', 0)
    monkeypatch.setattr(executor, 'CONTENT_OUT_IN__TXT_CACHE', '')
    monkeypatch.setattr(executor, 'LABEL_PM3_CMD_TASK_RUNNING', False)
    monkeypatch.setattr(executor, 'LABEL_PM3_CMD_TASK_STOPPING', False)
    monkeypatch.setattr(executor, 'reworkPM3All', Mock(side_effect=AssertionError('unexpected restart')))
    yield commands, violations, entered, release
    release.set()


def join(worker):
    worker.join(3)
    assert not worker.is_alive(), 'worker did not release PM3 ownership'


@pytest.fixture
def ownership_probe(monkeypatch):
    """Observe the waiter's actual lock attempt, without a scheduling sleep."""
    lock = executor.LOCK_THREAD
    armed, attempted = threading.Event(), threading.Event()
    result = []

    class ObservedLock:
        def acquire(self, *args, **kwargs):
            if armed.is_set():
                armed.clear()
                acquired = lock.acquire(blocking=False)
                result.append(not acquired)
                attempted.set()
                if acquired:
                    return True
            return lock.acquire(*args, **kwargs)

        def release(self):
            lock.release()

        def __enter__(self):
            self.acquire()
            return self

        def __exit__(self, *args):
            self.release()

    monkeypatch.setattr(executor, 'LOCK_THREAD', ObservedLock())
    return armed, attempted, result


def test_cancelled_reader_cannot_issue_another_protocol_command(monkeypatch, wire):
    commands, violations, entered, release = wire
    after_command = []

    def protocol(*args):
        # A broad protocol fallback must not swallow operation cancellation.
        try:
            executor.startPM3Task('held', rework_max=0)
        except Exception:
            pass
        after_command.append(executor.getPrintContent())
        executor.startPM3Task('must-not-run', rework_max=0)
        return 1, 'cancelled.bin'

    monkeypatch.setattr(read, '_dispatch_read', protocol)
    reader = read.Reader()
    reader.call_reading, reader.call_exception = Mock(), Mock()
    reader.start(8, {})
    try:
        assert entered.wait(2)
        reader.stop()
    finally:
        release.set()
        join(reader._thread)
    assert commands == ['held']
    assert after_command == []
    assert violations == []
    reader.call_reading.assert_not_called()
    reader.call_exception.assert_not_called()


@pytest.mark.parametrize('channel', ['startPM3Task', 'startPM3Ctrl', 'startPM3Plat'])
def test_response_callback_cannot_start_nested_command(wire, channel):
    rejected = []

    def listener(text):
        with pytest.raises(RuntimeError, match='response callback'):
            getattr(executor, channel)('nested')
        rejected.append(channel)

    executor.resetReworkCount()
    assert executor.startPM3Task('first', listener=listener, rework_max=0) == 1
    assert rejected == [channel]
    assert wire[0] == ['first'] and not wire[1]


def test_stop_from_response_callback_does_not_wait_for_itself(wire):
    executor.resetReworkCount()
    results = []
    worker = threading.Thread(target=lambda: results.append(executor.startPM3Task(
        'first', listener=lambda text: executor.stopPM3Task(), rework_max=0)), daemon=True)
    worker.start()
    join(worker)
    assert results == [-1]
    assert wire[0] == ['first']
    assert not executor.LABEL_PM3_CMD_TASK_RUNNING


def test_reader_keeps_response_until_parsing_finishes(monkeypatch, wire, ownership_probe):
    commands, violations, _, _ = wire
    parsed, release_parser = threading.Event(), threading.Event()
    results = []

    def protocol(typ, infos, listener):
        executor.startPM3Task(infos['command'], rework_max=0)
        if infos['command'] == 'first':
            parsed.set()
            assert release_parser.wait(3)
        results.append((infos['command'], executor.getPrintContent()))
        return 1, ''

    monkeypatch.setattr(read, '_dispatch_read', protocol)
    first, second = read.Reader(), read.Reader()
    first.start(8, {'command': 'first'})
    try:
        assert parsed.wait(2)
        ownership_probe[0].set()
        second.start(8, {'command': 'second'})
        assert ownership_probe[1].wait(2), 'second Reader never attempted ownership'
        assert ownership_probe[2] == [True], 'response parsing did not retain ownership'
        assert commands == ['first'], 'second operation entered during response parsing'
    finally:
        release_parser.set()
        join(first._thread)
        if second._thread:
            join(second._thread)
    assert results == [('first', 'first\nNikola.D: 0\n'),
                       ('second', 'second\nNikola.D: 0\n')]
    assert violations == []


@pytest.mark.parametrize('kind', ['reader', 'scan_all', 'scan_type'])
def test_waiting_operation_can_be_cancelled_without_acquiring_pm3(monkeypatch, wire, ownership_probe, kind):
    commands, violations, entered, release = wire
    monkeypatch.setattr(read, '_dispatch_read',
                        lambda *args: (executor.startPM3Task('held', rework_max=0), ''))
    owner = read.Reader()
    owner.start(8, {})
    waiter = None
    try:
        assert entered.wait(2)
        ownership_probe[0].set()
        if kind == 'reader':
            waiter = read.Reader()
            waiter.start(8, {})
            assert ownership_probe[1].wait(2)
            waiter.stop()
            join(waiter._thread)
        else:
            waiter = scan.Scanner()
            waiter.call_resulted = Mock()
            method = waiter.scan_all_synchronous if kind == 'scan_all' else lambda: waiter.scan_type_synchronous(8)
            worker = threading.Thread(target=method)
            worker.start()
            assert ownership_probe[1].wait(2)
            assert waiter._scan_running
            waiter.scan_stop()
            join(worker)
            waiter.call_resulted.assert_not_called()
        assert commands == ['held']
        assert ownership_probe[2] == [True]
        assert owner.is_reading(), 'cancelling the waiter must not cancel the owner'
    finally:
        release.set()
        join(owner._thread)
    assert violations == []


def test_nonblocking_stop_stays_with_old_command_and_does_not_restart(monkeypatch, wire):
    commands, violations, entered, release = wire
    results = []
    executor.resetReworkCount()
    worker = threading.Thread(target=lambda: results.append(executor.startPM3Task('held')))
    worker.start()
    try:
        assert entered.wait(2)
        executor.stopPM3Task(wait=False)
        assert executor.LABEL_PM3_CMD_TASK_STOPPING
        assert worker.is_alive()
    finally:
        release.set()
        join(worker)
    assert results == [-1]
    assert not executor.LABEL_PM3_CMD_TASK_STOPPING
    assert not executor.LABEL_PM3_CMD_TASK_RUNNING
    assert executor.startPM3Task('next', rework_max=0) == 1
    assert commands == ['held', 'next']
    assert violations == []


def test_exception_releases_command_state_and_listener(monkeypatch, wire):
    listener = Mock()
    with monkeypatch.context() as patcher:
        patcher.setattr(executor, '_send_and_cache', Mock(side_effect=RuntimeError('broken socket')))
        with pytest.raises(RuntimeError, match='broken socket'):
            executor.startPM3Task('broken', listener=listener)
    assert listener not in executor.LIST_CALL_PRINT
    assert not executor.LABEL_PM3_CMD_TASK_RUNNING
    assert executor.LABEL_PM3_CMD_TASK_STOP
    executor.resetReworkCount()
    assert executor.startPM3Task('next', rework_max=0) == 1


@pytest.mark.parametrize('typed', [False, True])
def test_scanner_stop_before_worker_entry_cannot_be_lost(monkeypatch, wire, typed):
    workers = []
    monkeypatch.setattr(threading.Thread, 'start', lambda self: workers.append(self))
    scanner = scan.Scanner()
    scanner.call_resulted = Mock()
    if typed:
        scanner.scan_type_asynchronous(8)
    else:
        scanner.scan_all_asynchronous()
    scanner.scan_stop()
    workers[0].run()
    assert not scanner._scan_running
    assert wire[0] == []
    scanner.call_resulted.assert_not_called()


def test_new_scanner_waits_for_cancelled_reader_to_leave_socket(monkeypatch, wire, ownership_probe):
    commands, violations, entered, release = wire

    def protocol(*args):
        executor.startPM3Task('held', rework_max=0)
        return 1, ''

    def scan_card():
        executor.startPM3Task('fresh-scan', rework_max=0)
        return {'found': True, 'type': 8, 'return': 1}

    monkeypatch.setattr(read, '_dispatch_read', protocol)
    monkeypatch.setattr(scan, 'scan_14a', scan_card)
    reader, scanner = read.Reader(), scan.Scanner()
    scanner.call_resulted = Mock()
    reader.start(8, {})
    worker = threading.Thread(target=scanner.scan_all_synchronous)
    try:
        assert entered.wait(2)
        reader.stop()
        ownership_probe[0].set()
        worker.start()
        assert ownership_probe[1].wait(2), 'Scanner never attempted ownership'
        assert ownership_probe[2] == [True], 'Scanner did not wait for the Reader'
        assert commands == ['held'], 'new scan sent before old reader released transport'
        assert violations == []
    finally:
        release.set()
        join(reader._thread)
        if worker.ident:
            join(worker)
    assert commands == ['held', 'fresh-scan']
    scanner.call_resulted.assert_called_once_with({'found': True, 'type': 8, 'return': 1})
    assert violations == []


@pytest.mark.parametrize('entry', ['startPM3Ctrl', 'startPM3Plat', 'connect2PM3', 'resetReworkCount'])
def test_other_executor_entry_points_cannot_change_an_owned_session(monkeypatch, wire, ownership_probe, entry):
    parsing, release = threading.Event(), threading.Event()
    observed = []

    def protocol(*args):
        executor.startPM3Task('reader', rework_max=0)
        parsing.set()
        assert release.wait(3)
        observed.append(executor.getPrintContent())
        return 1, ''

    monkeypatch.setattr(read, '_dispatch_read', protocol)
    reader = read.Reader()
    reader.start(8, {})
    method = getattr(executor, entry)
    args = ('other',) if entry in ('startPM3Ctrl', 'startPM3Plat') else ()
    worker = threading.Thread(target=method, args=args)
    try:
        assert parsing.wait(2)
        ownership_probe[0].set()
        worker.start()
        assert ownership_probe[1].wait(2)
        assert ownership_probe[2] == [True]
        assert wire[0] == ['reader']
    finally:
        release.set()
        join(reader._thread)
        if worker.ident:
            join(worker)
    assert observed == ['reader\nNikola.D: 0\n']
    assert not wire[1]


def test_stop_between_protocol_commands_cancels_the_operation(monkeypatch, wire):
    between, release = threading.Event(), threading.Event()
    def protocol(*args):
        executor.startPM3Task('first', rework_max=0)
        between.set()
        assert release.wait(3)
        executor.startPM3Task('must-not-run', rework_max=0)
        return 1, ''
    monkeypatch.setattr(read, '_dispatch_read', protocol)
    reader = read.Reader()
    reader.call_reading = Mock()
    reader.start(8, {})
    try:
        assert between.wait(2)
        assert not executor.LABEL_PM3_CMD_TASK_RUNNING
        executor.stopPM3Task(wait=False)
    finally:
        release.set()
        join(reader._thread)
    assert wire[0] == ['first']
    reader.call_reading.assert_not_called()
