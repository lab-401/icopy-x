#!/usr/bin/env python3

##########################################################################
# Required Notice: Copyright ETOILE401 SAS (http://www.lab401.com)
#
# Initial author: ETOILE401 SAS & https://github.com/quantum-x/ as of April 16, 2026
#
# Since this date, each contribution is under the copyright of its respective author.
#
# Copyright of each contribution is tracked by the Git history. See the output of git shortlog -nse for a full list or git log --pretty=short --follow <path/to/sourcefile> |git shortlog -ne to track a specific file.
#
# A mailmap is maintained to map author and committer names and email addresses to canonical names and email addresses.
# If by accident a copyright was removed from a file and is not directly deducible from the Git history, please submit a PR.
#
#
# This software is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this software for commercial purposes.
#
# A copy of the license is available at:
# https://polyformproject.org/licenses/noncommercial/1.0.0
#
# This entire header "Required Notice" must remain in place.
##########################################################################

"""iCopy-X Screen Mirror Client.

Cross-platform application that connects to an iCopy-X device over USB
serial, displays its screen in real-time, and allows remote button control.

Usage:
    python mirror_client.py [serial_port]
    python mirror_client.py                    # auto-detect
    python mirror_client.py /dev/ttyACM0       # explicit port
    python mirror_client.py COM3               # Windows
    python mirror_client.py --assets-dir /path # custom assets directory
    python mirror_client.py --help             # show this help

Dependencies:
    pip install pyserial pillow
"""

import argparse
import logging
import struct
import sys
import threading
import time
import tkinter as tk
import zlib
from pathlib import Path

try:
    from PIL import Image, ImageTk
except ImportError:
    print("Error: Pillow is required. Install with: pip install pillow")
    sys.exit(1)

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("Error: pyserial is required. Install with: pip install pyserial")
    sys.exit(1)

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("mirror")

# ---------------------------------------------------------------------------
# Protocol constants
# ---------------------------------------------------------------------------
MAGIC = b'\x49\x43'  # "IC"

# Message types
MSG_FRAME   = 0x01  # device -> client: compressed RGB565 frame
MSG_KEY     = 0x02  # client -> device: key press
MSG_ACK     = 0x03  # client -> device: request next frame
MSG_HELLO   = 0x04  # client -> device: handshake
MSG_WELCOME = 0x05  # device -> client: screen dimensions

# Key codes
KEY_UP    = 0x01
KEY_DOWN  = 0x02
KEY_LEFT  = 0x03
KEY_RIGHT = 0x04
KEY_OK    = 0x05
KEY_M1    = 0x06
KEY_M2    = 0x07
KEY_PWR   = 0x08
KEY_ALL   = 0x09

# Header: MAGIC(2) + type(1) + length(2) = 5 bytes
HEADER_SIZE = 5

# Screen dimensions (default, overridden by WELCOME)
DEFAULT_WIDTH  = 240
DEFAULT_HEIGHT = 240

# Serial settings
BAUD_RATE = 115200
SERIAL_TIMEOUT = 1.0

# Reconnect interval (seconds)
RECONNECT_INTERVAL = 2.0

# ---------------------------------------------------------------------------
# Hotspot definitions
# ---------------------------------------------------------------------------
HOTSPOTS = {
    'image_size': (525, 1151),
    'screen_rect': (143, 148, 382, 387),  # x1, y1, x2, y2 (240x240 area)
    'exit_rect': (448, 6, 514, 25),       # EXIT button bounding box
    'buttons': {
        'M1':  (107, 474, 37),   # center_x, center_y, radius
        'M2':  (418, 474, 36),
        'U':   (265, 472, 18),
        'D':   (265, 597, 18),
        'L':   (200, 535, 18),
        'R':   (327, 538, 18),
        'OK':  (264, 533, 29),
        'PWR': (108, 595, 36),
        'ALL': (419, 595, 36),
    },
}

# Map button names to key codes
BUTTON_KEY_MAP = {
    'U':   KEY_UP,
    'D':   KEY_DOWN,
    'L':   KEY_LEFT,
    'R':   KEY_RIGHT,
    'OK':  KEY_OK,
    'M1':  KEY_M1,
    'M2':  KEY_M2,
    'PWR': KEY_PWR,
    'ALL': KEY_ALL,
}

# Keyboard shortcut map: keysym -> key code
KEYBOARD_MAP = {
    'Up':       KEY_UP,
    'Down':     KEY_DOWN,
    'Left':     KEY_LEFT,
    'Right':    KEY_RIGHT,
    'Return':   KEY_OK,
    'KP_Enter': KEY_OK,
    'Escape':   KEY_PWR,
    'space':    KEY_ALL,
    '1':        KEY_M1,
    '2':        KEY_M2,
    'F1':       KEY_M1,
    'F2':       KEY_M2,
    'F3':       KEY_ALL,
}

# ---------------------------------------------------------------------------
# RGB565 conversion
# ---------------------------------------------------------------------------

def rgb565_to_rgb888(data, width=240, height=240):
    """Convert RGB565 bytes to an RGB888 PIL Image.

    Uses numpy if available for speed, otherwise falls back to pure Python.
    """
    if HAS_NUMPY:
        return _rgb565_to_rgb888_numpy(data, width, height)
    return _rgb565_to_rgb888_pure(data, width, height)


def _rgb565_to_rgb888_numpy(data, width, height):
    """Fast RGB565 to RGB888 conversion using numpy."""
    pixels = np.frombuffer(data, dtype=np.uint16)
    r = ((pixels >> 11) & 0x1F) << 3
    g = ((pixels >> 5) & 0x3F) << 2
    b = (pixels & 0x1F) << 3
    rgb = np.stack([r, g, b], axis=-1).astype(np.uint8)
    return Image.fromarray(rgb.reshape(height, width, 3))


def _rgb565_to_rgb888_pure(data, width, height):
    """Pure Python RGB565 to RGB888 conversion (fallback)."""
    pixels = struct.unpack('<%dH' % (len(data) // 2), data)
    rgb_data = bytearray(len(pixels) * 3)
    for i, px in enumerate(pixels):
        rgb_data[i * 3]     = ((px >> 11) & 0x1F) << 3
        rgb_data[i * 3 + 1] = ((px >> 5) & 0x3F) << 2
        rgb_data[i * 3 + 2] = (px & 0x1F) << 3
    return Image.frombytes('RGB', (width, height), bytes(rgb_data))


# ---------------------------------------------------------------------------
# Protocol helpers
# ---------------------------------------------------------------------------

def build_message(msg_type, payload=b''):
    """Build a framed protocol message."""
    return MAGIC + struct.pack('B', msg_type) + struct.pack('>H', len(payload)) + payload


def parse_header(data):
    """Parse a 5-byte header. Returns (msg_type, payload_length) or None."""
    if len(data) < HEADER_SIZE:
        return None
    if data[0:2] != MAGIC:
        return None
    msg_type = data[2]
    payload_length = struct.unpack('>H', data[3:5])[0]
    return msg_type, payload_length


# ---------------------------------------------------------------------------
# Serial communication thread
# ---------------------------------------------------------------------------

class SerialConnection:
    """Manages serial communication with the iCopy-X device."""

    def __init__(self, port=None):
        self.port = port
        self.ser = None
        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        self._connected = False
        self.screen_width = DEFAULT_WIDTH
        self.screen_height = DEFAULT_HEIGHT

        # Callbacks (set by the UI)
        self.on_frame = None        # called with PIL Image
        self.on_connected = None    # called when WELCOME received
        self.on_disconnected = None # called when connection lost
        self.on_status = None       # called with status string

    @property
    def connected(self):
        return self._connected

    def start(self):
        """Start the connection thread."""
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the connection thread and close the port."""
        self._running = False
        # Close port first to unblock any blocking read
        self._close_port()
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    def send_key(self, key_code):
        """Send a KEY message to the device."""
        with self._lock:
            if self.ser and self._connected:
                try:
                    msg = build_message(MSG_KEY, bytes([key_code]))
                    self.ser.write(msg)
                    log.debug("Sent key: 0x%02x", key_code)
                except (serial.SerialException, OSError) as exc:
                    log.warning("Failed to send key: %s", exc)

    def _send_ack(self):
        """Send an ACK to request the next frame."""
        with self._lock:
            if self.ser:
                try:
                    self.ser.write(build_message(MSG_ACK))
                except (serial.SerialException, OSError):
                    pass

    def _send_hello(self):
        """Send a HELLO handshake."""
        with self._lock:
            if self.ser:
                try:
                    self.ser.write(build_message(MSG_HELLO))
                except (serial.SerialException, OSError):
                    pass

    def _close_port(self):
        """Close the serial port safely."""
        with self._lock:
            if self.ser:
                try:
                    self.ser.close()
                except Exception:
                    pass
                self.ser = None
            if self._connected:
                self._connected = False
                if self.on_disconnected:
                    self.on_disconnected()

    def _open_port(self, port):
        """Try to open a serial port. Returns True on success."""
        try:
            self.ser = serial.Serial(
                port=port,
                baudrate=BAUD_RATE,
                timeout=SERIAL_TIMEOUT,
                write_timeout=SERIAL_TIMEOUT,
            )
            log.info("Opened serial port: %s", port)
            return True
        except (serial.SerialException, OSError) as exc:
            log.debug("Could not open %s: %s", port, exc)
            self.ser = None
            return False

    def _auto_detect_port(self):
        """Scan available serial ports and try to find the iCopy-X device."""
        ports = serial.tools.list_ports.comports()
        candidates = []
        for p in ports:
            # Prefer ACM devices (CDC ACM class)
            if 'ACM' in p.device or 'usbmodem' in p.device:
                candidates.insert(0, p.device)
            elif 'USB' in p.device or 'COM' in p.device:
                candidates.append(p.device)

        for port in candidates:
            if self._try_handshake(port):
                return port
        return None

    def _try_handshake(self, port):
        """Open port, send HELLO, check for WELCOME. Returns True if device found."""
        if not self._open_port(port):
            return False

        self._send_hello()

        # Wait up to 2 seconds for WELCOME
        deadline = time.monotonic() + 2.0
        buf = b''
        while time.monotonic() < deadline and self._running:
            try:
                chunk = self.ser.read(max(1, self.ser.in_waiting))
                if chunk:
                    buf += chunk
                    result = self._try_parse_welcome(buf)
                    if result is not None:
                        return True
            except (serial.SerialException, OSError):
                break

        log.debug("No WELCOME from %s after 2s", port)
        self._close_port()
        return False

    def _try_parse_welcome(self, buf):
        """Try to find a WELCOME message in buf. Returns True if found."""
        # Scan for magic
        idx = buf.find(MAGIC)
        if idx < 0 or len(buf) - idx < HEADER_SIZE:
            return None
        header = parse_header(buf[idx:idx + HEADER_SIZE])
        if header is None:
            return None
        msg_type, payload_len = header
        if msg_type != MSG_WELCOME:
            return None
        if len(buf) - idx < HEADER_SIZE + payload_len:
            return None
        payload = buf[idx + HEADER_SIZE:idx + HEADER_SIZE + payload_len]
        if len(payload) >= 4:
            self.screen_width = struct.unpack('>H', payload[0:2])[0]
            self.screen_height = struct.unpack('>H', payload[2:4])[0]
        log.info("WELCOME: screen %dx%d", self.screen_width, self.screen_height)
        self._connected = True
        if self.on_connected:
            self.on_connected()
        return True

    def _run_loop(self):
        """Main connection loop: connect, receive frames, auto-reconnect."""
        while self._running:
            # Phase 1: connect
            if not self._connected:
                self._report_status("Connecting...")
                if self.port:
                    # Explicit port
                    if not self._try_handshake(self.port):
                        self._report_status("Cannot connect to %s — retrying..." % self.port)
                        self._wait(RECONNECT_INTERVAL)
                        continue
                else:
                    # Auto-detect
                    port = self._auto_detect_port()
                    if port is None:
                        self._report_status("No device found — retrying...")
                        self._wait(RECONNECT_INTERVAL)
                        continue
                    self.port = port

            # Phase 2: frame loop
            self._report_status("Connected")
            self._send_ack()  # request first frame
            self._frame_loop()

            # If we get here, connection was lost
            self._close_port()
            if self.port and not self._running:
                break
            self._report_status("Disconnected — reconnecting...")
            self._wait(RECONNECT_INTERVAL)

    def _frame_loop(self):
        """Read and dispatch frames until disconnect or stop."""
        buf = b''
        while self._running and self._connected:
            try:
                time.sleep(0.05)
                if not self.ser:
                    break
                waiting = self.ser.in_waiting
                if waiting == 0:
                    continue
                chunk = self.ser.read(waiting)
                if not chunk:
                    continue
                buf += chunk
                log.debug("Read %d bytes (buf=%d)", len(chunk), len(buf))
            except (serial.SerialException, OSError) as exc:
                log.warning("Serial read error: %s", exc)
                break

            # Process all complete messages in buffer
            while True:
                idx = buf.find(MAGIC)
                if idx < 0:
                    buf = b''
                    break
                if idx > 0:
                    # Discard bytes before magic
                    buf = buf[idx:]

                if len(buf) < HEADER_SIZE:
                    break

                header = parse_header(buf[:HEADER_SIZE])
                if header is None:
                    # Bad header — skip past this magic
                    buf = buf[2:]
                    continue

                msg_type, payload_len = header
                total = HEADER_SIZE + payload_len
                if len(buf) < total:
                    break  # incomplete message, wait for more data

                payload = buf[HEADER_SIZE:total]
                buf = buf[total:]

                self._handle_message(msg_type, payload)

    def _handle_message(self, msg_type, payload):
        """Dispatch a received message."""
        if msg_type == MSG_FRAME:
            log.debug("Frame: %d bytes compressed", len(payload))
            self._handle_frame(payload)
        elif msg_type == MSG_WELCOME:
            if len(payload) >= 4:
                self.screen_width = struct.unpack('>H', payload[0:2])[0]
                self.screen_height = struct.unpack('>H', payload[2:4])[0]
                log.info("WELCOME: screen %dx%d", self.screen_width, self.screen_height)
        else:
            log.debug("Unknown message type: 0x%02x (%d bytes)", msg_type, len(payload))

    def _handle_frame(self, payload):
        """Decompress and deliver a frame."""
        try:
            raw = zlib.decompress(payload)
        except zlib.error as exc:
            log.warning("Frame decompression error: %s — skipping", exc)
            self._send_ack()
            return

        expected = self.screen_width * self.screen_height * 2
        if len(raw) != expected:
            log.warning(
                "Frame size mismatch: got %d, expected %d — skipping",
                len(raw), expected,
            )
            self._send_ack()
            return

        log.debug("Frame decompressed: %d -> %d bytes", len(payload), len(raw))
        try:
            img = rgb565_to_rgb888(raw, self.screen_width, self.screen_height)
            if self.on_frame:
                self.on_frame(img)
        except Exception as exc:
            log.warning("Frame conversion error: %s", exc)

        # Request next frame
        self._send_ack()

    def _report_status(self, text):
        """Report a status string via callback."""
        log.info("%s", text)
        if self.on_status:
            self.on_status(text)

    def _wait(self, seconds):
        """Sleep in small increments so we can respond to stop quickly."""
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline and self._running:
            time.sleep(0.1)


# ---------------------------------------------------------------------------
# Tkinter UI
# ---------------------------------------------------------------------------

class MirrorApp:
    """Main application window."""

    HIGHLIGHT_DURATION_MS = 120  # button highlight feedback duration

    def __init__(self, serial_port=None, assets_dir=None):
        self.serial_port = serial_port
        self.assets_dir = self._resolve_assets_dir(assets_dir)
        self.conn = None

        # Tk setup — chromeless window with transparency
        self.root = tk.Tk()
        self.root.title("iCopy-X Mirror")
        self.root.overrideredirect(True)
        self.root.resizable(False, False)

        img_w, img_h = HOTSPOTS['image_size']
        # Center on screen
        sx = (self.root.winfo_screenwidth() - img_w) // 2
        sy = (self.root.winfo_screenheight() - img_h) // 2
        self.root.geometry("%dx%d+%d+%d" % (img_w, img_h, sx, sy))

        # Transparency: mask.png cyan (#00fff2) regions become see-through.
        # Use magenta as OS color key — won't appear in the device photo.
        TRANSPARENT = '#ff00ff'
        self.root.attributes('-transparentcolor', TRANSPARENT)
        self._transparent_color = TRANSPARENT
        self._transparent_rgb = (255, 0, 255)

        # Drag support (since no title bar)
        self._drag_x = 0
        self._drag_y = 0

        # Canvas background = transparent color key (invisible to user)
        self.canvas = tk.Canvas(
            self.root, width=img_w, height=img_h,
            highlightthickness=0, bg=TRANSPARENT,
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Screen overlay image (on canvas)
        self._bg_photo = None
        sx1, sy1, sx2, sy2 = HOTSPOTS['screen_rect']
        self._screen_id = self.canvas.create_image(
            sx1, sy1, anchor=tk.NW, image=None,
        )
        self._screen_photo = None

        # Status text (centered on screen area)
        scx = (sx1 + sx2) // 2
        scy = (sy1 + sy2) // 2
        self._status_id = self.canvas.create_text(
            scx, scy, text="Connecting...",
            fill='white', font=('Helvetica', 14, 'bold'),
            width=(sx2 - sx1 - 20),
            justify=tk.CENTER,
        )

        # Load background (after screen_id and status_id exist)
        self._load_background()

        # Button highlight overlays (hidden by default)
        self._highlight_ids = {}
        for name, (cx, cy, r) in HOTSPOTS['buttons'].items():
            oid = self.canvas.create_oval(
                cx - r, cy - r, cx + r, cy + r,
                outline='#00ff88', width=2, state=tk.HIDDEN,
            )
            self._highlight_ids[name] = oid

        # Bindings
        self.canvas.bind('<ButtonPress-1>', self._on_press)
        self.canvas.bind('<B1-Motion>', self._on_drag_motion)
        self.canvas.bind('<ButtonRelease-1>', self._on_release)
        for keysym in KEYBOARD_MAP:
            self.root.bind('<%s>' % keysym, self._on_keypress)
        # Numeric keys need special binding (not wrapped in <>)
        self.root.bind('<Key-1>', self._on_keypress)
        self.root.bind('<Key-2>', self._on_keypress)

        self.root.protocol('WM_DELETE_WINDOW', self._on_close)

        # Frame rate tracking
        self._frame_count = 0
        self._fps_time = time.monotonic()

    def _resolve_assets_dir(self, assets_dir):
        """Determine where to look for asset images."""
        if assets_dir:
            return Path(assets_dir)
        # Same directory as this script
        return Path(__file__).resolve().parent

    def _find_asset(self, filename):
        """Find an asset file, checking multiple locations."""
        candidates = [
            self.assets_dir / filename,
            Path.cwd() / filename,
        ]
        for p in candidates:
            if p.exists():
                return str(p)
        return None

    def _load_background(self):
        """Load device.png with mask.png-driven transparency.

        Transparency is ONLY defined by mask.png: cyan (#00fff2) pixels in the
        mask become the OS transparent color key. The device.png alpha channel
        is ignored — the image is flattened to RGB first.
        """
        device_path = self._find_asset('device.png')
        mask_path = self._find_asset('mask.png')
        if device_path:
            try:
                # Flatten device image to RGB — ignore any alpha
                bg_img = Image.open(device_path).convert('RGB')
                expected_w, expected_h = HOTSPOTS['image_size']
                if bg_img.size != (expected_w, expected_h):
                    bg_img = bg_img.resize((expected_w, expected_h), Image.LANCZOS)

                if mask_path:
                    mask_img = Image.open(mask_path).convert('RGB')
                    if mask_img.size != (expected_w, expected_h):
                        mask_img = mask_img.resize((expected_w, expected_h), Image.LANCZOS)
                    # Cyan (#00fff2) in mask = transparent in output
                    import numpy as np
                    dev = np.array(bg_img)
                    msk = np.array(mask_img)
                    cyan = (msk[:,:,0] < 10) & (msk[:,:,1] > 240) & (msk[:,:,2] > 230)
                    dev[cyan] = list(self._transparent_rgb)
                    bg_img = Image.fromarray(dev)

                self._bg_photo = ImageTk.PhotoImage(bg_img)
                self.canvas.create_image(0, 0, anchor=tk.NW, image=self._bg_photo)
                self.canvas.tag_raise(self._screen_id)
                log.info("Loaded background: %s", device_path)
                return
            except Exception as exc:
                log.warning("Could not load device.png: %s", exc)

        # Fallback: dark grey background with screen outline
        log.info("No device.png found — using fallback background")
        sx1, sy1, sx2, sy2 = HOTSPOTS['screen_rect']
        self.canvas.create_rectangle(
            sx1 - 1, sy1 - 1, sx2 + 1, sy2 + 1,
            outline='white', width=2,
        )
        # Draw button labels
        for name, (cx, cy, r) in HOTSPOTS['buttons'].items():
            self.canvas.create_oval(
                cx - r, cy - r, cx + r, cy + r,
                outline='#666666', width=1,
            )
            self.canvas.create_text(
                cx, cy, text=name, fill='#999999',
                font=('Helvetica', 9),
            )

    def _hit_test(self, x, y):
        """Returns hotspot name, 'exit', or None (drag area)."""
        ex1, ey1, ex2, ey2 = HOTSPOTS['exit_rect']
        if ex1 <= x <= ex2 and ey1 <= y <= ey2:
            return 'exit'
        for name, (cx, cy, r) in HOTSPOTS['buttons'].items():
            if ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5 <= r:
                return name
        return None

    def _on_press(self, event):
        """Left button down — determine if it's a hotspot click or drag start."""
        hit = self._hit_test(event.x, event.y)
        self._press_hit = hit
        self._drag_x = event.x
        self._drag_y = event.y
        self._dragged = False

    def _on_drag_motion(self, event):
        """Move window if dragging on non-hotspot area."""
        if self._press_hit is not None:
            return  # pressed on a button — don't drag
        self._dragged = True
        dx = event.x - self._drag_x
        dy = event.y - self._drag_y
        wx = self.root.winfo_x() + dx
        wy = self.root.winfo_y() + dy
        self.root.geometry('+%d+%d' % (wx, wy))

    def _on_release(self, event):
        """Left button up — fire button action if not dragged."""
        if self._dragged:
            return
        hit = self._press_hit
        if hit == 'exit':
            self._on_close()
        elif hit is not None:
            key_code = BUTTON_KEY_MAP.get(hit)
            if key_code and self.conn:
                self.conn.send_key(key_code)
                self._flash_button(hit)

    def _on_keypress(self, event):
        """Handle keyboard shortcut."""
        key_code = KEYBOARD_MAP.get(event.keysym)
        if key_code and self.conn:
            log.debug("Key: %s -> 0x%02x", event.keysym, key_code)
            self.conn.send_key(key_code)
            # Find button name for visual feedback
            for name, code in BUTTON_KEY_MAP.items():
                if code == key_code:
                    self._flash_button(name)
                    break

    def _flash_button(self, name):
        """Briefly highlight a button hotspot."""
        oid = self._highlight_ids.get(name)
        if oid is None:
            return
        self.canvas.itemconfigure(oid, state=tk.NORMAL)
        self.root.after(
            self.HIGHLIGHT_DURATION_MS,
            lambda: self.canvas.itemconfigure(oid, state=tk.HIDDEN),
        )

    def _update_frame(self, img):
        """Update the screen overlay with a new frame. Called from serial thread."""
        # Schedule on the Tk main thread
        self.root.after(0, self._set_screen_image, img)

    def _set_screen_image(self, img):
        """Set the screen image (must run on Tk thread)."""
        try:
            # Resize if the frame doesn't match the screen rect
            sx1, sy1, sx2, sy2 = HOTSPOTS['screen_rect']
            target_w = sx2 - sx1
            target_h = sy2 - sy1
            if img.size != (target_w, target_h):
                img = img.resize((target_w, target_h), Image.NEAREST)

            self._screen_photo = ImageTk.PhotoImage(img)
            self.canvas.itemconfigure(self._screen_id, image=self._screen_photo)

            # Hide status text once we have frames
            self.canvas.itemconfigure(self._status_id, state=tk.HIDDEN)

            # FPS counter
            self._frame_count += 1
            now = time.monotonic()
            elapsed = now - self._fps_time
            if elapsed >= 5.0:
                fps = self._frame_count / elapsed
                log.info("%.1f FPS", fps)
                self._frame_count = 0
                self._fps_time = now

        except tk.TclError:
            pass  # window destroyed

    def _update_status(self, text):
        """Update the status text. Called from serial thread."""
        self.root.after(0, self._set_status_text, text)

    def _set_status_text(self, text):
        """Set status text (must run on Tk thread)."""
        try:
            self.canvas.itemconfigure(
                self._status_id, text=text, state=tk.NORMAL,
            )
        except tk.TclError:
            pass

    def _on_connected(self):
        """Called when device connection is established."""
        self._update_status("Connected")

    def _on_disconnected(self):
        """Called when device connection is lost."""
        self._update_status("Disconnected")

    def _on_close(self):
        """Handle window close."""
        if self.conn:
            self.conn.stop()
            self.conn = None
        self.root.destroy()

    def run(self):
        """Start the application."""
        # Set up serial connection
        self.conn = SerialConnection(port=self.serial_port)
        self.conn.on_frame = self._update_frame
        self.conn.on_connected = self._on_connected
        self.conn.on_disconnected = self._on_disconnected
        self.conn.on_status = self._update_status
        self.conn.start()

        # Ensure status text is on top
        self.canvas.tag_raise(self._status_id)
        for oid in self._highlight_ids.values():
            self.canvas.tag_raise(oid)

        # Run Tk main loop
        self.root.mainloop()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="iCopy-X Screen Mirror Client",
        epilog=(
            "Connect to an iCopy-X device over USB serial, display its screen "
            "in real-time, and control it with mouse clicks or keyboard.\n\n"
            "Keyboard shortcuts:\n"
            "  Arrow keys    UP/DOWN/LEFT/RIGHT\n"
            "  Enter         OK\n"
            "  1 / F1        M1\n"
            "  2 / F2        M2\n"
            "  Escape        PWR\n"
            "  Space / F3    ALL\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        'port', nargs='?', default=None,
        help='Serial port (e.g. /dev/ttyACM0, COM3). Auto-detect if omitted.',
    )
    parser.add_argument(
        '--assets-dir', default=None,
        help='Directory containing device.png and mask.png assets.',
    )
    parser.add_argument(
        '-v', '--verbose', action='store_true',
        help='Enable debug logging.',
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    app = MirrorApp(
        serial_port=args.port,
        assets_dir=args.assets_dir,
    )
    app.run()


if __name__ == '__main__':
    main()
