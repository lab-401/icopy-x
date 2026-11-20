##########################################################################
# Required Notice: Copyright ETOILE401 SAS (http://www.lab401.com)
#
# Copyright (c) 2026: ETOILE401 SAS & https://github.com
#
#
# This software is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this software for commercial purposes.
#
# A copy of the license is available at:
# https://polyformproject.org
#
# This entire header "Required Notice" must remain in place.
##########################################################################

"""Dump Diff 2 dump discovery, parsing and comparison utilities.
Copyright (c) 2026: jareckib

Read supported RFID dumps, format memory blocks, extract metadata,
and identify changed blocks for the comparison screen.

"""

# Dump Diff 2 - independent implementation (2026).
# Concept inspired by Dump Diff by uaih3k9x; no source code reused.
import os, re, json

FORMATS = {
    'Paxton Net2': ('paxton', 'net2', 4),
    'Paxton Switch2': ('paxton', 'switch2', 4),
    'T5577': ('t55xx', None, 4),
    'MIFARE Classic': ('mf1', None, 16),
    'Ultralight / NTAG': ('mfu', None, 4),
    'iCLASS': ('iclass', None, 8),
}

def _hex(s):
    s = re.sub(r'\s+', '', s)
    if not s or len(s) % 2 or re.search(r'[^0-9a-fA-F]', s):
        raise ValueError('Invalid HEX data')
    return bytes.fromhex(s)

def _json_blocks(path, unit=None):
    with open(path, 'r') as f: obj = json.load(f)
    blocks = obj.get('blocks')
    if not isinstance(blocks, dict) or not blocks:
        raise ValueError('Missing blocks')
    indexes = sorted(int(k) for k in blocks)
    if indexes != list(range(indexes[-1] + 1)):
        raise ValueError('Incomplete block sequence')
    values = [_hex(blocks[str(k)]) for k in indexes]
    if unit and any(len(value) != unit for value in values):
        raise ValueError('Invalid JSON block length')
    return b''.join(values)

def _paxton(path, kind):
    with open(path, 'r') as f: lines = [s.strip() for s in f if s.strip()]
    if not lines: raise ValueError('Empty dump')
    # Net2 first line contains blocks 1..7; UID is stored separately on line 2.
    # Compare the complete memory record, excluding only block 0 (UID).
    raw = _hex(lines[0])
    if kind == 'net2':
        if len(raw) != 28: raise ValueError('Unexpected Net2 record length')
        if len(lines) < 2 or len(_hex(lines[1])) != 4:
            raise ValueError('Missing or invalid Net2 UID')
        return raw
    if len(raw) != 28: raise ValueError('Unexpected Switch2 record length (expected 7 blocks)')
    if len(lines) < 2 or len(_hex(lines[1])) != 4:
        raise ValueError('Missing or invalid Switch2 UID')
    return raw


def paxton_detail_blocks(path, category):
    """Decode display-only Hitag2 records; preserve comparison loader semantics.

    Net2 files: 28-byte first line represents blocks 1..7, while the
    4-byte UID is held on the second line. Do not drop the first four bytes:
    they are block 1 (password), not a header for the details display.
    Switch2 files contain seven 4-byte data blocks (blocks 1..7) on line 1 and UID on line 2.
    """
    with open(path, 'r') as f:
        lines = [line.strip() for line in f if line.strip()]
    if not lines:
        raise ValueError('Empty Paxton dump')
    raw = _hex(lines[0])
    if category == 'Paxton Net2':
        if len(raw) != 28:
            raise ValueError('Net2 details require seven complete 4-byte blocks')
        if len(lines) < 2:
            raise ValueError('Missing Net2 UID line')
        uid = _hex(lines[1])
        if len(uid) != 4:
            raise ValueError('Invalid Net2 UID')
        return [(0, 'UID', uid)] + [(i+1, ('Pwd','Key/Pwd','Config','User B4','User B5','User B6','User B7')[i], raw[i*4:(i+1)*4]) for i in range(7)]
    if category == 'Paxton Switch2':
        if len(raw) != 28:
            raise ValueError('Unexpected Switch2 record length (expected 7 blocks)')
        if len(lines) < 2 or len(_hex(lines[1])) != 4:
            raise ValueError('Missing or invalid Switch2 UID')
        uid = _hex(lines[1])
        names = ('Pwd', 'Key/Pwd', 'Config', 'User B4', 'User B5', 'User B6', 'User B7')
        return [(0, 'UID', uid)] + [(i+1, names[i], raw[i*4:(i+1)*4]) for i in range(7)]
    raise ValueError('Not a Paxton category')



def json_info_lines(path, category):
    """Use Proxmark3/iCopy JSON as the authoritative Info source.

    A selected .bin resolves to its same-stem .json sidecar. The memory
    comparison code continues to use the original binary dump.
    """
    if category not in ('MIFARE Classic', 'iCLASS'):
        return None
    json_path = os.path.splitext(path)[0] + '.json'
    if not os.path.isfile(json_path):
        return None
    with open(json_path, 'r') as f:
        obj = json.load(f)
    blocks = obj.get('blocks')
    if not isinstance(blocks, dict) or not blocks:
        raise ValueError('JSON missing blocks')
    unit = FORMATS[category][2]
    numbers = sorted((int(k) for k in blocks), key=int)
    if len(numbers) != len(blocks) or numbers[0] != 0 or numbers != list(range(numbers[-1] + 1)):
        raise ValueError('Invalid JSON block numbering')
    result = ['FileType: ' + str(obj.get('FileType', '?'))]
    card = obj.get('Card', {})
    if isinstance(card, dict):
        for key, value in card.items():
            if isinstance(value, (str, int)):
                result.append(str(key) + ': ' + str(value))
    for number in numbers:
        raw = _hex(blocks[str(number)])
        if len(raw) != unit:
            raise ValueError('Invalid JSON block %d length' % number)
        block_hex = raw.hex().upper()
        label = ('B%d:' % number).rjust(5) + ' '
        if len(block_hex) > 16:
            result.extend((label + block_hex[:16], ' ' * len(label) + block_hex[16:]))
        else:
            result.append(label + block_hex)
    return result

def detail_block_lines(path, category, data=None):
    if category in ('Paxton Net2', 'Paxton Switch2'):
        blocks = paxton_detail_blocks(path, category)
        return ['UID: ' + blocks[0][2].hex().upper(), 'Blocks: 8'] + [
            'B%d: %s' % (number, value.hex().upper()) for number, _, value in blocks]
    if data is None: data = load(path, category)
    if category == 'T5577':
        return ['P%d B%d: %s' % ((0 if i < 32 else 1), (i//4 if i < 32 else (i-32)//4), ' '.join('%02X' % b for b in data[i:i+4]))
                for i in range(0, len(data), 4)]
    if category in ('MIFARE Classic', 'Ultralight / NTAG', 'iCLASS'):
        unit = FORMATS[category][2]
        result = []
        for i in range(0, len(data), unit):
            block_hex = data[i:i+unit].hex().upper()
            label = 'B{}:'.format(i//unit)
            # Classic: 16 bytes = four 8-hex-digit rows; no truncation.
            # All rows are drawn at the same HEX X coordinate by both UIs.
            chunk = 16
            for offset in range(0, len(block_hex), chunk):
                piece = block_hex[offset:offset+chunk]
                result.append((label + ' ' + piece) if offset == 0 else (' ' * 6 + piece))
        return result
    return []

def _mfu_memory_bin(data, path=None):
    """Return only 4-byte tag pages from Proxmark3 MFU binary formats.

    New PM3 format: 56-byte prefix, offset 11 = last page index.
    Legacy PM3 format: 48-byte prefix, no page-count field.
    Raw dumps: pages start at byte zero. Ambiguous legacy/raw files are
    intentionally rejected rather than silently shifting page numbers.
    """
    if not data or len(data) % 4:
        raise ValueError('Invalid MFU page alignment')
    # New-format header has an explicit last-page index. Require its count
    # to agree exactly with the remaining memory length (and that the
    # remainder is a whole number of 4-byte pages, not a truncated guess).
    if len(data) >= 60 and (len(data) - 56) % 4 == 0 and data[11] + 1 == (len(data) - 56) // 4:
        pages = data[56:]
        if not pages or len(pages) > 1024:
            raise ValueError('Invalid MFU memory size')
        return pages
    # For legacy 48-byte headers, a JSON sidecar can establish the exact
    # memory bytes without guessing. It also works for partial raw dumps.
    if path:
        sidecar = os.path.splitext(path)[0] + '.json'
        if os.path.isfile(sidecar):
            reference = _json_blocks(sidecar)
            if data == reference:
                return data
            if len(data) >= 48 and data[48:] == reference:
                return reference
            if len(data) >= 56 and data[56:] == reference:
                return reference
    # Plain dumps may be 16, 20, 41, 45, 135 or 231 pages.
    # Use these sizes only to disambiguate; other sizes may be partial dumps.
    known_pages = (16, 20, 41, 45, 135, 231)
    if len(data) // 4 in known_pages:
        return data
    # A legacy 48-byte header has no reliable length discriminator.
    # Never guess: it could be a partial raw dump of the same size.
    raise ValueError('MFU BIN format ambiguous (raw or legacy 48-byte header); use matching JSON')


def _mf1_memory_bin(data, path=None):
    """MIFARE Classic: return 16-byte blocks only, without guessed offsets.

    Native raw Proxmark3/iCopy Classic dumps have no MFU-style prefix.
    A matching JSON sidecar can verify and remove an external wrapper.
    """
    if path:
        sidecar = os.path.splitext(path)[0] + '.json'
        if os.path.isfile(sidecar):
            reference = _json_blocks(sidecar, 16)
            if any(len(reference) == n * 16 for n in (20, 64, 128, 256)):
                if data == reference:
                    return data
                # Accept a header only if the full payload matches JSON exactly.
                if len(data) > len(reference) and data.endswith(reference):
                    return reference
                raise ValueError('MIFARE Classic BIN and JSON blocks disagree')
            raise ValueError('Unsupported MIFARE Classic JSON block count')
    valid_sizes = (20*16, 64*16, 128*16, 256*16)
    if len(data) in valid_sizes:
        return data
    raise ValueError('Unsupported/ambiguous MIFARE Classic BIN size (%d bytes); provide matching JSON' % len(data))

def load(path, category):
    if category not in FORMATS: raise ValueError('Unsupported category')
    _, variant, unit = FORMATS[category]
    ext = os.path.splitext(path)[1].lower()
    if os.path.getsize(path) > 1024 * 1024: raise ValueError('Dump exceeds safe 1 MiB limit')
    if variant: return _paxton(path, variant)
    if ext == '.bin':
        with open(path, 'rb') as f: data = f.read()
    elif ext == '.json': data = _json_blocks(path, unit if category == 'MIFARE Classic' else None)
    else: raise ValueError('Unsupported file extension')
    if category == 'Ultralight / NTAG' and ext == '.bin':
        data = _mfu_memory_bin(data, path)
    if category == 'MIFARE Classic' and ext == '.bin':
        data = _mf1_memory_bin(data, path)
    if category == 'MIFARE Classic' and len(data) not in (320,1024,2048,4096):
        raise ValueError('Invalid Classic dump size')
    if not data or len(data) % unit: raise ValueError('Invalid memory size')
    return data

def identity(path, category, data):
    """Return (kind, value) when tag identity is reliably available.

    T5577 has no factory UID; its encoded credential depends on modulation and
    format, so do not confuse its configuration blocks with a card identifier.
    """
    name = os.path.basename(path)
    if category == 'MIFARE Classic':
        if len(data) < 16:
            return None
        # Never present all-zero/all-FF manufacturer blocks as a real UID.
        # A four-byte UID has BCC at manufacturer byte 4.
        uid4 = data[:4]
        if uid4 not in (bytes(4), b'\xFF'*4) and data[4] == (uid4[0] ^ uid4[1] ^ uid4[2] ^ uid4[3]):
            return ('UID', uid4.hex().upper())
        # ISO14443A seven-byte cascade format: UID0..2 + BCC0,
        # UID3..6 + BCC1. Both BCC bytes must validate.
        if (data[3] == (0x88 ^ data[0] ^ data[1] ^ data[2]) and
                data[8] == (data[4] ^ data[5] ^ data[6] ^ data[7])):
            uid7 = data[:3] + data[4:8]
            if uid7 not in (bytes(7), b'\xFF'*7):
                return ('UID', uid7.hex().upper())
        return None
    if category == 'iCLASS':
        return ('CSN', data[:8].hex().upper()) if len(data) >= 8 else None
    if category == 'Ultralight / NTAG':
        # iCopy MFU dumps may include a metadata prefix, not only raw pages.
        # Prefer the UID in the native dump filename over assuming raw offset 0.
        match = re.search(r'M0-[^_]+_([0-9A-Fa-f]{14})_', name)
        if match:
            return ('UID', match.group(1).upper())
        # Raw 7-byte UID page layout with valid BCC0/BCC1.
        if len(data) >= 12 and data[3] == (0x88 ^ data[0] ^ data[1] ^ data[2]) and data[8] == (data[4] ^ data[5] ^ data[6] ^ data[7]):
            return ('UID', (data[:3] + data[4:8]).hex().upper())
    return None

def compare(path_a, path_b, category):
    a, b = load(path_a, category), load(path_b, category)
    if category in ('MIFARE Classic', 'Ultralight / NTAG', 'iCLASS') and len(a) != len(b):
        raise ValueError('Incompatible dump sizes')
    unit = FORMATS[category][2]
    id_a, id_b = identity(path_a, category, a), identity(path_b, category, b)
    different_fob = bool(id_a and id_b and id_a[0] == id_b[0] and id_a[1] != id_b[1])
    changes = []
    for offset in range(0, max(len(a), len(b)), unit):
        x, y = a[offset:offset+unit], b[offset:offset+unit]
        if x != y:
            change = {'block': offset//unit + (1 if category in ('Paxton Net2', 'Paxton Switch2') else 0), 'offset': offset + (4 if category in ('Paxton Net2', 'Paxton Switch2') else 0),
                      'a': x.hex().upper() or '--', 'b': y.hex().upper() or '--'}
            if category == 'T5577':
                change['page'] = 0 if offset < 32 else 1
                change['block'] = offset//4 if offset < 32 else (offset-32)//4
            changes.append(change)
    return {'same': not changes, 'changes': changes, 'size_a':len(a), 'size_b':len(b), 'different_fob':different_fob, 'identity_a':id_a, 'identity_b':id_b}

def discover(root, category):
    folder, variant, _ = FORMATS[category]
    directory = os.path.join(root, folder)
    if not os.path.isdir(directory): return []
    entries = []
    for name in os.listdir(directory):
        path = os.path.join(directory, name)
        if not os.path.isfile(path): continue
        ext = os.path.splitext(name)[1].lower()
        if variant:
            if ext != '.txt': continue
            try:
                with open(path, 'r') as f: txt=f.read(250).lower()
                if 'type=' + variant not in txt: continue
            except (IOError, OSError): continue
        elif ext not in ('.bin','.json'): continue
        entries.append(path)
    # Treat BIN and JSON with the same basename as one logical dump.
    grouped = {}
    for path in entries:
        stem = os.path.splitext(os.path.basename(path))[0]
        previous = grouped.get(stem)
        if previous is None or path.lower().endswith('.bin'):
            grouped[stem] = path
    return sorted(grouped.values(), key=lambda p: (-os.path.getmtime(p), os.path.basename(p)))


"""Universal, technology-neutral screen planner for iCopy-X/XS Details.

Technology-specific readers supply Section/Item data. Renderer owns layout.
"""
from dataclasses import dataclass, field

# Details: labels gray, ordinary data blue, findings red, warnings orange.
LABEL_COLOR = '#64748B'
VALUE_COLOR = '#1647D6'
TEXT_LINE_MAX_CHARS = 21  # Ordinary text: 21 content chars + one space on each side within 5px margins.
HEX_LINE_MAX_CHARS = 23  # HEX exception: 5px left/right margins, no extra outer spaces.
CHANGED_BYTE_COLOR = '#D62636'  # genuine differences only
WARNING_COLOR = '#E58A19'
CRITICAL_COLOR = '#D62636'

def anti_clone_color(raw, experimental=False):
    """Classify Anti-Clone findings, never unrelated UID/structure MATCH rows."""
    text = str(raw).strip().upper()
    if any(x in text for x in ('NO MATCH', 'NOT DETECTED', 'NOT TESTED', 'NONE FOUND')):
        return VALUE_COLOR
    if experimental or '(EXP)' in text or 'EXPERIMENTAL' in text or text.startswith('EXP:'):
        return WARNING_COLOR
    if text in ('STATUS: MATCH', 'DUMP A: MATCH', 'DUMP B: MATCH') or text.startswith(('A MATCH:', 'B MATCH:', 'MATCH:')):
        return CRITICAL_COLOR
    if text.startswith('DIAG:') or text.startswith(('A DIAG:', 'B DIAG:')):
        return CRITICAL_COLOR if any(x in text for x in ('MARKER', 'CANDIDATE', 'MISMATCH', '[FAIL]', 'POSSIBLE', 'DETECTED', '[PASS]')) else VALUE_COLOR
    if text.startswith(('STATUS: NO MATCH', 'DUMP A: NO MATCH', 'DUMP B: NO MATCH')):
        return VALUE_COLOR
    if text in ('NORALSY A', 'HEXACT A', 'HEXACT B', 'COMELIT A', 'COMELIT B',
                'INTRATONE A', 'GENERIC A', 'COGELEC GENERIC'):
        return CRITICAL_COLOR
    return VALUE_COLOR


def mfc_detail_color(section, raw, model):
    """Use original, untranslated findings and their section, not HEX/text guesses."""
    text = str(raw).strip()
    if str(section).startswith('Anti-Clone'):
        result = model.get('anti_clone_result') or {}
        for key, color in (('matches', CRITICAL_COLOR), ('experimental', WARNING_COLOR)):
            for entry in result.get(key) or []:
                name = str(entry.get('name') or entry.get('family') or 'Unknown') if isinstance(entry, dict) else str(entry)
                if text == name + (' (EXP)' if key == 'experimental' else ''):
                    return color
        upper = text.upper()
        if any(x in upper for x in ('NO MATCH', 'NOT DETECTED', 'NOT TESTED', 'NONE FOUND')):
            return VALUE_COLOR
        if '(EXP)' in upper or 'EXPERIMENTAL' in upper or upper.startswith('EXP:'):
            return WARNING_COLOR
        if upper.startswith('DIAG:'):
            if any(x in upper for x in ('WARNING', 'CANDIDATE', 'MISMATCH', '[FAIL]', 'POSSIBLE')):
                return WARNING_COLOR
            return CRITICAL_COLOR if any(x in upper for x in ('MARKER', 'DETECTED')) else VALUE_COLOR
        return anti_clone_color(raw)
    label, _, value = text.partition(':')
    label, value = label.strip(), value.strip()
    if str(section).startswith('Sequential') and model.get('sequential_status') == 'ON':
        if label in ('Block', 'Counter', 'Steps', 'Offset', 'Width', 'Endian', 'Width/endian'):
            return CRITICAL_COLOR
        if label == 'Sequential' and value == 'ON':
            return CRITICAL_COLOR
        if label == 'Rollback' and value == 'ON':
            return WARNING_COLOR
    if str(section).startswith('Classic Structure'):
        if text.startswith('Invalid trailer B') or (label in ('Access bits', 'UID BCC') and value.startswith('INVALID')):
            return WARNING_COLOR
        if label == 'Invalid trailers' and value.isdigit() and int(value) > 0:
            return WARNING_COLOR
        if text.startswith('Value block B') or (label == 'Value blocks' and value.isdigit() and int(value) > 0):
            return VALUE_COLOR
    return VALUE_COLOR


def _result_color(label, value, default):
    """Respect explicit finding classification; do not color generic MATCH red."""
    if default in (WARNING_COLOR, CRITICAL_COLOR):
        return default
    content = (str(label) + ' ' + str(value)).upper()
    if any(x in content for x in ('NO MATCH', 'NOT DETECTED', 'NOT TESTED', 'NONE FOUND')):
        return default
    if any(x in content for x in ('DANGER', 'CRITICAL', 'CONFIRMED CLONE', 'VULNERABLE')):
        return CRITICAL_COLOR
    if any(x in content for x in ('WARNING', '(EXP)', 'SUSPICIOUS', 'POSSIBLE', 'RISK:')):
        return WARNING_COLOR
    return default


PROFILES = {
    'mfc': {'anti_clone': True, 'sequential': True, 'block_bytes': 16},
    'paxton': {'anti_clone': False, 'sequential': False, 'block_bytes': 4},
    'iclass': {'anti_clone': False, 'sequential': False, 'block_bytes': 8},
    't5577': {'anti_clone': False, 'sequential': False, 'block_bytes': 4},
    'ultralight': {'anti_clone': False, 'sequential': False, 'block_bytes': 4},
}

@dataclass
class Item:
    label: str
    value: str = ''
    kind: str = 'pair'
    color: str = VALUE_COLOR
    changed: frozenset = field(default_factory=frozenset)

@dataclass
class Section:
    name: str
    items: list


def expand(item):
    """Measure complete fields before wrapping; preserve atomic HEX groups."""
    from tkinter import font as tkfont
    from _dump_diff_2_lib.screen_catalog import text_rows
    measure=tkfont.Font(family='Courier New',size=12).measure
    if item.kind=='filename':return [item]
    if item.kind in ('pair','stack','text_field'):
        label=item.label.rstrip(' :')+':' if item.label else ''
        value=str(item.value)
        if measure(label+' '+value)<=220 and '\n' not in value:
            return [Item(label,value,'pair',color=item.color,changed=item.changed)]
        hex_rows=None if item.kind=='text_field' else _details_hex_rows(value)
        values=hex_rows or text_rows(value,measure,220)
        labels=[Item(part,kind='label',color=LABEL_COLOR) for part in text_rows(label,measure,220)]
        return labels+[Item('',v,'hex' if hex_rows else 'center',color=item.color) for v in values]
    if item.kind=='center':
        hex_rows=_details_hex_rows(item.value)
        return [Item('',v,'hex' if hex_rows else 'center',color=item.color) for v in (hex_rows or text_rows(item.value,measure,220))]
    if item.kind=='block':
        cells=item.value.split();label=item.label.rstrip(' :')+':'
        if len(cells)==4 and measure(label+' '+item.value)<=220:
            return [Item(label,item.value,'pair',color=item.color,changed=item.changed)]
        if len(cells) not in (4,8,16):raise ValueError('Unsupported block byte count')
        return [Item(label,kind='label',color=LABEL_COLOR)]+[
            Item('',' '.join(cells[i:i+8]),'hex',color=item.color,changed=frozenset(j-i for j in item.changed if i<=j<i+8))
            for i in range(0,len(cells),8)]
    return [item]


def details_positions(title,lines,index=1):
    from _dump_diff_2_lib.screen_catalog import row_positions
    rows=([('heading',title,'',VALUE_COLOR)] if title else [])+[
        (x.kind,x.label,x.value,x.color) if x.kind in ('pair','filename') else
        (x.kind if x.kind in ('hex','label') else 'text',x.label if x.kind=='label' else x.value,'',x.color)
        for x in lines]
    positions=row_positions(rows,index>0)
    if title and lines and lines[0].kind=='filename':
        positions=[positions[0]]+[y+20 for y in positions[1:]]
    return positions


def plan(category, sections, limit=6):
    if category not in PROFILES: raise ValueError('Unknown dump category: ' + category)
    pages=[]
    for section in sections:
        key=section.name.lower().replace('-', '_').replace(' ', '_')
        if PROFILES[category].get(key) is False: continue
        title=section.name
        groups=[expand(item) for item in section.items]
        lines=[]
        for group in groups:
            if len(group)>limit-1 and not any(row.kind=='hex' for row in group):
                if lines: pages.append((title,lines));lines=[];title=''
                labels=[row for row in group if row.kind=='label']
                values=[row for row in group if row.kind!='label']
                room=limit-(1 if title else 0)-len(labels)
                if room<1:raise ValueError('Field label too large')
                for offset in range(0,len(values),room):
                    pages.append((title,labels+values[offset:offset+room]));title=''
                continue
            if len(group)>limit: raise ValueError('Atomic HEX item too large')
            if len(lines)+len(group)+(1 if title else 0)>limit or details_positions(title,lines+group)[-1]+18>171:
                if lines: pages.append((title,lines))
                title='';lines=[]
            lines.extend(group)
        if lines or title: pages.append((title,lines))
    return pages


def draw(canvas,page,index,total,tag='_dd2_details',ultralight_spacing=False):
    """Use the existing native Tk canvas; firmware renders bars and buttons."""
    from tkinter import font as tkfont
    face=('Courier New',12)
    measure=tkfont.Font(family=face[0],size=face[1]).measure
    blue,gray,red=VALUE_COLOR,LABEL_COLOR,CHANGED_BYTE_COLOR
    canvas.delete(tag)
    title,lines=page
    # Keep centered label/HEX pages at their original coordinates.
    # Arrows sit at the right edge, freeing the first data row.
    # Top spacing: 1-3 rows = 2 blanks; 4 rows = 1 blank; 5-6 = none.
    if ultralight_spacing and not title:
        y = 85 if len(lines) <= 3 else (64 if len(lines) == 4 else 43)
    else:
        y=43 if title else (85 if 1<=len(lines)<=3 else (64 if len(lines)==4 else 43))
    positions=details_positions(title,lines,index)
    if title:
        y=positions[0]
        canvas.create_text(120,y,text=title,anchor='n',fill=red if title=='Analysis Notice' else blue,font=face,tags=tag)
        y+=38 if title=='Analysis Notice' else 39 if lines and lines[0].kind=='filename' else 19
        # A titled section starts directly below the bar.
    pairs=[item for item in lines if item.kind=='pair' and item.label.rstrip(': ')!='Date']
    pair_width=max((measure(item.label+' ') for item in pairs),default=0)
    pair_total=pair_width+max((measure(item.value) for item in pairs),default=0)
    for item,y in zip(lines,positions[1:] if title else positions):
        if item.kind=='filename':
            # Plugin draws the fixed Name: and scrolling value at y=82.
            # Use the same 19 px baseline interval as every other Details row.
            y+=19
            continue
        if item.kind=='pair':
            prefix=item.label+' '
            pair_label_color = red if item.changed else gray
            column=measure(prefix) if item.label.rstrip(': ')=='Date' else pair_width
            column=measure(prefix)
            left=(240-measure(item.label+' '+item.value))/2 if not title and len(lines)==1 else measure(' ')
            from _dump_diff_2_lib.screen_catalog import draw_pair
            draw_pair(canvas,left,y,item.label,item.value,_result_color(item.label,item.value,item.color),face,tag,measure)
        elif item.kind=='hex':
            parts=item.value.split()
            widths=[measure(part+(' ' if i<len(parts)-1 else '')) for i,part in enumerate(parts)]
            width=sum(widths)
            if width > 230:
                raise ValueError('8-byte HEX row exceeds 5px margins: %s px' % width)
            x=(240-width)/2
            for i,part in enumerate(parts):
                canvas.create_text(x,y,text=part,anchor='nw',fill=red if i in item.changed else item.color,font=face,tags=tag)
                x+=widths[i]
        else:
            value=item.label if item.kind=='label' else item.value or item.label
            center=title=='Analysis Notice' or item.kind=='label' or (not title and len(lines)==1)
            canvas.create_text(120 if center else measure(' '),y,text=value,anchor='n' if center else 'nw',fill=item.color if item.kind=='label' else _result_color(item.label,value,item.color),
                               font=face,tags=tag)
        y+=19
    if index: canvas.create_text(235,43,text='▲',anchor='ne',fill=blue,font=('Arial',9),tags=tag)
    if index+1<total: canvas.create_text(235,198,text='▼',anchor='se',fill=blue,font=('Arial',9),tags=tag)
    canvas.create_text(120,190,text='Page {}/{}'.format(index+1,total),anchor='center',fill=blue,font=('Courier New',9),tags=tag)



import types as _types
_compare_api = _types.SimpleNamespace(FORMATS=FORMATS, _hex=_hex, load=load, identity=identity)
SCREEN_ENGINE_PROFILES = PROFILES


"""Single Details page adapter for prepared dump models; no Compare changes."""


CATS={'MIFARE Classic':'mfc','Paxton Net2':'paxton','Paxton Switch2':'paxton','iCLASS':'iclass','T5577':'t5577','Ultralight / NTAG':'ultralight'}
FIELDS={'mfc':'_mfc_details','paxton':'_paxton_details','iclass':'_iclass_details','t5577':'_t5577_details','ultralight':'_ul_details'}

def _details_hex(v):
    """Display full HEX bytes with spaces; never join or truncate bytes."""
    raw=str(v).strip()
    compact=re.sub(r'\s+', '', raw)
    if compact and len(compact)%2==0 and re.fullmatch(r'[0-9a-fA-F]+',compact):
        return ' '.join(compact[i:i+2].upper() for i in range(0,len(compact),2))
    return raw


def _details_hex_rows(value, bytes_per_row=8):
    """Return complete byte-aligned HEX rows, at most 8 bytes each."""
    formatted=_details_hex(value)
    if not formatted or not re.fullmatch(r'[0-9A-F]{2}(?: [0-9A-F]{2})*',formatted):
        return None
    parts=formatted.split()
    return [' '.join(parts[i:i+bytes_per_row]) for i in range(0,len(parts),bytes_per_row)]


def build(plugin):
    cat=CATS.get(plugin.category)
    if not cat:return None
    d=getattr(plugin,FIELDS[cat],None)
    if not d:return None
    title=d.get('type') or plugin.category
    first=[Item('Name:',str(d.get('name','')),kind='filename'),Item('Date:',str(d.get('date','')))]
    # Universal Details first-page order: Name, Date, Type, UID (if it fits).
    # The title occupies one of the six available physical rows.
    if cat=='mfc':
        # All four variants (Mini/1K/2K/4K) share this Details path.
        # Use the selected dump size when the sidecar has no Card.Type.
        variant={'MIFARE Classic Mini':'mfc-mini','MIFARE Classic 1K':'mfc-1',
                 'MIFARE Classic 2K':'mfc-2','MIFARE Classic 4K':'mfc-4'}.get(str(title),'')
    if cat=='ultralight':first.append(Item('Type:', 'mfu'))
    if cat=='iclass':
        # The parser already maps JSON FileType -> Type; use its value,
        # rather than inventing a value from the category or filename.
        json_type=next((str(value) for group in d.get('groups', [])
                        for label,value,marked in group
                        if str(label).strip().rstrip(':').lower() == 'type'), None)
        if json_type is not None:
            first.append(Item('Type:', json_type))
    if cat=='t5577':
        first.append(Item('Type:', 't55xx'))
        # P0 B0 is the 4-byte configuration. Keep the short label and
        # spaced HEX on ONE physical line (Config: 00 14 80 40).
        config = d.get('blocks', [])
        if config:
            first.append(Item('Config:', _details_hex(config[0])))
    # UID/CSN is not duplicated on subsequent metadata pages when it was moved.
    # Use the actual renderer expansion count, not an estimated character count.
    moved_uid=False
    if cat=='mfc':
        in_anti_section = False
        for kind,entries in d.get('sections',[]):
            if kind!='Card:':continue
            for key,value in entries:
                if str(key).strip().rstrip(':').upper()!='UID':continue
                uid_value=_details_hex(value)
                # Four-byte UID fits beside its label on the 12pt row.
                candidate=Item('UID:',uid_value,kind='pair') if len(uid_value.split())==4 else Item('UID:',uid_value)
                if len(uid_value.split()) == 4 and 1+sum(len(expand(x)) for x in first)+len(expand(candidate))<=6:
                    first.append(candidate);moved_uid=True
                break
            break
    elif cat=='ultralight' and d.get('uid'):
        uid_value=_details_hex(d['uid'])
        candidate=Item('UID:',uid_value,kind='pair') if len(uid_value.split())==4 else Item('UID:',uid_value)
        if len(uid_value.split()) == 4 and 1+sum(len(expand(x)) for x in first)+len(expand(candidate))<=6:
            first.append(candidate);moved_uid=True
    elif cat=='paxton' and d.get('blocks'):
        uid_value=_details_hex(d['blocks'][0])
        candidate=Item('UID:',uid_value,kind='pair') if len(uid_value.split())==4 else Item('UID:',uid_value)
        if len(uid_value.split()) == 4 and 1+sum(len(expand(x)) for x in first)+len(expand(candidate))<=6:
            first.append(candidate);moved_uid=True
    sections=[Section(title,first)]
    if cat=='mfc':
        in_anti_section = False
        for kind,entries in d.get('sections',[]):
            if kind=='Analysis Notice':
                from _dump_diff_2_lib.screen_catalog import analysis_notice_lines
                sections.append(Section(kind,[Item('',line,'center',color=LABEL_COLOR)
                    for line in analysis_notice_lines(plugin._translate)]))
                continue
            if kind=='blocks':
                changed={int(pos) for pos in d.get('changed_bytes',set()) if str(pos).isdigit()}
                sections.append(Section('',[
                    Item('Block %s:'%i,_details_hex(v),'block',
                         changed=frozenset(pos-i*16 for pos in changed if i*16 <= pos < (i+1)*16))
                    for i,v in entries]))
            elif kind=='Card:':
                # Card metadata is not a new invented section heading.
                sections.append(Section('', [Item(str(k).rstrip(':')+':',_details_hex(v)) for k,v in entries
                                             if not (moved_uid and str(k).strip().rstrip(':').upper()=='UID')
                                             and str(k).strip().rstrip(':').lower()!='type']))
            elif str(kind).startswith('Anti-Clone'):
                from _dump_diff_2_lib.screen_catalog import pm3_display_fields
                rows = pm3_display_fields(d.get('anti_clone_result'))
                sections.append(Section(str(kind).rstrip(':'), [
                    Item(row[0], row[1], 'stack' if len(row)>3 and row[3]=='hex' else 'text_field', color=row[2])
                    for row in rows]))
                in_anti_section = False
            else:
                rows=[]
                if str(kind).startswith('Anti-Clone'):
                    in_anti_section = True
                elif kind:
                    in_anti_section = False
                anti_section = in_anti_section
                for entry in entries:
                    if isinstance(entry,tuple) and len(entry)==2:
                        raw, wrapped=entry
                        # Prepared rows are (original text, already wrapped lines).
                        # Never stringify a Python list into the display.
                        finding_color = mfc_detail_color('Anti-Clone' if anti_section else kind, raw, d)
                        for line in (wrapped if isinstance(wrapped,(list,tuple)) else [wrapped]):
                            line=str(line)
                            if ':' in line and not line.startswith('['):
                                label,value=line.split(':',1)
                                rows.append(Item(label+':',value.strip(),color=finding_color))
                            else:
                                rows.append(Item('',line,'center',color=finding_color))
                    else:
                        rows.append(Item('',str(entry),'center'))
                sections.append(Section(str(kind).rstrip(':'),rows))
    elif cat=='paxton':
        names=['UID','Password','Key/Pwd','Config','User B4','User B5','User B6','User B7']
        blocks=d.get('blocks',[])
        # Page 2: no title; native 2-4-line top spacing places content at y=85.
        # Page 3: User B4..B7 together, for Net2 and Switch2.
        sections.append(Section('',[
            Item(names[i]+':',_details_hex(blocks[i]))
            for i in range(1,min(len(blocks),4))]))
        sections.append(Section('',[
            Item(names[i]+':',_details_hex(blocks[i]))
            for i in range(4,min(len(blocks),8))]))
    elif cat=='t5577':
        blocks=d.get('blocks',[])
        # Count ACTUAL rendered rows after expand(), not source blocks.
        # Pack up to six physical lines per page, keeping a label and its
        # HEX value together. P0 B0 is already on the first page.
        pending=[]
        used=0
        for i in range(1,len(blocks)):
            item=Item('P%d B%d:'%(0 if i<8 else 1,i if i<8 else i-8),
                      _details_hex(blocks[i]))
            height=len(expand(item))
            if height>6:
                raise ValueError('T5577 block exceeds Details page capacity')
            if pending and used+height>6:
                sections.append(Section('',pending))
                pending=[]
                used=0
            pending.append(item)
            used+=height
        if pending:
            sections.append(Section('',pending))
    elif cat=='iclass':
        # Layout is computed from EXPANDED physical rows, not JSON groups.
        # A titled first page with scrolling Name reserves one extra blank
        # physical row between title and Name (y=43 -> y=82).
        import re
        def iclass_field(label, value, marked=False):
            label=str(label).strip().rstrip(':')+':'
            raw=str(value).strip()
            compact=re.sub(r'\s+', '', raw)
            is_hex=(bool(compact) and len(compact)%2==0 and
                    bool(re.fullmatch(r'[0-9a-fA-F]+',compact)) and
                    (marked or len(compact)>=4))
            if is_hex:
                compact=compact.upper()
                chunks=[_details_hex(compact[i:i+16]) for i in range(0,len(compact),16)]
            else:
                # Split TXT/DEC on available physical width, never discard data.
                chunks=[raw[i:i+TEXT_LINE_MAX_CHARS] for i in range(0,len(raw),TEXT_LINE_MAX_CHARS)] or ['']
            if len(chunks)==1 and len(label+' '+chunks[0])<=TEXT_LINE_MAX_CHARS:
                return [[Item(label,chunks[0])]]
            # The label and its values are kept together whenever they fit;
            # oversized fields are continued in safe 6-row chunks.
            result=[]
            for offset in range(0,len(chunks),5):
                part=chunks[offset:offset+5]
                head=[Item(label,kind='label',color=LABEL_COLOR)] if offset==0 else []
                kind='hex' if is_hex else 'center'
                result.append(head+[Item('',chunk,kind) for chunk in part])
            return result
        groups=[]
        csn=d.get('csn')
        if csn:
            groups.extend(iclass_field('CSN',csn,True))
        for legacy in d.get('groups',[]):
            for label,value,marked in legacy:
                if str(label).strip().lower().rstrip(':') in ('created','json_fields','iclass data','csn','type','filetype'):
                    continue
                groups.extend(iclass_field(label,value,marked))
        # First page is reserved for Name, Date and Type. The title and
        # the blank line before Name also occupy physical screen rows.
        # An iCLASS CSN is normally 8 bytes, so it requires a grey label
        # plus its own HEX row; it must start on page 2 (same rule as UID
        # longer than four bytes). Never try to squeeze it onto page 1.
        base=first[:]
        first_height=2+sum(len(expand(item)) for item in base)
        if first_height>6:
            raise ValueError('iCLASS first Details page exceeds 6 physical rows')
        remaining=[[row for item in group for row in expand(item)] for group in groups]
        pages=[(title,base)]
        pending=[]
        for group in remaining:
            if len(group)>6:
                raise ValueError('iCLASS field exceeds physical screen capacity')
            if pending and len(pending)+len(group)>6:
                pages.append(('',pending));pending=[]
            pending.extend(group)
        if pending:pages.append(('',pending))
        # Top padding is calculated from final row count by draw():
        # <=3 rows + 2 blanks; 4 rows + 1 blank; 5-6 rows + 0.
        assert all((len(lines)+(2 if not heading and len(lines)<=3 else 1 if not heading and len(lines)==4 else 0)
                    +(2 if heading and lines and lines[0].kind=='filename' else 1 if heading else 0))<=6
                   for heading,lines in pages)
        return pages
    elif cat=='ultralight':
        # Flatten legacy JSON "sections" first: those sections are pre-paginated
        # using old 2-row assumptions and must NOT force new page breaks.
        # Atomic groups keep a label with its wrapped value on the same page.
        groups=[]
        memory=[]
        import re
        for kind,entries in d.get('sections',[]):
            if kind=='blocks':
                memory.extend(entries)
                continue
            for key,value in entries:
                label=str(key).strip().rstrip(':')
                if label.lower() in ('created','type','json_fields') or (moved_uid and label.lower()=='uid'):
                    continue
                raw=str(value).strip()
                compact=re.sub(r'\s+', '',raw)
                is_hex=(bool(compact) and len(compact)%2==0 and
                        all(c in '0123456789abcdefABCDEF' for c in compact))
                if is_hex:
                    compact=compact.upper()
                    pretty=' '.join(compact[i:i+2] for i in range(0,len(compact),2))
                else:
                    pretty=raw
                # Version and Signature always have grey label above blue HEX.
                forced_wrap=label.lower().startswith(('version','signature'))
                if is_hex and not forced_wrap and len(label+': '+pretty)<=HEX_LINE_MAX_CHARS:
                    groups.append([Item(label+':',pretty)])
                elif not is_hex and not forced_wrap and len(label+': '+pretty)<=TEXT_LINE_MAX_CHARS:
                    groups.append([Item(label+':',pretty)])
                else:
                    if label.lower().startswith('signature'):
                        label='Signature 32B'
                    if is_hex:
                        # Exactly 16 hexadecimal digits (8 bytes) per HEX row.
                        chunks=[' '.join(compact[j:j+2] for j in range(i,min(i+16,len(compact)),2)) for i in range(0,len(compact),16)]
                    else:
                        chunks=[raw[i:i+TEXT_LINE_MAX_CHARS] for i in range(0,len(raw),TEXT_LINE_MAX_CHARS)] or ['']
                    for start in range(0,len(chunks),5):
                        part=chunks[start:start+5]
                        head=[Item(label+':',kind='label',color=LABEL_COLOR)] if start==0 else []
                        groups.append(head+[Item('',chunk,'center') for chunk in part])
        # The UID is always shown: 4-byte UID can be on page 1;
        # longer UIDs are a two-row group on a subsequent page.
        if d.get('uid') and not moved_uid and not any(
                str(key).strip().rstrip(':').lower() == 'uid'
                for kind, entries in d.get('sections',[]) if kind != 'blocks'
                for key, value in entries):
            uid_hex=_details_hex(d['uid'])
            groups.insert(0, [Item('UID:',kind='label',color=LABEL_COLOR),
                              Item('',uid_hex,'center')])
        # Pack metadata and memory together: never leave an orphan one-line
        # page when the next memory rows can use its free space.
        for i,v in memory:
            groups.append([Item('Block %s:'%i,_details_hex(v),'block')])
        pending=[]
        for group in groups:
            if pending and len(pending)+len(group)>6:
                sections.append(Section('',pending));pending=[]
            pending.extend(group)
        if pending:sections.append(Section('',pending))
    # Final display-only safeguard: no technical JSON bookkeeping rows.
    for section in sections:
        section.items = [item for item in section.items
                         if item.label.rstrip(':') != 'Created']
    if cat=='mfc':
        # Merge untitled sections by actual rendered row count; each block
        # remains an indivisible 3-row unit (label + two 8-byte HEX rows).
        packed=[sections[0]]
        pending=[]
        used=0
        for section in sections[1:]:
            if section.name:
                if pending:packed.append(Section('',pending));pending=[];used=0
                packed.append(section)
                continue
            for item in section.items:
                height=len(expand(item))
                if pending and used+height>6:
                    packed.append(Section('',pending));pending=[];used=0
                pending.append(item);used+=height
                if used==6:
                    packed.append(Section('',pending));pending=[];used=0
        if pending:packed.append(Section('',pending))
        sections=packed
    translate=getattr(plugin,'_translate',lambda value:value)
    for section in sections:
        for item in section.items:
            item.label=translate(item.label)
            if item.kind!='filename':item.value=translate(item.value)
        from tkinter import font as tkfont
        measure=tkfont.Font(family='Courier New',size=12).measure
    pages = plan(cat,sections)
    if cat=='mfc':
        pages = [page for page in pages if page[0]=='Analysis Notice'] + [
            page for page in pages if page[0]!='Analysis Notice']
    return pages

def render_details(plugin):
    pages=getattr(plugin,'_universal_details_pages',None)
    if not pages:return False
    plugin.details_page=min(plugin.details_page,len(pages)-1)
    canvas=plugin._localized_canvas()
    draw(canvas,pages[plugin.details_page],plugin.details_page,len(pages),
         ultralight_spacing=(CATS.get(plugin.category) in ('ultralight','iclass','mfc')))
    if any(item.kind=='filename' for item in pages[plugin.details_page][1]):
        d=getattr(plugin,FIELDS[CATS[plugin.category]])
        plugin._draw_details_filename(canvas,'_dd2_details',d.get('name',''),82,('Courier New',12))
    plugin._footer_hint('Back',y=177,tag='_dd2_details_hint')
    return True


"""Shared 240x240 screen model, comparison, pagination, and diagnostics.
No RF commands. Keep device UI callbacks in plugin.py/ui.json.
"""
import json, os, time



CATEGORY_UNITS = {k:v[2] for k,v in _compare_api.FORMATS.items()}
SCREEN_PROFILES = {
    'MIFARE Classic': {'details': True, 'compare': True, 'anti_clone': True, 'sequential': True},
    'Paxton Net2': {'details': True, 'compare': True, 'anti_clone': False, 'sequential': False},
    'Paxton Switch2': {'details': True, 'compare': True, 'anti_clone': False, 'sequential': False},
    'T5577': {'details': True, 'compare': True, 'anti_clone': False, 'sequential': False},
    'iCLASS': {'details': True, 'compare': True, 'anti_clone': False, 'sequential': False},
    'Ultralight / NTAG': {'details': True, 'compare': True, 'anti_clone': False, 'sequential': False},
}

CLASSIC_SIZES = {320:'Mini',1024:'1K',2048:'2K',4096:'4K'}

def _sidecar_info(path, category):
    """Treat a same-stem JSON as metadata plus optional memory verification."""
    stem, ext = os.path.splitext(path)
    sidecar = stem + '.json'
    if not os.path.isfile(sidecar):
        return {}, None
    with open(sidecar, encoding='utf-8') as f:
        obj = json.load(f)
    if not isinstance(obj, dict):
        raise ValueError('Sidecar root must be an object')
    fields = {k:v for k,v in obj.items() if k != 'blocks'}
    blocks = obj.get('blocks')
    if blocks is not None:
        if not isinstance(blocks, dict) or not blocks:
            raise ValueError('Sidecar blocks must be a nonempty mapping')
        unit = CATEGORY_UNITS[category]
        keys = sorted(int(k) for k in blocks)
        if len(keys) != len(blocks) or keys != list(range(len(keys))):
            raise ValueError('Sidecar block indices are missing or duplicate')
        expected = []
        for i in keys:
            val = _compare_api._hex(str(blocks[str(i)]))
            if len(val) != unit:
                raise ValueError('Sidecar block %d has invalid length' % i)
            expected.append(val)
        memory = b''.join(expected)
    else:
        memory = None
    return fields, memory


def parse_dump(path, category):
    ext=os.path.splitext(path)[1].lower()
    try:
        metadata, reference = _sidecar_info(path,category) if category in ('MIFARE Classic','Ultralight / NTAG','iCLASS') else ({},None)
        # The BIN is the canonical memory source; JSON contributes metadata and
        # verifies the memory when it contains a blocks mapping.
        if ext == '.json' and reference is None:
            raise ValueError('Metadata-only JSON cannot be used as a standalone memory dump')
        if ext == '.bin' and category == 'Ultralight / NTAG':
            raw_bytes=open(path,'rb').read()
            if reference is not None:
                if raw_bytes == reference: raw=reference; mode='raw+json'
                elif len(raw_bytes) in (len(reference)+48,len(reference)+56) and raw_bytes.endswith(reference):
                    raw=reference; mode='header+json'
                else: raise ValueError('Ultralight BIN and JSON memory disagree')
            else:
                raw=_compare_api.load(path,category);mode='bin-only'
        else:
            raw=_compare_api.load(path,category)
            mode='bin+json' if ext=='.bin' and reference is not None else ext.lstrip('.')
        if reference is not None and raw != reference:
            raise ValueError('BIN and JSON memory disagree')
        unit=CATEGORY_UNITS[category]
        blocks=[raw[i:i+unit] for i in range(0,len(raw),unit)]
        ident=_compare_api.identity(path,category,raw)
        variant=CLASSIC_SIZES.get(len(raw),'UNKNOWN') if category=='MIFARE Classic' else None
        if category=='MIFARE Classic' and variant=='UNKNOWN': raise ValueError('Unsupported Classic size')
        return {'path':path,'category':category,'data':raw,'blocks':blocks,
                'identity':ident,'metadata':metadata,'variant':variant,'source_mode':mode}
    except Exception as exc:
        raise


def compare_parsed(a,b):
    if a['category']!=b['category']: raise ValueError('Different categories')
    category=a['category']
    if len(a['blocks'])!=len(b['blocks']): raise ValueError('Different block counts')
    result=[]
    for i,(x,y) in enumerate(zip(a['blocks'],b['blocks'])):
        changed=[j for j,(xx,yy) in enumerate(zip(x,y)) if xx!=yy]
        # Paxton block 0 UID is not part of _compare_api.load(); its UID is
        # read from the TXT second line and is not classified as a difference.
        result.append({'block':i+(1 if category.startswith('Paxton') else 0),
                       'a':x.hex().upper(),'b':y.hex().upper(),'changed':changed})
    return result


def screen_pages(a,b=None,limit=6):
    """Build shared Details/Compare pages, without inventing extra metadata.
    A/B rows only for changed blocks. A complete block group is atomic.
    """
    cat=a['category']
    if b is not None: rows=compare_parsed(a,b)
    else: rows=[{'block':i+(1 if cat.startswith('Paxton') else 0),'a':v.hex().upper(),'b':None,'changed':[]} for i,v in enumerate(a['blocks'])]
    sections=[]
    if cat.startswith('Paxton'):
        # Native Paxton TXT stores UID on the second line, not in load() bytes.
        def uid(p):
            with open(p['path']) as f: lines=[line.strip() for line in f if line.strip()]
            return lines[1].upper() if len(lines)>1 else None
        ua,ub=uid(a),uid(b) if b else None
        if ua:
            uid_items=[Item('UID'+(' (A)' if b and ua!=ub else '')+':',ua)]
            if b and ua!=ub: uid_items.append(Item('UID (B):',ub))
            sections.append(Section('',uid_items))
    elif a['identity']:
        label,value=a['identity']
        sections.append(Section('',[Item(label+':',value)]))
    block_sections=[]
    for r in rows:
        unit=len(bytes.fromhex(r['a']))
        label=('Block '+str(r['block']))
        if cat=='T5577': label='P%d B%d'%(0 if r['block']<8 else 1,r['block'] if r['block']<8 else r['block']-8)
        changed=frozenset(r['changed'])
        def mk(suffix,value):
            return Item(label+suffix+':',' '.join(value[i:i+2] for i in range(0,len(value),2)),
                        'block' if unit in (8,16) else 'pair',changed=changed)
        if changed:
            # Keep A and B together in the same section, each 16-byte block 3 rows.
            block_sections.append(Section('',[mk(' (A)',r['a']),mk(' (B)',r['b'])]))
        else: block_sections.append(Section('',[mk('',r['a'])]))
    # Preserve A/B as one atomic section; coalesce consecutive identical blocks.
    pending=[]
    for sec in block_sections:
        if len(sec.items)>1:
            if pending: sections.append(Section('',pending));pending=[]
            sections.append(sec)
        else: pending.extend(sec.items)
    if pending: sections.append(Section('',pending))
    ENGINE_PROFILES = SCREEN_ENGINE_PROFILES
    key={'MIFARE Classic':'mfc','Paxton Net2':'paxton','Paxton Switch2':'paxton','T5577':'t5577','iCLASS':'iclass','Ultralight / NTAG':'ultralight'}[cat]
    # The original planner cannot fit two 16-byte block groups (6 rows) on one
    # 6-row page if grouped as one item; flatten them into separate atomic blocks.
    pages=plan(key,sections,limit=limit)
    return pages


def render_screen(canvas,pages,index,tag='_dd2_universal'):
    draw(canvas,pages[index],index,len(pages),tag=tag)


def validate_pages(category, pages):
    """Check actual expanded renderer rows, field labels and paging constraints."""
    problems = []
    if not pages:
        problems.append('empty pages')
    for index, (title, lines) in enumerate(pages or []):
        if len(lines) + bool(title) > 6:
            problems.append('page %d exceeds 6 physical rows' % (index + 1))
        if not lines and not title:
            problems.append('page %d empty' % (index + 1))
        for line in lines:
            label = str(line.label)
            if category == 'Ultralight / NTAG' and label.startswith('Page '):
                problems.append('page %d uses Page instead of Block label: %s' % (index + 1, label))
            if line.kind == 'hex':
                parts = str(line.value).split()
                if len(parts) > 8 or any(len(part) != 2 for part in parts):
                    problems.append('page %d malformed HEX row: %s' % (index + 1, line.value))
            if line.kind == 'pair' and len(label + ' ' + str(line.value)) > 22:
                problems.append('page %d pair may exceed width: %s' % (index + 1, label))
    return problems


