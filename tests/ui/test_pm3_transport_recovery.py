"""Real TCP + executor + daemon reader; only the PM3 child is simulated.

Short deadlines make failure paths deterministic without RF hardware. The
fake child emits bytes, not mocked executor/daemon return values.
"""
import queue
import socketserver
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import executor
from main import rftask


class Process:
    pid = 999999

    def __init__(self):
        self.lines = queue.Queue()
        self.commands = []
        self.sent = threading.Event()
        self.dead = False
        self.on_command = lambda cmd: None
        self.stdin = SimpleNamespace(write=self.write, flush=lambda: None)
        self.stdout = SimpleNamespace(readline=self.lines.get)

    def write(self, data):
        command = data.decode().strip()
        self.commands.append(command)
        self.sent.set()
        self.on_command(command)

    def emit(self, text):
        for line in text.splitlines(True):
            self.lines.put(line.encode())

    def poll(self):
        return 0 if self.dead else None

    def kill(self):
        self.dead = True
        self.lines.put(b'')

    def wait(self, timeout):
        return 0


def wait_for(predicate):
    until = time.monotonic() + 3
    while not predicate():
        assert time.monotonic() < until, 'test synchronization timed out'
        threading.Event().wait(.002)


def start(function):
    results, errors = [], []

    def run():
        try:
            results.append(function())
        except BaseException as error:
            errors.append(error)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread, results, errors


def finish(worker):
    thread, results, errors = worker
    thread.join(3)
    assert not thread.is_alive(), 'worker did not unwind'
    assert not errors, errors
    return results


@pytest.fixture
def pipeline(monkeypatch):
    manager = rftask.RemoteTaskManager()
    child = Process()
    manager._process = child
    manager._has_manager = True
    manager._create_read_thread()
    server = socketserver.ThreadingTCPServer(('127.0.0.1', 0), manager._handler_class)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .01}, daemon=True)
    thread.start()
    for name, value in {
        '_socket_instance': None, '_pipeline_uncertain': False,
        '_pipeline_needs_cleanup': False, '_consecutive_reworks': 0,
        'CONTENT_OUT_IN__TXT_CACHE': '', 'LABEL_PM3_CMD_TASK_STOPPING': False,
        'LABEL_PM3_CMD_TASK_RUNNING': False, 'pm3_compat': None,
        'pm3_localize': None, 'hmi_driver': None,
        'PM3_REMOTE_CMD_PORT': server.server_address[1],
        'RESPONSE_POLL_SECONDS': .005, 'RESPONSE_DRAIN_SECONDS': .08,
    }.items():
        monkeypatch.setattr(executor, name, value)
    monkeypatch.setattr(rftask, 'COMMAND_LOCK_SECONDS', .03)
    monkeypatch.setattr(rftask, 'COMMAND_TIMEOUT_SECONDS', 2)
    # No real process group is ever queried or signalled by these tests.
    monkeypatch.setattr(rftask.os, 'getpgid', Mock(side_effect=OSError), raising=False)
    monkeypatch.setattr(rftask.os, 'killpg', Mock(side_effect=AssertionError), raising=False)
    try:
        yield manager, child
    finally:
        executor._close_socket()
        manager._has_manager = False
        if manager._process:
            manager._process.kill()
        child.kill()
        manager._output_event.set()
        manager._destroy_read_thread()
        server.shutdown()
        server.server_close()
        thread.join(2)


def fresh_response(child):
    child.on_command = lambda cmd: child.emit('FRESH ' + cmd + '\nNikola.D: 0\n')


def test_timeout_drains_late_reply_without_replay_or_stale_cache(pipeline):
    manager, child = pipeline
    worker = start(lambda: executor.startPM3Task('write-once', timeout=20))
    assert child.sent.wait(2)
    child.emit('PARTIAL OLD\n')
    wait_for(lambda: executor._pipeline_needs_cleanup)
    child.emit('Nikola.D: 0\n')
    assert finish(worker) == [-1]
    assert executor.getPrintContent() == ''
    assert not executor._pipeline_uncertain
    fresh_response(child)
    assert executor.startPM3Task('next', timeout=500) == 1
    assert 'FRESH next' in executor.getPrintContent()
    assert 'OLD' not in executor.getPrintContent()
    assert child.commands == ['write-once', 'next']


def test_busy_daemon_refuses_new_work_without_resetting_old_owner(pipeline):
    manager, child = pipeline
    restart = manager.reworkManager = Mock(side_effect=AssertionError('busy is not dirty'))
    assert executor.startPM3Task('write-once', timeout=10) == -1
    assert executor._pipeline_uncertain
    assert executor.startPM3Task('must-not-run', timeout=100) == -1
    assert child.commands == ['write-once']
    assert executor._pipeline_uncertain and executor.getPrintContent() == ''
    child.emit('OLD\nNikola.D: 0\n')
    wait_for(lambda: not manager._expecting_response)
    fresh_response(child)
    assert executor.startPM3Task('next', timeout=500) == 1
    assert child.commands == ['write-once', 'next']
    restart.assert_not_called()


def test_process_eof_is_failure_even_after_partial_output(pipeline):
    manager, child = pipeline
    worker = start(lambda: executor.startPM3Task('write-once', timeout=500))
    assert child.sent.wait(2)
    child.emit('Saved successfully (incomplete response)\n')
    child.kill()
    assert finish(worker) == [-1]
    assert manager._needs_recovery and not manager._response_complete
    assert 'Saved successfully' not in executor.getPrintContent()
    assert child.commands == ['write-once']


def test_daemon_eof_inside_marker_is_not_a_complete_status(pipeline):
    manager, child = pipeline
    worker = start(lambda: executor.startPM3Task('write-once', timeout=500))
    assert child.sent.wait(2)
    child.emit('Saved successfully\nNikola.D: -1')
    child.kill()
    assert finish(worker) == [-1]
    assert not manager._response_complete
    assert 'Saved successfully' not in executor.getPrintContent()


@pytest.mark.parametrize('response', ['pm3 -->\n', 'Nikola.D: 0\n'])
def test_completed_empty_response_never_triggers_ping_or_replay(pipeline, response):
    manager, child = pipeline
    child.on_command = lambda cmd: child.emit(response)
    executor.startPM3Task('write-once', timeout=500)
    assert child.commands == ['write-once']
    assert not manager._needs_recovery


def test_daemon_deadline_discards_partial_and_blocks_next_command(pipeline, monkeypatch):
    manager, child = pipeline
    monkeypatch.setattr(rftask, 'COMMAND_TIMEOUT_SECONDS', .03)
    child.on_command = lambda cmd: child.emit('PARTIAL\n')
    assert manager._request_task_cmd('write-once') == rftask.DEFAULT_OFFLINE
    child.emit('Nikola.D: 0\n')  # late EOR cannot cleanse a failed generation
    assert manager._request_task_cmd('must-not-run') == rftask.DEFAULT_OFFLINE
    assert manager._request_task_ctl('sync') == 'DIRTY\nNikola.D: -1'
    assert child.commands == ['write-once']


def test_cancel_returns_promptly_but_drains_under_ownership(pipeline):
    manager, child = pipeline
    worker = start(lambda: executor.startPM3Task('old', timeout=-1))
    assert child.sent.wait(2)
    executor.stopPM3Task(wait=False)
    wait_for(lambda: executor._pipeline_needs_cleanup)
    child.emit('OLD\nNikola.D: 0\n')
    assert finish(worker) == [-1]
    assert executor.getPrintContent() == ''
    fresh_response(child)
    assert executor.startPM3Task('new', timeout=500) == 1
    assert child.commands == ['old', 'new']


@pytest.mark.parametrize('creates_process', [False, True])
def test_restart_ack_controls_whether_new_command_can_run(pipeline, monkeypatch, creates_process):
    manager, old = pipeline
    old.kill()
    wait_for(lambda: manager._needs_recovery)
    executor._pipeline_uncertain = True
    replacement = Process()
    fresh_response(replacement)

    def create():
        if creates_process:
            manager._process = replacement
        return creates_process

    monkeypatch.setattr(manager, '_create_subprocess', create)
    # Only hardware settling delays are removed; sockets/events use real time.
    clock = SimpleNamespace(monotonic=time.monotonic, sleep=lambda delay: None)
    monkeypatch.setattr(executor, 'time', clock)
    monkeypatch.setattr(rftask, 'time', clock)
    result = executor.startPM3Task('new', timeout=500)
    assert result == (1 if creates_process else -1)
    assert replacement.commands == (['new'] if creates_process else [])
    assert old.commands == []
    assert executor._pipeline_uncertain is (not creates_process)


def test_restart_wakes_old_owner_as_failure_and_old_reader_cannot_complete_new(pipeline, monkeypatch):
    manager, old = pipeline
    worker = start(lambda: manager._send_cmd('old'))
    assert old.sent.wait(2)
    generation = manager._generation
    replacement = Process()

    def create():
        manager._process = replacement
        return True

    monkeypatch.setattr(manager, '_create_subprocess', create)
    monkeypatch.setattr(rftask, 'time', SimpleNamespace(sleep=lambda delay: None))
    assert manager.reworkManager()
    assert finish(worker) == [None]
    new_worker = start(lambda: manager._send_cmd('new'))
    assert replacement.sent.wait(2)
    # Deliberately feed a stale reader after a new process owns the buffer.
    stale = Process()
    stale.emit('OLD\nNikola.D: 0\n')
    manager._run_std_output_error(stale, generation)
    assert not manager._output_event.is_set()
    assert not manager._response_complete
    replacement.emit('FRESH\nNikola.D: 0\n')
    assert finish(new_worker) == ['FRESH\nNikola.D: 0']
    assert old.commands == ['old'] and replacement.commands == ['new']


@pytest.mark.parametrize('body', [
    b'Valid EM410x ID found!\n',
    b'Valid EM410x ID found!\nNikola.D: -1',
    b'Valid EM410x ID found!\nNikola.D: 0\nTRAILING DATA',
    b'Valid EM410x ID found! not-a-marker Nikola.D: 0\n',
    b'[usb] pm3 --> hf search\n',
])
def test_unterminated_or_embedded_markers_cannot_complete_a_reply(monkeypatch, body):
    chunks = [body, b'']
    wire = SimpleNamespace(settimeout=lambda t: None, sendall=Mock(),
                           recv=lambda n: chunks.pop(0))
    for name, value in {'_socket_instance': wire, '_pipeline_uncertain': False,
                        '_pipeline_needs_cleanup': False,
                        'LABEL_PM3_CMD_TASK_STOPPING': False}.items():
        monkeypatch.setattr(executor, name, value)
    assert executor._exchange('Nikola.D.CMD = once\n', 100) == ''
    assert executor._pipeline_uncertain
    wire.sendall.assert_called_once()


def test_trickled_bytes_do_not_extend_the_absolute_deadline(monkeypatch):
    received = []

    def recv(size):
        threading.Event().wait(.005)
        received.append(1)
        assert len(received) < 100, 'per-recv timeout allowed an indefinite trickle'
        return b'partial\n'

    wire = SimpleNamespace(settimeout=lambda t: None, sendall=Mock(), recv=recv)
    for name, value in {'_socket_instance': wire, '_pipeline_uncertain': False,
                        '_pipeline_needs_cleanup': False, 'RESPONSE_DRAIN_SECONDS': .02,
                        'LABEL_PM3_CMD_TASK_STOPPING': False}.items():
        monkeypatch.setattr(executor, name, value)
    assert executor._exchange('Nikola.D.CMD = once\n', 20) == ''
    assert executor._pipeline_uncertain
    assert len(received) < 100
    wire.sendall.assert_called_once()


def test_unreaped_child_prevents_replacement_and_success_ack(pipeline, monkeypatch):
    manager, child = pipeline
    monkeypatch.setattr(child, 'wait', Mock(side_effect=TimeoutError))
    spawn = Mock(side_effect=AssertionError('unreaped child must block replacement'))
    monkeypatch.setattr(manager, '_create_subprocess', spawn)
    assert manager._request_task_ctl('restart') == 'FAIL\nNikola.D: -1'
    assert manager._needs_recovery
    spawn.assert_not_called()


def test_kill_helper_timeout_prevents_replacement(pipeline, monkeypatch):
    manager, child = pipeline
    manager._pm3_kill_cmd = 'configured-test-helper'
    run = Mock(side_effect=rftask.subprocess.TimeoutExpired('configured-test-helper', 3))
    monkeypatch.setattr(rftask.subprocess, 'run', run)
    spawn = Mock(side_effect=AssertionError('failed cleanup must block replacement'))
    monkeypatch.setattr(manager, '_create_subprocess', spawn)
    assert manager._request_task_ctl('restart') == 'FAIL\nNikola.D: -1'
    assert run.call_args.kwargs['timeout'] == 3
    spawn.assert_not_called()


def test_delayed_tune_enter_cannot_abort_a_subsequent_command(pipeline, monkeypatch):
    manager, child = pipeline
    sleeping, release, finished = threading.Event(), threading.Event(), threading.Event()

    def sleep(delay):
        sleeping.set()
        assert release.wait(3)

    # Observe the callback's actual return without relying on scheduler sleeps.
    real_thread = threading.Thread

    def thread_factory(*args, **kwargs):
        target = kwargs['target']

        def wrapped():
            try:
                target()
            finally:
                finished.set()

        return real_thread(target=wrapped, daemon=True)

    monkeypatch.setattr(rftask, 'time', SimpleNamespace(sleep=sleep))
    monkeypatch.setattr(rftask, 'threading', SimpleNamespace(Thread=thread_factory))
    fresh_response(child)
    assert manager._send_cmd('hf tune') == 'FRESH hf tune\nNikola.D: 0'
    assert sleeping.wait(2)
    child.on_command = lambda cmd: None
    child.sent.clear()
    worker = start(lambda: manager._send_cmd('next'))
    assert child.sent.wait(2)
    release.set()
    assert finished.wait(2)
    assert child.commands == ['hf tune', 'next']
    child.emit('NEXT\nNikola.D: 0\n')
    assert finish(worker) == ['NEXT\nNikola.D: 0']
