##########################################################################
# Required Notice: Copyright ETOILE401 SAS (http://www.lab401.com)
#
# Copyright (c) 2026: ETOILE401 SAS & https://github.com/quantum-x/
# Copyright (c) 2026: Vost02
#
# This software is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this software for commercial purposes.
#
# A copy of the license is available at:
# https://polyformproject.org/licenses/noncommercial/1.0.0
#
# This entire header "Required Notice" must remain in place.
##########################################################################

"""Chameleon Ultra backend for the Chameleon Dump plugin.

Write: load an iCopy-X dump into a Chameleon Ultra slot.
Read:  save a Chameleon Ultra slot back out as an iCopy-X dump.

The Chameleon Ultra is expected on the iCopy-X USB host port (appears as
``/dev/ttyACM*`` or ``/dev/ttyUSB*``).  It identifies it with a
``GET_APP_VERSION`` (1000) handshake, writes the dump, enables the slot and
reads it back for verification.

Supported dump families (iCopy-X filename convention, or read from the
dump contents when the file has been renamed on the device):
    mf1     M1-<1K|4K|Plus-2K|Mini>-<4B|7B>_<uid>_<n>.bin  -> MIFARE Classic
    mfu     NTAG213|NTAG215|NTAG216_<uid>_<n>.bin          -> NTAG / MF0
    em410x  EM410x-ID_<id>_<n>.txt                         -> EM410x (LF)

Slots are 0..7 on the wire; the UI shows them as "Slot 1".."Slot 8".
The slot is left as a standard card (no gen1a/use-block0).

Reading enumerates the slots with ``GET_SLOT_INFO`` (1019) and saves the
emulator memory through ``dump_writer`` (see that module for the file
layout).
"""

import glob
import json
import os
import re
import struct
import time

SOF = 0x11
LRC1 = 0xEF
MAX_DATA = 512

CMD_GET_APP_VERSION = 1000
CMD_SET_ACTIVE_SLOT = 1003
CMD_SET_SLOT_TAG_TYPE = 1004
CMD_SET_SLOT_DATA_DEFAULT = 1005
CMD_SET_SLOT_ENABLE = 1006
CMD_SLOT_DATA_CONFIG_SAVE = 1009
CMD_GET_ACTIVE_SLOT = 1018
CMD_GET_SLOT_INFO = 1019
CMD_GET_ENABLED_SLOTS = 1023
CMD_MF1_WRITE_EMU_BLOCK_DATA = 4000
CMD_HF14A_SET_ANTI_COLL_DATA = 4001
CMD_MF1_READ_EMU_BLOCK_DATA = 4008
CMD_HF14A_GET_ANTI_COLL_DATA = 4018
CMD_MF0_NTAG_READ_EMU_PAGE_DATA = 4021
CMD_MF0_NTAG_WRITE_EMU_PAGE_DATA = 4022
CMD_MF0_NTAG_GET_VERSION_DATA = 4023
CMD_MF0_NTAG_SET_VERSION_DATA = 4024
CMD_MF0_NTAG_GET_SIGNATURE_DATA = 4025
CMD_MF0_NTAG_SET_SIGNATURE_DATA = 4026
CMD_MF0_NTAG_GET_PAGE_COUNT = 4030
CMD_EM410X_SET_EMU_ID = 5000
CMD_EM410X_GET_EMU_ID = 5001

CMD_NAMES = {
    1000: "GET_APP_VERSION",
    1003: "SET_ACTIVE_SLOT",
    1004: "SET_SLOT_TAG_TYPE",
    1005: "SET_SLOT_DATA_DEFAULT",
    1006: "SET_SLOT_ENABLE",
    1009: "SLOT_DATA_CONFIG_SAVE",
    1018: "GET_ACTIVE_SLOT",
    1019: "GET_SLOT_INFO",
    1023: "GET_ENABLED_SLOTS",
    4000: "MF1_WRITE_EMU_BLOCK_DATA",
    4001: "HF14A_SET_ANTI_COLL_DATA",
    4008: "MF1_READ_EMU_BLOCK_DATA",
    4018: "HF14A_GET_ANTI_COLL_DATA",
    4021: "MF0_NTAG_READ_EMU_PAGE_DATA",
    4022: "MF0_NTAG_WRITE_EMU_PAGE_DATA",
    4023: "MF0_NTAG_GET_VERSION_DATA",
    4024: "MF0_NTAG_SET_VERSION_DATA",
    4025: "MF0_NTAG_GET_SIGNATURE_DATA",
    4026: "MF0_NTAG_SET_SIGNATURE_DATA",
    4030: "MF0_NTAG_GET_PAGE_COUNT",
    5000: "EM410X_SET_EMU_ID",
    5001: "EM410X_GET_EMU_ID",
}

STATUS_NAMES = {
    0x00: "HF_TAG_OK",
    0x01: "HF_TAG_NO",
    0x02: "HF_ERR_STAT",
    0x03: "HF_ERR_CRC",
    0x04: "HF_COLLISION",
    0x06: "MF_ERR_AUTH",
    0x07: "HF_ERR_PARITY",
    0x08: "HF_ERR_ATS",
    0x40: "LF_TAG_OK",
    0x60: "PAR_ERR",
    0x66: "DEVICE_MODE_ERROR",
    0x67: "INVALID_CMD",
    0x68: "SUCCESS",
    0x69: "NOT_IMPLEMENTED",
    0x70: "FLASH_WRITE_FAIL",
    0x71: "FLASH_READ_FAIL",
    0x72: "INVALID_SLOT_TYPE",
}

OK_STATUS = (0x00, 0x40, 0x68)

TAG_SENSE_LF = 1
TAG_SENSE_HF = 2
TAG_TYPE_EM410X = 100

BLOCK_SIZE = 16
WRITE_CHUNK_BLOCKS = 31
READ_CHUNK_BLOCKS = 32
PAGE_SIZE = 4
PAGE_CHUNK = 127

# mf1: name -> (tag_specific_type_t, display name, block count)
MFC_CAP = {
    "1k": (1001, "MIFARE Classic 1K", 64),
    "4k": (1003, "MIFARE Classic 4K", 256),
    "plus-2k": (1002, "MIFARE Classic 2K", 128),
    "mini": (1000, "MIFARE Mini", 20),
}
MFC_NAME_RE = re.compile(
    r"^M1-(1K|4K|Plus-2K|Mini)-(4B|7B)_[0-9A-Fa-f]+_\d+$", re.IGNORECASE)

# mfu: name -> (tag_specific_type_t, display name, page count, GET_VERSION bytes)
NTAG_VERSION = {
    1100: "0004040201 000F03".replace(" ", ""),
    1101: "0004040201 001103".replace(" ", ""),
    1102: "0004040201 001303".replace(" ", ""),
}
NTAG_TYPES = {
    "NTAG213": (1100, "NTAG213", 45),
    "NTAG215": (1101, "NTAG215", 135),
    "NTAG216": (1102, "NTAG216", 231),
}
MFU_NAME_RE = re.compile(
    r"^(NTAG213|NTAG215|NTAG216)_[0-9A-Fa-f]+_\d+$", re.IGNORECASE)

EM410X_NAME_RE = re.compile(
    r"^EM410x-ID_([0-9A-Fa-f]+)_\d+$", re.IGNORECASE)

# Content fallbacks for dumps renamed on the device.  The family comes from
# the dump sub-directory, the rest from the files themselves: MIFARE Classic
# size from the .bin length + UID from block 0, NTAG from the page count,
# EM410x from the saved .txt.
_MF1_SIZE_BY_BYTES = {320: "mini", 1024: "1k", 2048: "plus-2k", 4096: "4k"}
_MFU_PAGES_BY_TYPE = {45: "NTAG213", 135: "NTAG215", 231: "NTAG216"}
_FAMILY_DIRS = ("mf1", "mfu", "em410x")

# Read-side maps: tag_specific_type_t (1019 GET_SLOT_INFO) -> capability.
# Only the families the built-in dump/write path understands are listed;
# everything else (HID, UL-C, EV1, SEOS, ...) is skipped by the reader.
MFC_READ_BLOCKS = {
    1000: ("Mini", 20),
    1001: ("1K", 64),
    1002: ("Plus-2K", 128),
    1003: ("4K", 256),
}
NTAG_READ = {
    1100: ("NTAG213", 45),
    1101: ("NTAG215", 135),
    1102: ("NTAG216", 231),
}
TAG_TYPE_EM410X_LF = 100

BAUD = 115200
CMD_TIMEOUT = 2.0

# Canonical iCopy-X dump directories (lowercase; the user partition may be
# mounted case-insensitively, so do not add case variants here).
DUMP_DIRS = (
    "/mnt/upan/dump/mf1",
    "/mnt/upan/dump/mfu",
    "/mnt/upan/dump/em410x",
)


class UltraError(Exception):
    pass


class UltraCommandError(UltraError):
    def __init__(self, cmd, status, tx, rx, step=""):
        self.cmd = cmd
        self.status = status
        self.tx = tx
        self.rx = rx
        self.step = step
        where = " while '%s'" % step if step else ""
        super(UltraCommandError, self).__init__(
            "command %d (%s)%s failed: %s (0x%04X)\n  TX %s\n  RX %s" % (
                cmd, CMD_NAMES.get(cmd, "UNKNOWN"), where,
                STATUS_NAMES.get(status, "?"), status,
                tx.hex(" ").upper(), rx.hex(" ").upper()))


def _lrc(data):
    return (-sum(data)) & 0xFF


def _build_frame(cmd, data=b"", status=0):
    data = bytes(data)
    if len(data) > MAX_DATA:
        raise UltraError("payload too long: %d > %d" % (len(data), MAX_DATA))
    body = struct.pack(">HHH", cmd, status, len(data))
    return bytes([SOF, LRC1]) + body + bytes([_lrc(body)]) + data + bytes([_lrc(data)])


def _parse_frame(buf):
    """Return (frame, skip). frame = (cmd, status, data, raw) or None."""
    buf = bytes(buf)
    i = 0
    n = len(buf)
    while i + 10 <= n:
        if buf[i] != SOF or buf[i + 1] != LRC1:
            i += 1
            continue
        cmd, status, length = struct.unpack_from(">HHH", buf, i + 2)
        if length > MAX_DATA:
            i += 1
            continue
        end = i + 10 + length
        if n < end:
            return None, i
        if buf[i + 8] != _lrc(buf[i + 2:i + 8]):
            i += 1
            continue
        data = buf[i + 9:i + 9 + length]
        if buf[i + 9 + length] != _lrc(data):
            i += 1
            continue
        return (cmd, status, data, bytes(buf[i:end])), i
    return None, i


class _SerialTransport:
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
        return self.ser.read(MAX_DATA + 10)

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


def _open_transport(port, baud=BAUD):
    return _SerialTransport(port, baud)


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


class _Ultra(object):
    def __init__(self, transport):
        self.t = transport

    def send(self, cmd, data=b"", timeout=CMD_TIMEOUT, step=""):
        self.t.reset_input()
        tx = _build_frame(cmd, data)
        self.t.write(tx)

        buf = bytearray()
        deadline = time.time() + timeout
        frame = None
        while True:
            frame, skip = _parse_frame(buf)
            if frame is not None:
                break
            if skip:
                del buf[:skip]
            remaining = deadline - time.time()
            if remaining <= 0:
                where = " while '%s'" % step if step else ""
                raise UltraError(
                    "command %d (%s)%s timed out\n  TX %s\n  RX(partial) %s" % (
                        cmd, CMD_NAMES.get(cmd, "UNKNOWN"), where,
                        tx.hex(" ").upper(), bytes(buf).hex(" ").upper()))
            buf += self.t.read_some(min(remaining, 0.1))

        rcmd, status, rdata, raw = frame
        if rcmd != cmd:
            raise UltraError("response for %d but got %d" % (cmd, rcmd))
        if status not in OK_STATUS:
            raise UltraCommandError(cmd, status, tx, raw, step)
        return rdata

    def close(self):
        self.t.close()


def _find_ultra(attempts=3, delay=0.4):
    last = "no serial device found"
    for _ in range(max(1, attempts)):
        for dev in _candidate_ports():
            transport = None
            try:
                transport = _open_transport(dev)
                ultra = _Ultra(transport)
                resp = ultra.send(CMD_GET_APP_VERSION, b"", timeout=1.0, step="handshake")
                if len(resp) >= 2:
                    version = (resp[0], resp[1])
                    transport = None
                    return ultra, dev, version
                last = "%s: short version response" % dev
            except Exception as exc:
                last = "%s: %s" % (dev, exc)
            finally:
                if transport is not None:
                    try:
                        transport.close()
                    except Exception:
                        pass
        time.sleep(delay)
    raise UltraError(last)


def _dump_dirs():
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


# ---------------------------------------------------------------------------
# Dump detection / parsing (iCopy-X filename convention, with a content
# fallback for dumps renamed on the device)
# ---------------------------------------------------------------------------

def _family_of(path):
    """Dump family from the folder name (``mf1``/``mfu``/``em410x``) or ''."""
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


def _detect_mf1_content(path):
    if os.path.splitext(path)[1].lower() != ".bin":
        return None
    variant = _MF1_SIZE_BY_BYTES.get(len(_read_bin(path) or b""))
    entry = MFC_CAP.get(variant) if variant else None
    if entry is None:
        return None
    tag_type, type_name, blocks = entry
    uidlen = 4
    uid_hex = (_json_card(path).get("UID") or "").strip()
    if _is_hex(uid_hex) and len(uid_hex) == 14:
        uidlen = 7
    elif _is_hex(uid_hex) and len(uid_hex) == 8:
        uidlen = 4
    else:
        found = _mf1_uid_from_block0(_read_bin(path))
        if found is not None:
            uidlen = found[1]
    return {"kind": "mf1", "tag_type": tag_type, "type_name": type_name,
            "blocks": blocks, "uidlen": uidlen}


def _detect_mfu_content(path):
    try:
        pages, _version, _signature = _parse_mfu(path)
    except (OSError, UltraError, ValueError):
        return None
    tag = _MFU_PAGES_BY_TYPE.get(len(pages) // 4)
    entry = NTAG_TYPES.get(tag) if tag else None
    if entry is None:
        return None
    tag_type, type_name, _pages = entry
    return {"kind": "mfu", "tag_type": tag_type, "type_name": type_name}


def _detect_em410x_content(path):
    id_bytes = _parse_em410x_id(path)
    if id_bytes is None:
        return None
    return {"kind": "em410x", "tag_type": TAG_TYPE_EM410X,
            "type_name": "EM410x", "id": id_bytes}


def _detect_dump(path, family=None):
    name = os.path.splitext(os.path.basename(path))[0]

    match = MFC_NAME_RE.match(name)
    if match:
        info = MFC_CAP.get(match.group(1).lower())
        if info:
            tag_type, type_name, blocks = info
            uidlen = 7 if match.group(2).upper() == "7B" else 4
            return {"kind": "mf1", "tag_type": tag_type, "type_name": type_name,
                    "blocks": blocks, "uidlen": uidlen}

    match = MFU_NAME_RE.match(name)
    if match:
        entry = NTAG_TYPES.get(match.group(1).upper())
        if entry:
            tag_type, type_name, _pages = entry
            return {"kind": "mfu", "tag_type": tag_type, "type_name": type_name}

    match = EM410X_NAME_RE.match(name)
    if match:
        return {"kind": "em410x", "tag_type": TAG_TYPE_EM410X,
                "type_name": "EM410x", "id": bytes.fromhex(match.group(1).upper())}

    # Renamed dump: the filename no longer identifies it, so use the family
    # folder and the file contents (mirrors the device's own Tag Info).
    family = (family or "").lower() or _family_of(path)
    if family == "mf1":
        return _detect_mf1_content(path)
    if family == "mfu":
        return _detect_mfu_content(path)
    if family == "em410x":
        return _detect_em410x_content(path)
    # No family hint (custom dump dir): sniff by extension / length.
    if os.path.splitext(path)[1].lower() == ".txt":
        return _detect_em410x_content(path)
    return _detect_mf1_content(path) or _detect_mfu_content(path)


def _parse_em410x_id(path):
    try:
        with open(path, "r", errors="ignore") as fh:
            text = fh.read()
    except OSError:
        text = ""
    for line in text.replace("\r", "").split("\n"):
        token = line.strip().replace(" ", "")
        if "=" in token:
            token = token.split("=", 1)[1]
        if re.fullmatch(r"[0-9A-Fa-f]{10}", token or ""):
            return bytes.fromhex(token.upper())
    return None


def _parse_mfu(path):
    """Return (pages, version, signature) from a PM3 mfu dump.

    The .json sibling is authoritative.  The .bin layout is
    version(8) + 4 + signature(32) + counters(12) + pages, so it is only
    a fallback if the .json is missing.
    """
    pages = None
    version = None
    signature = None
    json_path = os.path.splitext(path)[0] + ".json"
    if os.path.isfile(json_path):
        try:
            with open(json_path, "r", errors="ignore") as fh:
                doc = json.load(fh)
            card = doc.get("Card", {}) or {}
            blocks = doc.get("blocks", {}) or {}
            buf = bytearray()
            i = 0
            while str(i) in blocks and blocks[str(i)]:
                buf += bytes.fromhex(blocks[str(i)])
                i += 1
            if buf:
                pages = bytes(buf)
            if card.get("Version"):
                version = bytes.fromhex(card["Version"])
            if card.get("Signature"):
                signature = bytes.fromhex(card["Signature"])
        except (ValueError, TypeError, OSError):
            pages = None
    if pages is None:
        with open(path, "rb") as fh:
            raw = fh.read()
        if len(raw) < 60:
            raise UltraError("%s: mfu dump too short (%d bytes)" % (
                os.path.basename(path), len(raw)))
        version = raw[0:8]
        signature = raw[12:44]
        pages = raw[56:]
    if len(pages) < 8:
        raise UltraError("%s: mfu dump has too few pages" % os.path.basename(path))
    return pages, version, signature


def _read_dump(path, meta):
    """Return (payload, extra). extra carries per-type side data."""
    kind = meta["kind"]
    if kind == "mf1":
        with open(path, "rb") as fh:
            data = fh.read()
        expected = meta["blocks"] * BLOCK_SIZE
        if len(data) != expected:
            raise UltraError("%s: %d bytes but name implies %d" % (
                os.path.basename(path), len(data), expected))
        return data, {}
    if kind == "mfu":
        pages, version, signature = _parse_mfu(path)
        return pages, {"version": version, "signature": signature}
    if kind == "em410x":
        id_bytes = _parse_em410x_id(path)
        if id_bytes is None:
            raise UltraError("%s: no 10-hex EM410x id found" % os.path.basename(path))
        return id_bytes, {}
    raise UltraError("unknown dump kind: %s" % kind)


def _uid_of(data, meta):
    if meta["kind"] == "mf1":
        return data[:meta["uidlen"]]
    if meta["kind"] == "mfu":
        return data[0:3] + data[4:8]
    return data


def _anticoll_from_block0(dump, uidlen=4):
    if uidlen == 7:
        uid, sak, atqa = dump[0:7], dump[8], dump[9:11]
    else:
        uid, sak, atqa = dump[0:4], dump[5], dump[6:8]
    return bytes([uidlen]) + uid + atqa + bytes([sak, 0])


def _anticoll_from_ntag(data):
    uid = data[0:3] + data[4:8]
    return bytes([7]) + uid + bytes([0x44, 0x00]) + bytes([0x00, 0x00])


def _split_anticoll(anti, data):
    """(uid_len, uid_bytes, atqa_hex, sak_hex) from a 4018 response.

    4018 payload is ``uidlen|uid|atqa[2]|sak|atslen|ats``.  Falls back to
    block 0 (4-byte UID) when the slot has no anti-coll data stored.
    """
    if len(anti) >= 1:
        uid_len = anti[0]
        if uid_len in (4, 7) and len(anti) >= 1 + uid_len:
            uid = anti[1:1 + uid_len]
            atqa = anti[1 + uid_len:3 + uid_len]
            sak = anti[3 + uid_len:4 + uid_len]
            return (uid_len, bytes(uid),
                    atqa.hex().upper() if len(atqa) == 2 else None,
                    sak.hex().upper() if sak else None)
    return (4, bytes(data[:4]), None, None)


def _scan_dumps():
    out = []
    seen = set()
    for directory in _dump_dirs():
        try:
            names = sorted(os.listdir(directory))
        except OSError:
            continue
        family = os.path.basename(os.path.normpath(directory)).lower()
        for name in names:
            if not name.lower().endswith((".bin", ".txt")):
                continue
            path = os.path.join(directory, name)
            if path in seen:
                continue
            seen.add(path)
            meta = _detect_dump(path, family)
            if meta is None:
                continue
            try:
                data, _extra = _read_dump(path, meta)
            except (OSError, UltraError, ValueError):
                continue
            uid = _uid_of(data, meta).hex().upper()
            out.append({"path": path, "name": os.path.splitext(name)[0],
                        "uid": uid, "meta": meta})
    return out


# ---------------------------------------------------------------------------
# Plugin
# ---------------------------------------------------------------------------

class UltraBackend(object):
    """Chameleon Ultra backend for the Chameleon Dump plugin."""

    def __init__(self, host=None):
        self.host = host
        self._ultra = None
        self._port = None
        self._version = None
        self._dumps = []
        self._entry = None
        self._slot = 0
        self._read_slots = []
        self._read_entry = None
        self._active_slot = 0

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
        if self._ultra is not None:
            try:
                self._ultra.close()
            except Exception:
                pass
            self._ultra = None

    # -- UI methods ----------------------------------------------------

    def start(self, device=None):
        self._close()
        self._set("error_msg", "")
        self._set("progress_value", 0)
        self._set("progress_message", "")

        # Take ownership of an already-found device first, so every early
        # error return stays closable (on_destroy -> _close).
        if device is not None:
            self._ultra, self._port, self._version = device

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
                    "M1-...   NTAG213/215/216_...\nEM410x-ID_...\n"
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
                self._ultra, self._port, self._version = _find_ultra()
            except Exception as exc:
                self._set("error_msg",
                          self.tr("Chameleon Ultra not found.\n\n%s") % exc)
                return {"status": "error"}

        return {"status": "ready"}

    def choose_dump(self):
        idx = self._selected_index("select_dump")
        if idx < 0 or idx >= len(self._dumps):
            self._set("error_msg", self.tr("Dump selection out of range"))
            return {"status": "error"}
        entry = self._dumps[idx]
        try:
            data, extra = _read_dump(entry["path"], entry["meta"])
        except Exception as exc:
            self._set("error_msg", self.tr("Cannot read dump:\n%s") % exc)
            return {"status": "error"}
        entry["data"] = data
        entry["extra"] = extra
        self._entry = entry
        meta = entry["meta"]
        uidlen = meta.get("uidlen", len(_uid_of(data, meta)))
        self._set("dump_name", entry["name"])
        self._set("dump_uid", entry["uid"])
        self._set("card_type", self.tr("%s, UID %dB") % (meta["type_name"], uidlen))
        return {"status": "ready"}

    def choose_slot(self):
        idx = self._selected_index("select_slot")
        if idx < 0 or idx > 7:
            self._set("error_msg", self.tr("Invalid slot"))
            return {"status": "error"}
        self._slot = idx
        self._set("slot_text", self.tr("Slot %d") % (idx + 1))
        return {"status": "ready"}

    # -- read: Chameleon slot -> iCopy-X dump --------------------------

    def start_read(self, device=None):
        """List the readable slots of the connected Ultra."""
        self._close()
        self._set("error_msg", "")
        self._set("progress_value", 0)
        self._set("progress_message", "")
        self._read_slots = []

        # Take ownership of an already-found device first, so every early
        # error return stays closable (on_destroy -> _close).
        if device is not None:
            self._ultra, self._port, self._version = device

        if _load_card_dump() is None:
            self._set("error_msg", self.tr("Dump writer unavailable."))
            return {"status": "error"}

        if device is None:
            try:
                self._ultra, self._port, self._version = _find_ultra()
            except Exception as exc:
                self._set("error_msg",
                          self.tr("Chameleon Ultra not found.\n\n%s") % exc)
                return {"status": "error"}

        try:
            slots = self._scan_read_slots(self._ultra)
        except Exception as exc:
            self._set("error_msg", self.tr("Cannot read slots:\n%s") % exc)
            return {"status": "error"}

        if not slots:
            self._set(
                "error_msg",
                self.tr(
                    "No readable slot found.\n\nOnly MIFARE Classic, "
                    "NTAG213/215/216 and EM410x slots can be saved as dumps."))
            return {"status": "error"}

        self._read_slots = slots
        labels = [{"label": s["label"], "action": "run:choose_read_slot"}
                  for s in slots]
        self._set_list_items("read_slot", labels)
        return {"status": "ready"}

    def _scan_read_slots(self, ultra):
        info = ultra.send(CMD_GET_SLOT_INFO, b"", timeout=CMD_TIMEOUT,
                          step="1019 slot info")
        try:
            enabled = ultra.send(CMD_GET_ENABLED_SLOTS, b"",
                                 timeout=CMD_TIMEOUT, step="1023 enabled slots")
        except Exception:
            enabled = b""
        slots = []
        for i in range(min(8, len(info) // 4)):
            hf, lf = struct.unpack_from(">HH", info, i * 4)
            entry = self._classify_slot(i, hf, lf)
            if entry is None:
                continue
            if len(enabled) >= (i + 1) * 2:
                entry["enabled"] = bool(enabled[i * 2] or enabled[i * 2 + 1])
            slots.append(entry)
        return slots

    def _classify_slot(self, index, hf, lf):
        base = self.tr("Slot %d") % (index + 1)
        if hf in MFC_READ_BLOCKS:
            name, blocks = MFC_READ_BLOCKS[hf]
            return {"index": index, "family": "mf1", "tag_type": hf,
                    "name": name, "blocks": blocks,
                    "label": "%s  %s" % (base, name)}
        if hf in NTAG_READ:
            name, pages = NTAG_READ[hf]
            return {"index": index, "family": "mfu", "tag_type": hf,
                    "name": name, "pages": pages,
                    "label": "%s  %s" % (base, name)}
        if lf == TAG_TYPE_EM410X_LF:
            return {"index": index, "family": "em410x", "tag_type": lf,
                    "name": "EM410x", "label": "%s  EM410x" % base}
        return None

    def choose_read_slot(self):
        idx = self._selected_index("read_slot")
        if idx < 0 or idx >= len(self._read_slots):
            self._set("error_msg", self.tr("Slot selection out of range"))
            return {"status": "error"}
        entry = self._read_slots[idx]
        self._read_entry = entry
        self._set("read_slot_text", self.tr("Slot %d") % (entry["index"] + 1))
        self._set("read_type", entry["name"])
        return {"status": "ready"}

    def do_read(self):
        try:
            return self._do_read()
        except UltraCommandError as exc:
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
            raise UltraError("dump writer unavailable")

        entry = self._read_entry
        slot = entry["index"]

        ultra = self._ultra
        if ultra is None:
            self._progress(2, self.tr("Connecting"))
            ultra, port, version = _find_ultra()
            self._ultra = ultra
            self._port = port

        def do(cmd, payload, label, pct):
            self._progress(pct, label)
            return ultra.send(cmd, payload, timeout=CMD_TIMEOUT, step=label)

        do(CMD_SET_ACTIVE_SLOT, bytes([slot]), self.tr("1003 set active slot"), 4)
        self._active_slot = slot

        family = entry["family"]
        if family == "mf1":
            path, uid, detail = self._read_mf1(do, entry, card_dump)
        elif family == "mfu":
            path, uid, detail = self._read_mfu(do, entry, card_dump)
        else:
            path, uid, detail = self._read_em410x(do, entry, card_dump)

        self._progress(100, self.tr("Done"))
        self._set("result_title", self.tr("Saved"))
        self._set("result_detail", "\n".join([
            self.tr("%s -> dump") % entry["name"],
            os.path.basename(path),
            detail,
        ]))
        return {"status": "ok"}

    def _read_mf1(self, do, entry, card_dump):
        blocks = entry["blocks"]
        data = bytearray()
        for start in range(0, blocks, READ_CHUNK_BLOCKS):
            count = min(READ_CHUNK_BLOCKS, blocks - start)
            data += do(CMD_MF1_READ_EMU_BLOCK_DATA, bytes([start, count]),
                       self.tr("4008 read blocks %d-%d") % (
                           start, start + count - 1),
                       6 + int(80 * start / blocks))
        data = bytes(data)
        anti = do(CMD_HF14A_GET_ANTI_COLL_DATA, b"",
                  self.tr("4018 read anti-coll"), 90)
        uid_len, uid, atqa, sak = _split_anticoll(anti, data)
        uid = uid.hex().upper()
        path = card_dump.save_mf1(self._save_dir("mf1"), blocks, uid_len, uid,
                                  data, atqa=atqa, sak=sak)
        return path, uid, self.tr("UID %s, %dB, %d blocks") % (
            uid, uid_len, blocks)

    def _read_mfu(self, do, entry, card_dump):
        cap = entry["pages"]
        pages = cap
        try:
            resp = do(CMD_MF0_NTAG_GET_PAGE_COUNT, b"",
                      self.tr("4030 page count"), 6)
            avail = resp[0] if resp else 0
            if avail:
                pages = min(cap, avail)
        except UltraError:
            pages = cap

        buf = bytearray()
        for start in range(0, pages, PAGE_CHUNK):
            count = min(PAGE_CHUNK, pages - start)
            buf += do(CMD_MF0_NTAG_READ_EMU_PAGE_DATA, bytes([start, count]),
                      self.tr("4021 read pages %d-%d") % (
                          start, start + count - 1),
                      10 + int(70 * start / pages))
        page_data = bytes(buf)

        version = signature = None
        try:
            version = do(CMD_MF0_NTAG_GET_VERSION_DATA, b"",
                         self.tr("4023 get version"), 88)
        except UltraError:
            version = None
        try:
            signature = do(CMD_MF0_NTAG_GET_SIGNATURE_DATA, b"",
                           self.tr("4025 get signature"), 92)
        except UltraError:
            signature = None

        uid = card_dump.mfu_uid(page_data).hex().upper()
        path = card_dump.save_mfu(self._save_dir("mfu"), entry["name"], uid,
                                  page_data, version=version,
                                  signature=signature)
        return path, uid, self.tr("UID %s, %d pages") % (uid, pages)

    def _read_em410x(self, do, entry, card_dump):
        resp = do(CMD_EM410X_GET_EMU_ID, b"", self.tr("5001 read EM410x id"), 60)
        id_bytes = resp[2:7]
        if len(id_bytes) != 5:
            raise UltraError("5001 returned %d bytes, expected 5" % len(id_bytes))
        uid = id_bytes.hex().upper()
        path = card_dump.save_em410x(self._save_dir("em410x"), uid)
        return path, uid, self.tr("ID %s") % uid

    def _save_dir(self, family):
        override = os.environ.get("ULTRA_WRITER_DUMP_DIR")
        if override:
            return override
        card_dump = _load_card_dump()
        return card_dump.default_dir(family)

    def do_write(self):
        try:
            return self._do_write()
        except UltraCommandError as exc:
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
        extra = entry.get("extra", {})
        slot = self._slot
        kind = meta["kind"]

        ultra = self._ultra
        if ultra is None:
            self._progress(2, self.tr("Connecting"))
            ultra, port, version = _find_ultra()
            self._ultra = ultra
            self._port = port

        def do(cmd, payload, label, pct):
            self._progress(pct, label)
            return ultra.send(cmd, payload, timeout=CMD_TIMEOUT, step=label)

        do(CMD_SET_ACTIVE_SLOT, bytes([slot]), self.tr("1003 set active slot"), 4)
        do(CMD_SET_SLOT_TAG_TYPE, struct.pack(">BH", slot, meta["tag_type"]),
           self.tr("1004 set tag type"), 8)
        do(CMD_SET_SLOT_DATA_DEFAULT, struct.pack(">BH", slot, meta["tag_type"]),
           self.tr("1005 init slot"), 12)

        if kind == "mfu":
            # Ask the emulator how many pages this tag type has and only write
            # what both the dump and the slot can hold.
            resp = do(CMD_MF0_NTAG_GET_PAGE_COUNT, b"", self.tr("4030 page count"), 14)
            avail = resp[0] if resp else 0
            pages = len(data) // PAGE_SIZE
            if avail:
                pages = min(pages, avail)
            meta = dict(meta)
            meta["pages"] = pages

        if kind == "mf1":
            lines, sense = self._write_mf1(do, data, meta, slot)
        elif kind == "mfu":
            lines, sense = self._write_mfu(do, data, meta, slot, extra)
        else:
            lines, sense = self._write_em410x(do, data, meta, slot)

        do(CMD_SET_SLOT_ENABLE, bytes([slot, sense, 1]), self.tr("1006 enable slot"), 90)
        do(CMD_SLOT_DATA_CONFIG_SAVE, b"", self.tr("1009 store to flash"), 94)
        time.sleep(0.2)

        detail = self._verify(do, data, meta, slotsense=sense)
        self._progress(100, self.tr("Done"))

        self._set("result_title", self.tr("Success"))
        self._set("result_detail", "\n".join(
            [self.tr("%s -> Ultra Slot %d.") % (meta["type_name"], slot + 1)] + lines + detail))
        return {"status": "ok"}

    def _write_mf1(self, do, data, meta, slot):
        blocks = meta["blocks"]
        written = 0
        for start in range(0, blocks, WRITE_CHUNK_BLOCKS):
            count = min(WRITE_CHUNK_BLOCKS, blocks - start)
            chunk = data[start * BLOCK_SIZE:(start + count) * BLOCK_SIZE]
            pct = 16 + int(58 * written / blocks)
            do(CMD_MF1_WRITE_EMU_BLOCK_DATA, bytes([start]) + chunk,
               self.tr("4000 write blocks %d-%d") % (start, start + count - 1), pct)
            written += count
        # use-block0 off -> UID/SAK/ATQA come from res_coll, set here from block0
        do(CMD_HF14A_SET_ANTI_COLL_DATA, _anticoll_from_block0(data, meta["uidlen"]),
           self.tr("4001 set anti-coll data"), 82)
        return [], TAG_SENSE_HF

    def _write_mfu(self, do, data, meta, slot, extra):
        pages = meta["pages"]
        do(CMD_HF14A_SET_ANTI_COLL_DATA, _anticoll_from_ntag(data),
           self.tr("4001 set anti-coll data"), 20)
        version = extra.get("version") or bytes.fromhex(NTAG_VERSION[meta["tag_type"]])
        do(CMD_MF0_NTAG_SET_VERSION_DATA, version, self.tr("4024 set version"), 24)
        signature = extra.get("signature") or b""
        if len(signature) == 32:
            do(CMD_MF0_NTAG_SET_SIGNATURE_DATA, signature, self.tr("4026 set signature"), 28)
        p = 0
        for start in range(0, pages, PAGE_CHUNK):
            count = min(PAGE_CHUNK, pages - start)
            chunk = data[start * PAGE_SIZE:(start + count) * PAGE_SIZE]
            pct = 30 + int(48 * start / pages)
            do(CMD_MF0_NTAG_WRITE_EMU_PAGE_DATA, bytes([start, count]) + chunk,
               self.tr("4022 write pages %d-%d") % (start, start + count - 1), pct)
            p += count
        return [], TAG_SENSE_HF

    def _write_em410x(self, do, data, meta, slot):
        do(CMD_EM410X_SET_EMU_ID, data, self.tr("5000 set EM410x id"), 60)
        return [], TAG_SENSE_LF

    def _verify(self, do, data, meta, slotsense):
        kind = meta["kind"]
        if kind == "mf1":
            return self._verify_mf1(do, data, meta)
        if kind == "mfu":
            return self._verify_mfu(do, data, meta)
        return self._verify_em410x(do, data)

    def _verify_mf1(self, do, data, meta):
        blocks = meta["blocks"]
        readback = bytearray()
        for start in range(0, blocks, READ_CHUNK_BLOCKS):
            count = min(READ_CHUNK_BLOCKS, blocks - start)
            readback += do(CMD_MF1_READ_EMU_BLOCK_DATA, bytes([start, count]),
                           self.tr("4008 read blocks %d-%d") % (start, start + count - 1), 96)
        readback = bytes(readback)
        if len(readback) != len(data):
            raise UltraError("4008 returned %d bytes, expected %d" % (
                len(readback), len(data)))
        if readback != data:
            first = next(i for i in range(len(data)) if readback[i] != data[i])
            raise UltraError("4008 mismatch at block %d byte %d: %02X vs %02X" % (
                first // BLOCK_SIZE, first % BLOCK_SIZE, data[first], readback[first]))
        expected = _anticoll_from_block0(data, meta["uidlen"])
        anticoll = do(CMD_HF14A_GET_ANTI_COLL_DATA, b"", self.tr("4018 read anti-coll"), 98)
        if anticoll != expected:
            raise UltraError("4018 mismatch: %s vs %s" % (
                anticoll.hex(" ").upper(), expected.hex(" ").upper()))
        return [self.tr("4008: %d B identical.") % len(data),
                "4018: %s" % anticoll.hex(" ").upper()]

    def _verify_mfu(self, do, data, meta):
        pages = meta["pages"]
        readback = bytearray()
        for start in range(0, pages, PAGE_CHUNK):
            count = min(PAGE_CHUNK, pages - start)
            readback += do(CMD_MF0_NTAG_READ_EMU_PAGE_DATA, bytes([start, count]),
                           self.tr("4021 read pages %d-%d") % (start, start + count - 1), 96)
        readback = bytes(readback)
        if len(readback) != len(data):
            raise UltraError("4021 returned %d bytes, expected %d" % (
                len(readback), len(data)))
        if readback != data:
            first = next(i for i in range(len(data)) if readback[i] != data[i])
            raise UltraError("4021 mismatch at page %d: %02X vs %02X" % (
                first // PAGE_SIZE, data[first], readback[first]))
        expected = _anticoll_from_ntag(data)
        anticoll = do(CMD_HF14A_GET_ANTI_COLL_DATA, b"", self.tr("4018 read anti-coll"), 98)
        if anticoll != expected:
            raise UltraError("4018 mismatch: %s vs %s" % (
                anticoll.hex(" ").upper(), expected.hex(" ").upper()))
        return [self.tr("4021: %d pages identical.") % pages,
                "4018: %s" % anticoll.hex(" ").upper()]

    def _verify_em410x(self, do, data):
        resp = do(CMD_EM410X_GET_EMU_ID, b"", self.tr("5001 read EM410x id"), 96)
        got = resp[2:2 + len(data)]
        if got != data:
            raise UltraError("5001 mismatch: %s vs %s" % (
                got.hex(" ").upper(), data.hex(" ").upper()))
        return [self.tr("5001: id %s.") % data.hex().upper()]
