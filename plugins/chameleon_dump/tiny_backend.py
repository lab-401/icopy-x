"""Chameleon Tiny backend for the Chameleon Dump plugin.

Write: load an iCopy-X dump into a Chameleon Tiny slot.
Read:  save a Chameleon Tiny slot back out as an iCopy-X dump.

The Chameleon Tiny (proxgrind firmware, 2023 CI build or later) is expected
on the iCopy-X USB host port and appears as a USB CDC serial device.  It
uses the ChameleonMini text command set (VERSION?, SETTING=, CONFIG=,
UIDMODE=, SAKMODE=, ...) plus XModem for UPLOAD/DOWNLOAD, so a Chameleon
Mini should work too -- untested (no hardware to verify).

Supported dump families (iCopy-X filename convention, or read from the
dump contents when the file has been renamed on the device):
    mf1     M1-<1K|4K|Mini>-<4B|7B>_<uid>_<n>.bin   -> MF_CLASSIC_1K[_7B] / 4K[_7B] / MINI_4B
    mfu     NTAG213|NTAG215|NTAG216_<uid>_<n>.json  -> NTAG213 / NTAG215 / NTAG216

The Chameleon memory image is byte-identical to the PM3 raw dump for MIFARE
Classic, and the raw page image (4 bytes/page) for NTAG.

Protocol reference: PROJECT-NOTES.md section 2.3.
"""

import glob
import json
import os
import re
import time

PAGE_SIZE = 4
BLOCK_SIZE = 16

TINY_VID = 0x16D0
TINY_PID = 0x04B2
BAUD = 115200
CMD_TIMEOUT = 2.5
STORE_TIMEOUT = 15.0
XMODEM_BLOCK = 128

SOH = 0x01
NAK = 0x15
ACK = 0x06
EOT = 0x04
CAN = 0x18

# MIFARE Classic: variant -> (blocks, {uidlen: CONFIG name})
MFC_CAP = {
    "1k": (64, {4: "MF_CLASSIC_1K", 7: "MF_CLASSIC_1K_7B"}),
    "4k": (256, {4: "MF_CLASSIC_4K", 7: "MF_CLASSIC_4K_7B"}),
    "mini": (20, {4: "MF_CLASSIC_MINI_4B"}),
}
MFC_NAME_RE = re.compile(
    r"^M1-(1K|4K|Mini)-(4B|7B)_[0-9A-Fa-f]+_\d+$", re.IGNORECASE)

# NTAG: tag -> (pages, memory size in bytes)
NTAG_CFG = {
    "NTAG213": (45, 180),
    "NTAG215": (135, 540),
    "NTAG216": (231, 924),
}
MFU_NAME_RE = re.compile(
    r"^(NTAG213|NTAG215|NTAG216)_[0-9A-Fa-f]+_\d+$", re.IGNORECASE)

# Content fallbacks for dumps renamed on the device (see ultra_backend):
# family from the dump sub-directory, size from the .bin length, UID from
# block 0 (MIFARE Classic) or the page image (NTAG).
_MF1_SIZE_BY_BYTES = {320: "mini", 1024: "1k", 2048: "plus-2k", 4096: "4k"}
_MFU_PAGES_BY_TYPE = {45: "NTAG213", 135: "NTAG215", 231: "NTAG216"}
_FAMILY_DIRS = ("mf1", "mfu")

# SAKMODE is only accepted by the firmware for the 4-byte 1K/4K configs;
# the _7B variants reply 201:INVALID COMMAND USAGE.
SAKMODE_CONFIGS = ("MF_CLASSIC_1K", "MF_CLASSIC_4K")

# Read-side CONFIG name -> (filename size token, blocks, uid_len).
MFC_READ = {
    "MF_CLASSIC_1K": ("1K", 64, 4),
    "MF_CLASSIC_1K_7B": ("1K", 64, 7),
    "MF_CLASSIC_4K": ("4K", 256, 4),
    "MF_CLASSIC_4K_7B": ("4K", 256, 7),
    "MF_CLASSIC_MINI_4B": ("Mini", 20, 4),
}

# Default NTAG version bytes -- the AVR emulator does not report them.
NTAG_DEFAULT_VERSION = {
    "NTAG213": "0004040201000F03",
    "NTAG215": "0004040201001103",
    "NTAG216": "0004040201001303",
}

DUMP_DIRS = (
    "/mnt/upan/dump/mf1",
    "/mnt/upan/dump/mfu",
)


class TinyError(Exception):
    pass


class TinyTimeout(TinyError):
    pass


class TinyCommandError(TinyError):
    def __init__(self, cmd, code, text, step=""):
        self.cmd = cmd
        self.code = code
        self.text = text
        self.step = step
        where = " while '%s'" % step if step else ""
        super(TinyCommandError, self).__init__(
            "command %r%s failed: %d:%s" % (cmd, where, code, text))


# ---------------------------------------------------------------------------
# Dump detection / parsing
# ---------------------------------------------------------------------------

def _family_of(path):
    """Dump family from the folder name (``mf1``/``mfu``) or ''."""
    family = os.path.basename(os.path.dirname(path)).lower()
    return family if family in _FAMILY_DIRS else ""


def _read_bin(path):
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except OSError:
        return None


def _json_card(path):
    json_path = os.path.splitext(path)[0] + ".json"
    if not os.path.isfile(json_path):
        return {}
    try:
        with open(json_path, "r", errors="ignore") as fh:
            card = json.load(fh).get("Card", {})
    except (ValueError, OSError):
        return {}
    return card if isinstance(card, dict) else {}


def _is_hex(value, length=None):
    if not value or (length is not None and len(value) != length):
        return False
    return all(c in "0123456789ABCDEFabcdef" for c in value)


def _mf1_uid_from_block0(data):
    """``(uid, uid_len)`` from MIFARE Classic block 0, or None."""
    if not data or len(data) < 10:
        return None
    d = bytearray(data[:16])
    if len(d) >= 8 and (d[0] ^ d[1] ^ d[2] ^ d[3]) == d[4] and (d[6] & 0xC0) == 0:
        return bytes(d[0:4]).hex().upper(), 4
    if len(d) >= 9 and (d[8] & 0xC0) == 0x40:
        return bytes(d[0:7]).hex().upper(), 7
    return None


def _uidlen_from(path):
    uid_hex = (_json_card(path).get("UID") or "").strip()
    if _is_hex(uid_hex) and len(uid_hex) == 14:
        return 7
    if _is_hex(uid_hex) and len(uid_hex) == 8:
        return 4
    found = _mf1_uid_from_block0(_read_bin(path))
    return found[1] if found is not None else 4


def _detect_mf1_content(path):
    if os.path.splitext(path)[1].lower() != ".bin":
        return None
    variant = _MF1_SIZE_BY_BYTES.get(len(_read_bin(path) or b""))
    cap = MFC_CAP.get(variant) if variant else None
    if cap is None:
        return None
    blocks, cfgs = cap
    uidlen = _uidlen_from(path)
    config = cfgs.get(uidlen)
    if config is None:
        return None
    return {"kind": "mf1", "config": config, "type_name": config,
            "blocks": blocks, "memsize": blocks * BLOCK_SIZE, "uidlen": uidlen}


def _detect_mfu_content(path):
    try:
        pages = _parse_mfu_pages(path)
    except (OSError, TinyError, ValueError):
        return None
    tag = _MFU_PAGES_BY_TYPE.get(len(pages) // 4)
    cap = NTAG_CFG.get(tag) if tag else None
    if cap is None:
        return None
    page_count, memsize = cap
    return {"kind": "mfu", "config": tag, "type_name": tag,
            "pages": page_count, "memsize": memsize, "uidlen": 7}


def _detect_dump(path, family=None):
    name = os.path.splitext(os.path.basename(path))[0]

    match = MFC_NAME_RE.match(name)
    if match:
        variant = match.group(1).lower()
        info = MFC_CAP.get(variant)
        if info:
            blocks, cfgs = info
            uidlen = 7 if match.group(2).upper() == "7B" else 4
            config = cfgs.get(uidlen)
            if config:
                return {"kind": "mf1", "config": config, "type_name": config,
                        "blocks": blocks, "memsize": blocks * BLOCK_SIZE,
                        "uidlen": uidlen}

    match = MFU_NAME_RE.match(name)
    if match:
        tag = match.group(1).upper()
        pages, memsize = NTAG_CFG[tag]
        return {"kind": "mfu", "config": tag, "type_name": tag,
                "pages": pages, "memsize": memsize, "uidlen": 7}

    # Renamed dump: the filename no longer identifies it, so use the family
    # folder and the file contents (mirrors the device's own Tag Info).
    family = (family or "").lower() or _family_of(path)
    if family == "mf1":
        return _detect_mf1_content(path)
    if family == "mfu":
        return _detect_mfu_content(path)
    # No family hint (custom dump dir): sniff by length / page count.
    return _detect_mf1_content(path) or _detect_mfu_content(path)


def _parse_mfu_pages(path):
    """Return the raw page image from a PM3 mfu dump (json preferred)."""
    json_path = os.path.splitext(path)[0] + ".json"
    if os.path.isfile(json_path):
        with open(json_path, "r", errors="ignore") as fh:
            doc = json.load(fh)
        blocks = doc.get("blocks", {}) or {}
        buf = bytearray()
        i = 0
        while str(i) in blocks and blocks[str(i)]:
            buf += bytes.fromhex(blocks[str(i)])
            i += 1
        if buf:
            return bytes(buf)
    with open(path, "rb") as fh:
        raw = fh.read()
    if len(raw) < 60:
        raise TinyError("%s: mfu dump too short (%d bytes)" % (
            os.path.basename(path), len(raw)))
    # version(8) + 4 + signature(32) + counters(12) + pages
    return raw[56:]


def _read_dump(path, meta):
    kind = meta["kind"]
    if kind == "mf1":
        with open(path, "rb") as fh:
            data = fh.read()
        if len(data) != meta["memsize"]:
            raise TinyError("%s: %d bytes but name implies %d" % (
                os.path.basename(path), len(data), meta["memsize"]))
        return data
    if kind == "mfu":
        pages = _parse_mfu_pages(path)
        if len(pages) < meta["memsize"]:
            raise TinyError("%s: %d page bytes, need %d for %s" % (
                os.path.basename(path), len(pages), meta["memsize"], meta["config"]))
        return pages[:meta["memsize"]]
    raise TinyError("unknown dump kind: %s" % kind)


def _uid_of(data, meta):
    if meta["kind"] == "mfu":
        return data[0:3] + data[4:8]
    return data[:meta["uidlen"]]


# ---------------------------------------------------------------------------
# Transport / device
# ---------------------------------------------------------------------------

class _TinyTransport(object):
    def __init__(self, port, baud=BAUD):
        import serial
        self.ser = serial.Serial(port=port, baudrate=baud, timeout=0.05)
        try:
            self.ser.dtr = True
        except Exception:
            pass
        try:
            self.ser.reset_input_buffer()
        except Exception:
            pass

    def write(self, data):
        self.ser.write(data)
        self.ser.flush()

    def read_some(self, timeout):
        self.ser.timeout = timeout
        return self.ser.read(4096)

    def reset_input(self):
        try:
            self.ser.reset_input_buffer()
        except Exception:
            pass

    def close(self):
        try:
            self.ser.close()
        except Exception:
            pass


class _Tiny(object):
    def __init__(self, transport):
        self.t = transport
        self.rx = bytearray()

    # -- buffered receive --------------------------------------------------
    def _recv(self, timeout):
        if self.rx:
            out = bytes(self.rx)
            self.rx.clear()
            return out
        return self.t.read_some(timeout)

    def _read_byte(self, timeout):
        deadline = time.time() + timeout
        while time.time() < deadline:
            b = self._recv(0.5)
            if b:
                if len(b) > 1:
                    self.rx += b[1:]
                return b[0]
        return None

    def _read_exact(self, n, timeout):
        out = bytearray()
        deadline = time.time() + timeout
        while len(out) < n and time.time() < deadline:
            b = self._recv(0.5)
            if b:
                out += b
        if len(out) > n:
            self.rx += out[n:]
            del out[n:]
        return bytes(out)

    def _read_line(self, timeout):
        buf = bytearray()
        deadline = time.time() + timeout
        while time.time() < deadline:
            b = self._recv(0.2)
            if not b:
                continue
            buf += b
            if b"\n" in buf:
                line, _, rest = bytes(buf).partition(b"\n")
                self.rx += rest
                return line.decode("ascii", "replace").rstrip("\r")
        return bytes(buf).decode("ascii", "replace").rstrip("\r\n")

    # -- line protocol -----------------------------------------------------
    def command(self, text, timeout=CMD_TIMEOUT, step=""):
        self.rx.clear()
        self.t.reset_input()
        self.t.write((text + "\r").encode("ascii"))
        line = self._read_line(timeout)
        if not line:
            raise TinyTimeout("command %r%s timed out" % (
                text, " while '%s'" % step if step else ""))
        if ":" not in line:
            raise TinyError("command %r: bad response %r" % (text, line))
        code_s, msg = line.split(":", 1)
        try:
            code = int(code_s)
        except ValueError:
            raise TinyError("command %r: bad status %r" % (text, line))
        extra = None
        if code == 101:
            extra = self._read_line(timeout)
        return code, msg, extra

    def value(self, text, timeout=CMD_TIMEOUT):
        code, _msg, extra = self.command(text, timeout)
        return extra

    def expect_ok(self, text, step="", timeout=CMD_TIMEOUT):
        code, msg, _extra = self.command(text, timeout, step)
        if code != 100:
            raise TinyCommandError(text, code, msg, step)

    # -- XModem ------------------------------------------------------------
    def upload(self, image, on_progress=None):
        self.rx.clear()
        self.t.reset_input()
        self.t.write(b"UPLOAD\r")
        line = self._read_line(CMD_TIMEOUT)
        if not line.startswith("110"):
            raise TinyError("UPLOAD: expected 110, got %r" % line)
        if self._read_byte(8.0) != NAK:
            raise TinyTimeout("UPLOAD: no NAK from device")

        n = len(image)
        pkt = 1
        off = 0
        while off < n:
            blk = image[off:off + XMODEM_BLOCK]
            off += XMODEM_BLOCK
            if len(blk) < XMODEM_BLOCK:
                blk = blk + b"\x00" * (XMODEM_BLOCK - len(blk))
            self.t.write(bytes([SOH, pkt, 255 - pkt]) + blk + bytes([sum(blk) & 0xFF]))
            if self._read_byte(3.0) != ACK:
                raise TinyError("UPLOAD: no ACK for packet %d" % pkt)
            if on_progress is not None:
                on_progress(min(off, n), n)
            pkt = (pkt + 1) % 256
        self.t.write(bytes([EOT]))
        if self._read_byte(3.0) != ACK:
            raise TinyError("UPLOAD: no ACK for EOT")

    def download(self):
        self.rx.clear()
        self.t.reset_input()
        self.t.write(b"DOWNLOAD\r")
        line = self._read_line(CMD_TIMEOUT)
        if not line.startswith("110"):
            raise TinyError("DOWNLOAD: expected 110, got %r" % line)
        self.t.write(bytes([NAK]))
        data = bytearray()
        while True:
            v = self._read_byte(6.0)
            if v is None:
                raise TinyTimeout("DOWNLOAD: timeout after %d bytes" % len(data))
            if v == SOH:
                rest = self._read_exact(2 + XMODEM_BLOCK + 1, 3.0)
                if len(rest) < 2 + XMODEM_BLOCK + 1:
                    raise TinyTimeout("DOWNLOAD: short frame")
                fno, nfno = rest[0], rest[1]
                blk = rest[2:2 + XMODEM_BLOCK]
                csum = rest[2 + XMODEM_BLOCK]
                if (sum(blk) & 0xFF) == csum and (fno + nfno) == 0xFF:
                    data += blk
                    self.t.write(bytes([ACK]))
                else:
                    self.t.write(bytes([NAK]))
            elif v == EOT:
                self.t.write(bytes([ACK]))
                break
            elif v == CAN:
                raise TinyError("DOWNLOAD: cancelled (CAN)")
        return bytes(data)

    def close(self):
        self.t.close()


def _candidate_ports():
    ports = []
    for pattern in ("/dev/ttyACM*", "/dev/ttyUSB*"):
        ports.extend(sorted(glob.glob(pattern)))
    for by_id in sorted(glob.glob("/dev/serial/by-id/*")):
        try:
            real = os.path.realpath(by_id)
        except OSError:
            real = by_id
        if real not in ports:
            ports.append(real)
    return ports


def _find_tiny(attempts=3, delay=0.4):
    last = "no serial device found"
    for _ in range(max(1, attempts)):
        for dev in _candidate_ports():
            transport = None
            try:
                transport = _TinyTransport(dev)
                tiny = _Tiny(transport)
                code, _msg, extra = tiny.command("VERSION?", timeout=1.5)
                if code == 101 and extra and "Chameleon" in extra:
                    transport = None  # keep this port open (finally must not close it)
                    return tiny, dev, extra
                last = "%s: %r" % (dev, extra or code)
            except Exception as exc:
                last = "%s: %s" % (dev, exc)
            finally:
                if transport is not None:
                    try:
                        transport.close()
                    except Exception:
                        pass
        time.sleep(delay)
    raise TinyError(last)


def _dump_dirs():
    override = os.environ.get("TINY_WRITER_DUMP_DIR")
    if not override:
        override = os.environ.get("ULTRA_WRITER_DUMP_DIR")
    if override:
        return (override,)
    return DUMP_DIRS


# Optional card-notes store (shared with the card_notes plugin via
# lib.card_notes).  Missing/malformed file or an unavailable store simply
# yields no notes; the writer never depends on it.
def _load_store():
    try:
        from lib import card_notes as store
    except Exception:
        return None
    return store


def _note_for(store, family, uid):
    """Note for a dump, keyed by its (content-derived) UID."""
    if store is None or not uid:
        return ""
    return store.lookup(family, uid)


# Dump writer (dump_writer.py, next to this file) used by the read-to-dump
# flow.  Loaded lazily via importlib so it works whether the plugin was
# imported through the loader or directly, and so a missing module only
# disables reading, never the write path.
_CARD_DUMP = None
_CARD_DUMP_TRIED = False


def _load_card_dump():
    global _CARD_DUMP, _CARD_DUMP_TRIED
    if not _CARD_DUMP_TRIED:
        _CARD_DUMP_TRIED = True
        try:
            import importlib.util
            path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                'dump_writer.py')
            spec = importlib.util.spec_from_file_location(
                'chameleon_dump_dump_writer', path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            _CARD_DUMP = module
        except Exception:
            _CARD_DUMP = None
    return _CARD_DUMP


def _uid_used(uid):
    """True when a slot's UID hint looks like real content.

    The ChameleonMini reports its default config (MF_CLASSIC_1K) for every
    never-written slot and answers ``UID?`` with the blank/erased value --
    all ``0`` or all ``F``.  Such slots are skipped so only slots holding a
    real card are listed.
    """
    text = (uid or '').strip().upper()
    if not text:
        return False
    if text.strip('0') == '' or text.strip('F') == '':
        return False
    return True


def _scan_dumps():
    out = []
    for directory in _dump_dirs():
        try:
            names = sorted(os.listdir(directory))
        except OSError:
            continue
        family = os.path.basename(os.path.normpath(directory)).lower()
        # A dump may have both .bin and .json siblings; keep one (prefer .bin,
        # whose .json is read as a side file by _parse_mfu_pages).
        by_base = {}
        order = []
        for name in names:
            if not name.lower().endswith((".bin", ".json")):
                continue
            base = os.path.splitext(name)[0]
            if base not in by_base:
                by_base[base] = name
                order.append(base)
            elif name.lower().endswith(".bin"):
                by_base[base] = name
        for base in order:
            path = os.path.join(directory, by_base[base])
            meta = _detect_dump(path, family)
            if meta is None:
                continue
            try:
                data = _read_dump(path, meta)
            except (OSError, TinyError, ValueError):
                continue
            out.append({"path": path, "name": base,
                        "uid": _uid_of(data, meta).hex().upper(), "meta": meta})
    return out


# ---------------------------------------------------------------------------
# Plugin
# ---------------------------------------------------------------------------

class TinyBackend(object):
    """ChameleonMini / Tiny backend for the Chameleon Dump plugin."""

    def __init__(self, host=None):
        self.host = host
        self._tiny = None
        self._port = None
        self._version = None
        self._dumps = []
        self._entry = None
        self._slot = 1
        self._read_slots = []
        self._read_entry = None

    # -- host helpers --------------------------------------------------

    def _set(self, key, value):
        if self.host is not None:
            self.host.set_var(key, value)

    def _progress(self, value, message):
        if self.host is not None:
            self.host.set_progress(value, message)

    def tr(self, text):
        translator = getattr(self.host, "tr", None)
        return translator(text) if translator is not None else text

    def _selected_index(self, state_id):
        list_state = getattr(self.host, "_list_state", None) or {}
        entry = list_state.get(state_id) or {}
        try:
            return int(entry.get("selected", 0))
        except (TypeError, ValueError):
            return 0

    def _set_list_items(self, state_id, items):
        screens = getattr(self.host, "_screens", None)
        if not screens or state_id not in screens:
            return False
        state_def = screens[state_id]
        screen = state_def.get("screen", state_def)
        content = screen.setdefault("content", {})
        content["type"] = "list"
        content["items"] = items
        return True

    # -- lifecycle -----------------------------------------------------

    def on_destroy(self):
        self._close()

    def _close(self):
        if self._tiny is not None:
            try:
                self._tiny.close()
            except Exception:
                pass
            self._tiny = None

    # -- UI methods ----------------------------------------------------

    def start(self, device=None):
        self._close()
        self._set("error_msg", "")
        self._set("progress_value", 0)
        self._set("progress_message", "")

        # Take ownership of an already-found device first, so every early
        # error return stays closable (on_destroy -> _close).
        if device is not None:
            self._tiny, self._port, self._version = device

        try:
            dumps = _scan_dumps()
        except Exception as exc:
            self._set("error_msg", self.tr("Dump scan failed:\n%s") % exc)
            return {"status": "error"}

        if not dumps:
            self._set(
                "error_msg",
                self.tr(
                    "No supported dump found.\n\nLooked for iCopy-X dumps:\n"
                    "M1-1K/4K/Mini-4B/7B_...\nNTAG213/215/216_...\n"
                    "in /mnt/upan/dump/"))
            return {"status": "error"}

        self._dumps = dumps
        store = _load_store()
        labels = []
        for entry in dumps:
            name = entry["name"]
            short = name if len(name) <= 28 else name[:27] + "~"
            note = _note_for(store, entry["meta"]["kind"], entry["uid"])
            if note:
                short = "%s  %s" % (note, short)
                if len(short) > 34:
                    short = short[:33] + "~"
            labels.append({"label": short, "action": "run:choose_dump"})
        self._set_list_items("select_dump", labels)

        if device is None:
            try:
                self._tiny, self._port, self._version = _find_tiny()
            except Exception as exc:
                self._set("error_msg", self.tr(
                    "Chameleon Mini/Tiny not found.\n\n%s") % exc)
                return {"status": "error"}

        return {"status": "ready"}

    def choose_dump(self):
        idx = self._selected_index("select_dump")
        if idx < 0 or idx >= len(self._dumps):
            self._set("error_msg", self.tr("Dump selection out of range"))
            return {"status": "error"}
        entry = self._dumps[idx]
        try:
            data = _read_dump(entry["path"], entry["meta"])
        except Exception as exc:
            self._set("error_msg", self.tr("Cannot read dump:\n%s") % exc)
            return {"status": "error"}
        entry["data"] = data
        self._entry = entry
        meta = entry["meta"]
        self._set("dump_name", entry["name"])
        self._set("dump_uid", entry["uid"])
        self._set("card_type", self.tr("%s, UID %dB") % (meta["type_name"], meta["uidlen"]))
        return {"status": "ready"}

    def choose_slot(self):
        idx = self._selected_index("select_slot")
        if idx < 0 or idx > 7:
            self._set("error_msg", self.tr("Invalid slot"))
            return {"status": "error"}
        self._slot = idx + 1
        self._set("slot_text", self.tr("Slot %d") % (idx + 1))
        return {"status": "ready"}

    # -- read: Chameleon slot -> iCopy-X dump --------------------------

    def start_read(self, device=None):
        """List the readable slots of the connected ChameleonMini/Tiny."""
        self._close()
        self._set("error_msg", "")
        self._set("progress_value", 0)
        self._set("progress_message", "")
        self._read_slots = []

        # Take ownership of an already-found device first, so every early
        # error return stays closable (on_destroy -> _close).
        if device is not None:
            self._tiny, self._port, self._version = device

        if _load_card_dump() is None:
            self._set("error_msg", self.tr("Dump writer unavailable."))
            return {"status": "error"}

        if device is None:
            try:
                self._tiny, self._port, self._version = _find_tiny()
            except Exception as exc:
                self._set("error_msg", self.tr(
                    "Chameleon Mini/Tiny not found.\n\n%s") % exc)
                return {"status": "error"}

        original = self._query_setting(self._tiny)
        try:
            slots = self._scan_read_slots(self._tiny)
        except Exception as exc:
            self._set("error_msg", self.tr("Cannot read slots:\n%s") % exc)
            return {"status": "error"}
        finally:
            if original is not None:
                try:
                    self._tiny.expect_ok("SETTING=%d" % original)
                except Exception:
                    pass

        if not slots:
            self._set(
                "error_msg",
                self.tr(
                    "No readable slot found.\n\nOnly MIFARE Classic and "
                    "NTAG213/215/216 slots can be saved as dumps."))
            return {"status": "error"}

        self._read_slots = slots
        labels = [{"label": s["label"], "action": "run:choose_read_slot"}
                  for s in slots]
        self._set_list_items("read_slot", labels)
        return {"status": "ready"}

    def _query_setting(self, tiny):
        try:
            value = tiny.value("SETTING?")
            return int((value or "").strip())
        except Exception:
            return None

    def _scan_read_slots(self, tiny):
        slots = []
        for n in range(1, 9):
            try:
                tiny.expect_ok("SETTING=%d" % n, step="select slot")
                _code, msg, extra = tiny.command("CONFIG?")
            except Exception:
                continue
            cfg = (extra or msg or "").strip().upper()
            entry = self._classify_read_slot(n, cfg)
            if entry is None:
                continue
            # ChameleonMini reports its default config (MF_CLASSIC_1K) for
            # every never-written slot, so the type alone cannot tell an
            # empty slot from a real card.  An unwritten slot has an
            # all-zero UID; skip those so only slots with content list.
            uid = self._read_uid_hint(tiny)
            if not _uid_used(uid):
                continue
            entry["uid"] = uid
            slots.append(entry)
        return slots

    def _read_uid_hint(self, tiny):
        try:
            return (tiny.value("UID?") or "").strip().upper()
        except Exception:
            return ""

    def _classify_read_slot(self, slot, cfg):
        base = self.tr("Slot %d") % slot
        if cfg in MFC_READ:
            size, blocks, uid_len = MFC_READ[cfg]
            return {"slot": slot, "family": "mf1", "config": cfg,
                    "name": size, "blocks": blocks, "uidlen": uid_len,
                    "label": "%s  %s" % (base, size)}
        if cfg in NTAG_CFG:
            pages, memsize = NTAG_CFG[cfg]
            return {"slot": slot, "family": "mfu", "config": cfg,
                    "name": cfg, "pages": pages, "memsize": memsize,
                    "uidlen": 7, "label": "%s  %s" % (base, cfg)}
        return None

    def choose_read_slot(self):
        idx = self._selected_index("read_slot")
        if idx < 0 or idx >= len(self._read_slots):
            self._set("error_msg", self.tr("Slot selection out of range"))
            return {"status": "error"}
        entry = self._read_slots[idx]
        self._read_entry = entry
        self._set("read_slot_text", self.tr("Slot %d") % entry["slot"])
        self._set("read_type", entry["name"])
        return {"status": "ready"}

    def do_read(self):
        try:
            return self._do_read()
        except TinyCommandError as exc:
            self._set("result_title", self.tr("Read Failed"))
            self._set("result_detail", str(exc))
            return {"status": "fail"}
        except Exception as exc:
            self._set("result_title", self.tr("Read Failed"))
            self._set("result_detail", "%s: %s" % (type(exc).__name__, exc))
            return {"status": "fail"}

    def _do_read(self):
        card_dump = _load_card_dump()
        if card_dump is None:
            raise TinyError("dump writer unavailable")

        entry = self._read_entry
        tiny = self._tiny
        if tiny is None:
            self._progress(2, self.tr("Connecting"))
            tiny, port, version = _find_tiny()
            self._tiny = tiny
            self._port = port

        self._progress(6, self.tr("SETTING=%d") % entry["slot"])
        tiny.expect_ok("SETTING=%d" % entry["slot"], step="select slot")

        self._progress(20, self.tr("Reading slot"))
        image = tiny.download()

        if entry["family"] == "mf1":
            path, uid, detail = self._read_mf1(entry, image, card_dump)
        else:
            path, uid, detail = self._read_mfu(entry, image, card_dump)

        self._progress(100, self.tr("Done"))
        self._set("result_title", self.tr("Saved"))
        self._set("result_detail", "\n".join([
            self.tr("%s -> dump") % entry["name"],
            os.path.basename(path),
            detail,
        ]))
        return {"status": "ok"}

    def _read_mf1(self, entry, image, card_dump):
        blocks = entry["blocks"]
        uid_len = entry["uidlen"]
        data = image[:blocks * BLOCK_SIZE]
        if len(data) != blocks * BLOCK_SIZE:
            raise TinyError("slot returned %d bytes, expected %d" % (
                len(image), blocks * BLOCK_SIZE))
        uid = self._mf1_uid(entry, data, uid_len)
        path = card_dump.save_mf1(self._save_dir("mf1"), blocks, uid_len, uid,
                                  data)
        return path, uid, self.tr("UID %s, %dB, %d blocks") % (
            uid, uid_len, blocks)

    def _read_mfu(self, entry, image, card_dump):
        pages = entry["pages"]
        memsize = entry["memsize"]
        data = image[:memsize]
        if len(data) != memsize:
            raise TinyError("slot returned %d bytes, expected %d" % (
                len(image), memsize))
        uid = card_dump.mfu_uid(data).hex().upper()
        version = bytes.fromhex(NTAG_DEFAULT_VERSION[entry["config"]])
        path = card_dump.save_mfu(self._save_dir("mfu"), entry["name"], uid,
                                  data, version=version)
        return path, uid, self.tr("UID %s, %d pages") % (uid, pages)

    def _mf1_uid(self, entry, data, uid_len):
        hint = (entry.get("uid") or "").upper()
        if len(hint) == uid_len * 2:
            return hint
        if uid_len == 7 and len(data) >= 8:
            return (data[0:3] + data[4:8]).hex().upper()
        return data[:uid_len].hex().upper()

    def _save_dir(self, family):
        override = os.environ.get("TINY_WRITER_DUMP_DIR")
        if not override:
            override = os.environ.get("ULTRA_WRITER_DUMP_DIR")
        if override:
            return override
        card_dump = _load_card_dump()
        return card_dump.default_dir(family)

    def do_write(self):
        try:
            return self._do_write()
        except TinyCommandError as exc:
            self._set("result_title", self.tr("Write Failed"))
            self._set("result_detail", str(exc))
            return {"status": "fail"}
        except Exception as exc:
            self._set("result_title", self.tr("Write Failed"))
            self._set("result_detail", "%s: %s" % (type(exc).__name__, exc))
            return {"status": "fail"}

    # -- core ----------------------------------------------------------

    def _do_write(self):
        entry = self._entry
        meta = entry["meta"]
        data = entry["data"]
        slot = self._slot
        kind = meta["kind"]

        tiny = self._tiny
        if tiny is None:
            self._progress(2, self.tr("Connecting"))
            tiny, port, version = _find_tiny()
            self._tiny = tiny
            self._port = port

        self._progress(4, self.tr("SETTING=%d") % slot)
        tiny.expect_ok("SETTING=%d" % slot, step="select slot")
        self._progress(8, self.tr("CONFIG=%s") % meta["config"])
        tiny.expect_ok("CONFIG=%s" % meta["config"], step="set config")
        if kind == "mf1":
            self._progress(12, self.tr("UIDMODE=0"))
            tiny.expect_ok("UIDMODE=0", step="standard card")
            if meta["config"] in SAKMODE_CONFIGS:
                self._progress(14, self.tr("SAKMODE=1"))
                tiny.expect_ok("SAKMODE=1", step="SAK/ATQA from block 0")
        self._progress(16, self.tr("CLEAR"))
        tiny.expect_ok("CLEAR", step="clear slot")

        def on_up(off, total):
            self._progress(16 + int(60 * off / max(total, 1)),
                           self.tr("Writing %d/%d") % (off, total))

        tiny.upload(data, on_progress=on_up)

        self._progress(80, self.tr("STORE"))
        tiny.expect_ok("STORE", step="store to flash", timeout=STORE_TIMEOUT)
        time.sleep(0.2)

        self._progress(86, self.tr("Verify"))
        back = tiny.download()
        memsize = meta["memsize"]
        if bytes(back[:memsize]) != bytes(data[:memsize]):
            first = next((i for i in range(min(len(back), memsize))
                          if back[i] != data[i]), None)
            where = ("offset 0x%04X: %02X vs %02X" % (first, data[first], back[first])
                     if first is not None else "length")
            raise TinyError("verify mismatch at %s" % where)

        self._progress(96, self.tr("Readback OK"))
        cfg = tiny.value("CONFIG?")
        uid = tiny.value("UID?")
        self._progress(100, self.tr("Done"))

        self._set("result_title", self.tr("Success"))
        self._set("result_detail", "\n".join([
            self.tr("%s -> %s") % (meta["type_name"], self._slot_text()),
            self.tr("DOWNLOAD %d B identical") % memsize,
            self.tr("CONFIG %s") % cfg,
            self.tr("UID %s") % uid,
        ]))
        return {"status": "ok"}

    def _slot_text(self):
        return self.tr("Slot %d") % self._slot
