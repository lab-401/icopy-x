"""Chameleon Dump plugin: auto-detect backend, read a slot out as a dump."""

import importlib.util
import json
import os
import struct

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load_dispatcher():
    path = os.path.join(REPO, 'plugins', 'chameleon_dump', 'plugin.py')
    spec = importlib.util.spec_from_file_location('chameleon_dump_test', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cd = _load_dispatcher()
ux = cd._ultra
tx = cd._tiny


def _no_device(*a, **k):
    raise RuntimeError('no device')


class FakeHost(object):
    def __init__(self):
        self._screens = {
            'read_slot': {'screen': {'content': {'type': 'list', 'items': []}}},
        }
        self._list_state = {}
        self.vars = {}
        self.progress = []

    def set_var(self, key, value):
        self.vars[key] = value

    def get_var(self, key, default=None):
        return self.vars.get(key, default)

    def set_progress(self, value, message=None):
        self.progress.append((value, message))
        self.vars['progress_value'] = value
        self.vars['progress_message'] = message

    def tr(self, text):
        return text


def _items(host):
    return [i['label'] for i in
            host._screens['read_slot']['screen']['content']['items']]


# ======================================================================
# Ultra
# ======================================================================

def _mfc_slot(uid_hex, hf, blocks, enabled=True):
    data = bytearray(blocks * 16)
    data[0:len(uid_hex) // 2] = bytes.fromhex(uid_hex)
    anti = (bytes([len(uid_hex) // 2]) + bytes.fromhex(uid_hex) +
            bytes.fromhex('0400') + bytes([0x08, 0x00]))
    return {'hf': hf, 'lf': 0, 'mem': bytes(data), 'anticoll': anti,
            'enabled': enabled}


def _ntag_slot(hf, uid_hex):
    pages = bytearray(45 * 4)
    raw = bytes.fromhex(uid_hex)
    pages[0:3] = raw[0:3]
    pages[3] = 0x95
    pages[4:8] = raw[3:7]
    return {'hf': hf, 'lf': 0, 'pages': bytes(pages),
            'version': bytes.fromhex('0004040201000F03'),
            'signature': bytes.fromhex('CC' * 32), 'enabled': True}


class FakeUltra(object):
    def __init__(self, slots):
        self.slots = slots
        self.active = 0
        self.closed = False

    def send(self, cmd, data=b'', timeout=None, step=''):
        if cmd == 1019:
            out = bytearray()
            for s in self.slots:
                out += struct.pack('>HH', s.get('hf', 0), s.get('lf', 0))
            return bytes(out)
        if cmd == 1023:
            out = bytearray()
            for s in self.slots:
                out += bytes([1 if s.get('enabled') else 0, 0])
            return bytes(out)
        if cmd == 1003:
            self.active = data[0]
            return b''
        s = self.slots[self.active]
        if cmd == 4008:
            start, count = data[0], data[1]
            return s['mem'][start * 16:(start + count) * 16]
        if cmd == 4018:
            return s.get('anticoll', b'')
        if cmd == 4030:
            return bytes([len(s.get('pages', b'')) // 4])
        if cmd == 4021:
            start, count = data[0], data[1]
            return s['pages'][start * 4:(start + count) * 4]
        if cmd == 4023:
            return s.get('version', b'')
        if cmd == 4025:
            return s.get('signature', b'')
        if cmd == 5001:
            return b'\x00\x64' + s.get('em410x', b'')
        return b''

    def close(self):
        self.closed = True


def _ultra(monkeypatch, tmp_path, slots):
    ultra = FakeUltra(slots)
    monkeypatch.setattr(ux, '_find_ultra',
                        lambda *a, **k: (ultra, 'MOCK', (2, 2)))
    monkeypatch.setattr(tx, '_find_tiny', _no_device)
    monkeypatch.setenv('ULTRA_WRITER_DUMP_DIR', str(tmp_path))
    monkeypatch.setenv('TINY_WRITER_DUMP_DIR', str(tmp_path))
    host = FakeHost()
    return cd.ChameleonDumpPlugin(host), host, ultra


def test_ultra_read_mfc_4b(monkeypatch, tmp_path):
    slots = [_mfc_slot('DAEFB416', 1001, 64)] + [{} for _ in range(7)]
    plugin, host, _ = _ultra(monkeypatch, tmp_path, slots)

    assert plugin.start_read()['status'] == 'ready'
    assert _items(host) == ['Slot 1  1K']

    host._list_state['read_slot'] = {'selected': 0}
    assert plugin.choose_read_slot()['status'] == 'ready'
    assert host.vars['read_type'] == '1K'

    assert plugin.do_read()['status'] == 'ok'
    path = tmp_path / 'M1-1K-4B_DAEFB416_1.bin'
    assert path.exists()
    assert path.stat().st_size == 1024
    doc = json.loads((tmp_path / 'M1-1K-4B_DAEFB416_1.json').read_text())
    assert doc['blocks']['0'].startswith('DAEFB416')


def test_ultra_read_mfc_7b_uses_anticoll_uid(monkeypatch, tmp_path):
    slot = _mfc_slot('AABBCCDDEEFF00', 1003, 256)
    plugin, host, _ = _ultra(monkeypatch, tmp_path, [slot] + [{}] * 7)
    plugin.start_read()
    host._list_state['read_slot'] = {'selected': 0}
    plugin.choose_read_slot()
    assert plugin.do_read()['status'] == 'ok'
    assert (tmp_path / 'M1-4K-7B_AABBCCDDEEFF00_1.bin').exists()


def test_ultra_read_ntag(monkeypatch, tmp_path):
    slots = [{}] + [_ntag_slot(1100, '1D32320E950000')] + [{} for _ in range(6)]
    plugin, host, _ = _ultra(monkeypatch, tmp_path, slots)
    plugin.start_read()
    assert _items(host) == ['Slot 2  NTAG213']
    host._list_state['read_slot'] = {'selected': 0}
    plugin.choose_read_slot()
    assert plugin.do_read()['status'] == 'ok'
    path = tmp_path / 'NTAG213_1D32320E950000_1.bin'
    assert path.exists()
    blob = path.read_bytes()
    assert len(blob) == 236
    assert blob[56:60] == bytes.fromhex('1D323295')
    doc = json.loads((tmp_path / 'NTAG213_1D32320E950000_1.json').read_text())
    assert doc['Card']['Version'] == '0004040201000F03'


def test_ultra_read_em410x(monkeypatch, tmp_path):
    slots = [{'hf': 0, 'lf': 100, 'em410x': bytes.fromhex('0000BC614E')}]
    slots += [{} for _ in range(7)]
    plugin, host, _ = _ultra(monkeypatch, tmp_path, slots)
    plugin.start_read()
    assert _items(host) == ['Slot 1  EM410x']
    host._list_state['read_slot'] = {'selected': 0}
    plugin.choose_read_slot()
    assert plugin.do_read()['status'] == 'ok'
    text = (tmp_path / 'EM410x-ID_0000BC614E_1.txt').read_text()
    assert text == '0000BC614E\n0000BC614E\n'


def test_ultra_read_skips_unsupported_and_empty(monkeypatch, tmp_path):
    slots = [{'hf': 1103}, {'hf': 999}, {}, _mfc_slot('0AD828D2', 1001, 64)]
    slots += [{} for _ in range(4)]
    plugin, host, _ = _ultra(monkeypatch, tmp_path, slots)
    assert plugin.start_read()['status'] == 'ready'
    assert _items(host) == ['Slot 4  1K']


def test_ultra_read_no_slots_is_error(monkeypatch, tmp_path):
    plugin, host, ultra = _ultra(monkeypatch, tmp_path, [{} for _ in range(8)])
    assert plugin.start_read()['status'] == 'error'
    assert 'No readable slot' in host.vars['error_msg']
    assert ultra.closed  # detection-opened port must not leak


# ======================================================================
# Tiny
# ======================================================================

class FakeTiny(object):
    def __init__(self, slots):
        self.slots = slots          # {1..8: {'config':..., 'mem': bytes}}
        self.active = 1
        self.closed = False

    def expect_ok(self, text, step='', timeout=None):
        if text.startswith('SETTING='):
            self.active = int(text.split('=', 1)[1])
            return
        if text in ('CLEAR', 'STORE'):
            return
        raise tx.TinyCommandError(text, 201, 'INVALID COMMAND USAGE', step)

    def command(self, text, timeout=None, step=''):
        if text == 'CONFIG?':
            return (101, 'OK WITH TEXT', self.slots[self.active]['config'])
        raise tx.TinyCommandError(text, 200, 'UNKNOWN COMMAND', step)

    def value(self, text, timeout=None):
        if text == 'UID?':
            return self.slots[self.active]['mem'][0:4].hex().upper()
        if text == 'SETTING?':
            return str(self.active)
        return None

    def download(self):
        return bytes(self.slots[self.active]['mem'])

    def close(self):
        self.closed = True


def _tiny(monkeypatch, tmp_path, slots):
    tiny = FakeTiny(slots)
    monkeypatch.setattr(ux, '_find_ultra', _no_device)
    monkeypatch.setattr(tx, '_find_tiny',
                        lambda *a, **k: (tiny, 'MOCK', 'mock'))
    monkeypatch.setenv('ULTRA_WRITER_DUMP_DIR', str(tmp_path))
    monkeypatch.setenv('TINY_WRITER_DUMP_DIR', str(tmp_path))
    host = FakeHost()
    return cd.ChameleonDumpPlugin(host), host, tiny


def _tiny_slots():
    mfc = bytearray(1024)
    mfc[0:4] = bytes.fromhex('0AD828D2')
    ntag = bytearray(180)
    ntag[0:3] = bytes.fromhex('1D3232')
    ntag[4:8] = bytes.fromhex('0E950000')
    slots = {n: {'config': 'NONE', 'mem': b''} for n in range(1, 9)}
    slots[1] = {'config': 'MF_CLASSIC_1K', 'mem': bytes(mfc)}
    # Slot 2 mimics a never-written slot (UID all zero) and slot 3 the
    # factory-erased value (UID all F) -- both report the default config.
    slots[2] = {'config': 'MF_CLASSIC_1K', 'mem': bytes(1024)}
    slots[3] = {'config': 'MF_CLASSIC_1K', 'mem': b'\xff' * 1024}
    slots[8] = {'config': 'NTAG213', 'mem': bytes(ntag)}
    return slots


def test_tiny_read_lists_supported_slots(monkeypatch, tmp_path):
    plugin, host, _ = _tiny(monkeypatch, tmp_path, _tiny_slots())
    assert plugin.start_read()['status'] == 'ready'
    assert _items(host) == ['Slot 1  1K', 'Slot 8  NTAG213']


def test_tiny_read_skips_unwritten_default_slot(monkeypatch, tmp_path):
    slots = {n: {'config': 'MF_CLASSIC_1K', 'mem': bytes(1024)}
             for n in range(1, 9)}
    plugin, host, tiny = _tiny(monkeypatch, tmp_path, slots)
    assert plugin.start_read()['status'] == 'error'
    assert 'No readable slot' in host.vars['error_msg']


def test_tiny_read_mfc(monkeypatch, tmp_path):
    plugin, host, _ = _tiny(monkeypatch, tmp_path, _tiny_slots())
    plugin.start_read()
    host._list_state['read_slot'] = {'selected': 0}
    plugin.choose_read_slot()
    assert plugin.do_read()['status'] == 'ok'
    assert (tmp_path / 'M1-1K-4B_0AD828D2_1.bin').read_bytes() == (
        _tiny_slots()[1]['mem'])


def test_tiny_read_ntag(monkeypatch, tmp_path):
    plugin, host, _ = _tiny(monkeypatch, tmp_path, _tiny_slots())
    plugin.start_read()
    host._list_state['read_slot'] = {'selected': 1}
    plugin.choose_read_slot()
    assert plugin.do_read()['status'] == 'ok'
    path = tmp_path / 'NTAG213_1D32320E950000_1.bin'
    assert path.exists()
    blob = path.read_bytes()
    assert len(blob) == 236
    assert blob[0:8] == bytes.fromhex('0004040201000F03')


def test_tiny_read_no_slots_is_error(monkeypatch, tmp_path):
    slots = {n: {'config': 'NONE', 'mem': b''} for n in range(1, 9)}
    plugin, host, tiny = _tiny(monkeypatch, tmp_path, slots)
    assert plugin.start_read()['status'] == 'error'
    assert 'No readable slot' in host.vars['error_msg']
    assert tiny.closed  # detection-opened port must not leak


# ======================================================================
# Renamed dumps: detect family/type from the dump contents
# ======================================================================

def _mf1_block0_bin(uid_hex, blocks):
    data = bytearray(blocks * 16)
    uid = bytes.fromhex(uid_hex)
    data[0:len(uid)] = uid
    data[4] = data[0] ^ data[1] ^ data[2] ^ data[3]
    data[5] = 0x08
    data[6:8] = bytes.fromhex('0400')
    return bytes(data)


def test_ultra_scan_renamed_mf1_1k(monkeypatch, tmp_path):
    (tmp_path / 'FRONT-DOOR.bin').write_bytes(_mf1_block0_bin('DEADBEEF', 64))
    monkeypatch.setenv('ULTRA_WRITER_DUMP_DIR', str(tmp_path))
    dumps = ux._scan_dumps()
    assert len(dumps) == 1
    assert dumps[0]['meta']['kind'] == 'mf1'
    assert dumps[0]['meta']['blocks'] == 64
    assert dumps[0]['uid'] == 'DEADBEEF'


def test_ultra_scan_renamed_mf1_plus2k(monkeypatch, tmp_path):
    (tmp_path / 'BIG.bin').write_bytes(_mf1_block0_bin('DEADBEEF', 128))
    monkeypatch.setenv('ULTRA_WRITER_DUMP_DIR', str(tmp_path))
    dumps = ux._scan_dumps()
    assert dumps[0]['meta']['blocks'] == 128
    assert dumps[0]['meta']['type_name'] == 'MIFARE Classic 2K'


def test_ultra_scan_renamed_mfu(monkeypatch, tmp_path):
    pages = bytearray(45 * 4)
    pages[0:3] = bytes.fromhex('1D3232')
    pages[4:8] = bytes.fromhex('0E950000')
    (tmp_path / 'tag.bin').write_bytes(b'\x00' * 56 + bytes(pages))
    monkeypatch.setenv('ULTRA_WRITER_DUMP_DIR', str(tmp_path))
    dumps = ux._scan_dumps()
    assert dumps[0]['meta']['kind'] == 'mfu'
    assert dumps[0]['meta']['type_name'] == 'NTAG213'
    assert dumps[0]['uid'] == '1D32320E950000'


def test_ultra_scan_renamed_em410x(monkeypatch, tmp_path):
    (tmp_path / 'KEYFOB.txt').write_text('0000BC614E\n0000BC614E\n')
    monkeypatch.setenv('ULTRA_WRITER_DUMP_DIR', str(tmp_path))
    dumps = ux._scan_dumps()
    assert dumps[0]['meta']['kind'] == 'em410x'
    assert dumps[0]['uid'] == '0000BC614E'


def test_tiny_scan_renamed_mf1(monkeypatch, tmp_path):
    (tmp_path / 'FRONT-DOOR.bin').write_bytes(_mf1_block0_bin('0AD828D2', 64))
    monkeypatch.setenv('TINY_WRITER_DUMP_DIR', str(tmp_path))
    dumps = tx._scan_dumps()
    assert dumps[0]['meta']['kind'] == 'mf1'
    assert dumps[0]['meta']['config'] == 'MF_CLASSIC_1K'
    assert dumps[0]['uid'] == '0AD828D2'


def test_tiny_scan_renamed_mfu(monkeypatch, tmp_path):
    pages = bytearray(45 * 4)
    pages[0:3] = bytes.fromhex('1D3232')
    pages[4:8] = bytes.fromhex('0E950000')
    (tmp_path / 'tag.bin').write_bytes(b'\x00' * 56 + bytes(pages))
    monkeypatch.setenv('TINY_WRITER_DUMP_DIR', str(tmp_path))
    dumps = tx._scan_dumps()
    assert dumps[0]['meta']['kind'] == 'mfu'
    assert dumps[0]['meta']['config'] == 'NTAG213'
    assert dumps[0]['uid'] == '1D32320E950000'


# ======================================================================
# Detection
# ======================================================================

def test_no_device_reports_error(monkeypatch, tmp_path):
    monkeypatch.setattr(ux, '_find_ultra', _no_device)
    monkeypatch.setattr(tx, '_find_tiny', _no_device)
    host = FakeHost()
    plugin = cd.ChameleonDumpPlugin(host)
    assert plugin.start_read()['status'] == 'error'
    assert 'No Chameleon' in host.vars['error_msg']


# ======================================================================
# ui.json — Back must never re-enter a scanning state
# ======================================================================

def _ui_states():
    path = os.path.join(REPO, 'plugins', 'chameleon_dump', 'ui.json')
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)['states']


def test_back_returns_to_menu_without_rescan():
    states = _ui_states()
    assert states['select_dump']['screen']['keys']['M1'] == 'set_state:menu'
    assert states['select_slot']['screen']['keys']['M1'] == 'set_state:select_dump'
    assert states['read_slot']['screen']['keys']['M1'] == 'set_state:menu'
