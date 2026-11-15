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

"""Dump Diff 2: Anti-Clone, security diagnostics, and multi-capture sequential analysis.
Copyright (c) 2026: jareckib
Consolidated module for security diagnostics and sequential scan analysis.
"""

# Vendor payloads are decoded by the external PM3 client, not this plugin.
import re

import os
import json
import hashlib
import tempfile
import threading
from collections import OrderedDict

PM3_SCHEMA = 1
CLASSIC_LENGTHS = (320, 1024, 2048, 4096)


def scan(data):
    """Offline fallback. Manufacturer decoders run only in the PM3 client."""
    return {'status': 'NOT TESTED', 'matches': [], 'experimental': [],
            'diagnostics': [], 'fields': [], 'schema': PM3_SCHEMA,
            'reason': 'PM3 analysis unavailable', 'analysis_state': 'unavailable'}


def _pm3_lines(text):
    text = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', str(text or ''))
    for line in text.replace('\r', '\n').splitlines():
        line = re.sub(r'^\[(?:\+|=|#|!!?|\-|\?)\]\s?', '', line).strip()
        if line and not re.search(r'pm3\s*-->|Nikola\.D', line):
            yield line


def parse_pm3_output(text, expected=None, transport_ok=True):
    """Parse observed PM3 text, never reproduce vendor decoding algorithms.

    Retain section/record context and unknown diagnostic text. A successful
    transport, a recognised family and a verified signature are separate facts.
    """
    result = scan(expected)
    lines = list(_pm3_lines(text))
    result['analysis_state'] = 'complete'
    result['reason'] = 'PM3 results; not proof of protection'
    if not transport_ok:
        result.update(analysis_state='transport_error', reason='PM3 command failed')
        return result
    if not lines:
        result.update(analysis_state='empty', reason='PM3 returned no data')
        return result
    joined = '\n'.join(lines)
    if re.search(r"can't find|cannot open|failed to open", joined, re.I):
        result.update(analysis_state='input_error', reason='PM3 cannot open dump')
        return result
    if re.search(r'JSON objects failed|error, json|unexpected token', joined, re.I):
        result.update(analysis_state='input_error', reason='PM3 cannot decode dump')
        return result
    if re.search(r'unknown command|invalid command|unrecognized option', joined, re.I):
        result.update(analysis_state='unsupported', reason='PM3 analysis unsupported')
        return result
    if expected is not None:
        if not isinstance(expected, bytes) or len(expected) not in CLASSIC_LENGTHS:
            result.update(analysis_state='input_error', reason='Invalid Classic dump size')
            return result
        blocks = {}
        for line in lines:
            match = re.search(r'\|\s*(\d+)\s*\|\s*((?:[0-9A-Fa-f]{2}\s+){15}[0-9A-Fa-f]{2})\s*\|', line)
            if match:
                number = int(match.group(1))
                value = bytes.fromhex(match.group(2))
                if number in blocks and blocks[number] != value:
                    result.update(analysis_state='incomplete', reason='PM3 blocks disagree')
                    return result
                blocks[number] = value
        if sorted(blocks) != list(range(len(expected)//16)) or any(
                value != expected[number*16:number*16+16] for number, value in blocks.items()):
            result.update(analysis_state='incomplete', reason='PM3 dump not verified')
            return result
    section = 'PM3'
    active = False
    seen = set()
    family_names = ('Noralsy', 'Comelit', 'Urmet', 'Hexact', 'COGELEC',
                    'Intratone', 'VIGIK', 'PROAC', 'HID PACS', 'RKF')
    skip = ('Called with no save option', 'Hint:', 'background blue', 'cyan =',
            'File size ', 'Loaded ', 'loaded ', 'execute command', 'OFFLINE mode',
            'No history', 'No preferences')
    for line in lines:
        if line.startswith(skip):
            continue
        # Input memory and key tables have their own approved UI owner.
        if '|' in line and (re.match(r'^(?:\d+\s*)?\|', line) or
                            re.match(r'^\d+\s*\|\s*\d+\s*\|', line)):
            continue
        if re.fullmatch(r'[-+| ]+', line):
            continue
        heading = re.match(r'^-{3,}\s*(.*?)\s*-{3,}(.*)$', line)
        if heading:
            candidate = (heading.group(1) + heading.group(2)).strip()
            if any(name.lower() in candidate.lower() for name in family_names) or active:
                section, active = candidate, True
            else:
                continue
        detected = re.search(r'\bdetected\b|service badge|RKF travel card|^System\.{2,}', line, re.I)
        if detected or heading:
            found = [name for name in family_names if name.lower() in line.lower()]
            if 'VIGIK PACS' in line and 'VIGIK' in found:
                found[found.index('VIGIK')] = 'VIGIK PACS'
            for family in found:
                if family not in result['matches']:
                    result['matches'].append(family)
            if found:
                active = True
                if not heading:
                    section = ' / '.join(found)
        # Keep validity warnings outside a vendor section too.
        warning = re.search(r'invalid|wrong .*CRC|not checked|not verified|mismatch|DISAGREE|no public key|unexpected behavior', line, re.I)
        if not active and not warning:
            continue
        if heading:
            continue
        # Preserve context of repeated fields in RKF and Wiegand records.
        if re.match(r'^(?:dynamic data|record \d+|element \d+|Trying with a preamble)', line, re.I):
            section = re.sub(r' / (?:dynamic data|record|element|Trying).*$', '', section) + ' / ' + line
        pair = re.match(r'^(.*?)\.{2,}\s*(.*)$', line)
        if not pair:
            pair = re.match(r'^([^:]{1,48}):\s*(.*)$', line)
        if not pair:
            pair = re.match(r'^(\S(?:.*?\S)?)\s{2,}(\S.*)$', line)
        label, value = (pair.group(1).strip(), pair.group(2).strip()) if pair else ('Info', line)
        if not value:
            continue
        identity = (section, label, value)
        if identity in seen:
            continue
        seen.add(identity)
        severity = 'warning' if warning else 'info'
        result['fields'].append({'section': section, 'label': label, 'value': value, 'severity': severity})
        # Existing native layouts paginate every diagnostic without truncation.
        result['diagnostics'].append(section + ' / ' + label + ': ' + value)
    result['status'] = 'MATCH' if result['matches'] else 'NO MATCH'
    result['signature_state'] = ('not_verified' if 'no public key recovered a valid block' in joined else 'not_reported')
    result['mad_crc_state'] = ('invalid' if re.search(r'Wrong MAD.*CRC|MAD CRC.*invalid', joined, re.I)
                               else 'unchecked' if re.search(r'Overriding crc check', joined, re.I) else 'not_reported')
    return result


def pm3_version_details(text):
    """Keep client and device revisions separate; absent fields stay unknown."""
    details = {'client': None, 'bootrom': None, 'os': None, 'model': None,
               'mismatch_reported': False, 'nikola': None}
    section = ''
    for raw in str(text or '').splitlines():
        line = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', raw).strip()
        if re.fullmatch(r'\[\s*(Client|ARM|Model|FPGA|Hardware)\s*\]', line, re.I):
            section = line.strip('[] ').lower()
            continue
        if section == 'client' and details['client'] is None and line:
            details['client'] = line
        for label, key in (('Bootrom', 'bootrom'), ('OS', 'os'), ('Firmware', 'model'), ('NIKOLA', 'nikola')):
            separator = r':' if key == 'nikola' else r'[.:]+'
            match = re.match(r'(?:\[[^]]+\]\s*)?' + label + separator + r'\s*(.+)', line, re.I)
            if match:
                details[key] = match.group(1)
        if 'firmware does not match' in line.lower():
            details['mismatch_reported'] = True
    return details


def pm3_firmware_family(text):
    details = pm3_version_details(text)
    # Match the documented factory signature, not the Nikola.D command trailer.
    nikola = details['nikola'] or ''
    os_version = details['os'] or ''
    if (re.match(r'^v3\.1(?:\s|$)', nikola) and
            '2022-06-09' in nikola and '385d892f' in os_version):
        return 'legacy_1090'
    if not nikola and 'iceman' in os_version.lower() and '385d892f' not in os_version:
        return 'iceman'
    return 'unknown'


class PM3Analysis:
    """Device-side command adapter; no firmware/framework mutations."""
    MAX_OUTPUT = 1024 * 1024

    def __init__(self, host, executor_module=None):
        self.host = host
        self.executor = executor_module
        self.capabilities = None
        self.firmware_family = 'unknown'
        self.cache = OrderedDict()
        self.lock = threading.RLock()

    def check_firmware(self):
        """Worker-only startup probe; never infer a revision from transport status."""
        try:
            ok, output = self.host.pm3_command('hw version', timeout=8000)
            self.firmware_family = pm3_firmware_family(output) if ok else 'unknown'
        except Exception as exc:
            self.firmware_family = 'unknown'
        return self.firmware_family


    def _command(self, cmd, timeout=15000):
        raw = ['']
        oversized = [False]
        def capture(text):
            text = str(text or '')
            previous = raw[0]
            if text.startswith(previous):
                current = text
            elif previous.endswith(text):
                current = previous
            else:
                current = previous + '\n' + text
            if len(current) > self.MAX_OUTPUT:
                oversized[0] = True
                current = current[:self.MAX_OUTPUT]
            raw[0] = current
        self.executor.add_task_call(capture)
        try:
            ok, output = self.host.pm3_command(cmd, timeout=timeout)
        finally:
            self.executor.del_task_call(capture)
        # Raw capture is required: cleaned cache may have lost section headers.
        text = raw[0]
        valid = bool(ok and text and not oversized[0])
        return valid, text

    def analyze(self, data, cancelled=None):
        data = bytes(data)
        if len(data) not in CLASSIC_LENGTHS:
            raise ValueError('Invalid Classic dump size')
        if self.firmware_family == 'legacy_1090':
            result = scan(data)
            result.update(analysis_state='unsupported', reason='Anti-Clone analysis unavailable.')
            return result
        digest = hashlib.sha256(data).hexdigest()
        with self.lock:
            if digest in self.cache:
                return json.loads(json.dumps(self.cache[digest]))
            result = scan(data)
            event = cancelled or threading.Event()
            if event.is_set():
                return result
            try:
                if self.executor is None:
                    import executor
                    self.executor = executor
                required = ('pm3_operation', 'add_task_call', 'del_task_call')
                if not all(callable(getattr(self.executor, name, None)) for name in required):
                    result['reason'] = 'PM3 raw response unavailable'
                    return result
                if not callable(getattr(self.host, 'pm3_command', None)):
                    return result
                with self.executor.pm3_operation(event):
                    if self.capabilities is None:
                        version_ok, version = self._command('hw version', 8000)
                        help_ok, help_text = self._command('hf mf view -h', 8000)
                        mad_ok, mad_help = self._command('hf mf mad -h', 8000)
                        self.capabilities = {'version': version,
                            'version_details': pm3_version_details(version),
                            'probe_ok': {'hw version': version_ok, 'hf mf view -h': help_ok,
                                         'hf mf mad -h': mad_ok},
                            'view_help': help_text, 'mad_help': mad_help,
                            'view': bool(help_ok and '--selftest' in help_text and ('--file' in help_text or '-f' in help_text)),
                            'mad': bool(mad_ok and ('--file' in mad_help or '-f' in mad_help))}
                        # Failed transport is transient, not a permanent lack of support.
                        if not version_ok or not help_ok:
                            self.capabilities = None
                            result['reason'] = 'PM3 capability check failed'
                            return result
                    if not self.capabilities['view']:
                        result['reason'] = 'PM3 client update required'
                        result['analysis_state'] = 'unsupported'
                        return result
                    with tempfile.TemporaryDirectory(prefix='dd2_pm3_') as directory:
                        path = os.path.join(directory, 'memory.bin')
                        with open(path, 'wb') as stream:
                            stream.write(data)
                        # Generated path contains no user-controlled command syntax.
                        ok, text = self._command('hf mf view -f "' + path + '" -v')
                        result = parse_pm3_output(text, data, ok)
                        if result['analysis_state'] == 'complete' and self.capabilities['mad'] and (
                                'MAD key detected' in text or 'Overriding crc check' in text):
                            mok, mad = self._command('hf mf mad -f "' + path + '" -v')
                            result['mad_crc_state'] = 'not_reported'
                            if mok:
                                for line in _pm3_lines(mad):
                                    if re.search(r'Wrong MAD.*CRC|CRC.*invalid', line, re.I):
                                        result['mad_crc_state'] = 'invalid'
                                        result['diagnostics'].append('MAD / CRC: ' + line)
                                    elif re.search(r'CRC.*(?:ok|valid)', line, re.I) and result['mad_crc_state'] != 'invalid':
                                        result['mad_crc_state'] = 'valid'
                            else:
                                result['diagnostics'].append('MAD: PM3 command failed')
                        result['source'] = {'schema': PM3_SCHEMA, 'sha256': digest,
                                            'client': self.capabilities['version']}
                if event.is_set():
                    return scan(data)
                if result['analysis_state'] == 'complete':
                    self.cache[digest] = result
                    while len(self.cache) > 24:
                        self.cache.popitem(last=False)
            except Exception as exc:
                result = scan(data)
                result['reason'] = 'PM3 analysis unavailable'
            except BaseException as exc:
                cancellation = getattr(self.executor, 'PM3OperationCancelled', None)
                if cancellation is None or not isinstance(exc, cancellation):
                    raise
                result = scan(data)
                result['analysis_state'] = 'cancelled'
            return json.loads(json.dumps(result))


def _mfc_sector(block):
    """Absolute Classic block index -> sector (1K and 4K)."""
    return block // 4 if block < 128 else 32 + (block - 128) // 16


def _sector_trailer(block):
    """Classic sector trailer position, including 4K large sectors."""
    return (block % 4 == 3) if block < 128 else ((block - 128) % 16 == 15)


def _mfc_uid(data):
    """Return a UID only when manufacturer-block BCC validates."""
    if len(data) < 16:
        return None
    if data[4] == (data[0] ^ data[1] ^ data[2] ^ data[3]):
        return data[:4]
    if data[7] == (data[3] ^ data[4] ^ data[5] ^ data[6]):
        return data[:3] + data[4:8]
    return None


def analyze_anticopy(data_a, data_b, reports=None):
    """Compare signatures and changed blocks, without claiming active protection.

    Changed data on two snapshots with the same validated UID is only a
    candidate for dynamic content. It is NOT evidence of a rolling code:
    application data, counters and ordinary updates can change too.
    """
    a, b = reports if reports is not None else (scan(data_a), scan(data_b))
    changed = []
    data_blocks = []
    trailer_blocks = []
    manufacturer_blocks = []
    valid = (isinstance(data_a, bytes) and isinstance(data_b, bytes)
             and len(data_a) == len(data_b)
             and len(data_a) in CLASSIC_LENGTHS)
    if valid:
        for block in range(len(data_a) // 16):
            off = block * 16
            if data_a[off:off+16] != data_b[off:off+16]:
                changed.append((_mfc_sector(block), block))
                if block == 0:
                    manufacturer_blocks.append(block)
                elif _sector_trailer(block):
                    trailer_blocks.append(block)
                else:
                    data_blocks.append(block)
    uid_a = _mfc_uid(data_a) if valid else None
    uid_b = _mfc_uid(data_b) if valid else None
    same_uid = bool(uid_a is not None and uid_a == uid_b)
    dynamic_candidate = bool(same_uid and data_blocks)
    status = ('POSSIBLE' if a['matches'] or b['matches'] else
              ('UNVERIFIED' if a['experimental'] or b['experimental'] else 'UNKNOWN'))
    return {'a': a, 'b': b, 'changed': changed, 'status': status,
            'same_uid': same_uid, 'uid_checked': bool(uid_a and uid_b),
            'data_blocks_changed': data_blocks,
            'trailer_blocks_changed': trailer_blocks,
            'manufacturer_blocks_changed': manufacturer_blocks,
            'dynamic_candidate': dynamic_candidate,
            'comparison_valid': valid}


def anticopy_info_lines(result):
    if not result:
        return ['Anti-Copy: NOT TESTED']
    lines = ['Anti-Copy: ' + result['status']]
    for key in ('a', 'b'):
        obj = result[key]
        lines.append('Dump ' + key.upper() + ': ' + obj['status'])
        for match in obj['matches']:
            lines.append('  ' + match + ' [HEURISTIC]')
        for note in obj.get('diagnostics', []):
            lines.append('  ' + note)
        for match in obj.get('experimental', []):
            lines.append('  ' + match + (' [HEURISTIC]' if match in ('Block0 88 marker', 'Urmet Captiv marker') else ' [UNVERIFIED]'))
    if not result.get('comparison_valid'):
        lines.append('Comparison: NOT TESTED')
    else:
        lines.append('Changed blocks: ' + str(len(result['changed'])))
        lines.append('Data blocks: ' + str(len(result['data_blocks_changed'])))
        lines.append('Sector trailers: ' + str(len(result['trailer_blocks_changed'])))
        lines.append('Manufacturer blocks: ' + str(len(result.get('manufacturer_blocks_changed', []))))
        if result.get('uid_checked') and not result.get('same_uid'):
            lines.append('Different UID: no rolling inference')
        for sector, block in result['changed'][:24]:
            lines.append('S{} B{} changed'.format(sector, block))
        if len(result['changed']) > 24:
            lines.append('... more changes')
    lines += ['PM3 results; not proof of protection']
    return lines

def analyze_mfc(data_a, data_b):
    """Backwards-compatible Stage 1 interface for existing tests."""
    if not isinstance(data_a, bytes) or not isinstance(data_b, bytes):
        raise ValueError('Expected bytes')
    if not data_a or not data_b or len(data_a)%16 or len(data_b)%16:
        raise ValueError('Invalid MIFARE Classic block data')
    if len(data_a)!=len(data_b):
        return {'status':'INCOMPLETE','anti_copy':'UNKNOWN','changed_blocks':[]}
    result=analyze_anticopy(data_a,data_b)
    changes=[]
    for sector,block in result['changed']:
        off=block*16
        changes.append({'sector':sector,'block':block,'a':data_a[off:off+16].hex().upper(),'b':data_b[off:off+16].hex().upper()})
    return {'status':'CHANGED' if changes else 'UNCHANGED',
            'anti_copy':result['status'],'changed_blocks':changes}


##########################################################################
# Required Notice: Copyright ETOILE401 SAS (http://www.lab401.com)
#
# Copyright (c) 2026: ETOILE401 SAS & https://github.com
#
# This software is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this software for commercial purposes.
#
# A copy of the license is available at:
# https://polyformproject.org
#
# This entire header "Required Notice" must remain in place.
##########################################################################

"""Dump Diff 2 - supplementary two-dump security diagnostics.

Independent implementation. Concept inspired by Dump Diff by uaih3k9x.
These tests identify candidate structures; they do not prove Anti-Copy.
"""


def analyze_security(a, b, sequential=False):
    """Inspect MIFARE Classic data blocks, excluding manufacturer/trailers."""
    result = {'sequential': bool(sequential), 'counter': [], 'mirror': []}
    if len(a) != len(b) or len(a) < 64 or len(a) % 16:
        return result
    blocks = len(a) // 16
    if blocks not in (64, 256):  # MIFARE Classic 1K or 4K.
        return result
    def is_trailer(i):
        # Classic 4K: sectors 0-31 have 4 blocks; sectors 32-39 have 16.
        return (i % 4 == 3) if i < 128 else ((i - 128) % 16 == 15)
    data = [i for i in range(blocks) if i != 0 and not is_trailer(i)]
    if sequential:
        # Only a single, isolated byte increasing by one is a weak candidate.
        # Do not interpret arbitrary 16/32-bit overlapping windows as counters.
        for i in data:
            aa, bb = a[i*16:(i+1)*16], b[i*16:(i+1)*16]
            changed = [j for j in range(16) if aa[j] != bb[j]]
            if len(changed) == 1 and (bb[changed[0]] - aa[changed[0]]) == 1:
                result['counter'].append((i, changed[0]))
    # Mirror/complement: require 2-byte matching windows that CHANGE in both
    # dumps and preserve their relationship, to reduce incidental matches.
    changed_blocks = [i for i in data if a[i*16:(i+1)*16] != b[i*16:(i+1)*16]] if sequential else []
    for pos, i in enumerate(changed_blocks):
        for j in changed_blocks[pos+1:]:
            for off in range(15):
                x0, x1 = a[i*16+off:i*16+off+2], b[i*16+off:i*16+off+2]
                if x0 == x1:
                    continue
                for other in range(15):
                    y0, y1 = a[j*16+other:j*16+other+2], b[j*16+other:j*16+other+2]
                    if y0 == y1:
                        continue
                    if (x0 == y0 and x1 == y1) or (bytes(v ^ 255 for v in x0) == y0 and bytes(v ^ 255 for v in x1) == y1):
                        result['mirror'].append((i, j))
                        break
                if result['mirror'] and result['mirror'][-1] == (i, j):
                    break
    return result


def security_info_lines(report, enabled):
    lines = ['Security analysis']
    if not enabled:
        lines.extend(['Sequential: OFF', 'Counter: Disabled', 'Mirror: Disabled'])
    else:
        lines.append('Sequential: ELIGIBLE')
        lines.append('Counter: {} cand.'.format(len(report.get('counter', []))))
        lines.append('Mirror: {} cand.'.format(len(report.get('mirror', []))))
        for block, offset in report.get('counter', [])[:4]:
            lines.append('B{} byte{}: +1'.format(block, offset))
        for left, right in report.get('mirror', [])[:3]:
            lines.append('Mirror B{} / B{}'.format(left, right))
    lines.append('HEURISTIC - NOT PROOF')
    return lines


"""Read-only multi-capture comparison for Dump Diff 2.

No claims of cryptographic cloneability are made from dump differences.
"""

def analyze_sequence(captures, block_size, uid=None):
    if len(captures) < 3:
        raise ValueError('At least three complete captures required')
    if block_size not in (8, 16):
        raise ValueError('Unsupported block size')
    if any(not isinstance(c, (bytes, bytearray)) or not c or len(c) % block_size for c in captures):
        raise ValueError('Invalid capture')
    if len({len(c) for c in captures}) != 1:
        raise ValueError('Capture lengths differ')
    nblocks = len(captures[0]) // block_size
    changed = []
    details = []
    for block in range(nblocks):
        vals = [bytes(c[block*block_size:(block+1)*block_size]) for c in captures]
        if len(set(vals)) > 1:
            changed.append(block)
            details.append((block, vals))
    counters = []
    # Heuristic only: a 1-, 2- or 4-byte field strictly increments by +1 or -1
    # across every capture. Check both byte orders; no crypto conclusions.
    for block, vals in details:
        for width in (1, 2, 4):
            for pos in range(block_size-width+1):
                for order in ('big', 'little'):
                    numbers = [int.from_bytes(v[pos:pos+width], order) for v in vals]
                    steps = [b-a for a,b in zip(numbers, numbers[1:])]
                    if (steps and steps[0] in (1, -1) and all(x in (1, -1) for x in steps)
                            and all(all(a[i] == b[i] for i in range(block_size)
                                        if not pos <= i < pos+width)
                                    for a,b in zip(vals,vals[1:]))):
                        counters.append({'block':block, 'offset':pos, 'width':width,
                                         'endian':order, 'step':steps[0], 'steps':steps, 'alternating':all(x == -steps[i-1] for i,x in enumerate(steps) if i>0)})
    # A 16-bit and 32-bit interpretation of the same changed bytes must
    # not be reported as two independent counters. Prefer wider field.
    unique=[]
    for c in sorted(counters,key=lambda c:(c['block'],c['offset'],-c['width'])):
        covered=set(range(c['offset'],c['offset']+c['width']))
        if any(p['block']==c['block'] and p['step']==c['step'] and
               p['endian']==c['endian'] and covered.issubset(
                   range(p['offset'],p['offset']+p['width'])) for p in unique):
            continue
        unique.append(c)
    counters=unique
    return {'scans':len(captures), 'blocks':nblocks, 'changed':changed,
            'details':details, 'possible_counters':counters,
            'identical':not changed, 'uid':uid}


# Integrated MIFARE Classic structural analysis
"""Read-only MIFARE Classic structural checks (not a proof of authenticity)."""

SIZES = {320: 'Mini', 1024: '1K', 2048: '2K', 4096: '4K'}

def trailer_blocks(size):
    """Classic sector geometry; 2K treated as 32 x 4-block sectors."""
    if size not in SIZES:
        return []
    blocks = size // 16
    return [i for i in range(blocks) if
            (i % 4 == 3 if i < 128 else (i - 128) % 16 == 15)]

def analyze_mfc_structure(data):
    if not isinstance(data, (bytes, bytearray)) or len(data) not in SIZES:
        return {'supported': False, 'reason': 'Unsupported Classic memory size'}
    data = bytes(data)
    trailers = trailer_blocks(len(data))
    access_invalid = []
    for block in trailers:
        b6,b7,b8 = data[block*16+6:block*16+9]
        valid = (((b6 >> 4) ^ (b7 >> 4)) == 15 and
                 ((b6 & 15) ^ (b8 & 15)) == 15 and
                 ((b7 & 15) ^ (b8 >> 4)) == 15)
        if not valid: access_invalid.append(block)
    values=[]
    for block in range(len(data)//16):
        if block == 0 or block in trailers: continue
        b = data[block*16:(block+1)*16]
        if (b[:4] == b[8:12] and
            all((b[i] ^ b[i+4]) == 255 for i in range(4)) and
            b[12] == b[14] and b[13] == b[15] and
            (b[12] ^ b[13]) == 255):
            values.append(block)
    return {'supported': True, 'variant': SIZES[len(data)],
            'blocks': len(data)//16, 'sectors': len(trailers),
            'trailers': trailers, 'access_invalid': access_invalid,
            'access_checked': len(trailers), 'value_blocks': values,
            'bcc0': (data[0]^data[1]^data[2]^data[3]) == data[4],
            'bcc0_note': '4-byte UID BCC candidate only'}

MFC_SIZES = SIZES


"""Shared Auto Scan report results, used by saved logs and MIFARE Details."""

def sequential(captures, candidates):
    """Require >=3 full scans; every step is +1 or -1.

    Counter width/endian remain hypotheses; no cryptographic conclusions.
    """
    found=[]
    if len(captures)<3:return found
    for c in candidates or []:
        if not isinstance(c,dict):continue
        try:
            block,offset,width=int(c['block']),int(c['offset']),int(c['width'])
            endian=str(c['endian'])
            if width not in (1,2,4) or endian not in ('big','little') or not 0<=offset<=16-width:continue
            start=block*16+offset
            if start<0 or any(len(raw)<start+width for raw in captures):continue
            vals=[int.from_bytes(raw[start:start+width],endian) for raw in captures]
            diffs=[b-a for a,b in zip(vals,vals[1:])]
            if diffs and diffs[0] in (-1,1) and all(d in (-1,1) for d in diffs):
                found.append({'block':block,'offset':offset,'width':width,'endian':endian,
                              'values':vals,'steps':diffs,'status':'ON', 'counter_rollback':len(set(vals))<len(vals)})
        except (ValueError,TypeError,KeyError,OverflowError):continue
    return found

def complete(captures,result):
    result=dict(result or {})
    if not captures:return result
    if any(len(x)!=len(captures[0]) for x in captures):raise ValueError('Inconsistent scan sizes')
    first=captures[0]
    changed=[i for i in range(len(first)) if any(x[i]!=first[i] for x in captures[1:])]
    result['changed_bytes']=changed
    result['changed_blocks']=sorted({i//16 for i in changed})
    result['scans']=len(captures)
    result['blocks']=len(first)//16
    result['sequential_candidates']=sequential(captures,result.get('possible_counters'))
    result['sequential_status']='ON' if result['sequential_candidates'] else 'OFF'
    result['mirror_status']='NOT TESTED'
    return result


def valid_snapshot(captures, result):
    """Validate stored UI fields without inventing or recomputing findings."""
    def integer(x):
        return isinstance(x,int) and not isinstance(x,bool)
    if not isinstance(result,dict) or result.get('scans') != len(captures):
        return False
    size=len(captures[0]);blocks=size//16
    metadata=result.get('scan_metadata')
    if metadata is not None:
        if not isinstance(metadata,list) or len(metadata)!=len(captures):return False
        if any(not isinstance(row,dict) or any(not isinstance(k,str) or not isinstance(v,str) for k,v in row.items()) for row in metadata):return False
    for key,limit in (('changed_bytes',size),('changed_blocks',blocks)):
        values=result.get(key,[])
        if not isinstance(values,list) or any(not integer(x) or not 0<=x<limit for x in values):
            return False
    ac=result.get('anti_copy',{})
    if not isinstance(ac,dict):return False
    for key in ('matches','experimental','diagnostics'):
        vals=ac.get(key,[])
        if not isinstance(vals,list) or any(not isinstance(x,(str,dict)) for x in vals):return False
    for key in ('possible_counters','sequential_candidates'):
        counters=result.get(key,[])
        if not isinstance(counters,list):return False
        for item in counters:
            if not isinstance(item,dict):return False
            if not all(integer(item.get(k)) for k in ('block','offset','width')):return False
            if not 0<=item['block']<blocks or item['width'] not in (1,2,4):return False
            if not 0<=item['offset']<=16-item['width'] or item.get('endian') not in ('little','big'):return False
            if 'step' in item and not integer(item['step']):return False
            if key=='sequential_candidates':
                if item.get('status')!='ON':return False
                vals=item.get('values');steps=item.get('steps')
                if not isinstance(vals,list) or len(vals)!=len(captures) or not all(integer(v) for v in vals):return False
                if not isinstance(steps,list) or len(steps)!=len(captures)-1 or not all(integer(v) and v in (-1,1) for v in steps):return False
                start=item['block']*16+item['offset']
                actual=[int.from_bytes(raw[start:start+item['width']],item['endian']) for raw in captures]
                if vals!=actual or steps!=[b-a for a,b in zip(actual,actual[1:])]:return False
                if len(captures)<3:return False
    return True
