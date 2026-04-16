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
# ANSI stripping
# ---------------------------------------------------------------------------

_ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')


def strip_ansi(text):
    """Remove ANSI color/formatting escape sequences from text."""
    if not text:
        return text
    return _ANSI_RE.sub('', text)


# ---------------------------------------------------------------------------
# Translation rules
#
# Each rule: (compiled_regex, replacement)
#   replacement is either a string template (for re.sub) or a callable
#   that takes the match object and returns the translated command.
#
# Rules are tried in order; first match wins.  Order matters: more specific
# patterns must come before less specific ones (e.g. 'hf mf wrbl' before
# 'hf mf rdbl', 'nested o' before bare 'nested').
# ---------------------------------------------------------------------------

def _translate_mf_fchk(m):
    """hf mf fchk {size} {keyfile} -> hf mf fchk {--size_flag} -f {keyfile}"""
    return 'hf mf fchk %s -f %s' % (_size_flag(m.group(1)), m.group(2))


def _translate_mf_nested(m):
    """hf mf nested o {blk} {A/B} {key} {tblk} {ttype}"""
    blk = m.group(1)
    kt = _key_type_flag(m.group(2))
    key = m.group(3)
    tblk = m.group(4)
    tkt = _target_key_type_flag(m.group(5))
    return 'hf mf nested --1k --blk %s %s -k %s --tblk %s %s' % (blk, kt, key, tblk, tkt)


def _translate_mf_nested_sized(m):
    """hf mf nested {size} {blk} {A/B} {key} {tblk} {ttype}"""
    size = m.group(1)
    blk = m.group(2)
    kt = _key_type_flag(m.group(3))
    key = m.group(4)
    tblk = m.group(5)
    tkt = _target_key_type_flag(m.group(6))
    return 'hf mf nested %s --blk %s %s -k %s --tblk %s %s' % (
        _size_flag(size), blk, kt, key, tblk, tkt)


def _translate_mf_staticnested(m):
    """hf mf staticnested {size} {blk} {A/B} {key}"""
    return 'hf mf staticnested %s --blk %s %s -k %s' % (
        _size_flag(m.group(1)), m.group(2),
        _key_type_flag(m.group(3)), m.group(4))


def _translate_mf_wrbl(m):
    """hf mf wrbl {blk} {A/B} {key} {data}"""
    # Always add --force: iceman requires it for block 0 (manufacturer)
    # and sector trailers with strict access conditions.  Legacy PM3
    # had no such checks — --force restores legacy behavior.
    return 'hf mf wrbl --blk %s %s -k %s -d %s --force' % (
        m.group(1), _key_type_flag(m.group(2)), m.group(3), m.group(4))


def _translate_mf_rdbl(m):
    """hf mf rdbl {blk} {A/B} {key}"""
    return 'hf mf rdbl --blk %s %s -k %s' % (
        m.group(1), _key_type_flag(m.group(2)), m.group(3))


def _translate_mf_rdsc(m):
    """hf mf rdsc {sec} {A/B} {key}"""
    return 'hf mf rdsc -s %s %s -k %s' % (
        m.group(1), _key_type_flag(m.group(2)), m.group(3))


def _translate_mf_csetuid(m):
    """hf mf csetuid {uid} {sak} {atqa} w"""
    uid = m.group(1)
    sak = m.group(2)
    atqa = m.group(3)
    # 'w' suffix is optional in capture
    has_w = m.group(4) is not None
    result = 'hf mf csetuid -u %s -s %s -a %s' % (uid, sak, atqa)
    if has_w:
        result += ' -w'
    return result


def _translate_mf_csave(m):
    """hf mf csave {type} o {file}"""
    return 'hf mf csave --1k -f %s' % m.group(2)


def _translate_em410x_write(m):
    """lf em 410x_write {id} 1 -> lf em 410x clone --id {id}"""
    return 'lf em 410x clone --id %s' % m.group(1)


def _translate_em4x05_info_pwd(m):
    """lf em 4x05_info {pwd} -> lf em 4x05 info -p {pwd}"""
    return 'lf em 4x05 info -p %s' % m.group(1)


def _translate_em4x05_read(m):
    """lf em 4x05_read {blk} {key} -> lf em 4x05 read -a {blk} -p {key}"""
    return 'lf em 4x05 read -a %s -p %s' % (m.group(1), m.group(2))


def _translate_em4x05_write(m):
    """lf em 4x05_write {blk} {data} {key} -> lf em 4x05 write -a {blk} -d {data} -p {key}"""
    return 'lf em 4x05 write -a %s -d %s -p %s' % (
        m.group(1), m.group(2), m.group(3))


def _translate_14a_raw(m):
    """hf 14a raw ... -p ... -> hf 14a raw ... -k ...
    Replace -p (keep-field-on) with -k. Must not touch other flags."""
    cmd = m.group(0)
    # Replace only the -p flag that means keep-field-on.
    # -p appears as a standalone flag (not followed by a value argument).
    # Use word-boundary-like matching: -p followed by space or end-of-string,
    # and preceded by space or start-of-string.
    return re.sub(r'(?<=\s)-p(?=\s|$)', '-k', cmd)


# Commands that hang on iceman firmware and must be blocked.
# These are supplementary commands — the scan flow has all the data it needs
# before calling them.  'hf iclass info' hangs due to FPGA chip mismatch
# reported by hw version on iCopy-X hardware.
_BLOCKED_CMDS_ICEMAN = frozenset({
    'hf iclass info',
})

# Build the rule table.  Each entry is (compiled_regex, replacement).
# replacement: str -> re.sub template; callable -> called with match object.
#
# IMPORTANT for idempotency: patterns are written to match OLD syntax only.
# Already-translated commands (containing --blk, -k, -f etc.) will NOT match
# these patterns because the positional structure differs.

_TRANSLATION_RULES = [
    # -----------------------------------------------------------------------
    # Category 3: NAME CHANGES (must come first — change command name)
    # -----------------------------------------------------------------------

    # lf em 410x_write {id} 1 -> lf em 410x clone --id {id}
    (re.compile(r'^lf em 410x_write\s+(\S+)(?:\s+1)?$'), _translate_em410x_write),

    # lf em 410x_read -> lf em 410x reader
    (re.compile(r'^lf em 410x_read$'), 'lf em 410x reader'),

    # lf {type} read -> lf {type} reader (19 LF protocols renamed in iceman)
    # Also: lf fdx read -> lf fdxb reader (namespace + verb change)
    (re.compile(r'^lf fdx read$'), 'lf fdxb reader'),
    (re.compile(r'^(lf (?:hid|indala|awid|io|gproxii|securakey|viking|pyramid|'
                r'gallagher|jablotron|keri|nedap|noralsy|pac|paradox|presco|'
                r'visa2000|nexwatch)) read$'), r'\1 reader'),

    # lf em 410x_sim {id} -> lf em 410x sim --id {id}
    (re.compile(r'^lf em 410x_sim\s+(\S+)$'), r'lf em 410x sim --id \1'),

    # lf em 4x05_write {blk} {data} {key} -> lf em 4x05 write -b {blk} -d {data} -p {key}
    (re.compile(r'^lf em 4x05_write\s+(\S+)\s+(\S+)\s+(\S+)$'), _translate_em4x05_write),

    # lf em 4x05_read {blk} {key} -> lf em 4x05 read -b {blk} -p {key}
    (re.compile(r'^lf em 4x05_read\s+(\S+)\s+(\S+)$'), _translate_em4x05_read),

    # lf em 4x05_info {pwd} -> lf em 4x05 info -p {pwd}
    (re.compile(r'^lf em 4x05_info\s+(\S+)$'), _translate_em4x05_info_pwd),

    # lf em 4x05_info (no args) -> lf em 4x05 info
    (re.compile(r'^lf em 4x05_info$'), 'lf em 4x05 info'),

    # lf em 4x05_dump f {file} -> lf em 4x05 dump -f {file}
    (re.compile(r'^lf em 4x05_dump\s+f\s+(\S+)$'), r'lf em 4x05 dump -f \1'),

    # lf em 4x05_dump (no args) -> lf em 4x05 dump
    (re.compile(r'^lf em 4x05_dump$'), 'lf em 4x05 dump'),

    # lf em 4x05_read {blk} (no key) -> lf em 4x05 read -b {blk}
    # lf em 4x05_read {blk} (no key) -> lf em 4x05 read -a {blk}
    (re.compile(r'^lf em 4x05_read\s+(\S+)$'), r'lf em 4x05 read -a \1'),

    # -----------------------------------------------------------------------
    # Category 2: ARGUMENT CHANGES -- complex (must come before simpler)
    # -----------------------------------------------------------------------

    # hf mf nested o {blk} {A/B} {key} {tblk} {ttype}  (one-sector mode)
    (re.compile(r'^hf mf nested\s+o\s+(\S+)\s+([AB])\s+(\S+)\s+(\S+)\s+([AB])$'),
     _translate_mf_nested),

    # hf mf nested {size} {blk} {A/B} {key} {tblk} {ttype}  (size-code mode)
    # hfmfkeys.py sends: 'hf mf nested 1 0 A FFFFFFFFFFFF 4 A'
    (re.compile(r'^hf mf nested\s+([0-9]+)\s+(\S+)\s+([AB])\s+(\S+)\s+(\S+)\s+([AB])$'),
     _translate_mf_nested_sized),

    # hf mf staticnested {size} {blk} {A/B} {key}
    (re.compile(r'^hf mf staticnested\s+(\S+)\s+(\S+)\s+([AB])\s+(\S+)$'),
     _translate_mf_staticnested),

    # hf mf fchk {size} {keyfile}
    (re.compile(r'^hf mf fchk\s+([0-9]+)\s+(\S+)$'), _translate_mf_fchk),

    # hf mf wrbl {blk} {A/B} {key} {data}  (must come before rdbl)
    (re.compile(r'^hf mf wrbl\s+(\S+)\s+([AB])\s+(\S+)\s+(\S+)$'), _translate_mf_wrbl),

    # hf mf rdbl {blk} {A/B} {key}
    (re.compile(r'^hf mf rdbl\s+(\S+)\s+([AB])\s+(\S+)$'), _translate_mf_rdbl),

    # hf mf rdsc {sec} {A/B} {key}
    (re.compile(r'^hf mf rdsc\s+(\S+)\s+([AB])\s+(\S+)$'), _translate_mf_rdsc),

    # hf mf csetuid {uid} {sak} {atqa} [w]
    (re.compile(r'^hf mf csetuid\s+(\S+)\s+(\S+)\s+(\S+)(?:\s+(w))?$'), _translate_mf_csetuid),

    # hf mf csetblk {blk} {data}
    (re.compile(r'^hf mf csetblk\s+(\S+)\s+(\S+)$'), r'hf mf csetblk --blk \1 -d \2'),

    # hf mf cgetblk {blk}
    (re.compile(r'^hf mf cgetblk\s+(\S+)$'), r'hf mf cgetblk --blk \1'),

    # hf mf cload b {file}
    (re.compile(r'^hf mf cload\s+b\s+(\S+)$'), r'hf mf cload -f \1'),

    # hf mf csave {type} o {file}
    (re.compile(r'^hf mf csave\s+(\S+)\s+o\s+(\S+)$'), _translate_mf_csave),

    # hf mf dump (bare, no args) -> hf mf dump --1k
    (re.compile(r'^hf mf dump$'), 'hf mf dump --1k'),

    # hf mf restore (bare, no args) -> hf mf restore --1k
    (re.compile(r'^hf mf restore$'), 'hf mf restore --1k'),

    # -----------------------------------------------------------------------
    # Category 2: ARGUMENT CHANGES -- simple flag prefix additions
    # -----------------------------------------------------------------------

    # hf mfu dump f {file} -> hf mfu dump -f {file}
    (re.compile(r'^hf mfu dump\s+f\s+(\S+)$'), r'hf mfu dump -f \1'),

    # hf mfu restore s e f {file} -> hf mfu restore -s -e -f {file}
    (re.compile(r'^hf mfu restore\s+s\s+e\s+f\s+(\S+)$'), r'hf mfu restore -s -e -f \1'),

    # hf 15 dump f {path} -> hf 15 dump -f {path}
    (re.compile(r'^hf 15 dump\s+f\s+(\S+)$'), r'hf 15 dump -f \1'),

    # hf 15 restore f {file} -> hf 15 restore -f {file}
    (re.compile(r'^hf 15 restore\s+f\s+(\S+)$'), r'hf 15 restore -f \1'),

    # hf 15 csetuid {uid} -> hf 15 csetuid -u {uid}
    (re.compile(r'^hf 15 csetuid\s+(\S+)$'), r'hf 15 csetuid -u \1'),

    # hf iclass dump k {key} f {path} [e] -> hf iclass dump -k {key} -f {path} [--elite]
    # 3-arg form (with file path) — MUST come before 1-arg/2-arg forms
    (re.compile(r'^hf iclass dump\s+k\s+(\S+)\s+f\s+(\S+)\s+e$'),
     r'hf iclass dump -k \1 -f \2 --elite'),
    (re.compile(r'^hf iclass dump\s+k\s+(\S+)\s+f\s+(\S+)$'),
     r'hf iclass dump -k \1 -f \2'),
    # hf iclass dump k {key} [e] -> hf iclass dump -k {key} [--elite]
    (re.compile(r'^hf iclass dump\s+k\s+(\S+)\s+e$'), r'hf iclass dump -k \1 --elite'),
    (re.compile(r'^hf iclass dump\s+k\s+(\S+)$'), r'hf iclass dump -k \1'),

    # hf iclass chk f {file} -> hf iclass chk -f {file}
    (re.compile(r'^hf iclass chk\s+f\s+(\S+)$'), r'hf iclass chk -f \1'),
    # hf iclass chk (bare, no args) -> hf iclass chk --vb6kdf
    (re.compile(r'^hf iclass chk$'), 'hf iclass chk --vb6kdf'),

    # hf iclass rdbl b {blk} k {key} [e] -> hf iclass rdbl --blk {blk} -k {key} [--elite]
    (re.compile(r'^hf iclass rdbl\s+b\s+(\S+)\s+k\s+(\S+)\s+e$'),
     r'hf iclass rdbl --blk \1 -k \2 --elite'),
    (re.compile(r'^hf iclass rdbl\s+b\s+(\S+)\s+k\s+(\S+)$'),
     r'hf iclass rdbl --blk \1 -k \2'),

    # hf iclass wrbl -b {blk} ... -> hf iclass wrbl --blk {blk} ...
    # iclasswrite.py already uses flag syntax but -b is wrong (no short flag defined)
    (re.compile(r'^(hf iclass wrbl)\s+-b\s+(\S+)\s+(.+)$'), r'\1 --blk \2 \3'),

    # hf iclass calcnewkey o {old} n {new} [--elite] -> --old {old} --new {new} [--elite]
    (re.compile(r'^hf iclass calcnewkey\s+o\s+(\S+)\s+n\s+(\S+)\s+(--elite)$'),
     r'hf iclass calcnewkey --old \1 --new \2 --elite'),
    (re.compile(r'^hf iclass calcnewkey\s+o\s+(\S+)\s+n\s+(\S+)$'),
     r'hf iclass calcnewkey --old \1 --new \2'),

    # lf t55xx detect p {pwd} -> lf t55xx detect -p {pwd}
    (re.compile(r'^lf t55xx detect\s+p\s+(\S+)$'), r'lf t55xx detect -p \1'),

    # lf t55xx dump f {file} p {key} -> lf t55xx dump -f {file} -p {key}  (3-arg, before 2-arg)
    (re.compile(r'^lf t55xx dump\s+f\s+(\S+)\s+p\s+(\S+)$'), r'lf t55xx dump -f \1 -p \2'),

    # lf t55xx dump f {file} -> lf t55xx dump -f {file}
    (re.compile(r'^lf t55xx dump\s+f\s+(\S+)$'), r'lf t55xx dump -f \1'),

    # lf t55xx read b {blk} p {key} o {page} -> lf t55xx read -b {blk} -p {key} --page1
    (re.compile(r'^lf t55xx read\s+b\s+(\S+)\s+p\s+(\S+)\s+o\s+(\S+)$'),
     r'lf t55xx read -b \1 -p \2 --page1'),

    # lf t55xx read b {blk} p {key} -> lf t55xx read -b {blk} -p {key}  (before single-arg)
    (re.compile(r'^lf t55xx read\s+b\s+(\S+)\s+p\s+(\S+)$'), r'lf t55xx read -b \1 -p \2'),

    # lf t55xx read b {blk} -> lf t55xx read -b {blk}
    (re.compile(r'^lf t55xx read\s+b\s+(\S+)$'), r'lf t55xx read -b \1'),

    # lf t55xx write b {blk} d {data} p {key} -> ... -b -d -p  (3-arg, before 2-arg)
    (re.compile(r'^lf t55xx write\s+b\s+(\S+)\s+d\s+(\S+)\s+p\s+(\S+)$'),
     r'lf t55xx write -b \1 -d \2 -p \3'),

    # lf t55xx write b {blk} d {data} -> lf t55xx write -b {blk} -d {data}
    (re.compile(r'^lf t55xx write\s+b\s+(\S+)\s+d\s+(\S+)$'), r'lf t55xx write -b \1 -d \2'),

    # lf t55xx wipe p {key} -> lf t55xx wipe -p {key}
    (re.compile(r'^lf t55xx wipe\s+p\s+(\S+)$'), r'lf t55xx wipe -p \1'),

    # lf t55xx restore f {file} -> lf t55xx restore -f {file}
    (re.compile(r'^lf t55xx restore\s+f\s+(\S+)$'), r'lf t55xx restore -f \1'),

    # lf t55xx chk f {file} -> lf t55xx chk -f {file}
    (re.compile(r'^lf t55xx chk\s+f\s+(\S+)$'), r'lf t55xx chk -f \1'),

    # lf hid clone {raw} -> lf hid clone -r {raw}
    (re.compile(r'^lf hid clone\s+(\S+)$'), r'lf hid clone -r \1'),

    # lf indala clone {type} -r {raw} -> lf indala clone -r {raw}
    (re.compile(r'^lf indala clone\s+\S+\s+-r\s+(\S+)$'), r'lf indala clone -r \1'),

    # lf fdx clone c {C} n {N} -> lf fdxb clone --country {C} --national {N}
    # Command renamed from 'lf fdx' to 'lf fdxb' in iceman, flags also changed.
    (re.compile(r'^lf fdx clone\s+c\s+(\S+)\s+n\s+(\S+)$'),
     r'lf fdxb clone --country \1 --national \2'),

    # lf {type} clone b {raw} -> lf {type} clone -r {raw}
    # Covers: securakey, gallagher, pac, paradox
    (re.compile(r'^(lf (?:securakey|gallagher|pac|paradox) clone)\s+b\s+(\S+)$'), r'\1 -r \2'),

    # lf nexwatch clone r {raw} -> lf nexwatch clone -r {raw}
    (re.compile(r'^lf nexwatch clone\s+r\s+(\S+)$'), r'lf nexwatch clone -r \1'),

    # data save f {file} -> data save -f {file}
    (re.compile(r'^data save\s+f\s+(\S+)$'), r'data save -f \1'),

    # hf 14a raw ... -p ... -> hf 14a raw ... -k ...
    # This is a flag rename, not a structural change.  Match the whole command
    # only when it contains the -p flag (standalone, not part of another word).
    (re.compile(r'^hf 14a raw\s+.*(?<=\s)-p(?=\s|$).*$'), _translate_14a_raw),

    # hf 14a sim t {type} u {uid} -> hf 14a sim -t {type} -u {uid}
    # Simulation command — positional t/u became flags in iceman.
    (re.compile(r'^hf 14a sim\s+t\s+(\S+)\s+u\s+(\S+)$'), r'hf 14a sim -t \1 -u \2'),

    # hf list {protocol} -> hf list -t {protocol}
    # Trace listing — positional protocol became -t flag in iceman.
    (re.compile(r'^hf list\s+(\S+)$'), r'hf list -t \1'),
    (re.compile(r'^lf list\s+(\S+)$'), r'lf list -t \1'),

    # lf config a {avg} t {trig} s {skip} -> lf config -a {avg} -t {trig} -s {skip}
    # T5577 sniff configuration — positional args became flags.
    (re.compile(r'^lf config\s+a\s+(\S+)\s+t\s+(\S+)\s+s\s+(\S+)$'),
     r'lf config -a \1 -t \2 -s \3'),

    # mem spiffs load f {src} o {dest} -> mem spiffs upload -s {src} -d {dest}
    # Diagnosis flash memory test — 'load' renamed to 'upload' in iceman,
    # positional f/o became -s/-d flags.
    (re.compile(r'^mem spiffs load\s+f\s+(\S+)\s+o\s+(\S+)$'),
     r'mem spiffs upload -s \1 -d \2'),
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
    """Return True if we're on iceman firmware and need translation."""
    return _current_version == PM3_VERSION_ICEMAN


def translate(cmd):
    """Translate old-syntax PM3 command to current PM3 version syntax.

    If version is original or unknown, returns cmd unchanged.
    If version is iceman, applies translation rules.

    The function is idempotent: calling it on an already-translated command
    will not break it, because the regex patterns only match old-style
    positional syntax.

    Args:
        cmd: PM3 command string (e.g. 'hf mf rdbl 0 A FFFFFFFFFFFF')

    Returns:
        Translated command string.
    """
    if not cmd:
        return cmd

    if _current_version != PM3_VERSION_ICEMAN:
        return cmd

    stripped = cmd.strip()

    # Commands that hang on iceman firmware (FPGA mismatch / hardware issue).
    # Substitute with a harmless command that returns quickly.  The middleware
    # handles empty/missing data gracefully for these supplementary commands.
    if stripped in _BLOCKED_CMDS_ICEMAN:
        logger.info("translate: blocked '%s' (known to hang on iceman)", stripped)
        return 'hw ping'

    for pattern, replacement in _TRANSLATION_RULES:
        m = pattern.match(stripped)
        if m:
            if callable(replacement):
                result = replacement(m)
            else:
                result = m.expand(replacement)
            logger.debug("translate: '%s' -> '%s'", stripped, result)
            return result

    # No rule matched -- pass through unchanged
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

# Normalize dotted field separators to colon format (runs AFTER prefix strip
# and AFTER command-specific normalizers, so only catches remaining patterns).
# Matches lines like "Prng detection..... weak" and normalizes
# the dots to ": " to match old format "Prng detection: weak".
# Uses non-greedy .*? to avoid consuming dots in the match group.
_RE_DOTTED_SEPARATOR = re.compile(
    r'^(\s*\S.*?\S)\.{3,}\s+', re.MULTILINE)

# Strip UID type annotations like "( ONUID, re-used )" from UID lines
_RE_UID_ANNOTATION = re.compile(
    r'(UID:\s*(?:[0-9A-Fa-f]{2}\s*)+?)\s+\([^)]*\)')

# Normalize ISO number spacing: "ISO 14443-A" -> "ISO14443-A" etc.
_RE_ISO_SPACE = re.compile(r'\bISO\s+(1\d{4})')


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
    """Phase C: Generic normalizations that run AFTER command-specific ones.

    Catches remaining dotted separators not handled by specific normalizers,
    strips UID annotations, and normalizes ISO number spacing.
    """
    if not text:
        return text

    # Normalize remaining dotted separators to colon
    # Command-specific normalizers already handled their own dotted patterns
    # (T55xx, EM4x05, Magic, Chipset), so this only catches leftovers
    # like "Prng detection..... weak", "Static nonce....... yes"
    text = _RE_DOTTED_SEPARATOR.sub(r'\1: ', text)

    # FDX-B: After dot-to-colon conversion, "Animal ID...........: X"
    # is now "Animal ID: X".  Remove the colon so REGEX_ANIMAL's \s+ matches.
    # Must run here (Phase C) because Phase B sees the dotted form.
    text = _RE_ANIMAL_ID_COLON.sub(r'\1 ', text)

    # Strip UID annotations: "UID: 5E 5B CE 4C   ( ONUID, re-used )"
    # -> "UID: 5E 5B CE 4C"
    text = _RE_UID_ANNOTATION.sub(r'\1', text)

    # Normalize ISO numbers: "ISO 15693" -> "ISO15693"
    text = _RE_ISO_SPACE.sub(r'ISO\1', text)

    return text


# ===========================================================================
# Layer 2: Command-specific response normalizations
# ===========================================================================

# -- Track B: fchk table normalization --

# New fchk table row: " 000 | 003 | FFFFFFFFFFFF | 1 | FFFFFFFFFFFF | 1"
# Old fchk table row: "| 000 | ffffffffffff   | 1 | ffffffffffff   | 1 |"
_RE_FCHK_NEW_ROW = re.compile(
    r'^\s*(\d{3})\s*\|\s*\d{3}\s*\|\s*([A-Fa-f0-9-]{12})\s*\|\s*(\d)\s*\|\s*([A-Fa-f0-9-]{12})\s*\|\s*(\d)',
    re.MULTILINE)

# New fchk separator: "-----+-----+--------------+---+--------------+----"
_RE_FCHK_NEW_SEP = re.compile(
    r'^-{3,}\+.*$', re.MULTILINE)

# New fchk header: " Sec | Blk | key A        |res| key B        |res"
_RE_FCHK_NEW_HDR = re.compile(
    r'^\s*Sec\s*\|\s*Blk\s*\|.*$', re.MULTILINE)


def _normalize_fchk_table(text):
    """Normalize RRG fchk key table to old pipe-bordered format.

    New: ' 000 | 003 | FFFFFFFFFFFF | 1 | FFFFFFFFFFFF | 1'
    Old: '| 000 | ffffffffffff   | 1 | ffffffffffff   | 1 |'

    Key changes:
    - Remove Blk column
    - Add pipe borders
    - Lowercase hex keys (old used PRIx64, new uses PRIX64)
    - Adjust spacing
    """
    # Replace data rows
    def _fchk_row_replace(m):
        sec = m.group(1)
        key_a = m.group(2).lower()
        res_a = m.group(3)
        key_b = m.group(4).lower()
        res_b = m.group(5)
        return '| %s | %s   | %s | %s   | %s |' % (
            sec, key_a, res_a, key_b, res_b)

    text = _RE_FCHK_NEW_ROW.sub(_fchk_row_replace, text)

    # Replace separators
    text = _RE_FCHK_NEW_SEP.sub(
        '|-----|----------------|---|----------------|---|', text)

    # Replace header
    text = _RE_FCHK_NEW_HDR.sub(
        '| Sec | key A          |res| key B          |res|', text)

    return text


# -- Track B: darkside key format --

# New: "Found valid key [ AABBCCDDEEFF ]"
# Old: "Found valid key: aabbccddeeff"  (middleware regex: r'Found valid key\s*:\s*(...)')
_RE_DARKSIDE_NEW = re.compile(
    r'Found valid key\s*\[\s*([A-Fa-f0-9]{12})\s*\]')


def _normalize_darkside_key(text):
    """Normalize darkside key output to old format.

    Preserves 'Found' capitalization to match middleware regex in
    hfmfkeys.py: r'Found valid key\\s*:\\s*([A-Fa-f0-9]{12})'
    """
    def _dk_replace(m):
        return 'Found valid key: %s' % m.group(1).lower()
    return _RE_DARKSIDE_NEW.sub(_dk_replace, text)


# -- Track C: wrbl/rdsc/restore isOk normalization --

def _normalize_wrbl_response(text):
    """Normalize wrbl/rdsc/restore response format.

    New: 'Write ( ok )' / 'Write ( fail )'
    Old: 'isOk:01' / 'isOk:00'

    Also handles restore table rows:
    New: ' N | data... | ( ok )' / '( fail )'
    """
    # wrbl success
    text = text.replace('Write ( ok )', 'isOk:01')
    text = text.replace('Write ( fail )', 'isOk:00')

    # restore rows: "( ok )" -> "isOk:01", "( fail )" -> "isOk:00"
    # Be careful not to replace other "(ok)" patterns
    text = re.sub(r'\(\s*ok\s*\)', 'isOk:01', text)
    text = re.sub(r'\(\s*fail\s*\)', 'isOk:00', text)

    return text


# -- Track C: rdbl/cgetblk data format --

# New rdbl table row: "  0 | AA BB CC DD EE FF 00 11 22 33 44 55 66 77 88 99 | .ascii."
# Old rdbl format:    "data: AA BB CC DD EE FF 00 11 22 33 44 55 66 77 88 99"
_RE_RDBL_TABLE_ROW = re.compile(
    r'^\s*(\d+)\s*\|\s*((?:[A-Fa-f0-9]{2}\s+){15}[A-Fa-f0-9]{2})\s*\|.*$',
    re.MULTILINE)

# Table headers from rdbl/rdsc/cgetblk
_RE_RDBL_TABLE_HDR = re.compile(
    r'^\s*#\s*\|\s*sector\s+\d+.*$', re.MULTILINE)
_RE_RDBL_TABLE_SEP = re.compile(
    r'^-{3,}\+-{3,}.*$', re.MULTILINE)


def _normalize_rdbl_response(text):
    """Normalize rdbl/cgetblk block data to old 'data:' format.

    New: '  0 | AA BB CC ... | ascii'
    Old: 'data: AA BB CC ...'

    Preserves block number for sector reads (multiple blocks).
    """
    def _rdbl_replace(m):
        block_data = m.group(2).strip()
        return 'data: %s' % block_data

    text = _RE_RDBL_TABLE_ROW.sub(_rdbl_replace, text)
    # Remove table headers and separators
    text = _RE_RDBL_TABLE_HDR.sub('', text)
    text = _RE_RDBL_TABLE_SEP.sub('', text)
    return text


# -- Track C: Magic capabilities --

_RE_MAGIC_DOTTED = re.compile(r'Magic capabilities\.{3,}\s+', re.MULTILINE)


def _normalize_magic_capabilities(text):
    """Normalize magic capabilities format.

    New: 'Magic capabilities... Gen 1a'
    Old: 'Magic capabilities : Gen 1a'
    """
    return _RE_MAGIC_DOTTED.sub('Magic capabilities : ', text)


# -- Track D: EM410x ID format --

# New: "EM 410x ID 0100000058"
# Old: "EM TAG ID      : 0100000058"
# Requires minimum 5 hex chars to avoid matching "found!" in "Valid EM 410x ID found!"
_RE_EM410X_NEW = re.compile(r'EM 410x (?:XL )?ID\s+([0-9A-Fa-f]{5,})')

# Also normalize the "Valid" keyword line: "Valid EM 410x ID" -> "Valid EM410x ID"
_RE_VALID_EM410X = re.compile(r'Valid EM 410x ID')


def _normalize_em410x_id(text):
    """Normalize EM410x ID format.

    New: 'EM 410x ID 0100000058' -> 'EM TAG ID      : 0100000058'
    New: 'Valid EM 410x ID' -> 'Valid EM410x ID'
    """
    # Normalize the data ID line
    def _em_replace(m):
        return 'EM TAG ID      : %s' % m.group(1)
    text = _RE_EM410X_NEW.sub(_em_replace, text)
    # Normalize the Valid keyword line
    text = _RE_VALID_EM410X.sub('Valid EM410x ID', text)
    return text


# -- Track D: Chipset detection format --

_RE_CHIPSET_NEW = re.compile(r'^\s*Chipset\.{3,}\s+(.*?)$', re.MULTILINE)


def _normalize_chipset_detection(text):
    """Normalize chipset detection format.

    New: 'Chipset... EM4x05 / EM4x69'
    Old: 'Chipset detection: EM4x05 / EM4x69'
    """
    return _RE_CHIPSET_NEW.sub(r'Chipset detection: \1', text)


# -- Track D: 'No data found!' restoration --

def _normalize_lf_no_data(text):
    """Restore 'No data found!' message for lf search.

    In the new firmware, this message was removed. If lf search produces
    no tag detection AND no 'No known 125/134 kHz tags found!', the
    middleware expects 'No data found!' to be present.
    This is handled at the scan level - if lf search returns empty/no
    valid tags, we inject the expected marker.
    """
    # If the text is empty or has no tag detection at all, inject the marker
    if not text or not text.strip():
        return 'No data found!\n'
    return text


# -- Track D: HID Prox format --

# New HID output uses hid_print_card() with wiegand decode
# We need to extract raw value and emit old-style "HID Prox - XXXX"
_RE_HID_RAW = re.compile(r'raw:\s*([0-9A-Fa-f]+)', re.IGNORECASE)

# Strip leading zeros from HID Prox hex (iceman pads to 24 chars, legacy was 8-16)
_RE_HID_PROX_LINE = re.compile(r'HID Prox - (0*)([0-9A-Fa-f]+)')


def _normalize_hid_prox(text):
    """Normalize HID Prox output to old format.

    Bug 2: iceman outputs 'HID Prox - 000000000000002006222332' (24 chars,
    zero-padded) while legacy used shorter hex (8-16 chars).  Strip leading
    zeros so lfsearch REGEX_HID extracts the meaningful portion.

    Also prepend old-style line if missing (pure wiegand decode output).
    """
    if 'Valid HID Prox ID' not in text:
        return text

    if 'HID Prox -' not in text:
        # Pure wiegand decode output — prepend old-style line from raw
        m = _RE_HID_RAW.search(text)
        if m:
            raw = m.group(1)
            text = 'HID Prox - %s\n%s' % (raw, text)

    # Strip leading zeros from HID Prox line (keep at least 8 chars)
    def _strip_hid_zeros(m):
        leading = m.group(1)
        value = m.group(2)
        # Keep at least 8 hex chars to match legacy %08x format
        full = leading + value
        stripped = full.lstrip('0') or '0'
        if len(stripped) < 8:
            stripped = full[-(max(8, len(stripped))):]
        return 'HID Prox - %s' % stripped

    text = _RE_HID_PROX_LINE.sub(_strip_hid_zeros, text)
    return text


# -- Track D: FDX-B Animal ID format --

# Bug 3: iceman outputs "Animal ID: 060-030207938416" (colon after ID).
# Legacy output: "Animal Tag ID      0060-030207938416" (spaces, no colon).
# lfsearch REGEX_ANIMAL = r'.*ID\s+([xX0-9A-Fa-f\-]{2,})' requires
# whitespace after ID, not a colon.  Fix: remove colons after ID keywords.
_RE_ANIMAL_ID_COLON = re.compile(r'(Animal(?:\s+Tag)?\s+ID)[\s.]*:', re.IGNORECASE)


def _normalize_fdxb_animal_id(text):
    """Normalize FDX-B Animal ID format for REGEX_ANIMAL matching.

    New: 'Animal ID: 060-030207938416'
    Old: 'Animal Tag ID      0060-030207938416'

    Remove colon after 'Animal ID' so REGEX_ANIMAL's \\s+ matches.
    """
    if 'FDX-B' not in text and 'Animal' not in text:
        return text
    return _RE_ANIMAL_ID_COLON.sub(r'\1 ', text)


# -- Track D: Gallagher field format --

# Bug 5: iceman outputs "GALLAGHER - Region: 0 Facility: 4369 Card No.: 0"
# lfsearch _RE_FC expects "FC:" and _RE_CN expects "Card:" or "CN:".
# "Facility:" doesn't match _RE_FC; "Card No.:" confuses _RE_CN.
_RE_GALLAGHER_FACILITY = re.compile(r'\bFacility:\s+(\d+)')
_RE_GALLAGHER_CARD_NO = re.compile(r'\bCard No\.:\s+(\d+)')


def _normalize_gallagher_fields(text):
    """Normalize Gallagher field names for FC/CN regex matching.

    New: 'Facility: 4369 Card No.: 0'
    Old: 'FC: 4369 Card: 0'

    Convert Gallagher-specific field names to the standard FC:/Card: format
    that lfsearch _RE_FC and _RE_CN expect.
    """
    if 'GALLAGHER' not in text:
        return text
    text = _RE_GALLAGHER_FACILITY.sub(r'FC: \1', text)
    text = _RE_GALLAGHER_CARD_NO.sub(r'Card: \1', text)
    return text


# -- Track D: SecuraKey hex FC --

# Bug 6: iceman outputs "FC: 0x2AAA" (hex) but lfsearch's getFCCN()
# calls int(cleanHexStr(fc)) which fails on hex letters ('2AAA').
# Legacy PM3 output FC as decimal.  Convert hex FC to decimal.
_RE_FC_HEX = re.compile(r'\bFC:\s+(0x[0-9A-Fa-f]+)')


def _normalize_securakey_fc_hex(text):
    """Convert hex FC values to decimal for lfsearch compatibility.

    New: 'FC: 0x2AAA'  -> 'FC: 10922'
    """
    if 'Securakey' not in text and 'SECURAKEY' not in text:
        return text

    def _hex_to_dec(m):
        try:
            return 'FC: %d' % int(m.group(1), 16)
        except ValueError:
            return m.group(0)

    return _RE_FC_HEX.sub(_hex_to_dec, text)


# -- Track D: AWID unknown format card number --

# Bug 1: iceman outputs "AWID - len: 222 -unknown- (57051) - Wiegand: ..."
# For known formats, FC:/Card: are present.  For unknown formats, the card
# number is in parentheses but no Card: line exists.  lfsearch setUID2FCCN
# needs Card: to extract CN.
_RE_AWID_UNKNOWN_CARD = re.compile(
    r'AWID\s*-\s*len:\s*\d+\s+-unknown-\s+\((\d+)\)')


def _normalize_awid_card_number(text):
    """Add Card: line for AWID unknown format cards.

    New: 'AWID - len: 222 -unknown- (57051) - Wiegand: ...'
    Fix: Append 'Card: 57051' so _RE_CN can extract it.
    """
    if 'AWID' not in text:
        return text
    m = _RE_AWID_UNKNOWN_CARD.search(text)
    if m and 'Card:' not in text:
        card_num = m.group(1)
        # Insert Card: line after the AWID detection line
        text = text + '\nCard: %s' % card_num
    return text


# -- Track D: Keri / keyword case normalization --

# Bug 7: iceman may output "Valid Keri ID" (mixed case) but lfsearch
# checks "Valid KERI ID" (all caps).  hasKeyword uses case-sensitive
# re.search.  Normalize known case differences.
_LF_KEYWORD_CASE_MAP = {
    'Valid Keri ID': 'Valid KERI ID',
    'Valid keri ID': 'Valid KERI ID',
}


def _normalize_lf_keyword_case(text):
    """Normalize case of LF Valid keyword lines.

    Iceman may use different casing than the legacy PM3 for certain tag
    detection keywords.  lfsearch.py checks exact case via re.search.
    """
    for old, new in _LF_KEYWORD_CASE_MAP.items():
        if old in text:
            text = text.replace(old, new)
    return text


# -- Track D: Indala long raw to short UID --

# Bug 8: iceman outputs "Indala (len 130)  Raw: 800000000000005..."
# The full raw is 28+ bytes (56+ hex chars) which is too long for display.
# The lfsearch handler sets data = raw (full hex), which truncates on
# the small screen showing only trailing zeros.
# For long Indala, extract the meaningful middle portion as a Card: line.
_RE_INDALA_LONG = re.compile(
    r'Indala\s+\(len\s+(\d+)\)\s+Raw:\s+([0-9A-Fa-f]+)')


def _normalize_indala_uid(text):
    """Add short Card ID for long Indala raw data.

    For Indala cards with raw > 16 hex chars, extract a meaningful
    portion and add as Card: line so REGEX_CARD_ID can extract a
    display-friendly UID.
    """
    if 'Indala' not in text:
        return text
    m = _RE_INDALA_LONG.search(text)
    if not m:
        return text
    raw_hex = m.group(2)
    if len(raw_hex) <= 16:
        return text  # Short Indala, raw is already usable
    # Extract meaningful portion: strip leading 80/00 padding and trailing 00s
    stripped = raw_hex.lstrip('0')
    if stripped.startswith('8'):
        # Leading 0x80 is a start marker, skip it
        stripped = stripped[1:].lstrip('0')
    # Trim trailing zeros
    stripped_trail = stripped.rstrip('0') or stripped[:8]
    # Use up to 16 chars of the meaningful portion
    short_id = stripped_trail[:16] if len(stripped_trail) > 16 else stripped_trail
    if short_id and 'Card:' not in text:
        text = text + '\nCard: %s' % short_id
    return text


# -- Track E: T55xx config normalization --

# New T55xx config lines use dots and no colon, lowercase "type"
# These patterns run on prefix-stripped text (no [+] markers)
_RE_T55XX_CHIP_NEW = re.compile(
    r'^\s*Chip type\.{3,}\s+(.*?)$', re.MULTILINE | re.IGNORECASE)
_RE_T55XX_MOD_NEW = re.compile(
    r'^\s*Modulation\.{3,}\s+(.*?)$', re.MULTILINE)
_RE_T55XX_BLOCK0_NEW = re.compile(
    r'^\s*Block0\.{3,}\s+([A-Fa-f0-9]{8})(?:\s+\S.*)?$', re.MULTILINE)
_RE_T55XX_PWD_SET_NEW = re.compile(
    r'^\s*Password set\.{3,}\s+(.*?)$', re.MULTILINE | re.IGNORECASE)
_RE_T55XX_PWD_NEW = re.compile(
    r'^\s*Password\.{3,}\s+([A-Fa-f0-9]{8})', re.MULTILINE | re.IGNORECASE)


def _normalize_t55xx_config(text):
    """Normalize T55xx configuration output to old format.

    New: 'Chip type......... T55x7'
    Old: '     Chip Type      : T55x7'

    Restores colon separators and proper casing for regex matching.
    """
    text = _RE_T55XX_CHIP_NEW.sub(
        r'     Chip Type      : \1', text)
    text = _RE_T55XX_MOD_NEW.sub(
        r'     Modulation     : \1', text)
    text = _RE_T55XX_BLOCK0_NEW.sub(
        r'     Block0         : 0x\1', text)
    text = _RE_T55XX_PWD_SET_NEW.sub(
        r'     Password Set   : \1', text)
    text = _RE_T55XX_PWD_NEW.sub(
        r'     Password       : \1', text)
    return text


# -- Track E: EM4x05 info normalization --

_RE_EM4X05_CHIP_NEW = re.compile(
    r'^\s*Chip type\.{3,}\s+(.*?)$', re.MULTILINE | re.IGNORECASE)
_RE_EM4X05_SERIAL_NEW = re.compile(
    r'^\s*Serialno\.{3,}\s+([A-Fa-f0-9]+)', re.MULTILINE)
_RE_EM4X05_CONFIG_NEW = re.compile(
    r'^\s*Config word\.{3,}\s+([A-Fa-f0-9]+)', re.MULTILINE | re.IGNORECASE)


def _normalize_em4x05_info(text):
    """Normalize EM4x05 info output to old format.

    Restores colon-separated labels with pipe separators and parentheticals
    for middleware regex matching:
      _RE_CHIP  = r'.*Chip Type.*\\|(.*)'
      _RE_CONFIG = r'.*ConfigWord:(.*)\\(.*'
    """
    # Chip Type needs pipe: " Chip Type:   9 | EM4305"
    def _em_chip_replace(m):
        val = m.group(1).strip()
        return ' Chip Type:   %s | %s' % ('0', val)
    text = _RE_EM4X05_CHIP_NEW.sub(_em_chip_replace, text)
    text = _RE_EM4X05_SERIAL_NEW.sub(
        r'  Serial #: \1', text)
    # ConfigWord needs parenthetical: "ConfigWord: 00080040 (xx)"
    def _em_config_replace(m):
        val = m.group(1).strip()
        return ' ConfigWord: %s (%s)' % (val, val)
    text = _RE_EM4X05_CONFIG_NEW.sub(_em_config_replace, text)
    return text


# -- Track E: save message normalization --

_RE_SAVED_UPPER = re.compile(r'^Saved\s+', re.MULTILINE)


def _normalize_save_messages(text):
    """Normalize file save messages from uppercase to lowercase.

    New: 'Saved 64 bytes to binary file `lf-t55xx-...`'
    Old: 'saved 64 bytes to binary file lf-t55xx-...'

    Also strips backtick quoting around filenames.
    """
    text = _RE_SAVED_UPPER.sub('saved ', text)
    # Strip backtick quoting: `filename` -> filename
    text = re.sub(r'`([^`]+)`', r'\1', text)
    return text


# -- Track F: hf 15 restore normalization --

def _normalize_hf15_restore(text):
    """Normalize hf 15 restore response for legacy keyword matching.

    New (iceman): 'Restoring data blocks\\n\\nDone!'
    Old (legacy): 'Write OK\\n...\\ndone'

    hf15write.py checks hasKeyword('Write OK') and hasKeyword('done').
    Iceman uses 'Done!' instead.  Inject legacy keywords on success.
    """
    if 'Done' in text:
        text = text + '\nWrite OK\ndone'
    return text


# -- Track F: iCLASS write normalization --

_RE_ICLASS_OK = re.compile(
    r'Wrote block \d+\s*/\s*0x[0-9A-Fa-f]+\s*\(\s*ok\s*\)')


def _normalize_iclass_wrbl(text):
    """Normalize iCLASS write block response.

    New: 'Wrote block 7 / 0x07 ( ok )'
    Old: 'Wrote block 07 successful'
    """
    def _ic_replace(m):
        return m.group(0).replace('( ok )', 'successful')
    return _RE_ICLASS_OK.sub(_ic_replace, text)


# -- Track F: iCLASS rdbl response normalization --

# New iclass rdbl format: " block   6/0x06 : AA BB CC DD EE FF 00 11"
# Old iclass rdbl format: "Block 6 : AA BB CC DD EE FF 00 11"
# Middleware regex: r'[Bb]lock \d+ : ([a-fA-F0-9 ]+)'
# The /0xHH part and extra padding break the \d+ match.
_RE_ICLASS_RDBL_NEW = re.compile(
    r'^\s*block\s+(\d+)/0x[0-9A-Fa-f]+\s*:\s*(.+)$',
    re.MULTILINE | re.IGNORECASE)


def _normalize_iclass_rdbl(text):
    """Normalize iCLASS read block response to old format.

    New: ' block   6/0x06 : AA BB CC DD EE FF 00 11'
    Old: 'Block 6 : AA BB CC DD EE FF 00 11'

    Strips the /0xHH hex representation and normalizes spacing
    so middleware regex r'[Bb]lock \\d+ : ([a-fA-F0-9 ]+)' matches.
    """
    def _ic_rdbl_replace(m):
        return 'Block %s : %s' % (m.group(1), m.group(2).strip())
    return _RE_ICLASS_RDBL_NEW.sub(_ic_rdbl_replace, text)


# -- Track E: T55xx chk password normalization --

# New T55xx chk outputs 4 bracket variants:
#   "found valid password [ XXXXXXXX ]"       (no colon, lowercase)
#   "found valid password : [ XXXXXXXX ]"     (colon+space, lowercase)
#   "found valid password: [ XXXXXXXX ]"      (colon, lowercase)
#   "Found valid password: [ XXXXXXXX ]"      (colon, uppercase F)
# Old format: "Found valid password: XXXXXXXX" (colon, no brackets)
# Middleware regex: r'Found valid.*?:\s*([A-Fa-f0-9]+)'
_RE_T55XX_PWD_FOUND = re.compile(
    r'[Ff]ound valid\s+password\s*:?\s*\[\s*([0-9A-Fa-f]{8})\s*\]')


def _normalize_t55xx_chk_password(text):
    """Normalize T55xx chk password output to old colon format.

    All four new-format bracket variants → 'Found valid password: XXXXXXXX'
    so middleware regex r'Found valid.*?:\\s*([A-Fa-f0-9]+)' matches.
    """
    def _pwd_replace(m):
        return 'Found valid password: %s' % m.group(1)
    return _RE_T55XX_PWD_FOUND.sub(_pwd_replace, text)


# -- Track F: hf 15 csetuid normalization --

def _normalize_hf15_csetuid(text):
    """Normalize hf 15 csetuid response.

    New: 'Setting new UID ( ok )', 'no tag found'
    Old: 'setting new UID (ok)', "can't read card UID"
    """
    text = text.replace('Setting new UID ( ok )', 'setting new UID (ok)')
    text = text.replace('Setting new UID ( fail )', 'setting new UID (failed)')
    text = text.replace('no tag found', "can't read card UID")
    return text


# -- Track F: FeliCa reader normalization --

def _normalize_felica_reader(text):
    """Normalize FeliCa reader response.

    New: 'FeliCa card select failed', IDm without header
    Old: 'card timeout', 'FeliCa tag info' header, 'IDm  XXXX' with spaces
    """
    text = text.replace('FeliCa card select failed', 'card timeout')
    # Restore "FeliCa tag info" header if IDm is present
    if 'IDm' in text and 'FeliCa tag info' not in text:
        text = 'FeliCa tag info\n' + text
    # Normalize IDm format: "IDm: XXXX" -> "IDm  XX XX XX..."
    idm_match = re.search(r'IDm:\s*([0-9A-Fa-f]+)', text)
    if idm_match:
        raw = idm_match.group(1)
        spaced = ' '.join(raw[i:i+2] for i in range(0, len(raw), 2))
        text = text.replace(idm_match.group(0), 'IDm  %s' % spaced)
    return text


# -- MANUFACTURER label restoration --

def _normalize_manufacturer(text):
    """Restore MANUFACTURER: label removed in new firmware.

    The new firmware removed the 'MANUFACTURER:' label entirely,
    printing just the manufacturer name indented.  The old regex
    pattern '.*MANUFACTURER:(.*)' needs this label.

    We detect the manufacturer section by checking for known
    manufacturer names (NXP, Infineon, etc.) on indented lines
    following the SAK line.
    """
    # Only add if MANUFACTURER: is not already present
    if 'MANUFACTURER:' in text:
        return text

    # Known manufacturer strings from PM3 source
    _MANUFACTURERS = [
        'NXP', 'Infineon', 'STMicroelectronics', 'Motorola',
        'Philips', 'ATMEL', 'EM Micro', 'Shanghai',
        'Gemplus', 'Inside Contactless',
    ]
    lines = text.split('\n')
    for i, line in enumerate(lines):
        stripped = line.strip()
        for mfr in _MANUFACTURERS:
            if stripped.startswith(mfr):
                lines[i] = 'MANUFACTURER: %s' % stripped
                return '\n'.join(lines)
    return text


# -- Track G: ISO15693 manufacturer normalization for hf search --

# Bug 10: iceman's hf search uses 'STMicroelectronics' or 'ST Microelectronics'
# but hfsearch.py checks for 'ST Microelectronics SA France'.
# Map iceman manufacturer names to legacy equivalents.
_ISO15693_MANUFACTURER_MAP = {
    'STMicroelectronics': 'ST Microelectronics SA France',
    'ST Microelectronics SA': 'ST Microelectronics SA France',
    'ST Microelectronics': 'ST Microelectronics SA France',
}


def _normalize_iso15693_manufacturer(text):
    """Normalize ISO15693 manufacturer names for hfsearch keyword matching.

    Iceman uses short manufacturer names (e.g., 'STMicroelectronics') but
    hfsearch.py expects the full legacy string ('ST Microelectronics SA France')
    for proper ISO15693 subtype detection (ST SA vs ICODE).
    """
    if 'ISO15693' not in text and 'iso15693' not in text.lower():
        return text
    for short, full in _ISO15693_MANUFACTURER_MAP.items():
        if short in text and full not in text:
            text = text.replace(short, full)
            break
    return text


# ===========================================================================
# Command-specific dispatch table
# ===========================================================================

# Maps command prefixes to lists of normalizer functions.
# Multiple normalizers can be applied per command.
_RESPONSE_NORMALIZERS = {
    'hf mf fchk': [_normalize_fchk_table],
    'hf mf chk': [_normalize_fchk_table],
    'hf mf darkside': [_normalize_darkside_key],
    'hf mf nested': [_normalize_fchk_table, _normalize_darkside_key],
    'hf mf staticnested': [_normalize_fchk_table],
    'hf mf wrbl': [_normalize_wrbl_response],
    'hf mf rdbl': [_normalize_rdbl_response],
    'hf mf rdsc': [_normalize_rdbl_response, _normalize_wrbl_response],
    'hf mf cgetblk': [_normalize_rdbl_response],
    'hf mf csetblk': [],
    'hf mf csetuid': [],
    'hf mf cload': [],
    'hf mf cwipe': [],
    'hf mf dump': [_normalize_rdbl_response],
    'hf mf restore': [_normalize_wrbl_response],
    'hf 14a info': [_normalize_magic_capabilities, _normalize_manufacturer],
    'hf sea': [_normalize_iso15693_manufacturer],
    'hf search': [_normalize_iso15693_manufacturer],
    'hf mfu info': [],
    'hf mfu dump': [_normalize_save_messages],
    'hf mfu restore': [],
    'hf 15 dump': [_normalize_save_messages],
    'hf 15 restore': [_normalize_hf15_restore],
    'hf 15 csetuid': [_normalize_hf15_csetuid],
    'hf iclass dump': [_normalize_save_messages],
    'hf iclass rdbl': [_normalize_iclass_rdbl],
    'hf iclass wrbl': [_normalize_iclass_wrbl],
    'hf iclass chk': [],
    'hf felica reader': [_normalize_felica_reader],
    'hf felica litedump': [],
    'lf sea': [_normalize_em410x_id, _normalize_hid_prox,
               _normalize_chipset_detection, _normalize_fdxb_animal_id,
               _normalize_gallagher_fields, _normalize_securakey_fc_hex,
               _normalize_awid_card_number, _normalize_lf_keyword_case,
               _normalize_indala_uid],
    'lf search': [_normalize_em410x_id, _normalize_hid_prox,
                  _normalize_chipset_detection, _normalize_fdxb_animal_id,
                  _normalize_gallagher_fields, _normalize_securakey_fc_hex,
                  _normalize_awid_card_number, _normalize_lf_keyword_case,
                  _normalize_indala_uid],
    'lf t55xx detect': [_normalize_t55xx_config],
    'lf t55xx dump': [_normalize_t55xx_config, _normalize_save_messages],
    'lf t55xx read': [],
    'lf t55xx write': [],
    'lf t55xx wipe': [],
    'lf t55xx chk': [_normalize_t55xx_chk_password],
    'lf t55xx restore': [],
    'lf em 4x05 info': [_normalize_em4x05_info],
    'lf em 4x05_info': [_normalize_em4x05_info],
    'lf em 4x05 dump': [_normalize_em4x05_info, _normalize_save_messages],
    'lf em 4x05_dump': [_normalize_em4x05_info, _normalize_save_messages],
    'lf em 4x05 read': [],
    'lf em 4x05_read': [],
    'lf em 410x reader': [_normalize_em410x_id],
    'lf em 410x_read': [_normalize_em410x_id],
    'data save': [_normalize_save_messages],
}


# ===========================================================================
# Public API: translate_response
# ===========================================================================

def translate_response(text, cmd=None):
    """Normalize RRG/Iceman PM3 response output to old-format patterns.

    Called by executor._send_and_cache() after strip_ansi(), before caching.
    Only active when firmware version is iceman.

    Three-phase normalization (order matters!):
      Phase A (pre):  noise removal + line prefix stripping
      Phase B:        command-specific normalizers (T55xx, fchk table, etc.)
      Phase C (post): remaining dotted-to-colon, UID annotations, ISO numbers

    Command-specific normalizers run AFTER prefix stripping but BEFORE the
    generic dotted-to-colon, so they can match their own dotted patterns
    (e.g. T55xx "Chip type......... T55x7") and apply custom formatting
    (e.g. restoring "0x" prefix on Block0).

    The function is idempotent: calling it on already-normalized (old-format)
    text will not break it, because the regex patterns only match new-format
    structures.

    Args:
        text: Raw response text (already ANSI-stripped)
        cmd: Optional command string for command-specific normalization

    Returns:
        Normalized response text matching old-format patterns.
    """
    if not text:
        return text

    if _current_version != PM3_VERSION_ICEMAN:
        return text

    # Phase A: Strip noise and line prefixes
    result = _pre_normalize(text)

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
