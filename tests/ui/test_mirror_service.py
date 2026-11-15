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


# ---------------------------------------------------------------------------
# Transport selection (USB serial gadget vs Ethernet over the RNDIS link)
# ---------------------------------------------------------------------------

def _settings_stub(monkeypatch, transport=0):
    import sys
    import types

    stub = types.ModuleType('settings')
    stub.getMirrorTransport = lambda: transport
    monkeypatch.setitem(sys.modules, 'settings', stub)
    return stub


def test_configured_transport_defaults_to_serial(monkeypatch):
    _settings_stub(monkeypatch, 0)
    assert mirror_service._configured_transport() == mirror_service.TRANSPORT_SERIAL


def test_configured_transport_reads_the_saved_value(monkeypatch):
    _settings_stub(monkeypatch, 1)
    assert mirror_service._configured_transport() == mirror_service.TRANSPORT_ETHERNET


def test_configured_transport_survives_a_broken_setting(monkeypatch):
    stub = _settings_stub(monkeypatch, 0)

    def boom():
        raise RuntimeError('config unreadable')

    stub.getMirrorTransport = boom
    assert mirror_service._configured_transport() == mirror_service.TRANSPORT_SERIAL


@pytest.fixture
def service_paths(monkeypatch, tmp_path):
    """Point the service at a temporary framebuffer and neutral gadget calls."""
    fb = tmp_path / 'fb.raw'
    fb.write_bytes(b'\x01' * mirror_service.FB_SIZE)
    monkeypatch.setattr(mirror_service, 'FB_PATH', str(fb))
    calls = []
    monkeypatch.setattr(mirror_service.MirrorService, '_load_gadget',
                        lambda self: calls.append('load'))
    monkeypatch.setattr(mirror_service.MirrorService, '_unload_gadget',
                        lambda self: calls.append('unload'))
    monkeypatch.setattr(mirror_service.MirrorService, '_serve_loop', lambda self: None)
    monkeypatch.setattr(mirror_service.MirrorService, '_serve_tcp_loop', lambda self: None)
    return calls


def test_ethernet_transport_leaves_the_usb_gadget_alone(service_paths):
    svc = mirror_service.MirrorService()
    svc.start(mirror_service.TRANSPORT_ETHERNET)
    assert svc.is_running
    assert svc._transport == mirror_service.TRANSPORT_ETHERNET
    svc.stop()
    assert service_paths == [], 'RNDIS must not be displaced by the ethernet transport'


def test_serial_transport_still_takes_the_gadget(service_paths):
    svc = mirror_service.MirrorService()
    svc.start(mirror_service.TRANSPORT_SERIAL)
    svc.stop()
    assert service_paths == ['load', 'unload']


def test_handle_serves_welcome_and_frames_over_a_socket(service_paths, monkeypatch):
    """The TCP loop hands the accepted socket fd to _handle(); prove that path."""
    import socket as _socket
    import struct as _struct
    import threading as _threading
    import zlib as _zlib

    svc = mirror_service.MirrorService()
    svc._running = True
    svc._fb_fd = open(mirror_service.FB_PATH, 'rb')

    srv, cli = _socket.socketpair()
    srv.settimeout(5)
    cli.settimeout(5)
    worker = _threading.Thread(target=svc._handle, args=(srv.fileno(),), daemon=True)
    worker.start()

    def recv_msg():
        head = b''
        while len(head) < 5:
            chunk = cli.recv(5 - len(head))
            assert chunk, 'connection closed'
            head += chunk
        assert head[:2] == mirror_service.MAGIC
        size = _struct.unpack('>H', head[3:5])[0]
        body = b''
        while len(body) < size:
            chunk = cli.recv(size - len(body))
            assert chunk, 'connection closed'
            body += chunk
        return head[2], body

    try:
        cli.sendall(mirror_service.MAGIC + _struct.pack('>BH', 0x04, 0))
        msg_type, payload = recv_msg()
        assert msg_type == 0x05, 'expected WELCOME'
        assert _struct.unpack('>HH', payload) == (240, 240)

        cli.sendall(mirror_service.MAGIC + _struct.pack('>BH', 0x03, 0))
        msg_type, payload = recv_msg()
        assert msg_type == 0x01, 'expected FRAME'
        assert len(_zlib.decompress(payload)) == mirror_service.FB_SIZE
    finally:
        svc._running = False
        cli.close()
        srv.close()
        worker.join(timeout=3)
        if svc._fb_fd:
            svc._fb_fd.close()
