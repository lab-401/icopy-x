#!/usr/bin/env python3
"""Scan a handler function and emit its PrintAndLogEx lines."""
import re
import sys

def strip_comments_and_strings_mask(text):
    """Return a parallel-length mask where 1=code, 0=comment/string.
    Actually we return a string where comment/string chars replaced by space, preserving line numbers.
    """
    out = list(text)
    i = 0
    n = len(text)
    in_block = False
    in_line = False
    in_str = False
    in_chr = False
    while i < n:
        ch = text[i]
        nxt = text[i+1] if i+1 < n else ''
        if in_block:
            if ch == '*' and nxt == '/':
                out[i] = ' '
                out[i+1] = ' '
                i += 2
                in_block = False
                continue
            if ch != '\n':
                out[i] = ' '
            i += 1
            continue
        if in_line:
            if ch == '\n':
                in_line = False
            else:
                out[i] = ' '
            i += 1
            continue
        if in_str:
            out[i] = ' '  # blank out string contents, keep quotes position as space too
            if ch == '\\' and nxt:
                out[i+1] = ' '
                i += 2
                continue
            if ch == '"':
                in_str = False
            i += 1
            continue
        if in_chr:
            out[i] = ' '
            if ch == '\\' and nxt:
                out[i+1] = ' '
                i += 2
                continue
            if ch == "'":
                in_chr = False
            i += 1
            continue
        # not in any
        if ch == '/' and nxt == '*':
            out[i] = ' '
            out[i+1] = ' '
            i += 2
            in_block = True
            continue
        if ch == '/' and nxt == '/':
            out[i] = ' '
            out[i+1] = ' '
            i += 2
            in_line = True
            continue
        # Don't blank out strings in "live" code; we want to see them!
        # But we DO want to skip finding PrintAndLogEx tokens inside string literals.
        # The handler scanner looks for "PrintAndLogEx\s*\(" identifier which won't appear
        # in strings meaningfully. So leave strings intact for code.
        i += 1
    return ''.join(out)


def extract_handler(path, handler):
    with open(path) as f:
        raw = f.read()
    stripped = strip_comments_and_strings_mask(raw)
    src = stripped.split('\n')
    src = [s + '\n' for s in src]
    # Full text for regex-over-multiline matches
    start = None
    for i, line in enumerate(src, 1):
        if re.match(r'^(static\s+)?int\s+' + handler + r'\s*\(', line):
            start = i
            break
    if start is None:
        return None, None, []
    brace = 0
    started = False
    end = start
    for i in range(start-1, len(src)):
        for ch in src[i]:
            if ch == '{':
                brace += 1
                started = True
            elif ch == '}':
                brace -= 1
                if started and brace == 0:
                    end = i + 1
                    break
        if started and brace == 0:
            break

    # For extracting PrintAndLogEx strings we use the ORIGINAL raw source (to preserve literals)
    raw_src = raw.split('\n')
    raw_src = [s + '\n' for s in raw_src]

    # Detect delegate calls (functions called within the body that likely emit output)
    delegate_calls = set()
    SKIP = {
        'PrintAndLogEx', 'CLIParserInit', 'CLIParserFree', 'CLIExecWithReturn',
        'CLIGetHexWithReturn', 'CLIGetStrWithReturn', 'arg_get_lit', 'arg_get_int',
        'arg_get_int_def', 'arg_get_str', 'arg_param_begin', 'arg_param_end',
        'arg_lit0', 'arg_int0', 'arg_int1', 'arg_str0', 'arg_str1',
        'strlen', 'memcpy', 'memset', 'memcmp', 'strcmp', 'strcpy', 'strncpy',
        'snprintf', 'sprintf', 'printf', 'fprintf', 'malloc', 'free', 'calloc',
        'sizeof', 'ARRAYLEN', 'if', 'while', 'for', 'switch', 'return',
        'SendCommandNG', 'SendCommandMIX', 'WaitForResponse', 'WaitForResponseTimeout',
        'clearCommandBuffer', 'hf_read_uid', 'SelectCard14443A_4',
    }
    for i in range(start-1, end):
        for m in re.finditer(r'\b([a-zA-Z_][a-zA-Z0-9_]+)\s*\(', src[i]):
            name = m.group(1)
            if name in SKIP or name.startswith('arg_') or name == handler:
                continue
            # Track names that look like helpers likely to emit output
            if re.search(r'(print|show|display|dump|info|read|demod|sim|reader|clone|write|sniff|brute|watch|chk|restore|view|check|find|scan|detect|decode|usage|help|list)', name, re.I):
                delegate_calls.add(name)

    results = []
    i = start - 1
    while i < end:
        line = src[i]   # stripped-of-comments for detection
        m = re.search(r'PrintAndLogEx\s*\(\s*([A-Z]+)\s*,', line)
        if m and m.group(1) != 'DEBUG':
            pm_line = i + 1
            level = m.group(1)
            # accumulate continuation lines from raw source until matching ')' at top level
            # Use raw_src to preserve string literals
            buf = raw_src[i]
            # find PrintAndLogEx in the raw line; locate idx
            idx = buf.find('PrintAndLogEx(')
            if idx == -1:
                # fallback: use stripped position
                idx = line.find('PrintAndLogEx(')
                buf = line
            paren = 0
            j = idx
            in_str_raw = False
            while True:
                while j < len(buf):
                    ch = buf[j]
                    # Track string literals in raw so we don't count parens inside strings
                    if ch == '\\' and in_str_raw:
                        j += 2
                        continue
                    if ch == '"':
                        in_str_raw = not in_str_raw
                    elif not in_str_raw:
                        if ch == '(':
                            paren += 1
                        elif ch == ')':
                            paren -= 1
                            if paren == 0:
                                j += 1
                                break
                    j += 1
                if paren == 0:
                    break
                i += 1
                if i >= end:
                    break
                extra = raw_src[i]
                j = len(buf)
                buf += extra
            body = buf[idx:j]
            results.append((pm_line, level, body))
        i += 1
    return start, end, results, delegate_calls


if __name__ == '__main__':
    path = sys.argv[1]
    handler = sys.argv[2]
    r = extract_handler(path, handler)
    if len(r) == 3:
        s, e, res = r; delegates = set()
    else:
        s, e, res, delegates = r
    print(f"# {handler} @ {path}:{s}-{e}")
    print(f"# delegates: {sorted(delegates)}")
    for line, level, body in res:
        body_clean = re.sub(r'\s+', ' ', body).strip()
        if len(body_clean) > 300:
            body_clean = body_clean[:300] + '...'
        print(f"{line}\t{level}\t{body_clean}")
