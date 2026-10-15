import copy
import base64
import json
import os
import tempfile
import uuid
from datetime import datetime, timezone


DEFAULT_DIRECTORY = '/mnt/upan/dump/ics_decoder/credentials'


def _verified_source(capture):
    try:
        import ics_decoder
        raw = base64.b64decode(capture['raw_response_b64'], validate=True)
        text = raw.decode('utf-8', errors='replace')
        if text != capture.get('raw_response_text'):
            return None
        return ics_decoder.parse_block(text, raw)
    except (ImportError, KeyError, TypeError, ValueError):
        return None


def legacy_block(capture):
    if not isinstance(capture, dict) or capture.get('status') in ('malformed', 'decoder_error'):
        return None
    legacy = capture.get('derived_legacy') or {}
    if not isinstance(legacy, dict):
        return None
    if legacy.get('source') != 'decoder_reported':
        return None
    blk7 = legacy.get('blk7')
    fields = capture.get('raw_fields')
    reported = fields.get('blk7') if isinstance(fields, dict) else None
    if not isinstance(blk7, str) or not isinstance(reported, str):
        return None
    if blk7.upper() != reported.replace(' ', '').upper():
        return None
    verified = _verified_source(capture)
    if not verified or verified.get('derived_legacy') != legacy:
        return None
    if isinstance(blk7, str) and len(blk7) == 16 and all(
        character in '0123456789abcdefABCDEF' for character in blk7
    ) and int(blk7, 16) != 0:
        return blk7.upper()
    return None


def validated_h10301(capture):
    if not isinstance(capture, dict) or capture.get('status') != 'decoded':
        return False
    if capture.get('format') != 'H10301 (26-bit)' or capture.get('bit_length') != 26:
        return False
    fc, card_id = capture.get('fc'), capture.get('id')
    if not (isinstance(fc, int) and isinstance(card_id, int) and
            0 <= fc <= 255 and 0 <= card_id <= 65535 and (fc or card_id)):
        return False
    frame = capture.get('wiedata')
    fields = capture.get('raw_fields')
    if not isinstance(fields, dict):
        return False
    if not (isinstance(frame, str) and len(frame) == 26 and
            set(frame) <= {'0', '1'} and
            fields.get('wiedata') == frame and
            fields.get('fc') == str(fc) and fields.get('id') == str(card_id)):
        return False
    verified = _verified_source(capture)
    return bool(verified and verified.get('status') == 'decoded' and
                verified.get('format') == 'H10301 (26-bit)' and
                verified.get('fc') == fc and verified.get('id') == card_id and
                verified.get('wiedata') == frame and
                verified.get('raw_fields') == fields)


def can_write(capture):
    if not isinstance(capture, dict) or capture.get('status') in ('malformed', 'decoder_error'):
        return False
    return bool(legacy_block(capture) or validated_h10301(capture))


def create_record(capture, name=''):
    source_keys = (
        'source_technology', 'bit_length', 'wiedata', 'bits', 'hex',
        'sio_pacs', 'sio_container', 'reported_fc', 'reported_id',
        'raw_fields', 'raw_response_b64', 'raw_response_text',
    )
    decoded_keys = ('format', 'status', 'fc', 'id', 'raw')
    timestamp = datetime.now(timezone.utc).isoformat()
    default_name = 'Credential {}'.format(timestamp[:16].replace('T', ' '))
    return {
        'schema_version': 1,
        'id': str(uuid.uuid4()),
        'name': name.strip() or default_name,
        'saved_at': timestamp,
        'source': {key: copy.deepcopy(capture[key]) for key in source_keys if key in capture},
        'decoded': {key: copy.deepcopy(capture[key]) for key in decoded_keys if key in capture},
        'derived_legacy': copy.deepcopy(capture.get('derived_legacy')),
        'capture': copy.deepcopy(capture),
    }


class SavedCredentials:
    def __init__(self, directory=DEFAULT_DIRECTORY):
        self.directory = directory

    def save(self, capture, name=''):
        record = create_record(capture, name)
        os.makedirs(self.directory, exist_ok=True)
        path = os.path.join(self.directory, record['id'] + '.json')
        payload = json.dumps(record, ensure_ascii=False, sort_keys=True).encode('utf-8')
        fd, temporary = tempfile.mkstemp(prefix='.ics-', suffix='.tmp', dir=self.directory)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return record

    def all(self):
        if not os.path.isdir(self.directory):
            return []
        records = []
        for filename in os.listdir(self.directory):
            if not filename.endswith('.json'):
                continue
            path = os.path.join(self.directory, filename)
            try:
                with open(path, 'r', encoding='utf-8') as stream:
                    record = json.load(stream)
                if (isinstance(record, dict) and
                        filename == record.get('id', '') + '.json' and
                        isinstance(record.get('capture'), dict) and
                        isinstance(record.get('name'), str) and
                        isinstance(record.get('saved_at'), str) and
                        str(uuid.UUID(record['id'])) == record['id']):
                    records.append(record)
            except (OSError, ValueError, TypeError):
                continue
        return sorted(records, key=lambda record: record.get('saved_at', ''), reverse=True)

    def delete(self, record_id):
        if str(uuid.UUID(record_id)) != record_id:
            raise ValueError('Invalid credential ID')
        os.unlink(os.path.join(self.directory, record_id + '.json'))
