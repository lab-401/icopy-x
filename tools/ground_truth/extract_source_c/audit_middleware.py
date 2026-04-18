#!/usr/bin/env python3
"""Audit middleware files for startPM3Task calls and regex usage."""
import os
import re
import json
from pathlib import Path

MW = Path('/home/qx/icopy-x-reimpl/src/middleware')
SKIP = {'pm3_compat.py', 'executor.py', 'pm3_flash.py', 'pm3_response_catalog.py',
        'tagtypes.py', '__init__.py'}

# patterns
RE_STARTPM3 = re.compile(r'startPM3Task\s*\(\s*([^,)\n]+)', re.DOTALL)
RE_RECTRIGGER = re.compile(r'recordTriggers?\s*\(\s*\[([^\]]+)\]')
RE_HASKEYWORD = re.compile(r'hasKeyword\(\s*([^)]+)\s*\)')
RE_GETCONTENT = re.compile(r'getContentFromRegex\w*\(\s*([^)]+)\s*\)')
RE_GETREPONSE = re.compile(r'getResponseFromRegex\w*\(\s*([^)]+)\s*\)')
RE_COMPILE = re.compile(r're\.compile\(\s*r?(["\'].*?["\']), re\.')
RE_RESEARCH = re.compile(r're\.(search|match|findall)\(\s*r?(["\'].*?["\'])', re.DOTALL)
RE_COMPILE_MULTI = re.compile(r're\.compile\(\s*(r?[\'"].*?[\'"])\s*[,)]', re.DOTALL)
RE_EXEC_REG = re.compile(r'executor\.\w*[Rr]egex\w*\(')

def scan(file_path):
    text = file_path.read_text()
    issued = []
    keywords = []
    regexes = []
    triggers = []

    for m in RE_STARTPM3.finditer(text):
        issued.append((file_path.name, m.start(), m.group(1).strip()))
    for m in RE_RECTRIGGER.finditer(text):
        triggers.append((file_path.name, m.start(), m.group(1).strip()[:150]))
    for m in RE_HASKEYWORD.finditer(text):
        keywords.append((file_path.name, m.start(), m.group(1).strip()[:160]))
    for m in RE_GETCONTENT.finditer(text):
        regexes.append((file_path.name, m.start(), 'getContentFromRegex', m.group(1).strip()[:160]))
    for m in RE_GETREPONSE.finditer(text):
        regexes.append((file_path.name, m.start(), 'getResponseFromRegex', m.group(1).strip()[:160]))
    for m in RE_COMPILE_MULTI.finditer(text):
        regexes.append((file_path.name, m.start(), 're.compile', m.group(1).strip()[:160]))
    return issued, keywords, regexes, triggers

def lineno(path, byte_off):
    with open(path) as f:
        data = f.read()
    return data[:byte_off].count('\n') + 1

out = {}
for p in sorted(MW.iterdir()):
    if p.suffix != '.py' or p.name in SKIP:
        continue
    issued, keywords, regexes, triggers = scan(p)
    out[p.name] = {
        'issued': [(lineno(p, off), cmd) for (_, off, cmd) in issued],
        'keywords': [(lineno(p, off), kw) for (_, off, kw) in keywords],
        'regexes': [(lineno(p, off), kind, r) for (_, off, kind, r) in regexes],
        'triggers': [(lineno(p, off), t) for (_, off, t) in triggers]
    }

print(json.dumps(out, indent=2))
