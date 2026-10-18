"""Build failures must stop publication, including the historical FPGA mismatch."""
import importlib.util
import json
from pathlib import Path
import struct
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('pm3_build_contract', ROOT/'tools/pm3_build_contract.py')
contract = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(contract)


@pytest.fixture
def source(tmp_path):
    path = tmp_path/'source'
    (path/'client').mkdir(parents=True)
    (path/'client/Makefile').write_bytes(
        b'ifeq ($(PLATFORM),PM3ICOPYX)\n  INCLUDES += -DICOPYX\nendif\n')
    subprocess.run(['git', 'init', str(path)], check=True, capture_output=True)
    subprocess.run(['git', '-C', str(path), 'add', '.'], check=True)
    subprocess.run(['git', '-C', str(path), '-c', 'user.name=Build Test',
                    '-c', 'user.email=build@example.invalid', 'commit', '-m', 'fixture'],
                   check=True, capture_output=True)
    return path


def commit(source):
    return subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()


def test_required_patch_applies_and_accepts_already_present_fix(source):
    patch = ROOT/'tools/patches/pm3_client_icopyx_xc3.patch'
    first = contract.apply_group(source, [patch], 'fpga')
    assert first['state'] == 'applied'
    assert '-DICOPYX -DXC3' in (source/'client/Makefile').read_text()
    assert contract.apply_group(source, [patch], 'fpga')['state'] == 'already-present'


def test_changed_upstream_context_fails_loudly(source):
    (source/'client/Makefile').write_text('a different upstream build system\n')
    with pytest.raises(ValueError, match='Required patch group fpga has 0 matches'):
        contract.apply_group(source, [ROOT/'tools/patches/pm3_client_icopyx_xc3.patch'], 'fpga')


def test_ambiguous_variants_are_not_silently_selected(source):
    patch = ROOT/'tools/patches/pm3_client_icopyx_xc3.patch'
    with pytest.raises(ValueError, match='has 2 matches'):
        contract.apply_group(source, [patch, patch], 'fpga')
    assert '-DXC3' not in (source/'client/Makefile').read_text()


def test_missing_patch_and_moved_source_fail(source):
    with pytest.raises(ValueError, match='Missing required patch'):
        contract.apply_group(source, [source/'missing.patch'], 'fpga')
    with pytest.raises(ValueError, match='differs from the resolved commit'):
        contract.revision(source, '0'*40)


def test_new_unclassified_patch_requires_review(source, tmp_path):
    patches = tmp_path/'patches'
    patches.mkdir()
    (patches/'pm3_new.patch').write_text('not classified')
    with pytest.raises(ValueError, match='Unclassified PM3 patches'):
        contract.prepare_client(source, patches, 'companion', commit(source))


@pytest.mark.parametrize('data', [b'', b'\0' + b'2s30vq100\0', b'\0' + b'2s50vq144\0',
                                b'\0' + b'3s100evq100\0' + b'2s30vq100\0'])
def test_wrong_or_mixed_client_identifiers_fail(tmp_path, data):
    binary = tmp_path/'client'
    binary.write_bytes(data)
    with pytest.raises(ValueError, match='FPGA identifier'):
        contract.check_client(binary)


def bitstream(part=b'3s100evq100'):
    def field(tag, value):
        return tag+struct.pack('>H', len(value)+1)+value+b'\0'
    return (b'\x00\x09\x0f\xf0\x0f\xf0\x0f\xf0\x0f\xf0\x00\x00\x01' +
            field(b'a', b'fpga_icopyx_hf.ncd') + field(b'b', part) +
            field(b'c', b'FFFFFFFFFF') + field(b'd', b'FFFFFFFF') +
            b'e\x00\x00\x00\x04DATA')


@pytest.mark.parametrize('data', [b'', bitstream()[:-1], bitstream()+b'extra',
                                bitstream().replace(b'\x00\x01a', b'\x00\x01x')])
def test_invalid_bitstream_is_not_accepted(tmp_path, data):
    with pytest.raises(ValueError):
        contract.bitstream_part(data)


def test_bitstream_reads_actual_part_field():
    assert contract.bitstream_part(bitstream()) == '3s100evq100'
    assert contract.bitstream_part(bitstream(b'2s30vq100')) == '2s30vq100'


@pytest.fixture
def bundle(source, tmp_path):
    sha = commit(source)
    contract.prepare_client(source, ROOT/'tools/patches', 'companion', sha)
    binary = tmp_path/'proxmark3'
    binary.write_bytes(b'\x7fELF\0' + b'3s100evq100\0')
    lua = tmp_path/'lua.zip'
    lua.write_bytes(b'lua archive fixture')
    firmware = tmp_path/'fullimage.elf'
    firmware.write_bytes(b'\x7fELF\0fpga_icopyx_hf.ncd image 3s100evq100 timestamp\0')
    (source/'fpga').mkdir()
    (source/contract.BITSTREAM).write_bytes(bitstream())
    cm, fm, output = [tmp_path/p for p in ('client.json', 'firmware.json', 'combined.json')]
    contract.client_record(source, sha, 'v4.test', binary, cm, lua)
    contract.firmware_record(source, sha, 'v4.test', firmware, fm)
    return dict(client=binary, client_metadata=cm, firmware=firmware,
                firmware_metadata=fm, lua=lua, output=output)


def test_matching_build_records_and_artifacts_assemble(bundle):
    contract.assemble(**bundle)
    record = json.loads(bundle['output'].read_text())
    assert record['pm3_client_sha256'] == contract.sha256(bundle['client'])
    assert record['fpga_input']['origin'] == 'upstream-prebuilt-bitstream'
    assert record['fpga_part'] == '3s100evq100'


@pytest.mark.parametrize('artifact', ['client', 'firmware', 'lua'])
def test_changed_artifact_cannot_reuse_old_manifest(bundle, artifact):
    with bundle[artifact].open('ab') as stream:
        stream.write(b'changed')
    with pytest.raises(ValueError, match='hash mismatch'):
        contract.assemble(**bundle)
    assert not bundle['output'].exists()


@pytest.mark.parametrize('key,value', [('source_commit', '0'*40), ('fpga_part', '2s30vq100'),
                                      ('build_platform', 'PM3GENERIC'), ('source_tag', 'v4.other')])
def test_mismatched_build_records_cannot_assemble(bundle, key, value):
    path = bundle['client_metadata']
    record = json.loads(path.read_text()); record[key] = value
    contract.write_json(path, record)
    with pytest.raises(ValueError, match='mismatch'):
        contract.assemble(**bundle)


def test_wrong_firmware_fpga_cannot_be_certified(source, tmp_path):
    (source/'fpga').mkdir()
    (source/contract.BITSTREAM).write_bytes(bitstream(b'2s30vq100'))
    binary = tmp_path/'image'
    binary.write_bytes(b'\x7fELF\0fpga_icopyx_hf.ncd image 3s100evq100 now\0')
    with pytest.raises(ValueError, match='Upstream bitstream targets the wrong FPGA'):
        contract.firmware_record(source, commit(source), 'v4.test', binary, tmp_path/'manifest')
    binary.write_bytes(b'\x7fELF\0fpga_pm3_hf.ncd image 2s30vq100 now\0')
    with pytest.raises(ValueError, match='version table'):
        contract.check_firmware(binary)
