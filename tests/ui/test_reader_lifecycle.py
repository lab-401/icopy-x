"""Real Reader workers; protocol work is held at an explicit test boundary."""
import threading
from unittest.mock import Mock

import pytest
import read


@pytest.mark.parametrize('raises', [False, True])
def test_stop_suppresses_late_progress_completion_and_exception(monkeypatch, raises):
    entered, release = threading.Event(), threading.Event()

    def protocol(typ, infos, listener):
        listener({'progress': 10})
        entered.set()
        assert release.wait(2)
        listener({'progress': 80})
        if raises:
            raise RuntimeError('late transport error')
        return 1, 'cancelled.bin'

    monkeypatch.setattr(read, '_dispatch_read', protocol)
    reader = read.Reader()
    reader.call_reading, reader.call_exception = Mock(), Mock()
    reader.start(1, {'infos': {}})
    try:
        assert entered.wait(2)
        reader.stop()
    finally:
        release.set()
        reader._thread.join(2)
    assert not reader._thread.is_alive()
    reader.call_reading.assert_called_once_with({'progress': 10})
    reader.call_exception.assert_not_called()


def test_running_reader_cannot_be_restarted_until_worker_exits(monkeypatch):
    entered, release = threading.Event(), threading.Event()
    listeners = []

    def protocol(typ, infos, listener):
        listeners.append(listener)
        entered.set()
        assert release.wait(2)
        return 1, 'read.bin'

    monkeypatch.setattr(read, '_dispatch_read', protocol)
    reader = read.Reader()
    reader.call_reading = Mock()
    reader.start(1, {})
    try:
        assert entered.wait(2)
        assert reader.is_reading()
        reader.stop()
        assert reader.is_reading(), 'stop requests cancellation; worker still owns the read'
        with pytest.raises(RuntimeError, match='already running'):
            reader.start(1, {})
    finally:
        release.set()
        reader._thread.join(2)
    assert not reader.is_reading()
    reader.start(1, {})
    reader._thread.join(2)
    reader.call_reading.assert_called_once()
    listeners[0]({'progress': 99})
    reader.call_reading.assert_called_once()


def test_thread_start_failure_releases_reader(monkeypatch):
    reader = read.Reader()
    with monkeypatch.context() as patcher:
        patcher.setattr(threading.Thread, 'start', Mock(side_effect=RuntimeError('thread unavailable')))
        with pytest.raises(RuntimeError, match='unavailable'):
            reader.start(1, {})
    assert not reader.is_reading()
    monkeypatch.setattr(read, '_dispatch_read', lambda *args: (1, 'read.bin'))
    reader.start(1, {})
    reader._thread.join(2)
    assert not reader.is_reading()


def test_stop_before_worker_entry_skips_protocol(monkeypatch):
    monkeypatch.setattr(threading.Thread, 'start', lambda self: None)
    protocol = Mock()
    monkeypatch.setattr(read, '_dispatch_read', protocol)
    reader = read.Reader()
    reader.start(1, {})
    reader.stop()
    reader._thread.run()
    protocol.assert_not_called()
    assert not reader.is_reading()


def test_normal_reader_still_delivers_progress_and_result(monkeypatch):
    def protocol(typ, infos, listener):
        listener({'progress': 10})
        return 1, 'read.bin'

    monkeypatch.setattr(read, '_dispatch_read', protocol)
    reader = read.Reader()
    reader.call_reading, reader.call_exception = Mock(), Mock()
    reader.start(1, {'infos': {'uid': '11223344'}})
    reader._thread.join(2)
    assert not reader._thread.is_alive()
    assert reader.call_reading.call_count == 2
    result = reader.call_reading.call_args[0][0]
    assert result['success'] and result['bundle'] == 'read.bin'
    reader.call_exception.assert_not_called()
