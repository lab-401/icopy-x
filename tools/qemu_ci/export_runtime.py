"""Export only factory ARM runtime dependencies, inside trusted qemu_env.sh.

No original application code, credentials, SD data or system configuration is
included. The resulting private bundle is an input to disposable CI workers.
"""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import posixpath
import shutil
import tarfile


PATHS = (
    'root2/root/usr/local/python-3.8.0',
    'root2/root/home/pi/.local/lib/python3.8/site-packages',
    'root2/root/lib/arm-linux-gnueabihf',
    'root2/root/lib/ld-linux-armhf.so.3',
    'root2/root/usr/lib/arm-linux-gnueabihf',
    'root1/lib/arm-linux-gnueabihf',
    'root1/usr/lib/arm-linux-gnueabihf',
    'root1/usr/share/fonts',
    'root2/root/home/pi/ipk_app_main/res/font/mononoki-Regular.ttf',
    'root2/root/home/pi/ipk_app_main/res/font/monozhwqy.ttf',
)


def normalize_links(root):
    """Keep links inside their guest filesystem; omit uncopied dependencies."""
    omitted = {}
    for path in sorted(root.rglob('*')):
        if not path.is_symlink():
            continue
        relative = path.relative_to(root).as_posix()
        link = os.readlink(path)
        filesystem = root / ('sdcard/root2/root' if relative.startswith('sdcard/root2/root/')
                             else 'sdcard/root1')
        destination = Path(posixpath.normpath(str(filesystem / link.lstrip('/'))
                                           if link.startswith('/') else str(path.parent / link)))
        if os.path.commonpath((str(filesystem), str(destination))) != str(filesystem):
            raise ValueError('Symlink escapes guest filesystem: ' + relative)
        path.unlink()
        path.symlink_to(os.path.relpath(destination, path.parent))
    # A target can itself be an omitted link. Iterate until all retained links resolve.
    while True:
        dangling = [path for path in root.rglob('*') if path.is_symlink() and not path.exists()]
        if not dangling:
            break
        for path in dangling:
            omitted[path.relative_to(root).as_posix()] = os.readlink(path)
            path.unlink()
    return omitted


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path, help='New directory outside the private /mnt and /tmp')
    args = parser.parse_args()
    manifest = json.loads((Path(os.environ['ICOPY_QEMU_RUN']) / 'environment.json').read_text())
    output = args.output.resolve()
    if str(output).startswith(('/mnt/', '/tmp/')):
        parser.error('Export must survive the environment namespace')
    output.mkdir(exist_ok=False)
    root = output / 'runtime'
    root.mkdir()
    selected = list(PATHS)
    for filesystem in ('root1', 'root2/root'):
        name = filesystem + '/usr/share/tcltk'
        if (Path('/mnt/sdcard') / name).is_dir():
            selected.append(name)
    if not any(name.endswith('/tcltk') for name in selected):
        raise ValueError('Factory Tcl/Tk script libraries are missing')
    for name in selected:
        source = Path('/mnt/sdcard') / name
        target = root / 'sdcard' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, target, symlinks=True)
        elif source.is_symlink():
            target.symlink_to(os.readlink(source))
        else:
            shutil.copyfile(source, target)
    shutil.copyfile(os.environ['QEMU_BIN'], root / 'qemu-arm-static')
    (root / 'qemu-arm-static').chmod(0o755)
    omitted_links = normalize_links(root)
    files = {}
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            files[relative] = {'symlink': os.readlink(path)}
        elif path.is_file():
            files[relative] = {'sha256': sha256(path), 'bytes': path.stat().st_size}
    record = dict(schema=1, source_image_sha256=manifest['image_sha256'],
                  exporter_sha256=sha256(Path(__file__)),
                  qemu_sha256=manifest['qemu_sha256'], qemu_version=manifest['qemu_version'],
                  selected_paths=selected, omitted_links=omitted_links, files=files)
    (root / 'runtime.json').write_text(json.dumps(record, indent=2) + '\n')
    archive_path = output / 'runtime.tar.gz'
    with archive_path.open('xb') as raw, gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0) as zipped, tarfile.open(fileobj=zipped, mode='w|') as archive:
        for path in [root] + sorted(root.rglob('*')):
            name = path.relative_to(output).as_posix()
            info = archive.gettarinfo(str(path), arcname=name)
            info.uid = info.gid = info.mtime = 0
            info.uname = info.gname = ''
            info.mode = 0o755 if info.isdir() or info.mode & 0o111 else 0o644
            if info.isfile():
                with path.open('rb') as source:
                    archive.addfile(info, source)
            else:
                archive.addfile(info)
    result = dict(archive_sha256=sha256(archive_path), archive_bytes=archive_path.stat().st_size,
                  source_image_sha256=manifest['image_sha256'], qemu_sha256=manifest['qemu_sha256'],
                  files=len(files))
    (output / 'identity.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
