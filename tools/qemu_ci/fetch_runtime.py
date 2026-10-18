"""Download one pinned private runtime using an SSH forced-command account."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from unpack_runtime import unpack


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path, help='New runtime extraction directory')
    args = parser.parse_args()
    pin = json.loads(Path(__file__).with_name('runtime_pin.json').read_text())
    host, user = os.environ['QEMU_RUNTIME_HOST'], os.environ['QEMU_RUNTIME_USER']
    if not re.fullmatch('[A-Za-z0-9.-]+', host) or not re.fullmatch('[a-z_][a-z0-9_-]*', user):
        raise ValueError('Invalid runtime server configuration')
    with tempfile.TemporaryDirectory(prefix='icopy-runtime-fetch-') as directory:
        temporary = Path(directory)
        key = temporary / 'key'
        key.write_text(os.environ['QEMU_RUNTIME_KEY'].strip() + '\n')
        key.chmod(0o600)
        known_hosts = temporary / 'known_hosts'
        known_hosts.write_text(os.environ['QEMU_RUNTIME_KNOWN_HOSTS'].strip() + '\n')
        archive = temporary / 'runtime.tar.gz'
        with archive.open('xb') as output:
            subprocess.run(['ssh', '-F', '/dev/null', '-i', str(key),
                            '-o', 'BatchMode=yes', '-o', 'IdentitiesOnly=yes',
                            '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=15',
                            '-o', 'UserKnownHostsFile=' + str(known_hosts),
                            user + '@' + host, 'fetch-' + pin['archive_sha256']],
                           stdout=output, timeout=180, check=True)
        if archive.stat().st_size != pin['archive_bytes']:
            raise ValueError('Runtime archive size mismatch')
        runtime = unpack(archive, args.output, pin['archive_sha256'])
    manifest = json.loads((runtime / 'runtime.json').read_text())
    if any(manifest[key] != pin[key] for key in ('source_image_sha256', 'qemu_sha256')):
        raise ValueError('Runtime provenance mismatch')
    print('Verified pinned factory runtime')


if __name__ == '__main__':
    main()
