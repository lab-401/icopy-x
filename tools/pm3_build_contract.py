#!/usr/bin/env python3
"""Fail closed on iCopy-X client/FPGA mismatches. Python 3.5+ for Xenial.

This checks build outputs and records the upstream bitstream input. It does
not synthesize Verilog or prove the hardware behavior of a bitstream.
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess


PLATFORM = 'PM3ICOPYX'
FPGA_PART = '3s100evq100'
BITSTREAM = 'fpga/fpga_icopyx_hf.bit'
PATCH_GROUPS = {
    'fpga': ('pm3_client_icopyx_xc3.patch',),
    'response-delimiter': ('pm3_eor_marker.patch',),
    'pipe-progress': ('pm3_suppress_inplace.patch',),
    'selection-diagnostic': ('pm3_14a_select_warning.patch',
                             'pm3_14a_select_warning_modern.patch'),
}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def revision(source, expected):
    require(re.fullmatch(r'[0-9a-f]{40}', expected) is not None, 'Expected a full PM3 commit')
    actual = subprocess.check_output(
        ['git', '-C', str(source), 'rev-parse', 'HEAD'], universal_newlines=True).strip()
    require(actual == expected, 'PM3 checkout differs from the resolved commit')
    return actual


def apply_group(source, patches, group):
    choices = []
    diagnostics = []
    for patch in patches:
        require(patch.is_file(), 'Missing required patch: ' + str(patch))
        for flags, state in (([], 'applied'), (['--reverse'], 'already-present')):
            result = subprocess.run(['git', '-C', str(source), 'apply', '--check'] +
                                    flags + [str(patch.resolve())],
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    universal_newlines=True)
            if result.returncode == 0:
                choices.append((patch, state))
                break
            diagnostics.append(result.stdout.strip())
    require(len(choices) == 1,
            'Required patch group {} has {} matches; review upstream changes.\n{}'.format(
                group, len(choices), '\n'.join(diagnostics)))
    patch, state = choices[0]
    if state == 'applied':
        subprocess.check_call(['git', '-C', str(source), 'apply', str(patch.resolve())])
    print('{}: {} ({})'.format(group, patch.name, state))
    return dict(group=group, patch=patch.name, sha256=sha256(patch), state=state)


def prepare_client(source, patch_dir, profile, commit):
    revision(source, commit)
    patch_dir = Path(patch_dir)
    known = {p for group in PATCH_GROUPS.values() for p in group}
    # Device builds disable readline; companion builds use modern readline.
    # This old compatibility patch is intentionally unnecessary in both profiles.
    known.add('pm3_readline_compat.patch')
    unknown = {p.name for p in patch_dir.glob('pm3_*.patch')} - known
    require(not unknown, 'Unclassified PM3 patches: ' + repr(sorted(unknown)))
    groups = ('fpga',) if profile == 'companion' else tuple(PATCH_GROUPS)
    applied = [apply_group(source, [patch_dir/p for p in PATCH_GROUPS[group]], group)
               for group in groups]
    write_json(Path(source)/'.icopy-client-patches.json',
               dict(source_commit=commit, profile=profile, patches=applied))


def check_client(path):
    # FPGA_TYPE is a standalone C string in each supported ELF/PE/Mach-O client.
    # Requiring the right value and rejecting both legacy targets catches the
    # actual v1.1.7 regression, independently of whether a patch reported success.
    data = Path(path).read_bytes()
    require(b'\0' + FPGA_PART.encode() + b'\0' in data,
            'Client lacks the iCopy-X FPGA identifier')
    for wrong in (b'2s30vq100', b'2s50vq144'):
        require(b'\0' + wrong + b'\0' not in data,
                'Client contains an incompatible FPGA identifier')


def bitstream_part(data):
    """Read the part field from a Xilinx .bit header, with bounded lengths."""
    offset = 0

    def take(size):
        nonlocal offset
        require(offset + size <= len(data), 'Truncated FPGA bitstream')
        result = data[offset:offset + size]
        offset += size
        return result

    def word():
        return struct.unpack('>H', take(2))[0]

    require(take(word()) == b'\x0f\xf0\x0f\xf0\x0f\xf0\x0f\xf0\x00',
            'Invalid Xilinx bitstream header')
    require(word() == 1, 'Invalid Xilinx header marker')
    fields = {}
    for tag in (b'a', b'b', b'c', b'd'):
        require(take(1) == tag, 'Unexpected Xilinx header field')
        value = take(word())
        require(value.endswith(b'\0'), 'Unterminated Xilinx header field')
        fields[tag] = value[:-1].decode('ascii')
    require(take(1) == b'e', 'Missing FPGA configuration payload')
    size = struct.unpack('>I', take(4))[0]
    require(size > 0 and offset + size == len(data), 'Invalid FPGA payload length')
    return fields[b'b']


def check_firmware(path):
    data = Path(path).read_bytes()
    require(data.startswith(b'\x7fELF'), 'Firmware is not an ELF image')
    identities = re.findall(rb'(fpga_[^\x00\s]+\.ncd) image ([^\x00\s]+)', data)
    require(identities == [(b'fpga_icopyx_hf.ncd', FPGA_PART.encode())],
            'Firmware FPGA version table does not identify one iCopy-X image')


def write_json(path, record):
    Path(path).write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')


def client_record(source, commit, tag, binary, output, lua=None):
    revision(source, commit)
    check_client(binary)
    record = dict(source_commit=commit, source_tag=tag, build_platform=PLATFORM,
                  fpga_part=FPGA_PART, client_sha256=sha256(binary))
    patches = json.loads((Path(source)/'.icopy-client-patches.json').read_text(encoding='utf-8'))
    require(patches['source_commit'] == commit, 'Patch provenance mismatch')
    record['patches'] = patches
    if lua is not None:
        record['lua_sha256'] = sha256(lua)
    write_json(output, record)


def firmware_record(source, commit, tag, binary, output):
    revision(source, commit)
    bitstream = Path(source) / BITSTREAM
    require(bitstream_part(bitstream.read_bytes()) == FPGA_PART,
            'Upstream bitstream targets the wrong FPGA')
    check_firmware(binary)
    record = dict(pm3_firmware_version=tag, pm3_client_version=tag,
                  pm3_firmware_sha256=sha256(binary), build_platform=PLATFORM,
                  build_date=datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
                  source_commit=commit, fpga_part=FPGA_PART,
                  fpga_input=dict(path=BITSTREAM, sha256=sha256(bitstream),
                                  origin='upstream-prebuilt-bitstream'))
    write_json(output, record)


def assemble(client, client_metadata, firmware, firmware_metadata, lua, output):
    c = json.loads(Path(client_metadata).read_text(encoding='utf-8'))
    f = json.loads(Path(firmware_metadata).read_text(encoding='utf-8'))
    check_client(client)
    check_firmware(firmware)
    require(c['build_platform'] == f['build_platform'] == PLATFORM, 'Platform mismatch')
    require(c['fpga_part'] == f['fpga_part'] == FPGA_PART, 'FPGA metadata mismatch')
    require(re.fullmatch(r'[0-9a-f]{40}', c['source_commit']) is not None,
            'Missing full PM3 source commit')
    require(c['source_commit'] == f['source_commit'], 'Client/firmware source mismatch')
    require(c['source_tag'] == f['pm3_firmware_version'] == f['pm3_client_version'],
            'Client/firmware version mismatch')
    require(c['client_sha256'] == sha256(client), 'Client artifact hash mismatch')
    require(c['lua_sha256'] == sha256(lua), 'Client Lua artifact hash mismatch')
    require(f['pm3_firmware_sha256'] == sha256(firmware), 'Firmware artifact hash mismatch')
    f['pm3_client_sha256'] = c['client_sha256']
    f['pm3_lua_sha256'] = c['lua_sha256']
    write_json(output, f)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command')
    for name in ('prepare-client', 'client', 'firmware'):
        p = sub.add_parser(name)
        p.add_argument('--source', required=True)
        p.add_argument('--commit', required=True)
        if name == 'prepare-client':
            p.add_argument('--patch-dir', required=True)
            p.add_argument('--profile', choices=('device', 'companion'), required=True)
        else:
            p.add_argument('--tag', required=True)
            p.add_argument('--binary', required=True)
            p.add_argument('--output', required=True)
            if name == 'client':
                p.add_argument('--lua')
    p = sub.add_parser('assemble')
    for field in ('client', 'client-metadata', 'firmware', 'firmware-metadata', 'lua', 'output'):
        p.add_argument('--' + field, required=True)
    args = vars(parser.parse_args())
    command = args.pop('command')
    actions = {'prepare-client': prepare_client, 'client': client_record,
               'firmware': firmware_record, 'assemble': assemble}
    require(command in actions, 'Choose a build contract command')
    actions[command](**args)


if __name__ == '__main__':
    main()
