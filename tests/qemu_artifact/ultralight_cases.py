"""Finite MFU responses and client-produced files for ARM reader acceptance.

Iceman reply shape follows the 2026-10-18 physical session, with a synthetic
UID and varied payload. Factory text is synthetic; its binary layout follows
the published factory client. No real PM3 or RF executes in these cases.
"""
from strict_transport import Transcript

UID = '04112233445566'


def binary(pages):
    header = bytearray(56)
    header[11] = pages - 1
    data = bytearray((n % 256 for n in range(4 * pages)))
    data[:8] = bytes.fromhex('041122BF33445566')
    return bytes(header + data)


class DumpTranscript(Transcript):
    """Only a matched dump command may produce the scripted file."""
    def __init__(self, steps, path, data):
        super().__init__(steps)
        self.path, self.data = path, data

    def sendall(self, payload):
        super().sendall(payload)
        if not self.steps and self.data is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_bytes(self.data)


def prepare(name, firmware, directory):
    partial = name in ('mfu_read_partial', 'mfu_auto_partial')
    path = directory / ('M0-UL_' + UID + '_1.bin')
    data = binary(8 if partial else 16)
    output = 'Partial dump created. (8 of 16 blocks)\n' if partial else 'Saved 120 bytes to binary file\n'
    if name == 'mfu_read_missing':
        data, output = None, 'Partial dump created. (8 of 16 blocks)\n'
    elif name == 'mfu_read_empty_file':
        data = b''
    elif name == 'mfu_read_truncated':
        data = data[:-4]
    elif name == 'mfu_read_empty_response':
        data, output = None, ''
    command = 'hf mfu dump {} {}'.format('f' if firmware == 'original' else '-f', str(path.with_suffix('')))
    steps = [dict(command='hf 14a info', response='UID: 04 11 22 33 44 55 66\n'
                  'ATQA: 00 44\nSAK: 00\nMIFARE Ultralight\nNikola.D: 0\n'),
             dict(command='hf mfu info', response='TYPE: MIFARE Ultralight (MF0ICU1)\n'
                  'UID: 04 11 22 33 44 55 66\nNikola.D: 0\n'),
             dict(command=command, response=output+'Nikola.D: 0\n')]
    return DumpTranscript(steps, path, data), partial
