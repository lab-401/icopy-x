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

"""mifare -- MIFARE Classic constants and utilities.
    Audit:       docs/ (lines 186-211)

This is a pure constants/utilities module.  No PM3 commands, no side effects.

MIFARE Classic memory model:
    Sectors 0-31:  4 blocks each  (blocks 0-127)   — 3 data + 1 trailer
    Sectors 32-39: 16 blocks each (blocks 128-255)  — 15 data + 1 trailer
"""

import re

# ---------------------------------------------------------------------------
# Size constants (bytes)
# Strings: __pyx_k_SIZE_1K, __pyx_k_SIZE_2K, __pyx_k_SIZE_4K, __pyx_k_SIZE_MINI
# ---------------------------------------------------------------------------
SIZE_1K = 1024
SIZE_2K = 2048
SIZE_4K = 4096
SIZE_MINI = 320

# ---------------------------------------------------------------------------
# Sector count constants
# Strings: __pyx_k_SECTOR_1K, __pyx_k_SECTOR_4K, etc.
# ---------------------------------------------------------------------------
SECTOR_1K = 16
SECTOR_2K = 32
SECTOR_4K = 40
SECTOR_Mini = 5

# ---------------------------------------------------------------------------
# Block count constants
# ---------------------------------------------------------------------------
BLOCK_1K = 64
BLOCK_2K = 128
BLOCK_4K = 256
BLOCK_Mini = 20

# ---------------------------------------------------------------------------
# Block / data constants
# Strings: __pyx_k_BLOCK_SIZE, __pyx_k_MAX_BLOCK_COUNT
# ---------------------------------------------------------------------------
BLOCK_SIZE = 16
MAX_BLOCK_COUNT = 256
MAX_SECTOR_COUNT = 40

# ---------------------------------------------------------------------------
# Key / data string constants
# Strings: __pyx_k_FFFFFFFFFFFF, __pyx_k_EMPTY_KEY, __pyx_k_EMPTY_DATA,
#          __pyx_k_EMPTY_TRAI
# ---------------------------------------------------------------------------
EMPTY_KEY = 'FFFFFFFFFFFF'
EMPTY_DATA = '00000000000000000000000000000000'
EMPTY_TRAI = 'FFFFFFFFFFFFFF078069FFFFFFFFFFFF'

# ---------------------------------------------------------------------------
# Key type constants
# Strings: __pyx_k_A, __pyx_k_B, __pyx_k_AB
# ---------------------------------------------------------------------------
A = 'A'
B = 'B'
AB = 'AB'


# ---------------------------------------------------------------------------
# Block ↔ Sector conversion
# ---------------------------------------------------------------------------
def blockToSector(blockIndex):
    """Convert a block number to its sector number.

    Sectors 0-31:  blocks 0-127   (4 blocks per sector)
    Sectors 32-39: blocks 128-255 (16 blocks per sector)
    """
    if blockIndex < 128:
        return blockIndex // 4
    return 32 + (blockIndex - 128) // 16


def sectorToBlock(sectorIndex):
    """Return the first block number in a sector."""
    if sectorIndex < 32:
        return sectorIndex * 4
    return 128 + (sectorIndex - 32) * 16


# ---------------------------------------------------------------------------
# Sector / block count queries
# ---------------------------------------------------------------------------
def getSectorCount(size):
    """Return the number of sectors for a given card byte size."""
    if size == SIZE_1K:
        return SECTOR_1K
    if size == SIZE_2K:
        return SECTOR_2K
    if size == SIZE_4K:
        return SECTOR_4K
    if size == SIZE_MINI:
        return SECTOR_Mini
    return 0


def getBlockCountInSector(sectorIndex):
    """Return the number of blocks in a sector (4 for small, 16 for large)."""
    if sectorIndex < 32:
        return 4
    if sectorIndex < 40:
        return 16
    return 0


def getKeyCount(size):
    """Return the total number of keys for a card size (2 per sector)."""
    return getSectorCount(size) * 2


# ---------------------------------------------------------------------------
# Block classification
# ---------------------------------------------------------------------------
def isFirstBlock(uiBlock):
    """Return True if the block is the first block in its sector."""
    if uiBlock < 128:
        return uiBlock % 4 == 0
    return (uiBlock - 128) % 16 == 0


def isTrailerBlock(uiBlock):
    """Return True if the block is a sector trailer."""
    if uiBlock < 128:
        return uiBlock % 4 == 3
    return (uiBlock - 128) % 16 == 15


def get_trailer_block(uiFirstBlock):
    """Return the trailer block number given the first block of a sector."""
    if uiFirstBlock < 128:
        return uiFirstBlock + 3
    return uiFirstBlock + 15


def getIndexOnSector(block, sector):
    """Return the index of a block within its sector (0-based)."""
    return block - sectorToBlock(sector)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def validateBlock(block):
    """Return True if the block number is within the valid range (0-255)."""
    return 0 <= block < MAX_BLOCK_COUNT


def validateSector(sector):
    """Return True if the sector number is within the valid range (0-39)."""
    return 0 <= sector < MAX_SECTOR_COUNT


def validateValueOperand(value):
    """Return True if the value is a valid 32-bit signed integer."""
    return -2147483648 <= value <= 2147483647


def isBlockData(data):
    """Return True if the hex string is valid 16-byte block data (32 hex chars)."""
    if not isinstance(data, str):
        return False
    return len(data) == 32 and bool(re.match(r'^[a-fA-F0-9]{32}$', data))
