"""Verify a maintainer-pinned runtime archive before bounded, safe extraction."""
import argparse
import hashlib
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
import shutil
import tarfile


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def safe_name(name):
    path = PurePosixPath(name)
    if (not name or path.is_absolute() or '..' in path.parts or '\\' in name or
            ':' in name or path.parts[0] != 'runtime'):
        raise ValueError('Unsafe runtime path: ' + repr(name))
    return path


def unpack(archive_path, output, expected):
    if not re.fullmatch('[0-9a-f]{64}', expected) or sha256(archive_path) != expected:
        raise ValueError('Runtime archive digest mismatch')
    output.mkdir(exist_ok=False)
    with tarfile.open(archive_path, 'r:gz') as archive:
        members = archive.getmembers()
        if len(members) > 25000 or sum(m.size for m in members) > 2 * 1024**3:
            raise ValueError('Oversized runtime archive')
        seen, links = set(), []
        for member in members:
            name = safe_name(member.name)
            if name in seen or member.size > 128 * 1024**2:
                raise ValueError('Duplicate or oversized runtime entry')
            seen.add(name)
            if member.issym():
                target = member.linkname
                safe_name(posixpath.normpath(str(name.parent / target)))
                if PurePosixPath(target).is_absolute():
                    raise ValueError('Absolute runtime symlink')
                links.append((name, target))
            elif not (member.isfile() or member.isdir()):
                raise ValueError('Special files and hardlinks are forbidden')
        link_names = {name for name, _ in links}
        for name in seen:
            if any(parent in link_names for parent in name.parents):
                raise ValueError('Runtime symlink used as an archive parent')
        for member in members:
            path = output / member.name
            path.parent.mkdir(parents=True, exist_ok=True)
            if member.isdir():
                path.mkdir(exist_ok=True)
                path.chmod(0o755)
            elif member.isfile():
                with archive.extractfile(member) as source, path.open('xb') as destination:
                    shutil.copyfileobj(source, destination)
                path.chmod(0o755 if member.mode & 0o111 else 0o644)
        for name, target in links:
            (output / str(name)).symlink_to(target)
        for name, _ in links:
            resolved = (output / str(name)).resolve(strict=True)
            if os.path.commonpath((str(output.resolve()), str(resolved))) != str(output.resolve()):
                raise ValueError('Runtime link escaped the extraction directory')
    return output / 'runtime'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--sha256', required=True)
    args = parser.parse_args()
    print(unpack(args.archive, args.output, args.sha256))
