"""Run exact IPKs in an offline, non-root namespace on a disposable Linux VM.

This trusted controller must come from the base branch. Candidate application
code runs only inside bubblewrap. It receives no host home, credentials, devices,
network, writable source tree or privileged capabilities.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import stat
import subprocess
import sys
import time
import uuid


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def read_guest_file(root, relative, limit=2 * 1024 * 1024):
    """Never follow a guest-controlled symlink when collecting host evidence."""
    parts = Path(relative).parts
    if not parts or Path(relative).is_absolute() or '..' in parts:
        raise ValueError('Invalid evidence path')
    fd = os.open(str(root), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts[:-1]:
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        file_fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        with os.fdopen(file_fd, 'rb') as source:
            metadata = os.fstat(source.fileno())
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > limit:
                raise ValueError('Oversized or non-regular evidence file')
            data = source.read(limit + 1)
            if len(data) > limit:
                raise ValueError('Evidence exceeded size bound while reading')
            return data
    finally:
        os.close(fd)


def command(runtime, artifacts, harness, work):
    rootfs = '/mnt/sdcard/root2/root'
    tcl_root = '/mnt/sdcard/root2/root/usr/share/tcltk'
    if not (runtime / 'sdcard/root2/root/usr/share/tcltk/tcl8.6').is_dir():
        tcl_root = '/mnt/sdcard/root1/usr/share/tcltk'
    env = {
        'PATH': '/usr/bin:/bin', 'HOME': '/tmp', 'LC_ALL': 'C.UTF-8', 'TZ': 'UTC',
        'PROJECT': '/harness', 'ICOPY_QEMU_RUN': '/work',
        'QEMU_BIN': '/runtime/qemu-arm-static', 'QEMU_LD_PREFIX': rootfs,
        'QEMU_PYTHON': rootfs + '/usr/local/python-3.8.0/bin/python3.8',
        'QEMU_SET_ENV': 'LD_LIBRARY_PATH=' + ':'.join((
            rootfs + '/usr/local/python-3.8.0/lib', rootfs + '/usr/lib/arm-linux-gnueabihf',
            rootfs + '/lib/arm-linux-gnueabihf', '/mnt/sdcard/root1/usr/lib/arm-linux-gnueabihf',
            '/mnt/sdcard/root1/lib/arm-linux-gnueabihf')),
        'FONTCONFIG_FILE': '/work/fonts.conf', 'XDG_CACHE_HOME': '/tmp/cache',
        'PYTHONDONTWRITEBYTECODE': '1', 'SDL_AUDIODRIVER': 'dummy',
        'TCL_LIBRARY': tcl_root + '/tcl8.6', 'TK_LIBRARY': tcl_root + '/tk8.6',
    }
    args = ['bwrap', '--unshare-pid', '--unshare-net', '--unshare-ipc', '--unshare-uts',
            '--unshare-cgroup-try', '--die-with-parent', '--new-session',
            '--cap-drop', 'ALL', '--cap-add', 'CAP_SETUID', '--cap-add', 'CAP_SETGID',
            '--cap-add', 'CAP_SETPCAP', '--clearenv',
            '--ro-bind', '/usr', '/usr', '--symlink', 'usr/bin', '/bin',
            '--symlink', 'usr/lib', '/lib', '--symlink', 'usr/lib64', '/lib64',
            '--proc', '/proc', '--dev', '/dev', '--perms', '1777', '--tmpfs', '/tmp',
            '--dir', '/etc', '--dir', '/mnt', '--dir', '/mnt/sdcard',
            '--perms', '1777', '--tmpfs', '/mnt/upan',
            '--ro-bind', str(runtime), '/runtime',
            '--ro-bind', str(runtime / 'sdcard'), '/mnt/sdcard',
            '--ro-bind', str(harness), '/harness', '--ro-bind', str(artifacts), '/artifacts',
            '--bind', str(work), '/work', '--chdir', '/work']
    for key, value in env.items():
        args.extend(('--setenv', key, value))
    # Root sets up mounts only. This trusted executable drops identity and every
    # capability before Python, QEMU or package code can execute.
    args.extend(('--', '/usr/bin/setpriv', '--reuid=65534', '--regid=65534',
                 '--clear-groups', '--bounding-set=-all', '--inh-caps=-all',
                 '--ambient-caps=-all', '/usr/bin/python3', '/harness/tools/qemu_ci/guest_job.py'))
    return args


def limits():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_FSIZE, (64 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', required=True, type=Path)
    parser.add_argument('--artifacts', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path, help='New result directory')
    parser.add_argument('--timeout', type=int, default=300)
    args = parser.parse_args(argv)
    if os.geteuid() != 0:
        parser.error('Trusted namespace setup requires sudo; candidate code runs as uid 65534')
    if not 1 <= args.timeout <= 600:
        parser.error('Timeout must be between 1 and 600 seconds')
    runtime, artifacts, output = (path.resolve() for path in (args.runtime, args.artifacts, args.output))
    harness = Path(__file__).resolve().parents[2]
    runtime_info = json.loads((runtime / 'runtime.json').read_text())
    assert sha256(runtime / 'qemu-arm-static') == runtime_info['qemu_sha256']
    package_hashes = {v: sha256(artifacts / ('icopy-x-' + v + '.ipk')) for v in ('flash', 'noflash')}
    output.mkdir(exist_ok=False)
    work, evidence = output / 'work', output / 'evidence'
    work.mkdir()
    evidence.mkdir()
    (work / 'results').mkdir()
    os.chown(work, 65534, 65534)
    os.chown(work / 'results', 65534, 65534)
    (work / 'fonts.conf').write_text('<fontconfig><dir>/mnt/sdcard/root2/root/home/pi/ipk_app_main/res/font</dir><cachedir>/tmp/font-cache</cachedir></fontconfig>\n')
    report = dict(status='INCOMPLETE', artifact_sha256=package_hashes,
                  runtime_image_sha256=runtime_info['source_image_sha256'],
                  qemu_sha256=runtime_info['qemu_sha256'], controller_sha256=sha256(Path(__file__)))
    pin = json.loads(Path(__file__).with_name('runtime_pin.json').read_text())
    if any(runtime_info[key] != pin[key] for key in ('source_image_sha256', 'qemu_sha256')):
        raise ValueError('Unexpected runtime identity')
    report['runtime_archive_sha256'] = pin['archive_sha256']
    started = time.monotonic()
    process = None
    unit = 'icopy-qemu-' + uuid.uuid4().hex + '.scope'
    try:
        with (evidence / 'worker.log').open('wb') as log:
            args_worker = ['systemd-run', '--quiet', '--scope', '--unit', unit,
                           '-p', 'MemoryMax=2G', '-p', 'TasksMax=128', '-p', 'CPUQuota=200%']
            args_worker += command(runtime, artifacts, harness, work)
            process = subprocess.Popen(args_worker, preexec_fn=limits,
                                       start_new_session=True, stdout=log, stderr=subprocess.STDOUT)
            report['returncode'] = process.wait(timeout=args.timeout)
        if report['returncode'] != 0:
            raise RuntimeError('Isolated worker failed with exit ' + str(report['returncode']))
        for relative in ('sandbox.json', 'job.json', 'results/runtime.json'):
            data = read_guest_file(work, relative)
            (evidence / relative.replace('/', '--')).write_bytes(data)
            parsed = json.loads(data)
            if relative != 'sandbox.json' and parsed.get('status') != 'PASS':
                raise RuntimeError('Missing successful report: ' + relative)
            if relative == 'results/runtime.json' and (not parsed['python'].startswith(pin['python'] + ' ') or
                    parsed['tcl'] != pin['tcl'] or parsed['tk'] != pin['tk'] or parsed['pointer_bits'] != 32):
                raise RuntimeError('Unexpected ARM interpreter/Tcl/Tk versions')
        expected = json.loads((harness / 'tests/qemu_artifact/critical_cases.json').read_text())
        for variant in ('flash', 'noflash'):
            relative = 'results/artifact-' + variant + '-critical/report.json'
            data = read_guest_file(work, relative)
            (evidence / (variant + '.json')).write_bytes(data)
            package = json.loads(data)
            critical = package.get('guest', {}).get('critical', {})
            rows = critical.get('cases', [])
            if (package.get('status') != 'PASS' or package.get('ipk_sha256') != package_hashes[variant] or
                    critical.get('profile') != expected['version'] or critical.get('status') != 'PASS' or
                    [row.get('id') for row in rows] != list(expected['cases']) or
                    any(row.get('status') != 'PASS' for row in rows)):
                raise RuntimeError('Incomplete or incorrect critical report for ' + variant)
        report['status'] = 'PASS'
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        report.update(status='FAIL', error=str(error))
    finally:
        # The unique scope also contains descendants that created new sessions.
        subprocess.run(['systemctl', 'kill', '--signal=KILL', unit],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        if process:
            try:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=5)
            except ProcessLookupError:
                pass
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
        # Copy a bounded allowlist only, including diagnostics on failed guests.
        for relative in ('sandbox.json', 'job.json', 'results/runtime.json', 'results/xvfb.log'):
            try:
                (evidence / relative.replace('/', '--')).write_bytes(read_guest_file(work, relative))
            except (OSError, ValueError):
                pass
        for variant in ('flash', 'noflash'):
            for name in ('guest.log', 'report.json', 'critical.json'):
                try:
                    data = read_guest_file(work, 'results/artifact-' + variant + '-critical/' + name)
                    (evidence / (variant + '-' + name)).write_bytes(data)
                except (OSError, ValueError):
                    pass
        report['seconds'] = round(time.monotonic() - started, 3)
        (evidence / 'summary.json').write_text(json.dumps(report, indent=2) + '\n')
        for path in evidence.iterdir():
            path.chmod(0o644)
    print(report['status'] + ': critical QEMU flows; evidence: ' + str(evidence))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
