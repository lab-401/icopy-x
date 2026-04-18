#!/usr/bin/env python3
"""Enumerate command tables from all cmd*.c files in a tree.
Also record the top-level 'hf/lf/hw/data/mem' dispatcher entries.
"""
import os
import re
import json
import sys

TOP_LEVEL_FILES = {
    'hf': 'cmdhf.c',
    'lf': 'cmdlf.c',
    'hw': 'cmdhw.c',
    'data': 'cmddata.c',
    'mem': 'cmdflashmem.c',
}

# Map from C handler name -> source file for subcommand tables
# We'll scan cmd*.c for static const command_t *Table[] or similar.

def find_tables(path):
    """Return list of (table_name, [(subname, handler_func, line), ...])"""
    with open(path) as f:
        src = f.read()
    tables = []
    for m in re.finditer(
        r'(?:static\s+)?command_t\s+(\w*[Tt]able\w*)\s*\[\s*\]\s*=\s*\{',
        src,
    ):
        name = m.group(1)
        start = m.end()
        # find matching terminator "};\n" at top-level (depth 0)
        depth = 1
        i = start
        while i < len(src) and depth > 0:
            ch = src[i]
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    break
            elif ch == '"':
                # skip string
                j = i + 1
                while j < len(src) and src[j] != '"':
                    if src[j] == '\\':
                        j += 2
                    else:
                        j += 1
                i = j
            i += 1
        body = src[start:i]
        entries = []
        for em in re.finditer(r'\{\s*"([^"]+)"\s*,\s*(\w+)\s*,', body):
            sub = em.group(1)
            handler = em.group(2)
            off = start + em.start()
            line = src[:off].count('\n') + 1
            entries.append((sub, handler, line))
        tables.append((name, entries))
    return tables


def scan_tree(root):
    """Scan every cmd*.c file in root and return map:
    {filename: [(tablename, [entries])]}
    """
    result = {}
    for fn in sorted(os.listdir(root)):
        if not fn.startswith('cmd') or not fn.endswith('.c'):
            continue
        p = os.path.join(root, fn)
        tabs = find_tables(p)
        if tabs:
            result[fn] = tabs
    return result


def main():
    out = {}
    for label, root in [('iceman', '/tmp/rrg-pm3/client/src'), ('legacy', '/tmp/factory_pm3/client/src')]:
        out[label] = scan_tree(root)
    # Print as JSON so we can consume programmatically
    print(json.dumps(out, indent=2, default=str))


if __name__ == '__main__':
    main()
