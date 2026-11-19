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
# EMERGENCY BACKUP - FAST STREAMING GZIP
##########################################################################
# Fast compressed image streaming for Emergency Backup.
# Purpose:
#   - Writes one conventional gzip stream around a raw SD card image.
#   - Compresses incoming data using zlib's DEFLATE implementation.
#   - Efficiently emits long runs of zero bytes with reusable full-flush
#     DEFLATE fragments instead of recompressing each complete zero block.
#   - Maintains gzip CRC32 and uncompressed size for the final trailer.
#   - Does not create a temporary uncompressed image or extra gzip members.
# Used by: plugin.py; the output sink manages splitting into 2 GiB parts.
# Compatibility: standard gzip decompressors; standard library only.
##########################################################################

# @copyright (2026) jareckib
import struct
import zlib

ZERO_BLOCK = 1024 * 1024
_ZERO = bytes(ZERO_BLOCK)


def _flushed_fragment(data):
    compressor = zlib.compressobj(1, zlib.DEFLATED, -zlib.MAX_WBITS)
    return compressor.compress(data) + compressor.flush(zlib.Z_FULL_FLUSH)


_ZERO_DEFLATE = _flushed_fragment(_ZERO)


class FastGzip(object):
    def __init__(self, sink, level=1):
        if level != 1:
            raise ValueError('FastGzip requires level 1')
        self.sink = sink
        self.compressor = zlib.compressobj(1, zlib.DEFLATED, -zlib.MAX_WBITS)
        self.crc = 0
        self.size = 0
        self.closed = False
        # gzip header: ID1 ID2 CM FLG MTIME XFL OS
        self.sink.write(b'\x1f\x8b\x08\x00\x00\x00\x00\x00\x04\xff')

    def write(self, data):
        if self.closed:
            raise ValueError('gzip already closed')
        if not data:
            return 0
        self.crc = zlib.crc32(data, self.crc)
        self.size += len(data)
        result = self.compressor.compress(data)
        if result:
            self.sink.write(result)
        return len(data)

    def write_zeros(self, amount, progress=None):
        if self.closed:
            raise ValueError('gzip already closed')
        if amount < 0:
            raise ValueError('negative zero run')
        if not amount:
            return
        # Reset the DEFLATE dictionary and align to a byte boundary.
        # A full-flush fragment starts with an empty dictionary and can be
        # repeated without ending the gzip member.
        result = self.compressor.flush(zlib.Z_FULL_FLUSH)
        if result:
            self.sink.write(result)
        while amount:
            take = min(ZERO_BLOCK, amount)
            if take == ZERO_BLOCK:
                result = _ZERO_DEFLATE
                raw = _ZERO
            else:
                raw = _ZERO[:take]
                result = _flushed_fragment(raw)
            self.sink.write(result)
            self.crc = zlib.crc32(raw, self.crc)
            self.size += take
            amount -= take
            if progress is not None:
                progress(take)
        self.compressor = zlib.compressobj(1, zlib.DEFLATED, -zlib.MAX_WBITS)

    def close(self):
        if self.closed:
            return
        self.sink.write(self.compressor.flush(zlib.Z_FINISH))
        self.sink.write(struct.pack('<II', self.crc & 0xffffffff,
                                    self.size & 0xffffffff))
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        # Complete trailer only on success; failures leave invalid .part,
        # which the plugin removes in its existing finally block.
        if exc_type is None:
            self.close()
        return False
