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
# T5577 PASSWORD FIND - CANDIDATES AND RESULT PARSING
##########################################################################
# Purpose:
#   - Reads hexadecimal password dictionaries, ignoring comments and duplicates.
#   - Orders dictionary candidates using priority and alternating traversal.
#   - Generates real calendar dates from both ends of a selected date range.
#   - Formats dates as YYYYMMDD or DDMMYYYY with leap-year correctness.
#   - Parses T55xx password-protection evidence and verification results.
# Dependencies: Python standard library only (datetime, re).
# Requirements: updated iCopy-X/XS software and newer Iceman PM3 firmware.
##########################################################################
# @copyright (2026) jareckib

"""Offline candidate ordering and RF result parsing."""
import datetime
import re
KEY = re.compile(r'^[0-9A-Fa-f]{8}$')

def dictionary(path):
    result, seen = [], set()
    try:
        with open(path, encoding='utf-8-sig', errors='replace') as f:
            for line in f:
                k = line.split('#',1)[0].strip().upper()
                if KEY.fullmatch(k) and k not in seen:
                    result.append(k); seen.add(k)
    except OSError: pass
    return result

def alternating(seq):
    l,r=0,len(seq)-1
    while l<=r:
        yield seq[l]; l+=1
        if l<=r: yield seq[r]; r-=1

def priority_alternating(seq):
    return list(seq[:4])+list(alternating(seq[4:]))

def dates(start,end,formats=('DDMMYYYY','YYYYMMDD')):
    if not formats or any(fmt not in ('YYYYMMDD','DDMMYYYY') for fmt in formats):
        raise ValueError('unsupported date format')
    a,b=start.toordinal(),end.toordinal()
    if a>b: raise ValueError('reversed dates')
    while a<=b:
        for n in ([a,b] if a!=b else [a]):
            d=datetime.date.fromordinal(n)
            for fmt in formats:
                yield d.strftime('%Y%m%d' if fmt=='YYYYMMDD' else '%d%m%Y')
        a+=1; b-=1

def _field(output, name):
    values = re.findall(r'(?im)^[ \t]*(?:\[[+=]\][ \t]*)?'+re.escape(name)+r'\.+[ \t]*([^\r\n]*)',str(output or ''))
    values = {value.strip().upper() for value in values}
    return values.pop() if len(values)==1 else None


def detect_state(out):
    block=_field(out,'Block0')
    state=_field(out,'Password set')
    if not block or not KEY.fullmatch(block) or state not in ('YES','NO'):
        return 'unknown',None
    pwd=bool(int(block,16)&0x10)
    if pwd!=(state=='YES'):return 'unknown',None
    return ('protected' if pwd else 'clear'),block


def read_block(output, number):
    pattern = r'(?im)^[ \t]*(?:\[[+=]\][ \t]*)?%02d[ \t]*\|[ \t]*([^|\r\n]*)\|' % number
    values={value.strip().upper() for value in re.findall(pattern,str(output or ''))}
    if len(values)!=1:return None
    value=values.pop()
    return value if KEY.fullmatch(value) else None


def verified(detect,read,key):
    state,block=detect_state(detect)
    password=_field(detect,'Password')
    return (state=='protected' and read_block(read,0)==block
            and KEY.fullmatch(str(key or '')) is not None
            and password==key.upper())
