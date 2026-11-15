"""Mirror transport must not hang when the client disappears.

A host that closes its side of the CDC ACM port does not deliver EOF to the
device — it just stops sending. Before the timeout, ``_readn`` blocked forever,
``_session()`` never returned, and a second client could not connect until
mirroring was toggled off and on again.
"""

import os
import threading
import time

import pytest

from lib import mirror_service


@pytest.fixture
def service():
    svc = mirror_service.MirrorService()
    svc._running = True
    return svc


def test_readn_returns_the_requested_bytes(service):
    read_fd, write_fd = os.pipe()
    try:
        os.write(write_fd, b'hello')
        assert service._readn(read_fd, 5) == b'hello'
    finally:
        os.close(read_fd)
        os.close(write_fd)


def test_readn_gives_up_when_the_client_goes_quiet(service, monkeypatch):
    monkeypatch.setattr(mirror_service, 'IDLE_TIMEOUT', 0.05)
    read_fd, write_fd = os.pipe()
    try:
        with pytest.raises(ConnectionError):
            service._readn(read_fd, 5)
    finally:
        os.close(read_fd)
        os.close(write_fd)


def test_readn_stops_when_the_service_is_stopped(service):
    service._running = False
    read_fd, write_fd = os.pipe()
    try:
        with pytest.raises(ConnectionError):
            service._readn(read_fd, 1)
    finally:
        os.close(read_fd)
        os.close(write_fd)


def test_session_ends_and_the_next_client_is_served(service, monkeypatch):
    """A dead session must not block the serve loop."""
    import time

    monkeypatch.setattr(mirror_service, 'IDLE_TIMEOUT', 0.05)
    monkeypatch.setattr(mirror_service.time, 'sleep', lambda _s: None)
    monkeypatch.setattr(mirror_service.os, 'system', lambda _cmd: 0)
    monkeypatch.setattr(mirror_service.os.path, 'exists', lambda _p: True)

    served = []

    def fake_open(path, flags):
        read_fd, write_fd = os.pipe()
        os.close(write_fd)
        served.append(read_fd)
        return read_fd

    monkeypatch.setattr(mirror_service.os, 'open', fake_open)

    started = time.monotonic()
    service._session()                      # one dead connection
    elapsed = time.monotonic() - started

    assert served, 'the session should have opened the serial device'
    assert elapsed < 2.0, 'a silent client must not hold the session open'


def test_readn_stops_promptly_when_the_service_is_stopped_mid_wait(service, monkeypatch):
    """stop() joins the serve thread with a 3 s timeout.

    If _readn sits in one long select() it keeps /dev/ttyGS0 open past that
    timeout, modprobe -r g_serial then fails, and the RNDIS gadget can never
    take the controller back (observed: toggling mirroring off left the device
    with no network and no mirror service).
    """
    monkeypatch.setattr(mirror_service, 'IDLE_TIMEOUT', 10.0)   # long idle window
    read_fd, write_fd = os.pipe()

    def stop_soon():
        time.sleep(0.15)
        service._running = False

    try:
        threading.Thread(target=stop_soon, daemon=True).start()
        started = time.monotonic()
        with pytest.raises(ConnectionError):
            service._readn(read_fd, 5)
        elapsed = time.monotonic() - started
        assert elapsed < 1.5, 'must react to stop(), not wait out the idle window'
    finally:
        os.close(read_fd)
        os.close(write_fd)
