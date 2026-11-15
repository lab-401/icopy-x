"""The client's Ethernet transport ("host:port") must not throttle the stream.

The frame loop reads ``in_waiting`` bytes per iteration and then sleeps. A
SocketTransport that reports "1" therefore delivers one byte per 50 ms — a few
bytes per second, i.e. a mirror window that never paints. These tests pin the
batch semantics and drive a full handshake over TCP without a GUI.
"""
import importlib.util
from pathlib import Path
import socket
import struct
import threading
import time
import zlib

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    'mirror_client', ROOT / 'tools/screen_mirror/mirror_client.py')
mc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mc)


@pytest.fixture
def pair():
    server, client = socket.socketpair()
    server.settimeout(5)
    client.settimeout(5)
    yield server, client
    for sock in (server, client):
        try:
            sock.close()
        except OSError:
            pass


def test_in_waiting_reports_a_batch_not_a_single_byte(pair):
    server, client = pair
    transport = mc.SocketTransport(server)

    assert transport.in_waiting == 0, 'nothing queued yet'
    client.sendall(b'x' * 4096)
    assert transport.in_waiting >= 4096, 'a poll must be able to drain the socket'
    assert transport.read(transport.in_waiting) == b'x' * 4096


def test_read_returns_what_is_available(pair):
    server, client = pair
    transport = mc.SocketTransport(server)

    client.sendall(b'abc')
    assert transport.read(65536) == b'abc', 'must not wait for the full count'


def test_write_and_close(pair):
    server, client = pair
    transport = mc.SocketTransport(server)

    assert transport.write(b'hello') == 5
    assert client.recv(5) == b'hello'
    transport.close()
    assert transport.is_open is False


def test_full_handshake_and_frames_over_tcp():
    """`mirror_client.py host:port` end to end, minus the Tk window."""
    width, height = mc.DEFAULT_WIDTH, mc.DEFAULT_HEIGHT
    raw = bytes([0x11, 0x22]) * (width * height)

    listener = socket.socket()
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(('127.0.0.1', 0))
    listener.listen(1)
    port = listener.getsockname()[1]
    seen = []

    def serve():
        conn, _ = listener.accept()
        conn.settimeout(10)
        try:
            while True:
                head = b''
                while len(head) < 5:
                    chunk = conn.recv(5 - len(head))
                    if not chunk:
                        return
                    head += chunk
                msg_type = head[2]
                size = struct.unpack('>H', head[3:5])[0]
                body = b''
                while len(body) < size:
                    body += conn.recv(size - len(body))
                seen.append(msg_type)
                if msg_type == mc.MSG_HELLO:
                    payload = struct.pack('>HH', width, height)
                    conn.sendall(mc.MAGIC + struct.pack('>BH', mc.MSG_WELCOME, len(payload)) + payload)
                elif msg_type == mc.MSG_ACK:
                    payload = zlib.compress(raw, 6)
                    conn.sendall(mc.MAGIC + struct.pack('>BH', mc.MSG_FRAME, len(payload)) + payload)
        except (OSError, socket.timeout):
            return
        finally:
            conn.close()

    threading.Thread(target=serve, daemon=True).start()
    connection = mc.SerialConnection('127.0.0.1:%d' % port)
    frames = []
    connection.on_frame = frames.append
    connection.start()
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and not frames:
            time.sleep(0.05)
    finally:
        connection.stop()
        listener.close()

    assert mc.MSG_HELLO in seen, 'the client must greet on connect'
    assert frames, 'no frame decoded over TCP'
    assert frames[0].size == (width, height)
    assert frames[0].getpixel((0, 0)) == (32, 64, 136), 'RGB565 0x1122 must decode'


# ---------------------------------------------------------------------------
# Reconnection: a dead session must not leave a frozen picture on screen
# ---------------------------------------------------------------------------

def _recv_exact(conn, count):
    data = b''
    while len(data) < count:
        chunk = conn.recv(count - len(data))
        if not chunk:
            return None
        data += chunk
    return data


def test_read_raises_when_the_peer_closes(pair):
    """EOF is a disconnect, not "no data yet" — otherwise the loop never leaves."""
    server, client = pair
    transport = mc.SocketTransport(server)

    client.close()
    with pytest.raises(OSError):
        transport.read(1)


class _Device:
    """Minimal mirror server: answers HELLO, then one frame per ACK."""

    def __init__(self, drop_after_frames=None, silent=False):
        self.drops = []
        self.listener = socket.socket()
        self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener.bind(('127.0.0.1', 0))
        self.listener.listen(2)
        self.port = self.listener.getsockname()[1]
        self.drop_after_frames = drop_after_frames
        self.silent = silent
        self.frames = 0
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        while True:
            try:
                conn, _ = self.listener.accept()
            except OSError:
                return
            threading.Thread(target=self._session, args=(conn,), daemon=True).start()

    def _session(self, conn):
        self.drops.append(time.monotonic())
        conn.settimeout(5)
        sent = 0
        try:
            while True:
                head = _recv_exact(conn, 5)
                if head is None:
                    return
                msg_type = head[2]
                size = struct.unpack('>H', head[3:5])[0]
                if _recv_exact(conn, size) is None:
                    return
                if msg_type == mc.MSG_HELLO:
                    payload = struct.pack('>HH', mc.DEFAULT_WIDTH, mc.DEFAULT_HEIGHT)
                    conn.sendall(mc.MAGIC + struct.pack('>BH', mc.MSG_WELCOME, len(payload)) + payload)
                    if self.silent:
                        # Keep the socket open and send nothing: no EOF, so the
                        # client can only notice via its stall timeout.
                        time.sleep(15)
                        return
                elif msg_type == mc.MSG_ACK and not self.silent:
                    payload = zlib.compress(bytes([0x11, 0x22]) * (mc.DEFAULT_WIDTH * mc.DEFAULT_HEIGHT), 6)
                    conn.sendall(mc.MAGIC + struct.pack('>BH', mc.MSG_FRAME, len(payload)) + payload)
                    self.frames += 1
                    sent += 1
                    if self.drop_after_frames and sent >= self.drop_after_frames:
                        return          # drop like a device restart
        except OSError:
            return
        finally:
            conn.close()

    def close(self):
        self.listener.close()


def _connect(port):
    connection = mc.SerialConnection('127.0.0.1:%d' % port)
    frames = []
    connection.on_frame = frames.append
    connection.start()
    return connection, frames


def test_client_reconnects_after_the_session_drops(monkeypatch):
    monkeypatch.setattr(mc, 'RECONNECT_INTERVAL', 0.2)
    device = _Device(drop_after_frames=2)
    connection, frames = _connect(device.port)
    try:
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline and (len(device.drops) < 2 or len(frames) < 3):
            time.sleep(0.05)
    finally:
        connection.stop()
        device.close()

    assert len(device.drops) >= 2, 'the client must open a new session after the drop'
    assert len(frames) >= 3, 'frames must flow again after reconnecting'


def test_client_reconnects_when_the_stream_goes_silent(monkeypatch):
    """Serial hosts never deliver EOF, so silence must time out too."""
    monkeypatch.setattr(mc, 'RECONNECT_INTERVAL', 0.2)
    monkeypatch.setattr(mc, 'STALL_TIMEOUT', 0.5)
    device = _Device(silent=True)
    connection, _frames = _connect(device.port)
    try:
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline and len(device.drops) < 2:
            time.sleep(0.05)
    finally:
        connection.stop()
        device.close()

    assert len(device.drops) >= 2, 'a silent session must be abandoned and retried'


def test_disconnect_blanks_the_last_frame():
    """A dropped session must not leave a frozen picture that still looks live."""
    class _Root:
        def after(self, _delay, fn):
            fn()

    class _Canvas:
        def __init__(self):
            self.calls = []

        def itemconfigure(self, item, **kwargs):
            self.calls.append((item, kwargs))

    app = mc.MirrorApp.__new__(mc.MirrorApp)
    app.root = _Root()
    app.canvas = _Canvas()
    app._screen_id = 1
    app._status_id = 2
    statuses = []
    app._update_status = statuses.append

    app._on_disconnected()

    assert (1, {'image': ''}) in app.canvas.calls, 'the stale frame must be removed'
    assert (2, {'state': mc.tk.NORMAL}) in app.canvas.calls, 'the status line returns'
    assert statuses and 'econnect' in statuses[0]
