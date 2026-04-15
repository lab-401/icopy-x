##########################################################################
# Required Notice: Copyright ETOILE401 SAS (http://www.lab401.com)
#
# Copyright (c) 2026: ETOILE401 SAS & https://github.com/quantum-x/
#
# This software is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this software for commercial purposes.
#
# A copy of the license is available at:
# https://polyformproject.org/licenses/noncommercial/1.0.0
#
# This entire header "Required Notice" must remain in place.
##########################################################################

"""Device-side screen mirroring service over USB serial.

Architecture:
  - Loads the g_serial kernel module to expose /dev/ttyGS0 as a USB CDC ACM device.
  - A background thread runs a serve loop that waits for a PC client to connect.
  - On connection, performs a HELLO/WELCOME handshake, then enters a frame-streaming
    loop: the client sends ACK to request a frame, the service reads /dev/fb1 (RGB565,
    240x240), zlib-compresses it, and writes it back as a MSG_FRAME message.
  - The client can also send MSG_KEY messages to inject button presses into the keymap.

Protocol (binary framing):
  - Header: 2-byte magic (0x49 0x43) + 1-byte type + 2-byte big-endian payload length
  - Types: HELLO (0x04), WELCOME (0x05), FRAME (0x01), KEY (0x02), ACK (0x03)

Transport:
  - USB CDC ACM via g_serial kernel module
  - Raw blocking I/O with os.read/os.write on the file descriptor
  - Shutdown closes the fd, which unblocks any pending os.read() with OSError
"""

import logging
import os
import struct
import threading
import time
import zlib

log = logging.getLogger(__name__)

MAGIC = b'\x49\x43'
MSG_FRAME = 0x01
MSG_KEY = 0x02
MSG_ACK = 0x03
MSG_HELLO = 0x04
MSG_WELCOME = 0x05

KEY_MAP = {
    0x01: 'UP', 0x02: 'DOWN', 0x03: 'LEFT', 0x04: 'RIGHT',
    0x05: 'OK', 0x06: 'M1', 0x07: 'M2', 0x08: 'PWR', 0x09: 'ALL',
}

FB_PATH = '/dev/fb1'
FB_SIZE = 240 * 240 * 2
SERIAL_PATH = '/dev/ttyGS0'
SCREEN_W = 240
SCREEN_H = 240


class MirrorService:

    def __init__(self):
        self._running = False
        self._thread = None
        self._fd = None
        self._fb_fd = None

    def start(self):
        if self._running:
            return
        self._load_gadget()
        try:
            self._fb_fd = open(FB_PATH, 'rb')
        except Exception as e:
            log.error('Cannot open framebuffer %s: %s', FB_PATH, e)
            self._fb_fd = None
        self._running = True
        self._thread = threading.Thread(target=self._serve_loop, daemon=True)
        self._thread.start()
        log.info('MirrorService started')

    def stop(self):
        self._running = False
        fd = self._fd
        if fd is not None:
            self._fd = None
            try:
                os.close(fd)
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=3)
            self._thread = None
        if self._fb_fd:
            try:
                self._fb_fd.close()
            except Exception:
                pass
            self._fb_fd = None
        self._unload_gadget()
        log.info('MirrorService stopped')

    @property
    def is_running(self):
        return self._running

    def _load_gadget(self):
        for mod in ('g_mass_storage', 'g_acm_ms', 'g_ether', 'g_serial'):
            os.system('sudo modprobe -r %s 2>/dev/null' % mod)
        os.system('sudo modprobe g_serial')

    def _unload_gadget(self):
        os.system('sudo modprobe -r g_serial 2>/dev/null')

    def _serve_loop(self):
        while self._running:
            try:
                self._session()
            except Exception as e:
                log.error('Session error: %s', e)
            if self._running:
                time.sleep(1)

    def _session(self):
        for _ in range(20):
            if not self._running:
                return
            if os.path.exists(SERIAL_PATH):
                break
            time.sleep(0.5)
        else:
            raise OSError('%s not available' % SERIAL_PATH)

        os.system(
            'stty -F %s raw -echo -echoe -echok -echoctl '
            '-onlcr -opost -icrnl -inlcr -igncr -istrip -ixon -ixoff'
            % SERIAL_PATH
        )

        fd = os.open(SERIAL_PATH, os.O_RDWR | os.O_NOCTTY)
        self._fd = fd

        try:
            self._handle(fd)
        finally:
            self._fd = None
            try:
                os.close(fd)
            except Exception:
                pass

    def _handle(self, fd):
        msg_type, _ = self._recv(fd)
        if msg_type != MSG_HELLO:
            return

        self._send(fd, MSG_WELCOME, struct.pack('>HH', SCREEN_W, SCREEN_H))

        while self._running:
            msg_type, payload = self._recv(fd)

            if msg_type == MSG_ACK:
                data = self._grab_frame()
                if data:
                    compressed = zlib.compress(data, 6)
                    self._send(fd, MSG_FRAME, compressed)

            elif msg_type == MSG_KEY:
                if payload and len(payload) >= 1:
                    self._key(payload[0])

            elif msg_type is None:
                break

    def _grab_frame(self):
        if not self._fb_fd:
            return None
        try:
            self._fb_fd.seek(0)
            d = self._fb_fd.read(FB_SIZE)
            return d if len(d) == FB_SIZE else None
        except Exception:
            return None

    def _key(self, code):
        name = KEY_MAP.get(code)
        if name:
            try:
                import keymap
                keymap.key.onKey(name)
            except Exception as e:
                log.error('Key injection failed: %s', e)

    def _send(self, fd, msg_type, payload=b''):
        """Send a framed message via a single os.write call."""
        hdr = MAGIC + struct.pack('>BH', msg_type, len(payload))
        data = hdr + payload
        os.write(fd, data)

    def _recv(self, fd):
        """Read a framed message. Blocking; fd close unblocks with OSError."""
        try:
            magic = self._readn(fd, 2)
            if magic != MAGIC:
                return None, None
            hdr = self._readn(fd, 3)
            mtype = hdr[0]
            plen = struct.unpack('>H', hdr[1:3])[0]
            payload = self._readn(fd, plen) if plen > 0 else b''
            return mtype, payload
        except (OSError, ConnectionError):
            return None, None

    def _readn(self, fd, n):
        """Read exactly n bytes. Blocking. fd close unblocks with OSError."""
        buf = b''
        while len(buf) < n:
            chunk = os.read(fd, n - len(buf))
            if not chunk:
                raise ConnectionError('EOF')
            buf += chunk
        return buf


_instance = None


def get_service():
    global _instance
    if _instance is None:
        _instance = MirrorService()
    return _instance
