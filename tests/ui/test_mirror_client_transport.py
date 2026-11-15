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
