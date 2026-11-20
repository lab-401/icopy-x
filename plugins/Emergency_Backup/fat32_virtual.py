##########################################################################
# Required Notice: Copyright ETOILE401 SAS (http://www.lab401.com)
#
# Copyright (c) 2026: ETOILE401 SAS & https://github.com/quantum-x/
#
# This software is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this software for commercial purposes.
#
# A copy of the license is available at:
# https://polyformproject.org/licenses/noncommercial/1.0.0
#
# This entire header "Required Notice" must remain in place.
##########################################################################

##########################################################################
# EMERGENCY BACKUP - VIRTUAL FAT32 IMAGE GENERATOR
##########################################################################
# Virtual UDUMP FAT32 image generation for Emergency Backup.
# Purpose:
#   - Indexes files and directories on the live UDUMP filesystem.
#   - Excludes the /backups tree to avoid copying the generated backup
#     into the backup itself.
#   - Builds FAT32/VFAT structures, directory entries, short-name aliases,
#     long filenames, allocation metadata and filesystem data regions.
#   - Streams a fresh read-only FAT32 representation into the output image;
#     does not build a separate temporary 11 GiB FAT32 file.
#   - Never writes to source block devices.
# Used by: plugin.py when constructing the p4 UDUMP part of the SD image.
# Compatibility: Python 3.8; standard library only.
##########################################################################

# @copyright (2026) jareckib
import math
import os
import stat
import struct
import time
from array import array

SECTOR = 512
SPC = 64
CLUSTER = SECTOR * SPC
RESERVED = 32
FATS = 2
ZERO = bytes(1024 * 1024)
_VALID = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789$%'-_@~`!(){}^#&")


def _sfn_checksum(s):
    n = 0
    for v in s:
        n = ((n & 1) << 7) + (n >> 1) + v
        n &= 255
    return n


def _long_entries(name, alias):
    units = name.encode('utf-16le')
    if len(units) > 510:
        raise ValueError('VFAT name longer than 255 UTF-16 units: %s' % name)
    units += b'\x00\x00'
    pairs = [units[i:i+2] for i in range(0, len(units), 2)]
    entries = []
    pieces = [pairs[i:i+13] for i in range(0, len(pairs), 13)]
    for i in range(len(pieces), 0, -1):
        ordinal = i | (0x40 if i == len(pieces) else 0)
        p = pieces[i-1] + [b'\xff\xff'] * (13 - len(pieces[i-1]))
        data = b''.join(p)
        e = bytearray(32)
        e[0] = ordinal
        e[1:11] = data[:10]
        e[11] = 0x0f
        e[12] = 0
        e[13] = _sfn_checksum(alias)
        e[14:26] = data[10:22]
        e[26:28] = b'\x00\x00'
        e[28:32] = data[22:26]
        entries.append(bytes(e))
    return entries


def _alias(name, taken):
    parts = name.rsplit('.', 1)
    base = parts[0] if len(parts) == 2 else name
    ext = parts[1] if len(parts) == 2 else ''
    base = ''.join(x for x in base.upper() if x in _VALID)
    ext = ''.join(x for x in ext.upper() if x in _VALID)[:3]
    if not base:
        base = 'FILE'
    candidate = (base[:8].ljust(8) + ext.ljust(3)).encode('ascii')
    if len(base) <= 8 and candidate not in taken:
        taken.add(candidate)
        return candidate
    for i in range(1, 1000000):
        suffix = '~%d' % i
        part = base[:8-len(suffix)] + suffix
        candidate = (part.ljust(8) + ext.ljust(3)).encode('ascii')
        if candidate not in taken:
            taken.add(candidate)
            return candidate
    raise ValueError('Cannot assign unique FAT short name')


def _timestamp(st):
    t = time.localtime(st.st_mtime)
    y = min(2107, max(1980, t.tm_year))
    return ((y-1980) << 9) | (t.tm_mon << 5) | t.tm_mday, (t.tm_hour << 11) | (t.tm_min << 5) | (t.tm_sec // 2)


class Node(object):
    def __init__(self, path, name, parent, directory, size, st=None):
        self.path, self.name, self.parent = path, name, parent
        self.directory, self.size, self.stat = directory, size, st
        self.children = []
        self.alias = None
        self.first = 0
        self.clusters = 0


def _nodes(root, excluded_dir):
    st = os.stat(root)
    base = Node(root, '', None, True, 0, st)
    dirs = {root: base}
    for path, subdirs, files in os.walk(root, topdown=True, followlinks=False):
        subdirs[:] = sorted(x for x in subdirs if not os.path.islink(os.path.join(path, x)) and os.path.realpath(os.path.join(path,x)) != os.path.realpath(excluded_dir))
        par = dirs[path]
        for name in subdirs:
            child = os.path.join(path, name)
            node = Node(child, name, par, True, 0, os.stat(child))
            dirs[child] = node
            par.children.append(node)
        for name in sorted(files):
            p = os.path.join(path, name)
            st = os.lstat(p)
            if not stat.S_ISREG(st.st_mode):
                raise ValueError('Unsupported UDUMP object: %s' % p)
            if st.st_size > 0xffffffff:
                raise ValueError('FAT32 single-file limit exceeded: %s' % p)
            par.children.append(Node(p, name, par, False, st.st_size, st))
    nodes = []
    def visit(node):
        nodes.append(node)
        used = set()
        for child in node.children:
            child.alias = _alias(child.name, used)
            visit(child)
    visit(base)
    return nodes


def _sfn_entry(node, parent=False):
    if parent:
        alias = b'..         '
    elif node.name == '':
        alias = b'.          '
    else:
        alias = node.alias
    dt, tm = _timestamp(node.stat)
    a = bytearray(32)
    a[:11] = alias
    a[11] = 0x10 if node.directory else 0x20
    struct.pack_into('<HHH', a, 14, tm, dt, dt)
    struct.pack_into('<H', a, 22, tm)
    struct.pack_into('<H', a, 24, dt)
    struct.pack_into('<H', a, 20, (node.first >> 16) & 0xffff)
    struct.pack_into('<H', a, 26, node.first & 0xffff)
    struct.pack_into('<I', a, 28, 0 if node.directory else node.size)
    return bytes(a)


def _dir_image(node):
    entries = []
    if node.parent is None:
        e = bytearray(32)
        e[:11] = b'ICOPY-X    '
        e[11] = 0x08
        entries.append(bytes(e))
    else:
        e = bytearray(32)
        e[:11] = b'.          '
        e[11] = 0x10
        struct.pack_into('<H',e,20,(node.first >> 16) & 0xffff)
        struct.pack_into('<H',e,26,node.first & 0xffff)
        entries.append(bytes(e))
        p = node.parent
        e = bytearray(_sfn_entry(p, parent=True))
        if p.parent is None:
            struct.pack_into('<HH',e,20,0,0)
            struct.pack_into('<H',e,26,p.first)
        entries.append(bytes(e))
    for child in node.children:
        entries.extend(_long_entries(child.name, child.alias))
        entries.append(_sfn_entry(child))
    b = b''.join(entries) + b'\0'*32
    return b + bytes(node.clusters * CLUSTER - len(b))


class VirtualFAT32(object):
    def __init__(self, root, excluded_dir, source_boot_sector, sectors, hidden_sectors=0):
        self.sectors = int(sectors)
        self.nodes = _nodes(root, excluded_dir)
        self.root = self.nodes[0]
        if self.sectors * SECTOR < 64 * 1024 * 1024:
            raise ValueError('UDUMP is too small for FAT32')
        # Determine stable FAT size from partition size.
        fat_sectors = 1
        while True:
            clusters = (self.sectors - RESERVED - FATS * fat_sectors) // SPC
            needed = (clusters + 2) * 4
            newer = (needed + SECTOR-1)//SECTOR
            if newer == fat_sectors:
                break
            fat_sectors = newer
        self.fat_sectors = fat_sectors
        self.cluster_count = clusters
        if not 65525 <= clusters < 0x0ffffff0:
            raise ValueError('UDUMP not in FAT32 cluster-count range')
        current = 2
        for node in self.nodes:
            if node.directory:
                count = (1 if node.parent is None else 2)
                for c in node.children:
                    count += len(_long_entries(c.name, c.alias)) + 1
                count += 1
                length = count * 32
                node.clusters = max(1, (length + CLUSTER-1)//CLUSTER)
            else:
                node.clusters = (node.size + CLUSTER-1)//CLUSTER
            if node.clusters:
                node.first = current
                current += node.clusters
        if current-2 > clusters:
            raise ValueError('UDUMP files exceed FAT32 image capacity')
        self.used = current - 2
        self.table = array('I', [0]) * (clusters + 2)
        self.table[0], self.table[1] = 0x0ffffff8, 0x0fffffff
        for node in self.nodes:
            for j in range(node.clusters):
                k = node.first + j
                self.table[k] = 0x0fffffff if j + 1 == node.clusters else k + 1
        source = source_boot_sector
        bs = bytearray(SECTOR)
        bs[:3] = b'\xeb\x58\x90'
        bs[3:11] = b'MSWIN4.1'
        struct.pack_into('<H',bs,11,SECTOR)
        bs[13] = SPC
        struct.pack_into('<H',bs,14,RESERVED)
        bs[16] = FATS
        struct.pack_into('<H',bs,17,0)
        struct.pack_into('<H',bs,19,0)
        bs[21] = 0xf8
        struct.pack_into('<H',bs,22,0)
        struct.pack_into('<H',bs,24,63)
        struct.pack_into('<H',bs,26,255)
        struct.pack_into('<I',bs,28,hidden_sectors)
        struct.pack_into('<I',bs,32,self.sectors)
        struct.pack_into('<I',bs,36,self.fat_sectors)
        struct.pack_into('<H',bs,40,0)
        struct.pack_into('<H',bs,42,0)
        struct.pack_into('<I',bs,44,2)
        struct.pack_into('<H',bs,48,1)
        struct.pack_into('<H',bs,50,6)
        bs[64] = 0x80
        bs[66] = 0x29
        bs[67:71] = source[67:71] if len(source) >= 71 else b'\x0c\xfd\x6a\xfc'
        bs[71:82] = b'ICOPY-X    '
        bs[82:90] = b'FAT32   '
        bs[510:512] = b'\x55\xaa'
        self.boot = bytes(bs)
        fi = bytearray(SECTOR)
        struct.pack_into('<I',fi,0,0x41615252)
        struct.pack_into('<I',fi,484,0x61417272)
        struct.pack_into('<I',fi,488,clusters - self.used)
        struct.pack_into('<I',fi,492,min(current,clusters+1) if current<=clusters+1 else 0xffffffff)
        fi[510:512] = b'\x55\xaa'
        self.fsinfo = bytes(fi)

    def stream_regions(self, chunk=1024*1024):
        """Yield (bytes, length) for data, (None, length) for zero runs."""
        # 32 reserved sectors: boot, fsinfo, backup boot and backup fsinfo.
        for i in range(RESERVED):
            if i in (0,6):
                yield self.boot, len(self.boot)
            elif i in (1,7):
                yield self.fsinfo, len(self.fsinfo)
            else:
                yield None, SECTOR
        fat = self.table.tobytes()
        fat += bytes(self.fat_sectors*SECTOR-len(fat))
        for _ in range(FATS):
            for i in range(0,len(fat),chunk):
                yield fat[i:i+chunk], len(fat[i:i+chunk])
        # Contiguous allocated file and directory clusters.
        for node in self.nodes:
            if not node.clusters:
                continue
            if node.directory:
                data = _dir_image(node)
                for i in range(0,len(data),chunk):
                    yield data[i:i+chunk], len(data[i:i+chunk])
            else:
                with open(node.path,'rb') as f:
                    remaining = node.size
                    while remaining:
                        data = f.read(min(remaining,chunk))
                        if not data:
                            raise IOError('UDUMP file changed during backup: %s' % node.path)
                        remaining -= len(data)
                        yield data, len(data)
                padding = node.clusters*CLUSTER-node.size
                if padding:
                    yield None, padding
        rest = self.sectors*SECTOR-(RESERVED+FATS*self.fat_sectors+self.used*SPC)*SECTOR
        if rest:
            yield None, rest

    def stream(self, chunk=1024*1024):
        """Legacy byte stream, retained for compatibility and regression tests."""
        for data, length in self.stream_regions(chunk):
            if data is not None:
                yield data
            else:
                while length:
                    n = min(length, len(ZERO))
                    yield ZERO[:n]
                    length -= n
