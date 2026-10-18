"""Fixed job executed inside the disposable worker's private namespaces."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys


def main():
    assert os.getuid() == 65534 and os.getgid() == 65534
    status = dict(line.split(':', 1) for line in Path('/proc/self/status').read_text().splitlines())
    assert all(int(status[key].strip(), 16) == 0 for key in
               ('CapEff', 'CapPrm', 'CapInh', 'CapBnd', 'CapAmb'))
    assert os.getgroups() == []
    assert status['NoNewPrivs'].strip() == '1'
    assert not any(key in os.environ for key in ('GITHUB_TOKEN', 'GH_TOKEN', 'SSH_AUTH_SOCK', 'SUDO_USER'))
    assert not Path('/home/runner').exists() and not Path('/home/qx').exists()
    with socket.socket() as probe:
        probe.settimeout(.5)
        assert probe.connect_ex(('1.1.1.1', 443)) != 0, 'Worker has external network access'
    probe = dict(uid=os.getuid(), gid=os.getgid(), effective_capabilities=status['CapEff'].strip(),
                 no_new_privileges=True, external_network=False, host_home_visible=False)
    Path('/work/sandbox.json').write_text(json.dumps(probe, indent=2) + '\n')
    failures = []
    commands = [('/usr/bin/python3', '/harness/tools/qemu_runtime_smoke.py')]
    for variant in ('noflash', 'flash'):
        commands.append(('/usr/bin/python3', '/harness/tools/qemu_artifact_smoke.py',
                         '/artifacts/icopy-x-' + variant + '.ipk', '--variant', variant,
                         '--profile', 'critical'))
    for command in commands:
        result = subprocess.run(command)
        if result.returncode:
            failures.append({'command': list(command), 'returncode': result.returncode})
    Path('/work/job.json').write_text(json.dumps({'status': 'FAIL' if failures else 'PASS',
                                                'failures': failures}, indent=2) + '\n')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
