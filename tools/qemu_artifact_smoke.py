"""Check and execute an explicit ZIP-format IPK inside qemu_env.sh.

Imports and UI navigation only; this does not install, flash or exercise RF.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import sys
import zipfile


REQUIRED = (
    'app.py', 'ipk_starter.py', 'main/main.py', 'lib/__init__.py',
    'lib/actmain.py', 'lib/actstack.py', 'lib/activity_main.py',
    'lib/activity_read.py', 'lib/executor.py', 'lib/scan.py', 'lib/read.py',
    'lib/ics_decoder.py', 'screens/main_menu.json', 'data/conf.ini',
    'res/font/mononoki-Regular.ttf', 'pm3/proxmark3', 'pm3/lua.zip',
)
FIRMWARE = 'res/firmware/pm3/manifest.json'
FIRMWARE_IMAGE = 'res/firmware/pm3/fullimage.elf'


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def extract_ipk(ipk, destination, variant):
    """Validate all names/metadata before extracting into a new directory."""
    if variant not in ('flash', 'noflash'):
        raise ValueError('Explicit flash or noflash variant required')
    with zipfile.ZipFile(ipk) as archive:
        entries = archive.infolist()
        if len(entries) > 40000 or sum(e.file_size for e in entries) > 1024 ** 3:
            raise ValueError('IPK exceeds the smoke-test extraction limits')
        names = set()
        for entry in entries:
            name = entry.orig_filename
            path = PurePosixPath(name)
            if (name != entry.filename or not path.parts or path.is_absolute() or '..' in path.parts or
                    '\\' in name or ':' in name or '\x00' in name or
                    str(path) != name.rstrip('/') or name in names):
                raise ValueError('Unsafe or duplicate ZIP entry: ' + repr(name))
            kind = stat.S_IFMT(entry.external_attr >> 16)
            if (kind not in (0, stat.S_IFREG, stat.S_IFDIR) or entry.flag_bits & 1 or
                    kind == stat.S_IFDIR and not entry.is_dir()):
                raise ValueError('Unsupported ZIP entry type/encryption: ' + name)
            names.add(name)
        for name in REQUIRED:
            if name not in names or archive.getinfo(name).file_size == 0:
                raise ValueError('Missing or empty packaged file: ' + name)
        firmware_names = [n for n in names if n.startswith('res/firmware/')]
        if variant == 'noflash' and firmware_names:
            raise ValueError('No-flash package contains firmware payloads')
        if variant == 'flash':
            for name in (FIRMWARE, FIRMWARE_IMAGE):
                if name not in names or archive.getinfo(name).file_size == 0:
                    raise ValueError('Missing or empty firmware file: ' + name)
            manifest = json.loads(archive.read(FIRMWARE))
            if not isinstance(manifest, dict):
                raise ValueError('Firmware manifest must be an object')
        destination.mkdir(parents=False, exist_ok=False)
        files = {}
        for entry in entries:
            target = destination / entry.filename
            if entry.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(entry) as source, target.open('xb') as output:
                for chunk in iter(lambda: source.read(1024 * 1024), b''):
                    output.write(chunk)
            files[entry.filename] = sha256(target)
    return files


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ipk', type=Path)
    parser.add_argument('--variant', required=True, choices=('flash', 'noflash'))
    parser.add_argument('--profile', choices=('smoke', 'critical'), default='smoke')
    args = parser.parse_args(argv)
    if not all(os.environ.get(k) for k in ('ICOPY_QEMU_RUN', 'QEMU_BIN', 'QEMU_PYTHON')):
        parser.error('Run inside tools/qemu_env.sh; missing emulation is an error')
    run = Path(os.environ['ICOPY_QEMU_RUN'])
    suffix = '-critical' if args.profile == 'critical' else ''
    output = run / 'results' / ('artifact-' + args.variant + suffix)
    output.mkdir(exist_ok=False)
    report = {'status': 'INCOMPLETE', 'variant': args.variant, 'profile': args.profile,
              'ipk': str(args.ipk.resolve()),
              'boundary': 'packaged module imports and real Tk menu navigation; no startup, RF or flashing'}
    report_path = output / 'report.json'
    report_path.write_text(json.dumps(report, indent=2) + '\n')
    project = Path(__file__).resolve().parents[1]
    guest = project / 'tests' / 'qemu_artifact' / 'guest_smoke.py'
    display = None
    runner = None
    try:
        report['ipk_sha256'] = sha256(args.ipk)
        report['harness_sha256'] = sha256(__file__)
        report['guest_harness_sha256'] = sha256(guest)
        if args.profile == 'critical':
            report['critical_inputs_sha256'] = {
                name: sha256(guest.parent / name) for name in
                ('critical_flows.py', 'strict_transport.py', 'ultralight_cases.py', 'recovery_transport.py',
                 'critical_cases.json', 'transcripts.json')}
            report['boundary'] = 'packaged ARM/Tk critical flows with scripted hardware boundaries; no RF, flashing or boot chain'
        extracted = output / 'app'
        files = extract_ipk(args.ipk, extracted, args.variant)
        (output / 'files.json').write_text(json.dumps(files, indent=2) + '\n')
        report['asset_hashes'] = {n: files[n] for n in files
                                  if n.startswith(('pm3/', 'res/firmware/'))}
        spec = importlib.util.spec_from_file_location(
            'flow_runner', project / 'tests' / 'flows' / 'run_all_flows.py')
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        with (output / 'xvfb.log').open('wb') as log:
            display, number = runner.start_display(log)
            env = dict(os.environ, DISPLAY=number)
            # The font configuration uses the artifact's fonts for this process.
            font_config = output / 'fonts.conf'
            from xml.sax.saxutils import escape
            font_config.write_text('<fontconfig><dir>' + escape(str(extracted / 'res' / 'font')) +
                                   '</dir><cachedir>/tmp/artifact-font-cache</cachedir></fontconfig>')
            env['FONTCONFIG_FILE'] = str(font_config)
            with (output / 'guest.log').open('wb') as guest_log:
                completed = subprocess.run(
                    [os.environ['QEMU_BIN'], os.environ['QEMU_PYTHON'], '-I', '-u',
                     str(guest), str(extracted), str(output), args.profile, args.variant], env=env,
                    stdout=guest_log, stderr=subprocess.STDOUT, timeout=120)
            if completed.returncode:
                raise RuntimeError('ARM guest exited with status ' + str(completed.returncode))
            if display.poll() is not None:
                raise RuntimeError('Xvfb exited during artifact execution')
        guest_report = json.loads((output / 'guest.json').read_text())
        if guest_report.get('status') != 'PASS':
            raise RuntimeError('Missing successful guest assertions')
        if args.profile == 'critical':
            expected = json.loads((guest.parent / 'critical_cases.json').read_text())
            critical = guest_report.get('critical', {})
            rows = critical.get('cases', [])
            if (critical.get('status') != 'PASS' or critical.get('profile') != expected['version'] or
                    [r['id'] for r in rows] != list(expected['cases']) or
                    any(r.get('status') != 'PASS' for r in rows)):
                raise RuntimeError('Critical-flow inventory incomplete or failed')
        for module in guest_report['modules'].values():
            if files.get(module['relative_path']) != module['sha256']:
                raise RuntimeError('Imported module does not match archive: ' + str(module))
        report.update(status='PASS', guest=guest_report)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, zipfile.BadZipFile) as error:
        report.update(status='FAIL', error=str(error))
    finally:
        if runner:
            runner.stop_process_group(display)
        report_path.write_text(json.dumps(report, indent=2) + '\n')
    print(report['status'] + ': ' + str(report_path), flush=True)
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
