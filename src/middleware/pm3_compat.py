##########################################################################
# Required Notice: Copyright ETOILE401 SAS (http://www.lab401.com)
#
# Initial author: ETOILE401 SAS & https://github.com/quantum-x/ as of April 16, 2026
#
# Since this date, each contribution is under the copyright of its respective author.
#
# Copyright of each contribution is tracked by the Git history. See the output of git shortlog -nse for a full list or git log --pretty=short --follow <path/to/sourcefile> |git shortlog -ne to track a specific file.
#
# A mailmap is maintained to map author and committer names and email addresses to canonical names and email addresses.
# If by accident a copyright was removed from a file and is not directly deducible from the Git history, please submit a PR.
#
#
# This software is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this software for commercial purposes.
#
# A copy of the license is available at:
# https://polyformproject.org/licenses/noncommercial/1.0.0
#
# This entire header "Required Notice" must remain in place.
##########################################################################

"""pm3_compat -- PM3 command & response translation layer.

Translates old-style (positional argument) PM3 commands used by the original
Lab401 iCopy-X firmware to the new CLI-flag syntax used by the RRG/Iceman
Proxmark3 client.  Also normalizes RRG response output back to the format
expected by existing middleware regex patterns and keyword checks.

Ground truth:
    /home/qx/archive/PM3_COMMAND_COMPAT.md -- full 54-command compatibility table
    src/middleware/pm3_response_catalog.py  -- complete response format diff catalog
    OLD source: iCopy-X-Community/icopyx-community-pm3 (factory FW, RRG 385d892f)
    NEW source: rfidresearchgroup/proxmark3 (RRG/Iceman v4.21128+)

Architecture:
    Module-level functions (no classes), matching other middleware modules.
    executor.py calls translate() before sending commands to the PM3 subprocess.
    executor.py calls translate_response() after receiving output, before caching.

Version detection:
    Original (Lab401): hw version output contains 'NIKOLA:' line
    Iceman (RRG):      hw version output has 'Iceman/master/vX.XXXXX'
"""

import logging
import re

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency: pm3_flash (may not be available under test)
# ---------------------------------------------------------------------------
try:
    from middleware import pm3_flash
except ImportError:
    try:
        import pm3_flash
    except ImportError:
        pm3_flash = None

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PM3_VERSION_ORIGINAL = 'original'  # Lab401 iCopy-X PM3
PM3_VERSION_ICEMAN = 'iceman'      # RRG/Iceman PM3

_current_version = None  # Set by detect_pm3_version()

# ---------------------------------------------------------------------------
# Legacy compatibility toggle.
#
# Set to False to disable ALL legacy (factory) firmware compatibility.
# When False:
#   - translate() is a no-op (iceman commands go direct)
#   - translate_response() is a no-op (executor cleanup is sufficient)
#   - detect_pm3_version() still runs but its result is unused
#
# When True (default):
#   - On iceman FW: forward rules translate any remaining factory-syntax
#     commands; response normalizers convert iceman output to factory format.
#   - On factory FW: reverse rules translate iceman-syntax commands back
#     to factory positional syntax.
#
# To fully remove legacy support: set LEGACY_COMPAT = False, or delete
# this file entirely.  executor.py handles pm3_compat being absent.
# ---------------------------------------------------------------------------
LEGACY_COMPAT = True

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _size_flag(n):
    """Convert numeric size code to RRG CLI flag."""
    return {'0': '--mini', '1': '--1k', '2': '--2k', '4': '--4k'}.get(str(n), '--1k')


def _key_type_flag(t):
    """Convert A/B key type to RRG CLI flag."""
    return '-a' if t.upper() == 'A' else '-b'


def _target_key_type_flag(t):
    """Convert A/B target key type to RRG CLI flag for nested attack."""
    return '--ta' if t.upper() == 'A' else '--tb'


# ---------------------------------------------------------------------------
# ANSI stripping — kept for backward compatibility.
# Primary cleanup now lives in executor._clean_pm3_output().
# ---------------------------------------------------------------------------

_ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')


def strip_ansi(text):
    """Remove ANSI color/formatting escape sequences from text.

    Note: executor.py now calls _clean_pm3_output() unconditionally,
    which includes ANSI stripping.  This function is retained for any
    external callers but is no longer called by executor.
    """
    if not text:
        return text
    return _ANSI_RE.sub('', text)


# ---------------------------------------------------------------------------
# iceman-FW hardware workarounds.
#
# Commands that hang on iceman firmware on iCopy-X hardware (FPGA chip
# mismatch reported by hw version).  Substituted with `hw ping` to avoid
# device hang.  These are NOT translations — the middleware and iceman
# share the same command spelling; the workaround is purely hardware.
# ---------------------------------------------------------------------------

_BLOCKED_CMDS_ICEMAN = frozenset({
    'hf iclass info',  # hangs due to FPGA chip mismatch on iCopy-X
})


# ---------------------------------------------------------------------------
# Reverse translation rules (iceman → factory/original)
#
# Used when running on original (factory) firmware with middleware modules
# that have been migrated to iceman syntax.  Converts iceman CLI-flag
# commands back to old-style positional syntax the factory PM3 understands.
#
# Populated flow-by-flow as middleware modules are migrated.
# Rules are tried in order; first match wins.
# ---------------------------------------------------------------------------

def _reverse_mf_rdbl(m):
    """hf mf rdbl --blk {blk} -a/-b -k {key} -> hf mf rdbl {blk} A/B {key}"""
    blk = m.group(1)
    typ = 'A' if m.group(2) == '-a' else 'B'
    key = m.group(3)
    return 'hf mf rdbl %s %s %s' % (blk, typ, key)


def _reverse_mf_rdsc(m):
    """hf mf rdsc -s {sec} -a/-b -k {key} -> hf mf rdsc {sec} A/B {key}"""
    sec = m.group(1)
    typ = 'A' if m.group(2) == '-a' else 'B'
    key = m.group(3)
    return 'hf mf rdsc %s %s %s' % (sec, typ, key)


def _reverse_mf_fchk(m):
    """hf mf fchk --mini/--1k/--2k/--4k -f {file} -> hf mf fchk 0/1/2/4 {file}"""
    size_map = {'--mini': '0', '--1k': '1', '--2k': '2', '--4k': '4'}
    sp = size_map.get(m.group(1), '1')
    return 'hf mf fchk %s %s' % (sp, m.group(2))


def _reverse_mf_nested(m):
    """hf mf nested --size --blk {blk} -a/-b -k {key} --tblk {tblk} --ta/--tb
    -> hf mf nested {size} {blk} A/B {key} {tblk} A/B"""
    size_map = {'--mini': '0', '--1k': '1', '--2k': '2', '--4k': '4'}
    sp = size_map.get(m.group(1), '1')
    blk = m.group(2)
    typ = 'A' if m.group(3) == '-a' else 'B'
    key = m.group(4)
    tblk = m.group(5)
    ttyp = 'A' if m.group(6) == '--ta' else 'B'
    return 'hf mf nested %s %s %s %s %s %s' % (sp, blk, typ, key, tblk, ttyp)


def _reverse_mf_wrbl(m):
    """hf mf wrbl --blk {blk} -a/-b -k {key} -d {data} --force
    -> hf mf wrbl {blk} A/B {key} {data}"""
    blk = m.group(1)
    typ = 'A' if m.group(2) == '-a' else 'B'
    key = m.group(3)
    data = m.group(4)
    return 'hf mf wrbl %s %s %s %s' % (blk, typ, key, data)


def _reverse_14a_raw(m):
    """hf 14a raw ... -k ... -> hf 14a raw ... -p ... (reverse flag rename)"""
    cmd = m.group(0)
    return re.sub(r'(?<=\s)-k(?=\s|$)', '-p', cmd)


def _reverse_mf_csetuid(m):
    """hf mf csetuid -u {uid} -s {sak} -a {atqa} [-w]
    -> hf mf csetuid {uid} {sak} {atqa} [w]"""
    uid = m.group(1)
    sak = m.group(2)
    atqa = m.group(3)
    has_w = m.group(4) is not None
    result = 'hf mf csetuid %s %s %s' % (uid, sak, atqa)
    if has_w:
        result += ' w'
    return result


def _reverse_em410x_clone(m):
    """lf em 410x clone --id {id} -> lf em 410x_write {id} 1"""
    return 'lf em 410x_write %s 1' % m.group(1)


def _reverse_indala_clone(m):
    """lf indala clone -r {raw} -> lf indala clone {raw} -r {raw}"""
    raw = m.group(1)
    return 'lf indala clone %s -r %s' % (raw, raw)


def _reverse_t55xx_read_page1(m):
    """lf t55xx read -b {blk} -p {key} --page1 -> lf t55xx read b {blk} p {key} o 1"""
    return 'lf t55xx read b %s p %s o 1' % (m.group(1), m.group(2))


_REVERSE_TRANSLATION_RULES = [
    # -----------------------------------------------------------------------
    # Flow 1: Scan — reverse rules (iceman → factory)
    # -----------------------------------------------------------------------

    # data save -f {file} -> data save f {file}
    (re.compile(r'^data save\s+-f\s+(\S+)$'), r'data save f \1'),

    # hf mf cgetblk --blk {blk} -> hf mf cgetblk {blk}
    (re.compile(r'^hf mf cgetblk\s+--blk\s+(\S+)$'), r'hf mf cgetblk \1'),

    # -----------------------------------------------------------------------
    # Flow 2: Read HF — reverse rules (iceman → factory)
    # -----------------------------------------------------------------------

    # hf mf rdbl --blk {blk} -a/-b -k {key} -> hf mf rdbl {blk} A/B {key}
    (re.compile(r'^hf mf rdbl\s+--blk\s+(\S+)\s+(-[ab])\s+-k\s+(\S+)$'),
     _reverse_mf_rdbl),

    # hf mf rdsc -s {sec} -a/-b -k {key} -> hf mf rdsc {sec} A/B {key}
    (re.compile(r'^hf mf rdsc\s+-s\s+(\S+)\s+(-[ab])\s+-k\s+(\S+)$'),
     _reverse_mf_rdsc),

    # hf mf fchk --mini/--1k/--2k/--4k -f {file} -> hf mf fchk 0/1/2/4 {file}
    (re.compile(r'^hf mf fchk\s+(--(?:mini|1k|2k|4k))\s+-f\s+(\S+)$'),
     _reverse_mf_fchk),

    # hf mf nested --size --blk {blk} -a/-b -k {key} --tblk {tblk} --ta/--tb
    (re.compile(r'^hf mf nested\s+(--(?:mini|1k|2k|4k))\s+--blk\s+(\S+)\s+(-[ab])\s+-k\s+(\S+)\s+--tblk\s+(\S+)\s+(--t[ab])$'),
     _reverse_mf_nested),

    # hf mfu dump -f {file} -> hf mfu dump f {file}
    (re.compile(r'^hf mfu dump\s+-f\s+(\S+)$'), r'hf mfu dump f \1'),

    # -----------------------------------------------------------------------
    # Flow 3: Write HF — reverse rules (iceman → factory)
    # -----------------------------------------------------------------------

    # hf mf wrbl --blk {blk} -a/-b -k {key} -d {data} --force
    (re.compile(r'^hf mf wrbl\s+--blk\s+(\S+)\s+(-[ab])\s+-k\s+(\S+)\s+-d\s+(\S+)\s+--force$'),
     _reverse_mf_wrbl),

    # hf 14a raw ... -k ... -> hf 14a raw ... -p ...
    (re.compile(r'^hf 14a raw\s+.*(?<=\s)-k(?=\s|$).*$'), _reverse_14a_raw),

    # hf mf cload -f {file} -> hf mf cload b {file}
    (re.compile(r'^hf mf cload\s+-f\s+(\S+)$'), r'hf mf cload b \1'),

    # hf mf csetuid -u {uid} -s {sak} -a {atqa} [-w]
    (re.compile(r'^hf mf csetuid\s+-u\s+(\S+)\s+-s\s+(\S+)\s+-a\s+(\S+)(?:\s+(-w))?$'),
     _reverse_mf_csetuid),

    # hf mfu restore -s -e -f {file} -> hf mfu restore s e f {file}
    (re.compile(r'^hf mfu restore\s+-s\s+-e\s+-f\s+(\S+)$'), r'hf mfu restore s e f \1'),

    # -----------------------------------------------------------------------
    # Flow 4: Erase — reverse rules (iceman → factory)
    # -----------------------------------------------------------------------

    # lf t55xx wipe -p {key} -> lf t55xx wipe p {key}
    (re.compile(r'^lf t55xx wipe\s+-p\s+(\S+)$'), r'lf t55xx wipe p \1'),

    # lf t55xx detect -p {key} -> lf t55xx detect p {key}
    (re.compile(r'^lf t55xx detect\s+-p\s+(\S+)$'), r'lf t55xx detect p \1'),

    # lf t55xx chk -f {file} -> lf t55xx chk f {file}
    (re.compile(r'^lf t55xx chk\s+-f\s+(\S+)$'), r'lf t55xx chk f \1'),

    # -----------------------------------------------------------------------
    # Flow 8: iCLASS — reverse rules (iceman → factory)
    # -----------------------------------------------------------------------

    # hf iclass rdbl --blk {blk} -k {key} --elite -> hf iclass rdbl b {blk} k {key} e
    # (elite variant must come before non-elite)
    (re.compile(r'^hf iclass rdbl\s+--blk\s+(\S+)\s+-k\s+(\S+)\s+--elite$'),
     r'hf iclass rdbl b \1 k \2 e'),
    # hf iclass rdbl --blk {blk} -k {key} -> hf iclass rdbl b {blk} k {key}
    (re.compile(r'^hf iclass rdbl\s+--blk\s+(\S+)\s+-k\s+(\S+)$'),
     r'hf iclass rdbl b \1 k \2'),

    # hf iclass chk --vb6kdf -> hf iclass chk
    (re.compile(r'^hf iclass chk\s+--vb6kdf$'), 'hf iclass chk'),

    # hf iclass dump -k {key} -f {path} --elite -> hf iclass dump k {key} f {path} e
    (re.compile(r'^hf iclass dump\s+-k\s+(\S+)\s+-f\s+(\S+)\s+--elite$'),
     r'hf iclass dump k \1 f \2 e'),
    # hf iclass dump -k {key} -f {path} -> hf iclass dump k {key} f {path}
    (re.compile(r'^hf iclass dump\s+-k\s+(\S+)\s+-f\s+(\S+)$'),
     r'hf iclass dump k \1 f \2'),
    # hf iclass dump -k {key} --elite -> hf iclass dump k {key} e
    (re.compile(r'^hf iclass dump\s+-k\s+(\S+)\s+--elite$'),
     r'hf iclass dump k \1 e'),
    # hf iclass dump -k {key} -> hf iclass dump k {key}
    (re.compile(r'^hf iclass dump\s+-k\s+(\S+)$'),
     r'hf iclass dump k \1'),

    # hf iclass calcnewkey --old {old} --new {new} --elite
    (re.compile(r'^hf iclass calcnewkey\s+--old\s+(\S+)\s+--new\s+(\S+)\s+--elite$'),
     r'hf iclass calcnewkey o \1 n \2 --elite'),
    # hf iclass calcnewkey --old {old} --new {new}
    (re.compile(r'^hf iclass calcnewkey\s+--old\s+(\S+)\s+--new\s+(\S+)$'),
     r'hf iclass calcnewkey o \1 n \2'),

    # hf iclass wrbl --blk {blk} -d {data} -k {key} --elite
    (re.compile(r'^hf iclass wrbl\s+--blk\s+(\S+)\s+-d\s+(\S+)\s+-k\s+(\S+)\s+--elite$'),
     r'hf iclass wrbl -b \1 -d \2 -k \3 --elite'),
    # hf iclass wrbl --blk {blk} -d {data} -k {key}
    (re.compile(r'^hf iclass wrbl\s+--blk\s+(\S+)\s+-d\s+(\S+)\s+-k\s+(\S+)$'),
     r'hf iclass wrbl -b \1 -d \2 -k \3'),

    # -----------------------------------------------------------------------
    # Flow 9: ISO15693 — reverse rules (iceman → factory)
    # -----------------------------------------------------------------------

    # hf 15 dump -f {path} -> hf 15 dump f {path}
    (re.compile(r'^hf 15 dump\s+-f\s+(\S+)$'), r'hf 15 dump f \1'),

    # hf 15 restore -f {path} -> hf 15 restore f {path}
    (re.compile(r'^hf 15 restore\s+-f\s+(\S+)$'), r'hf 15 restore f \1'),

    # hf 15 csetuid -u {uid} -> hf 15 csetuid {uid}
    (re.compile(r'^hf 15 csetuid\s+-u\s+(\S+)$'), r'hf 15 csetuid \1'),

    # -----------------------------------------------------------------------
    # Flows 5-7: Read/Write/Verify LF — reverse rules (iceman → factory)
    # -----------------------------------------------------------------------

    # -- LF reader commands (19 protocols: reader → read rename) --

    # lf em 410x reader -> lf em 410x_read
    (re.compile(r'^lf em 410x reader$'), 'lf em 410x_read'),

    # lf fdxb reader -> lf fdx read (namespace + verb change)
    (re.compile(r'^lf fdxb reader$'), 'lf fdx read'),

    # lf {type} reader -> lf {type} read (18 protocols)
    (re.compile(r'^(lf (?:hid|indala|awid|io|gproxii|securakey|viking|pyramid|'
                r'gallagher|jablotron|keri|nedap|noralsy|pac|paradox|presco|'
                r'visa2000|nexwatch)) reader$'), r'\1 read'),

    # -- LF EM4x05 commands --

    # lf em 4x05 info -p {pwd} -> lf em 4x05_info {pwd}
    (re.compile(r'^lf em 4x05 info\s+-p\s+(\S+)$'), r'lf em 4x05_info \1'),

    # lf em 4x05 info (no args) -> lf em 4x05_info
    (re.compile(r'^lf em 4x05 info$'), 'lf em 4x05_info'),

    # lf em 4x05 read -a {blk} -p {key} -> lf em 4x05_read {blk} {key}
    (re.compile(r'^lf em 4x05 read\s+-a\s+(\S+)\s+-p\s+(\S+)$'), r'lf em 4x05_read \1 \2'),

    # lf em 4x05 read -a {blk} (no key) -> lf em 4x05_read {blk}
    (re.compile(r'^lf em 4x05 read\s+-a\s+(\S+)$'), r'lf em 4x05_read \1'),

    # lf em 4x05 dump -f {file} -> lf em 4x05_dump f {file}
    (re.compile(r'^lf em 4x05 dump\s+-f\s+(\S+)$'), r'lf em 4x05_dump f \1'),

    # lf em 4x05 dump (no args) -> lf em 4x05_dump
    (re.compile(r'^lf em 4x05 dump$'), 'lf em 4x05_dump'),

    # lf em 4x05 write -a {blk} -d {data} -p {key} -> lf em 4x05_write {blk} {data} {key}
    (re.compile(r'^lf em 4x05 write\s+-a\s+(\S+)\s+-d\s+(\S+)\s+-p\s+(\S+)$'),
     r'lf em 4x05_write \1 \2 \3'),

    # lf em 4x05 write -a {blk} -d {data} (no key)
    (re.compile(r'^lf em 4x05 write\s+-a\s+(\S+)\s+-d\s+(\S+)$'),
     r'lf em 4x05_write \1 \2'),

    # -- LF T55xx commands (not already in Flow 4) --

    # lf t55xx dump -f {file} -p {key} (3-arg before 2-arg)
    (re.compile(r'^lf t55xx dump\s+-f\s+(\S+)\s+-p\s+(\S+)$'), r'lf t55xx dump f \1 p \2'),

    # lf t55xx dump -f {file}
    (re.compile(r'^lf t55xx dump\s+-f\s+(\S+)$'), r'lf t55xx dump f \1'),

    # lf t55xx read -b {blk} -p {key} --page1
    (re.compile(r'^lf t55xx read\s+-b\s+(\S+)\s+-p\s+(\S+)\s+--page1$'),
     _reverse_t55xx_read_page1),

    # lf t55xx read -b {blk} -p {key} (before single-arg)
    (re.compile(r'^lf t55xx read\s+-b\s+(\S+)\s+-p\s+(\S+)$'), r'lf t55xx read b \1 p \2'),

    # lf t55xx read -b {blk}
    (re.compile(r'^lf t55xx read\s+-b\s+(\S+)$'), r'lf t55xx read b \1'),

    # lf t55xx write -b {blk} -d {data} -p {key}
    (re.compile(r'^lf t55xx write\s+-b\s+(\S+)\s+-d\s+(\S+)\s+-p\s+(\S+)$'),
     r'lf t55xx write b \1 d \2 p \3'),

    # lf t55xx write -b {blk} -d {data}
    (re.compile(r'^lf t55xx write\s+-b\s+(\S+)\s+-d\s+(\S+)$'), r'lf t55xx write b \1 d \2'),

    # lf t55xx restore -f {file}
    (re.compile(r'^lf t55xx restore\s+-f\s+(\S+)$'), r'lf t55xx restore f \1'),

    # -- LF clone commands --

    # lf em 410x clone --id {id} -> lf em 410x_write {id} 1
    (re.compile(r'^lf em 410x clone\s+--id\s+(\S+)$'), _reverse_em410x_clone),

    # lf hid clone -r {raw} -> lf hid clone {raw}
    (re.compile(r'^lf hid clone\s+-r\s+(\S+)$'), r'lf hid clone \1'),

    # lf indala clone -r {raw} -> lf indala clone {raw} -r {raw}
    (re.compile(r'^lf indala clone\s+-r\s+(\S+)$'), _reverse_indala_clone),

    # lf fdxb clone --country {C} --national {N} -> lf fdx clone c {C} n {N}
    (re.compile(r'^lf fdxb clone\s+--country\s+(\S+)\s+--national\s+(\S+)$'),
     r'lf fdx clone c \1 n \2'),

    # lf {type} clone -r {raw} -> lf {type} clone b {raw}
    (re.compile(r'^(lf (?:securakey|gallagher|pac|paradox)) clone\s+-r\s+(\S+)$'),
     r'\1 clone b \2'),

    # lf nexwatch clone -r {raw} -> lf nexwatch clone r {raw}
    (re.compile(r'^lf nexwatch clone\s+-r\s+(\S+)$'), r'lf nexwatch clone r \1'),

    # -----------------------------------------------------------------------
    # Flow 12: Sniff — reverse rules (iceman → factory)
    # -----------------------------------------------------------------------

    # lf config -a {a} -t {t} -s {s} -> lf config a {a} t {t} s {s}
    (re.compile(r'^lf config\s+-a\s+(\S+)\s+-t\s+(\S+)\s+-s\s+(\S+)$'),
     r'lf config a \1 t \2 s \3'),

    # hf 14a/14b/iclass/topaz list / hf mf list (iceman aliases) -> hf list {proto}
    # Iceman has per-protocol list aliases; factory used `hf list <protocol>`.
    (re.compile(r'^hf mf list$'), 'hf list mf'),
    (re.compile(r'^hf 14a list$'), 'hf list 14a'),
    (re.compile(r'^hf 14b list$'), 'hf list 14b'),
    (re.compile(r'^hf iclass list$'), 'hf list iclass'),
    (re.compile(r'^hf topaz list$'), 'hf list topaz'),

    # -----------------------------------------------------------------------
    # Flow 13: Simulation — reverse rules (iceman → factory)
    # -----------------------------------------------------------------------

    # hf 14a sim -t {type} --uid {uid}  (or -u alias) -> hf 14a sim t {type} u {uid}
    (re.compile(r'^hf 14a sim\s+-t\s+(\S+)\s+(?:--uid|-u)\s+(\S+)$'),
     r'hf 14a sim t \1 u \2'),

    # hf mf csave --1k -f {file} -> hf mf csave 1 o {file}
    # hf mf csave --4k -f {file} -> hf mf csave 4 o {file}
    (re.compile(r'^hf mf csave\s+--1k\s+-f\s+(\S+)$'), r'hf mf csave 1 o \1'),
    (re.compile(r'^hf mf csave\s+--4k\s+-f\s+(\S+)$'), r'hf mf csave 4 o \1'),
    (re.compile(r'^hf mf csave\s+--mini\s+-f\s+(\S+)$'), r'hf mf csave 0 o \1'),
    (re.compile(r'^hf mf csave\s+--2k\s+-f\s+(\S+)$'), r'hf mf csave 2 o \1'),

    # lf em 410x sim --id {id} -> lf em 410x_sim {id}
    (re.compile(r'^lf em 410x sim\s+--id\s+(\S+)$'), r'lf em 410x_sim \1'),

    # lf em 410x watch -> lf em 410x_watch
    (re.compile(r'^lf em 410x watch$'), 'lf em 410x_watch'),

    # lf hid sim -r {raw} -> lf hid sim {raw}
    (re.compile(r'^lf hid sim\s+-r\s+(\S+)$'), r'lf hid sim \1'),

    # lf awid sim --fmt X --fc Y --cn Z -> lf awid sim X Y Z
    (re.compile(r'^lf awid sim\s+--fmt\s+(\S+)\s+--fc\s+(\S+)\s+--cn\s+(\S+)$'),
     r'lf awid sim \1 \2 \3'),

    # lf io sim --vn X --fc Y --cn Z -> lf io sim X Y Z
    (re.compile(r'^lf io sim\s+--vn\s+(\S+)\s+--fc\s+(\S+)\s+--cn\s+(\S+)$'),
     r'lf io sim \1 \2 \3'),

    # lf gproxii sim --xor 0 --fmt X --fc Y --cn Z -> lf gproxii sim X Y Z
    # Factory gproxii sim takes 3 positional args (fmt, fc, cn) — xor is iceman-only.
    (re.compile(r'^lf gproxii sim\s+--xor\s+\S+\s+--fmt\s+(\S+)\s+--fc\s+(\S+)\s+--cn\s+(\S+)$'),
     r'lf gproxii sim \1 \2 \3'),

    # lf viking sim --cn X -> lf viking sim X
    (re.compile(r'^lf viking sim\s+--cn\s+(\S+)$'), r'lf viking sim \1'),

    # lf pyramid sim --fc X --cn Y -> lf pyramid sim X Y
    (re.compile(r'^lf pyramid sim\s+--fc\s+(\S+)\s+--cn\s+(\S+)$'),
     r'lf pyramid sim \1 \2'),

    # lf jablotron sim --cn X -> lf jablotron sim X
    (re.compile(r'^lf jablotron sim\s+--cn\s+(\S+)$'), r'lf jablotron sim \1'),

    # lf nedap sim --st X --cc Y --id Z -> lf nedap sim s X c Y i Z
    (re.compile(r'^lf nedap sim\s+--st\s+(\S+)\s+--cc\s+(\S+)\s+--id\s+(\S+)$'),
     r'lf nedap sim s \1 c \2 i \3'),

    # lf fdxb sim --country X --national Y --animal -> lf fdx sim c X n Y s
    (re.compile(r'^lf fdxb sim\s+--country\s+(\S+)\s+--national\s+(\S+)\s+--animal$'),
     r'lf fdx sim c \1 n \2 s'),

    # lf fdxb sim --country X --national Y --extended Z -> lf fdx sim c X n Y e Z
    (re.compile(r'^lf fdxb sim\s+--country\s+(\S+)\s+--national\s+(\S+)\s+--extended\s+(\S+)$'),
     r'lf fdx sim c \1 n \2 e \3'),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_pm3_version():
    """Detect PM3 version.  Sets _current_version.  Returns version string.

    Uses pm3_flash.get_running_version() which sends 'hw version' to PM3
    and parses the output.

    Returns:
        PM3_VERSION_ORIGINAL or PM3_VERSION_ICEMAN, or None on failure.
    """
    global _current_version

    if pm3_flash is None:
        logger.warning("detect_pm3_version: pm3_flash module not available")
        _current_version = None
        return None

    try:
        ver = pm3_flash.get_running_version()
    except Exception as e:
        logger.error("detect_pm3_version failed: %s", e)
        _current_version = None
        return None

    if ver is None:
        logger.warning("detect_pm3_version: could not get running version")
        _current_version = None
        return None

    nikola = ver.get('nikola', '')
    if nikola:
        _current_version = PM3_VERSION_ORIGINAL
        logger.info("Detected PM3 version: original (NIKOLA: %s)", nikola)
    else:
        _current_version = PM3_VERSION_ICEMAN
        logger.info("Detected PM3 version: iceman (os: %s)", ver.get('os', ''))

    return _current_version


def configure_iceman():
    """Send one-time configuration to iceman PM3 after version detection.

    Called from application.py after detect_pm3_version() confirms iceman.
    Configures the PM3 to tolerate cards with bad BCC (common in Gen1a
    Chinese clones).  The legacy firmware accepted bad BCC by default;
    iceman rejects them unless configured.
    """
    if _current_version != PM3_VERSION_ICEMAN:
        return
    try:
        import executor
        executor.startPM3Task('hf 14a config --bcc ignore', 5000)
        logger.info("Configured iceman: BCC ignore for Gen1a compatibility")
    except Exception as e:
        logger.warning("configure_iceman failed: %s", e)


def get_version():
    """Return current PM3 version (PM3_VERSION_ORIGINAL, PM3_VERSION_ICEMAN, or None)."""
    return _current_version


def needs_translation():
    """Return True if translation may be needed in either direction.

    During the compat flip transition:
      - On iceman: forward rules still active for un-migrated modules
      - On original: reverse rules active for migrated modules
    After full migration + LEGACY_COMPAT=False, returns False always.
    """
    if not LEGACY_COMPAT:
        return False
    return _current_version in (PM3_VERSION_ICEMAN, PM3_VERSION_ORIGINAL)


def translate(cmd):
    """Translate iceman-native PM3 command to legacy factory syntax.

    After Phase 4 flip, middleware is iceman-native.  translate() runs
    only on legacy factory firmware, converting iceman CLI-flag commands
    DOWN to the positional-arg syntax legacy PM3 understands.

    On iceman firmware this function is a pass-through no-op except for
    the _BLOCKED_CMDS_ICEMAN hardware workaround (FPGA chip mismatch
    makes `hf iclass info` hang on iCopy-X hardware — substitute `hw ping`).

    When LEGACY_COMPAT is False, this is a no-op.

    Args:
        cmd: PM3 command string (iceman-native syntax)

    Returns:
        Translated command string.
    """
    if not cmd:
        return cmd

    if not LEGACY_COMPAT:
        return cmd

    stripped = cmd.strip()

    # Hardware workaround: block iceman commands that hang on iCopy-X.
    # Applies only when running iceman FW (legacy FW doesn't have this issue).
    if _current_version == PM3_VERSION_ICEMAN:
        if stripped in _BLOCKED_CMDS_ICEMAN:
            logger.info("translate: blocked '%s' (known to hang on iceman)", stripped)
            return 'hw ping'
        return cmd

    if _current_version != PM3_VERSION_ORIGINAL:
        return cmd

    # Legacy (factory) firmware: convert iceman CLI-flag syntax to legacy
    # positional form.  Middleware emits iceman form; factory PM3 needs
    # old positional commands.
    for pattern, replacement in _REVERSE_TRANSLATION_RULES:
        m = pattern.match(stripped)
        if m:
            if callable(replacement):
                result = replacement(m)
            else:
                result = m.expand(replacement)
            logger.debug("translate: '%s' -> '%s'", stripped, result)
            return result

    # No rule matched — pass through (iceman-native command works on
    # legacy for commands where syntax is identical).
    return cmd


# ---------------------------------------------------------------------------
# Response translation: normalize RRG/Iceman output to old-format patterns
#
# The middleware modules (hf14ainfo.py, hfmfkeys.py, hfmfwrite.py, etc.)
# parse PM3 output via hasKeyword() and getContentFromRegex*() using
# patterns written for the factory firmware (RRG 385d892f / Nikola v3.1).
# The new RRG firmware (v4.21128+) changed many output formats.
#
# translate_response() normalizes NEW output to look like OLD output
# so middleware modules work without modification.
#
# Ground truth: pm3_response_catalog.py documents every breaking change.
# ---------------------------------------------------------------------------

# ===========================================================================
# Generic response normalizations
#
# Split into phases to avoid ordering conflicts:
#   Phase A (pre): noise removal + line prefix stripping
#   Phase B: command-specific normalizers (operate on clean, prefix-free text)
#   Phase C (post): remaining generic normalizations (dotted-to-colon, etc.)
# ===========================================================================

# Strip [usb|script] pm3 --> echo lines (command echo from piped stdin)
_RE_ECHO_LINE = re.compile(r'^\[usb\|script\]\s*pm3\s*-->.*\n?', re.MULTILINE)

# Strip bare "pm3 -->" EOR marker emitted by the iCopy-X EOR patch.
# This marker is used by rftask.py to detect command completion but must
# NOT leak into middleware responses.
_RE_EOR_MARKER = re.compile(r'^pm3\s+-->\s*\n?', re.MULTILINE)

# Strip [=] ---------- ... ---------- section header lines
_RE_SECTION_HEADER = re.compile(
    r'^\[=\]\s*-{3,}.*-{3,}\s*\n?', re.MULTILINE)

# Strip bare [=] lines (empty info lines)
_RE_BARE_INFO = re.compile(r'^\[=\]\s*$\n?', re.MULTILINE)

# Strip [+]/[=]/[#]/[!!] prefix markers from lines.
# These are informational prefixes added by RRG's PrintAndLogEx.
# Note: strip_ansi already removes color codes; these are the text markers.
_RE_LINE_PREFIX = re.compile(r'^\[(?:\+|=|#|!!?|\-|/|\\|\|)\]\s?', re.MULTILINE)

# ---------------------------------------------------------------------------
# Legacy-direction global normalizations.
#
# Applied by _post_normalize() on LEGACY (factory) FW only.  Middleware was
# flipped to iceman-native in Phase 3; these rewriters bring known legacy
# field shapes UP to iceman shape so the iceman middleware regex matches.
#
# Targeted inversion: only known-field labels (Prng detection, Static nonce,
# Magic capabilities, Xor div key).  The prior blanket dotted-to-colon
# rewriter was removed — it inverted the correct direction.
# ---------------------------------------------------------------------------

# Legacy emits `Prng detection: weak|hard|fail` (cmdhf14a.c:1999-2003).
# Iceman emits `Prng detection..... weak` (5 dots) / `...... fail` (6 dots).
# Middleware `hf14ainfo._RE_PRNG = r'Prng detection\.+\s+(\w+)'` targets dots.
_RE_LEGACY_PRNG_COLON = re.compile(
    r'^(\s*)Prng detection:\s*', re.MULTILINE)

# Legacy emits `Static nonce: yes` (cmdhf14a.c:1989).
# Iceman emits `Static nonce....... yes` (7 dots).
# Middleware `hf14ainfo._KW_STATIC_NONCE = 'Static nonce....... yes'`.
_RE_LEGACY_STATIC_NONCE_COLON = re.compile(
    r'^(\s*)Static nonce:\s*', re.MULTILINE)

# Legacy emits `Magic capabilities : Gen 1a` (mifarehost.c:1171 w/ space).
# Iceman emits `Magic capabilities... Gen 1a` (3 dots).
# Middleware `hf14ainfo._KW_GEN1A = 'Magic capabilities... Gen 1a'`.
_RE_LEGACY_MAGIC_COLON = re.compile(
    r'^(\s*)Magic capabilities\s*:\s*', re.MULTILINE)

# Legacy emits `Xor div key : %s` (cmdhficlass.c:2784 w/ space).
# Iceman emits `Xor div key.... %s` (4 dots).
# Middleware `iclasswrite._RE_XOR_DIV_KEY = r'Xor div key\.+\s+...'`.
_RE_LEGACY_XOR_DIV_KEY_COLON = re.compile(
    r'^(\s*)Xor div key\s*:\s*', re.MULTILINE)

# Legacy emits `ISO15693` / `ISO14443-B` / `ISO18092` with NO space.
# Iceman emits `ISO 15693` / `ISO 14443-B` / `ISO 18092` WITH space.
# Middleware `hfsearch._KW_ISO15693 = 'Valid ISO 15693'` (with space).
_RE_LEGACY_ISO_NOSPACE = re.compile(r'\bISO(1\d{4})')


def _pre_normalize(text):
    """Phase A: Strip noise and line prefixes from RRG output.

    Removes echo lines, section headers, bare info lines, and [+]/[=]
    prefix markers. This produces clean text for command-specific
    normalizers to work with.
    """
    if not text:
        return text

    # Strip echo lines first (they contain the translated command)
    text = _RE_ECHO_LINE.sub('', text)

    # Strip EOR marker (iCopy-X patch: "pm3 -->" after each command)
    text = _RE_EOR_MARKER.sub('', text)

    # Strip section headers
    text = _RE_SECTION_HEADER.sub('', text)

    # Strip bare [=] lines
    text = _RE_BARE_INFO.sub('', text)

    # Strip line prefix markers: "[+] " -> ""
    text = _RE_LINE_PREFIX.sub('', text)

    return text


def _post_normalize(text):
    """Phase C: Generic legacy→iceman normalizations after command-specific.

    Targeted inversion of known-field labels that legacy FW emits with a
    colon separator but iceman emits with dots (middleware targets the
    iceman dotted shape).
    """
    if not text:
        return text

    # Legacy `Prng detection: weak` → iceman `Prng detection..... weak`
    # Use 5 dots (iceman's canonical form at cmdhf14a.c:3326).
    text = _RE_LEGACY_PRNG_COLON.sub(r'\1Prng detection..... ', text)

    # Legacy `Static nonce: yes` → iceman `Static nonce....... yes`
    # Use 7 dots (cmdhf14a.c:3319).
    text = _RE_LEGACY_STATIC_NONCE_COLON.sub(r'\1Static nonce....... ', text)

    # Legacy `Magic capabilities : Gen 1a` → iceman `Magic capabilities... Gen 1a`
    # Use 3 dots (mifarehost.c:1710).
    text = _RE_LEGACY_MAGIC_COLON.sub(r'\1Magic capabilities... ', text)

    # Legacy `Xor div key : <hex>` → iceman `Xor div key.... <hex>`
    # Use 4 dots (cmdhficlass.c:5419).
    text = _RE_LEGACY_XOR_DIV_KEY_COLON.sub(r'\1Xor div key.... ', text)

    # Legacy `ISO15693` → iceman `ISO 15693` (inject space).
    text = _RE_LEGACY_ISO_NOSPACE.sub(r'ISO \1', text)

    return text


# ===========================================================================
# Layer 2: Command-specific LEGACY->ICEMAN normalizers.
#
# Fire only when _current_version == PM3_VERSION_ORIGINAL (legacy factory
# firmware).  Middleware is iceman-native after Phase 3; these rewriters
# bring legacy FW output UP to iceman shape so middleware regex matches.
#
# Each entry cites:
#   LEGACY: /tmp/factory_pm3/client/src/<file>:<line>  (what factory emits)
#   ICEMAN: /tmp/rrg-pm3/client/src/<file>:<line>     (what middleware expects)
# ===========================================================================

# -- hf mf fchk table (device firmware-bump forward compat) --

# HEAD iceman row: " 000 | 003 | FFFFFFFFFFFF | 1 | FFFFFFFFFFFF | 1"
# Device iceman emits 4-col `| 000 | ... |` verbatim (no rewrite needed).
# Keep normalizer defined for the 5-col->4-col conversion when iceman HEAD
# flashes (unwired by default; wired for `hf mf fchk/chk/nested/staticnested`
# as forward-compat bump guard).  Gap log P3.2 dormant entry.
_RE_FCHK_NEW_ROW = re.compile(
    r'^\s*(\d{3})\s*\|\s*\d{3}\s*\|\s*([A-Fa-f0-9-]{12})\s*\|\s*(\d)\s*\|\s*([A-Fa-f0-9-]{12})\s*\|\s*(\d)',
    re.MULTILINE)
_RE_FCHK_NEW_SEP = re.compile(r'^-{3,}\+.*$', re.MULTILINE)
_RE_FCHK_NEW_HDR = re.compile(r'^\s*Sec\s*\|\s*Blk\s*\|.*$', re.MULTILINE)


def _normalize_fchk_table(text):
    """Rewrite iceman HEAD 5-col fchk table to 4-col for middleware.

    HEAD iceman (cmdhfmf.c:4966-5060 printKeyTable): 5-col +-separated.
    Device iceman (older build): 4-col |-bordered.  Middleware targets
    4-col (`hfmfkeys._RE_KEY_TABLE`).  Firmware-bump forward compat.
    """
    def _fchk_row_replace(m):
        sec = m.group(1)
        key_a = m.group(2).lower()
        res_a = m.group(3)
        key_b = m.group(4).lower()
        res_b = m.group(5)
        return '| %s | %s   | %s | %s   | %s |' % (
            sec, key_a, res_a, key_b, res_b)

    text = _RE_FCHK_NEW_ROW.sub(_fchk_row_replace, text)
    text = _RE_FCHK_NEW_SEP.sub(
        '|-----|----------------|---|----------------|---|', text)
    text = _RE_FCHK_NEW_HDR.sub(
        '| Sec | key A          |res| key B          |res|', text)
    return text


# -- hf mf wrbl / restore: legacy isOk -> iceman Write ( ok/fail ) --

# LEGACY: cmdhfmf.c:716,825,1307 `PrintAndLogEx(SUCCESS, "isOk:%02x", isOK)`.
# ICEMAN: cmdhfmf.c:1389,9677,9760 `PrintAndLogEx(SUCCESS, "Write ( ok )")`.
# Middleware `hfmfwrite._KW_WRBL_SUCCESS = r'Write \( ok \)'`.
def _normalize_wrbl_response(text):
    """Rewrite legacy `isOk:01`/`isOk:00` -> iceman `Write ( ok )`/`Write ( fail )`.

    Also rewrites `hf mf restore` table rows where legacy emits `| isOk:XX`.
    """
    text = text.replace('isOk:01', 'Write ( ok )')
    text = text.replace('isOk:00', 'Write ( fail )')
    return text


# -- lf em 410x: legacy EM TAG ID -> iceman EM 410x ID --

# LEGACY: cmdlfem4x.c:266/269 `"\nEM TAG ID      : %s"`.
# ICEMAN: cmdlfem410x.c:115 `"EM 410x ID <hex>"`.
# Middleware `lfsearch.REGEX_EM410X = r'EM 410x(?:\s+XL)?\s+ID\s+([0-9A-Fa-f]+)'`.
_RE_LEGACY_EM_TAG_ID = re.compile(r'EM TAG ID\s*:\s*([0-9A-Fa-f]+)')
# Keyword also differs: legacy `Valid EM410x ID` (no space) vs iceman
# `Valid EM 410x ID` (space).  Middleware keyword is iceman form.
_RE_LEGACY_VALID_EM410X = re.compile(r'Valid EM410x ID')


def _normalize_em410x_id(text):
    """Rewrite legacy `EM TAG ID      : <hex>` -> iceman `EM 410x ID <hex>`."""
    text = _RE_LEGACY_EM_TAG_ID.sub(r'EM 410x ID \1', text)
    text = _RE_LEGACY_VALID_EM410X.sub('Valid EM 410x ID', text)
    return text


# -- lf sea: legacy Chipset detection: -> iceman Chipset... --

# LEGACY: cmdlf.c:1349/1357/1365 `"Chipset detection: <name>"`.
# ICEMAN: cmdlf.c:1601-1655 `"Chipset... <name>"` (3 dots).
# Middleware `lfsearch._RE_CHIPSET = r'Chipset\.+\s+(.*)'`.
_RE_LEGACY_CHIPSET = re.compile(
    r'^(\s*)Chipset detection:\s*', re.MULTILINE)


def _normalize_chipset_detection(text):
    """Rewrite legacy `Chipset detection: <name>` -> iceman `Chipset... <name>`."""
    return _RE_LEGACY_CHIPSET.sub(r'\1Chipset... ', text)


# -- lf fdx/fdxb: legacy Animal ID: -> iceman Animal ID dotted --

# LEGACY: cmdlffdx.c:200 `"Animal ID:     %04u-%012u"` (colon + spaces);
#         cmdlffdx.c:282/286 `"Animal ID          <green>%04u-%012u"` (spaces).
# ICEMAN: cmdlffdxb.c:572/578 `"Animal ID........... <country>-<national>"`
#         (9-11 dots).
# Middleware `lfsearch.REGEX_ANIMAL = r'Animal ID\.+\s+([0-9\-]+)'`.
_RE_LEGACY_ANIMAL_ID_COLON = re.compile(
    r'^(\s*)Animal(?:\s+Tag)?\s+ID\s*:\s*', re.MULTILINE | re.IGNORECASE)
_RE_LEGACY_ANIMAL_ID_SPACES = re.compile(
    r'^(\s*)Animal(?:\s+Tag)?\s+ID\s{2,}', re.MULTILINE | re.IGNORECASE)


def _normalize_fdxb_animal_id(text):
    """Rewrite legacy `Animal ID:` or `Animal ID   ` -> iceman `Animal ID........`."""
    if 'Animal' not in text:
        return text
    # Colon form first (cmdlffdx.c:200)
    text = _RE_LEGACY_ANIMAL_ID_COLON.sub(r'\1Animal ID........... ', text)
    # Then space-padded form (cmdlffdx.c:282/286)
    text = _RE_LEGACY_ANIMAL_ID_SPACES.sub(r'\1Animal ID........... ', text)
    return text


# -- lf t55xx detect: legacy colon/pipe -> iceman dotted --

# LEGACY: cmdlft55xx.c:1606 `"     Chip Type      : <name>"` (CAPITAL T, colon).
#         cmdlft55xx.c:1612 `"     Block0         : 0x%08X"` (0x prefix, colon).
# ICEMAN: cmdlft55xx.c:1837 `" Chip type......... <name>"` (lowercase t, 9 dots).
#         cmdlft55xx.c:1843 `" Block0............ %08X %s"` (12 dots, no 0x).
# Middleware lft55xx._RE_CHIP_TYPE = r'Chip [Tt]ype\.+\s+(\S+)', _RE_BLOCK0,
# _RE_MODULATE, _RE_PWD all target iceman dotted shape.
_RE_LEGACY_CHIP_TYPE = re.compile(
    r'^(\s*)Chip Type\s+:\s*', re.MULTILINE)
_RE_LEGACY_MODULATION = re.compile(
    r'^(\s*)Modulation\s+:\s*', re.MULTILINE)
_RE_LEGACY_BLOCK0 = re.compile(
    r'^(\s*)Block0\s+:\s*0x([A-Fa-f0-9]+)', re.MULTILINE)
_RE_LEGACY_PWD_SET = re.compile(
    r'^(\s*)Password Set\s+:\s*', re.MULTILINE)
_RE_LEGACY_PWD = re.compile(
    r'^(\s*)Password\s+:\s*([A-Fa-f0-9]+)', re.MULTILINE)


def _normalize_t55xx_config(text):
    """Rewrite legacy T55xx colon/pipe config -> iceman dotted config."""
    text = _RE_LEGACY_CHIP_TYPE.sub(r'\1Chip type......... ', text)
    text = _RE_LEGACY_MODULATION.sub(r'\1Modulation........ ', text)
    text = _RE_LEGACY_BLOCK0.sub(r'\1Block0............ \2', text)
    text = _RE_LEGACY_PWD_SET.sub(r'\1Password set...... ', text)
    text = _RE_LEGACY_PWD.sub(r'\1Password.......... \2', text)
    return text


# -- lf em 4x05 info: legacy colon/pipe -> iceman dotted --

# LEGACY: cmdlfem4x.c:1266 `"\n Chip Type:   %u | <name>"` (decimal id + pipe).
#         cmdlfem4x.c:1242 `"ConfigWord: %08X (Word 4)\n"` (parenthetical).
#         Legacy emits `"  Serial #: %08X"` (no grep hit but matrix L1032).
# ICEMAN: cmdlfem4x05.c:869 `"Chip type..... <name>"` (5 dots, lowercase).
#         cmdlfem4x05.c:871 `"Serialno...... %08X"` (6 dots).
#         cmdlfem4x05.c:873 `"Block0........ %08x"` (8 dots, no `ConfigWord`).
# Middleware lfem4x05._RE_CHIP/SERIAL/CONFIG all target iceman dotted.
_RE_LEGACY_EM4X_CHIP = re.compile(
    r'^(\s*)Chip Type\s*:\s*\d+\s*\|\s*(\S+)', re.MULTILINE)
_RE_LEGACY_EM4X_SERIAL = re.compile(
    r'^(\s*)Serial\s*#\s*:\s*([A-Fa-f0-9]+)', re.MULTILINE)
# ConfigWord is structural-flip: iceman emits Block0 (raw), legacy emitted
# ConfigWord (decoded).  Inject `Block0........ <hex>` line from the
# `ConfigWord: <hex>` emission so middleware `_RE_CONFIG` (Block0 dotted)
# can capture the raw dword.  Gap log P3.5 accepts field-loss of the
# decoded `(Word 4)` annotation.
_RE_LEGACY_EM4X_CONFIG = re.compile(
    r'^(\s*)ConfigWord\s*:\s*([A-Fa-f0-9]+)(?:\s*\([^)]*\))?', re.MULTILINE)


def _normalize_em4x05_info(text):
    """Rewrite legacy EM4x05 colon/pipe info -> iceman dotted info."""
    text = _RE_LEGACY_EM4X_CHIP.sub(r'\1Chip type..... \2', text)
    text = _RE_LEGACY_EM4X_SERIAL.sub(r'\1Serialno...... \2', text)
    text = _RE_LEGACY_EM4X_CONFIG.sub(r'\1Block0........ \2', text)
    return text


# -- Save message normalization (legacy-lowercase -> iceman-capital) --

# LEGACY fileutils.c factory fork: `"saved %zu bytes to binary file %s"`.
# ICEMAN: fileutils.c:293 `"Saved %zu bytes to binary file \`%s\`"` (capital,
# backtick-quoted filename).
# Middleware dumpers use tolerant `[Ss]aved \d+ bytes to binary file` regex,
# so this is an idempotent upcase for exact-shape parity tests.
_RE_LEGACY_SAVED_LOWER = re.compile(r'^saved\s+', re.MULTILINE)


def _normalize_save_messages(text):
    """Rewrite legacy `saved N bytes` -> iceman `Saved N bytes`."""
    return _RE_LEGACY_SAVED_LOWER.sub('Saved ', text)


# -- hf 15 restore: legacy 'Write OK'+'done' -> iceman 'Done!' --

# LEGACY: cmdhf15.c:1737/1744 `"restore failed. Too many retries."` + `"done"`.
# ICEMAN: cmdhf15.c:2818 `PrintAndLogEx(INFO, "Done!")`.
# Middleware `hf15write._KW_RESTORE_SUCCESS = r"Done!"`.
def _normalize_hf15_restore(text):
    """Rewrite legacy `done` success sentinel -> iceman `Done!`."""
    # Only inject if legacy success sentinel present and iceman sentinel absent.
    if 'Done!' in text:
        return text
    # Legacy `done` (lowercase, no exclamation) emitted only on success path.
    # Avoid false-matching `done` inside other words by anchoring to start-of-line.
    if re.search(r'(?m)^done\b', text):
        text = text + '\nDone!'
    return text


# -- hf iclass wrbl: legacy 'Wrote block NN successful' -> iceman '( ok )' --

# LEGACY: cmdhficlass.c:2149 `"Wrote block %02X successful"`.
# ICEMAN: cmdhficlass.c:3134 `"Wrote block %d / 0x%02X ( ok )"`.
# Middleware `iclasswrite._KW_WRBL_SUCCESS = r'\( ok \)'`.
_RE_LEGACY_ICLASS_WROTE = re.compile(
    r'Wrote block ([0-9A-Fa-f]+)\s+successful')


def _normalize_iclass_wrbl(text):
    """Rewrite legacy `Wrote block NN successful` -> iceman ` ( ok )` form."""
    def _lg_replace(m):
        return 'Wrote block %s / 0x%s ( ok )' % (
            m.group(1), m.group(1).zfill(2).upper())
    return _RE_LEGACY_ICLASS_WROTE.sub(_lg_replace, text)


# -- hf iclass rdbl: legacy ' block NN : <hex>' -> iceman ' block N/0xNN : <hex>' --

# LEGACY: cmdhficlass.c:2399 `" block %02X : <hex>"` (capital-hex block number).
# ICEMAN: cmdhficlass.c:3501 `" block %3d/0x%02X : <hex>"` (decimal + /0xNN).
# Middleware `hficlass._RE_BLOCK_READ = r'block\s+\d+\s*/0x[0-9A-Fa-f]+\s*:\s+...'`.
_RE_LEGACY_ICLASS_BLOCK = re.compile(
    r'^(\s*)block\s+([0-9A-Fa-f]{1,2})\s*:\s+', re.MULTILINE | re.IGNORECASE)


def _normalize_iclass_rdbl(text):
    """Rewrite legacy ` block NN : <hex>` -> iceman ` block N/0x<NN> : <hex>`."""
    def _lg_replace(m):
        indent = m.group(1)
        blk_hex = m.group(2).upper().zfill(2)
        blk_dec = int(blk_hex, 16)
        return '%sblock %3d/0x%s : ' % (indent, blk_dec, blk_hex)
    return _RE_LEGACY_ICLASS_BLOCK.sub(_lg_replace, text)


# -- lf t55xx chk: legacy `Found valid password: <hex>` -> iceman bracketed --

# LEGACY: cmdlft55xx.c factory fork `"Found valid password: %08X"` (bare hex).
# ICEMAN: cmdlft55xx.c:3658/3660/3816 `"Found valid password: [ %08X ]"`
#         (bracketed).
# Middleware `lft55xx._RE_FOUND_VALID = r'Found valid password:\s*\[?\s*([A-Fa-f0-9]+)\s*\]?'`
# tolerates both via optional brackets; pre-flip adapter stripped brackets
# for the pre-refactor middleware.  Now we inject brackets on legacy.
_RE_LEGACY_PWD_BARE = re.compile(
    r'[Ff]ound valid\s+password:\s*([A-Fa-f0-9]{8})(?!\s*\])')


def _normalize_t55xx_chk_password(text):
    """Rewrite legacy `Found valid password: <hex>` -> iceman bracketed form."""
    return _RE_LEGACY_PWD_BARE.sub(r'Found valid password: [ \1 ]', text)


# -- hf 15 csetuid: legacy lowercase (ok) -> iceman `Setting new UID ( ok )` --

# LEGACY: cmdhf15.c:1811 `"setting new UID (" _GREEN_("ok") ")"` (lowercase s,
#         no space inside parens); :1808 `"(" _RED_("failed") ")"`.
# ICEMAN: cmdhf15.c:2900 `"Setting new UID ( " _GREEN_("ok") " )"` (capital S,
#         spaces inside parens).
# Middleware `hf15write._RE_CSETUID_OK = r"Setting new UID\s*\(\s*ok\s*\)"`.
def _normalize_hf15_csetuid(text):
    """Rewrite legacy lowercase `setting new UID (ok)` -> iceman shape."""
    text = text.replace('setting new UID (ok)', 'Setting new UID ( ok )')
    text = text.replace('setting new UID (failed)', 'Setting new UID ( fail )')
    # Legacy also has `can't read card UID` which iceman emits as `no tag found`.
    text = text.replace("can't read card UID", 'no tag found')
    return text


# -- hf felica reader: legacy `IDm  <hex>` -> iceman `IDm: <hex>` --

# LEGACY: cmdhffelica.c:1835 `"FeliCa tag info"` header + :1837 `"IDm  %s"`
#         (two spaces, no colon).
# ICEMAN: cmdhffelica.c:1183 `"IDm: " _GREEN_("%s")` (single colon-space).
# Middleware `hffelica._KW_FOUND = r'IDm:\s'` strict colon form.
_RE_LEGACY_IDM_NOCOLON = re.compile(r'\bIDm\s{2}(\S)')


def _normalize_felica_reader(text):
    """Rewrite legacy `IDm  <hex>` -> iceman `IDm: <hex>`."""
    return _RE_LEGACY_IDM_NOCOLON.sub(r'IDm: \1', text)


# ===========================================================================
# Command-specific dispatch table
# ===========================================================================

# Maps command prefixes to lists of normalizer functions.
# Multiple normalizers can be applied per command.
_RESPONSE_NORMALIZERS = {
    'hf mf fchk': [_normalize_fchk_table],
    'hf mf chk': [_normalize_fchk_table],
    'hf mf nested': [_normalize_fchk_table],
    'hf mf staticnested': [_normalize_fchk_table],
    'hf mf wrbl': [_normalize_wrbl_response],
    'hf mf restore': [_normalize_wrbl_response],
    'hf 15 restore': [_normalize_hf15_restore],
    'hf 15 csetuid': [_normalize_hf15_csetuid],
    'hf iclass rdbl': [_normalize_iclass_rdbl],
    'hf iclass wrbl': [_normalize_iclass_wrbl],
    'hf felica reader': [_normalize_felica_reader],
    'lf sea': [_normalize_em410x_id, _normalize_chipset_detection,
               _normalize_fdxb_animal_id],
    'lf search': [_normalize_em410x_id, _normalize_chipset_detection,
                  _normalize_fdxb_animal_id],
    'lf t55xx detect': [_normalize_t55xx_config],
    'lf t55xx dump': [_normalize_t55xx_config, _normalize_save_messages],
    'lf t55xx chk': [_normalize_t55xx_chk_password],
    'lf em 4x05 info': [_normalize_em4x05_info],
    'lf em 4x05_info': [_normalize_em4x05_info],
    'lf em 4x05 dump': [_normalize_em4x05_info, _normalize_save_messages],
    'lf em 4x05_dump': [_normalize_em4x05_info, _normalize_save_messages],
    'lf em 410x reader': [_normalize_em410x_id],
    'lf em 410x_read': [_normalize_em410x_id],
}


# ===========================================================================
# Public API: translate_response
# ===========================================================================

def translate_response(text, cmd=None):
    """Normalize PM3 response output for middleware pattern compatibility.

    Called by executor._send_and_cache() after _clean_pm3_output() (which
    handles ANSI stripping and [+]/[=] prefix removal unconditionally).

    After Phase 4 compat flip, middleware is iceman-native. This function
    now runs only on LEGACY (factory) firmware, rewriting legacy FW output
    UP to iceman shape so the iceman-native middleware regex matches.

    On iceman firmware: pass-through no-op (middleware regex matches
    iceman-native text directly; module is effectively inert).

    On factory firmware: phase B command-specific rewriters + phase C
    targeted field inverters convert legacy shapes to iceman shapes.

    Args:
        text: Response text (already cleaned by executor._clean_pm3_output)
        cmd: Optional command string for command-specific normalization

    Returns:
        Normalized response text.
    """
    if not text:
        return text

    if not LEGACY_COMPAT:
        return text

    if _current_version != PM3_VERSION_ORIGINAL:
        return text

    result = text

    # Phase B: Command-specific normalizations
    if cmd:
        cmd_stripped = cmd.strip()
        for prefix, normalizers in _RESPONSE_NORMALIZERS.items():
            if cmd_stripped.startswith(prefix):
                for normalizer in normalizers:
                    result = normalizer(result)
                break

    # Phase C: Remaining generic normalizations
    result = _post_normalize(result)

    return result
