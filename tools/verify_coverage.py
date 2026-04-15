#!/usr/bin/env python3

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

"""Step 4 Verification: cross-reference .so strings against fixture coverage.

For a given scope (read, scan, write, etc.), extracts all strings from the
relevant .so modules, categorizes each string, and checks whether it's
exercised by at least one fixture.

Usage:
    python3 tools/verify_coverage.py --scope read
    python3 tools/verify_coverage.py --scope scan
    python3 tools/verify_coverage.py --scope all

Output:
    - Coverage % per category (PM3 commands, branch keywords, regex patterns, UI text)
    - CRITICAL: branch-determining strings not in any fixture (missed logic paths)
    - WARNING: PM3 commands not covered
    - INFO: UI text not covered
    - Per-.so module breakdown
"""
import sys, re, json, argparse
from pathlib import Path
from collections import defaultdict

PROJECT = Path(__file__).resolve().parent.parent
STRINGS_DIR = PROJECT / "docs" / "v1090_strings"
sys.path.insert(0, str(PROJECT / "tools"))

# ============================================================================
# Scope → .so module mapping
# ============================================================================

SCOPES = {
    'read': {
        'description': 'Read Tag flow',
        'modules': [
        ],
        'fixture_indexes': ['ALL_READ_SCENARIOS', 'ALL_SCAN_SCENARIOS'],
    },
    'scan': {
        'description': 'Scan Tag flow',
        'modules': [
        ],
        'fixture_indexes': ['ALL_SCAN_SCENARIOS'],
    },
    'write': {
        'description': 'Write Tag flow',
        'modules': [
        ],
        'fixture_indexes': ['ALL_WRITE_SCENARIOS', 'ALL_SCAN_SCENARIOS'],
    },
    'erase': {
        'description': 'Erase Tag flow',
        'fixture_indexes': ['ALL_ERASE_SCENARIOS'],
    },
    'autocopy': {
        'description': 'AutoCopy flow',
        'modules': [
        ],
        'fixture_indexes': ['ALL_AUTOCOPY_SCENARIOS', 'ALL_SCAN_SCENARIOS',
                            'ALL_READ_SCENARIOS', 'ALL_WRITE_SCENARIOS'],
    },
}

# ============================================================================
# String categorization
# ============================================================================

# Category priority (first match wins)
CAT_INTERNAL = 'INTERNAL'   # Python/Cython internals — skip
CAT_PM3_CMD  = 'PM3_CMD'    # PM3 command string
CAT_REGEX    = 'REGEX'      # Regex pattern used for parsing
CAT_BRANCH   = 'BRANCH'     # Branch-determining keyword (hasKeyword/response match)
CAT_UI       = 'UI_TEXT'    # UI-facing text (toasts, labels)
CAT_DEBUG    = 'DEBUG'       # Debug/trace strings
CAT_DATA     = 'DATA'        # Data format strings, struct names
CAT_UNKNOWN  = 'UNKNOWN'     # Uncategorized

# Severity for uncovered strings
SEV_CRITICAL = 'CRITICAL'  # Missed branch — affects logic
SEV_WARNING  = 'WARNING'   # PM3 command not covered
SEV_INFO     = 'INFO'      # UI text, might affect display
SEV_SKIP     = 'SKIP'      # Internal/debug, no impact

def categorize_string(s):
    """Categorize a string extracted from a .so binary."""
    s_stripped = s.strip()
    if not s_stripped or len(s_stripped) < 3:
        return CAT_INTERNAL, SEV_SKIP

    # Binary data / ARM assembly fragments — high ratio of non-alphanumeric chars
    alnum = sum(1 for c in s_stripped if c.isalnum() or c in ' _.-:/')
    if len(s_stripped) > 3 and alnum / len(s_stripped) < 0.5:
        return CAT_INTERNAL, SEV_SKIP
    # Shared library names
    if s_stripped.endswith('.so') or '.so.' in s_stripped or s_stripped.startswith('GLIBC'):
        return CAT_INTERNAL, SEV_SKIP

    # --- INTERNAL: Python/Cython symbols ---
    if s_stripped.startswith('__pyx_') or s_stripped.startswith('__Pyx_'):
        return CAT_INTERNAL, SEV_SKIP
    if s_stripped.startswith('Py') and any(c.isupper() for c in s_stripped[2:4]):
        return CAT_INTERNAL, SEV_SKIP  # PyObject_, PyErr_, PyDict_, etc.
    if s_stripped.startswith('_Py'):
        return CAT_INTERNAL, SEV_SKIP
    if s_stripped.startswith('__assert') or s_stripped.startswith('__gmon'):
        return CAT_INTERNAL, SEV_SKIP
    if s_stripped.startswith('_init') or s_stripped.startswith('_fini') or s_stripped.startswith('_ITM_'):
        return CAT_INTERNAL, SEV_SKIP
    if s_stripped.startswith('C:\\Users\\') or s_stripped.startswith('/home/') or s_stripped.startswith('/usr/'):
        return CAT_INTERNAL, SEV_SKIP
    if s_stripped.startswith('Module ') and 'imported' in s_stripped:
        return CAT_INTERNAL, SEV_SKIP
    if 'cline_in_traceback' in s_stripped:
        return CAT_INTERNAL, SEV_SKIP
    if s_stripped in ('_init', '_fini', 'init', 'test', '__test__', '__module__', '__name__',
                      '__main__', '__import__', '__reduce_cython__', '__setstate_cython__',
                      'at least', 'at most', 'exactly', 'free variable', 'None',
                      'PRETTY_FUNCTION', 'result', 'self', 'data', 'key', 'info',
                      'enable', 'disable', 'parser', 'args', 'kwargs'):
        return CAT_INTERNAL, SEV_SKIP
    # Cython function/module markers
    if re.match(r'^__pyx_', s_stripped) or re.match(r'^__Pyx', s_stripped):
        return CAT_INTERNAL, SEV_SKIP
    if re.match(r'^\w+\.\w+$', s_stripped) and '.' in s_stripped:
        parts = s_stripped.split('.')
        if parts[0] in ('executor', 'scan', 'lfread', 'lft55xx', 'hfmfkeys', 'hfmfread',
                         'hficlass', 'iclassread', 'lfsearch', 'hfsearch', 'hf14ainfo',
                         'felicaread', 'legicread', 'hf15read', 'lfwrite', 'lfem4x05',
                         'hfmfwrite', 'hfmfuread', 'hfmfuwrite', 'hf15write', 'iclasswrite',
                         'hf14aread', 'hfmfuinfo', 'hffelica', 'sniff', 'commons',
                         'tagtypes', 'resources', 'config', 'settings', 'container',
                         'appfiles', 'template', 'audio', 'batteryui', 'actmain',
                         'actbase', 'actstack', 'application', 'debug', 'bytestr'):
            return CAT_INTERNAL, SEV_SKIP
    # Python type check strings
    if 'PyTuple_Check' in s_stripped or 'PyUnicode_' in s_stripped or 'PyObject_' in s_stripped:
        return CAT_INTERNAL, SEV_SKIP
    if re.match(r"^'%.+' object", s_stripped):
        return CAT_INTERNAL, SEV_SKIP
    if s_stripped.startswith('__pyx_') or s_stripped.endswith('__'):
        if not any(kw in s_stripped for kw in ['read', 'write', 'scan', 'dump', 'key']):
            return CAT_INTERNAL, SEV_SKIP

    # --- PM3 COMMANDS ---
    if re.match(r'^(hf|lf|hw|data) ', s_stripped):
        return CAT_PM3_CMD, SEV_WARNING
    if s_stripped.startswith('lf ') or s_stripped.startswith('hf '):
        return CAT_PM3_CMD, SEV_WARNING

    # --- REGEX PATTERNS (check BEFORE branch — regexes contain branch keywords) ---
    if any(c in s_stripped for c in (r'\s', r'\d', r'[a-f', r'[A-F', r'(?:', r'\w')):
        return CAT_REGEX, SEV_INFO
    if re.search(r'\[.+\]\+|\(\?:|\\[sdwS]|\.\*', s_stripped):
        return CAT_REGEX, SEV_INFO
    if re.search(r'\{[0-9,]+\}', s_stripped) and '\\' in s_stripped:
        return CAT_REGEX, SEV_INFO

    # --- CONSTANT NAMES (ALL_CAPS_WITH_UNDERSCORES) ---
    if re.match(r'^[A-Z][A-Z0-9_]{3,}$', s_stripped):
        return CAT_DATA, SEV_SKIP
    # --- Python kwargs that contain branch-indicator substrings ---
    if s_stripped in ('errors', 'failed', 'error', 'saved', 'enable', 'disable'):
        # Standalone single words: check context — if adjacent to encode/decode/format
        # these are Python string method kwargs, not branch keywords
        return CAT_INTERNAL, SEV_SKIP

    # --- BRANCH KEYWORDS (response patterns that determine logic flow) ---
    branch_indicators = [
        'found valid', 'No keys found', "Can't select card", "isn't vulnerable",
        'Try use', 'no candidates', 'button pressed', 'Aborted', 'isOk:',
        'Auth error', 'Read block error', 'saved', 'failed', 'error',
        'Partial dump', 'card select failed', 'dump completed',
        'Found valid', 'No valid key', 'saving dump', 'Error reading',
        'No tag found', 'Failed to identify', "Can't select",
        'Chip Type', 'Found valid password', 'Could not detect',
        'saved 12 blocks', 'Check pwd failed', 'Password Set',
        'valid key', 'EM4305', 'EM4469', 'Chip Type',
        'Multiple tags', 'MIFARE', 'iCLASS', 'FeliCa',
        'Valid ', 'No known', 'No data found',
    ]
    for kw in branch_indicators:
        if kw in s_stripped:
            return CAT_BRANCH, SEV_CRITICAL

    # --- DEBUG/TRACE ---
    if s_stripped.startswith('DEBUG:') or s_stripped.startswith('[DEBUG]'):
        return CAT_DEBUG, SEV_SKIP
    if 'PRETTY_FUNCTION' in s_stripped:
        return CAT_DEBUG, SEV_SKIP

    # --- UI TEXT ---
    ui_indicators = ['Read', 'Write', 'Scan', 'Success', 'Fail', 'Tag',
                     'Card', 'Key', 'Dump', 'Copy', 'Erase', 'Warning',
                     'toast', 'Toast', 'File saved', 'Missing key']
    for kw in ui_indicators:
        if kw in s_stripped:
            return CAT_UI, SEV_INFO

    # --- DATA format strings ---
    if re.match(r'^%[0-9sdxXf]', s_stripped) or s_stripped.startswith('{') or '%s' in s_stripped:
        return CAT_DATA, SEV_SKIP
    if re.match(r'^[A-Z_]{4,}$', s_stripped):  # ALL_CAPS constants
        return CAT_DATA, SEV_SKIP

    # --- Remaining function/variable names ---
    if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', s_stripped):
        # Single identifier — likely a function/variable name
        return CAT_INTERNAL, SEV_SKIP

    # Single short token — likely variable/function name
    if len(s_stripped) < 20 and re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', s_stripped):
        return CAT_INTERNAL, SEV_SKIP
    # Short fragments without spaces that aren't commands or keywords
    if len(s_stripped) < 15 and ' ' not in s_stripped:
        return CAT_INTERNAL, SEV_SKIP

    return CAT_UNKNOWN, SEV_INFO


# ============================================================================
# Fixture extraction
# ============================================================================

def load_fixtures(fixture_index_names):
    """Load all fixture text (commands + responses) from specified indexes."""
    import pm3_fixtures as pf
    commands = set()
    response_text = []

    for idx_name in fixture_index_names:
        idx = getattr(pf, idx_name, {})
        for name, fixture in idx.items():
            for key, val in fixture.items():
                if key.startswith('_'):
                    continue
                commands.add(key.strip())
                if isinstance(val, tuple) and len(val) == 2:
                    _, resp = val
                    if isinstance(resp, str):
                        response_text.append(resp)

    all_text = '\n'.join(response_text)
    return commands, all_text


# ============================================================================
# Coverage check
# ============================================================================

def check_coverage(so_file, fixture_cmds, fixture_text):
    """Check every string in a .so extraction file against fixtures."""
    path = STRINGS_DIR / so_file
    if not path.exists():
        return None

    fixture_text_lower = fixture_text.lower()
    fixture_cmds_lower = {c.lower() for c in fixture_cmds}

    results = []
    for line in path.read_text().splitlines():
        s = line.strip()
        if not s:
            continue

        cat, severity = categorize_string(s)
        covered = False

        if cat == CAT_INTERNAL or cat == CAT_DEBUG:
            covered = True  # Don't count internals as uncovered
        elif cat == CAT_PM3_CMD:
            # Check if any fixture command matches (substring)
            s_lower = s.lower().strip()
            covered = any(fc in s_lower or s_lower.startswith(fc.split()[0]) for fc in fixture_cmds_lower)
            if not covered:
                # Check if it's a parameterized variant of a covered command
                base = re.sub(r'\{[^}]*\}', '', s_lower).strip()
                covered = any(fc in base or base in fc for fc in fixture_cmds_lower if len(fc) > 3)
        elif cat == CAT_BRANCH:
            covered = s.lower() in fixture_text_lower or any(
                w in fixture_text_lower for w in s.lower().split() if len(w) > 4
            )
        elif cat == CAT_REGEX:
            # Regex patterns — check if the pattern text appears in our docs or code
            covered = s in fixture_text or any(
                part in fixture_text for part in s.split('|') if len(part) > 5
            )
        elif cat == CAT_UI:
            covered = s.lower() in fixture_text_lower
        elif cat == CAT_DATA:
            covered = True  # Format strings are not branch-determining
        else:
            # Unknown — check for any substring match
            covered = any(w.lower() in fixture_text_lower for w in s.split() if len(w) > 5)

        results.append({
            'string': s,
            'category': cat,
            'severity': severity,
            'covered': covered,
        })

    return results


# ============================================================================
# Reporting
# ============================================================================

def report(scope_name, scope_cfg, all_results):
    """Generate the coverage report."""
    print("=" * 78)
    print(f"  STEP 4 VERIFICATION: {scope_cfg['description'].upper()}")
    print(f"  Scope: {scope_name} | Modules: {len(scope_cfg['modules'])}")
    print("=" * 78)

    # Aggregate by category
    by_cat = defaultdict(lambda: {'total': 0, 'covered': 0, 'uncovered': []})

    for so_file, results in all_results.items():
        for r in results:
            cat = r['category']
            by_cat[cat]['total'] += 1
            if r['covered']:
                by_cat[cat]['covered'] += 1
            else:
                by_cat[cat]['uncovered'].append((so_file, r))

    # Category summary
    print(f"\n  {'Category':<15s} {'Covered':>8s} {'Total':>8s} {'%':>7s}")
    print(f"  {'-'*15} {'-'*8} {'-'*8} {'-'*7}")

    focus_cats = [CAT_PM3_CMD, CAT_BRANCH, CAT_REGEX, CAT_UI, CAT_DATA, CAT_INTERNAL, CAT_UNKNOWN]
    total_focus = 0
    total_focus_covered = 0

    for cat in focus_cats:
        d = by_cat[cat]
        pct = (d['covered'] / d['total'] * 100) if d['total'] > 0 else 100
        marker = ''
        if cat in (CAT_PM3_CMD, CAT_BRANCH) and pct < 100:
            marker = ' <<<'
        elif cat == CAT_REGEX and pct < 80:
            marker = ' <'
        print(f"  {cat:<15s} {d['covered']:>8d} {d['total']:>8d} {pct:>6.1f}%{marker}")
        if cat not in (CAT_INTERNAL, CAT_DEBUG):
            total_focus += d['total']
            total_focus_covered += d['covered']

    focus_pct = (total_focus_covered / total_focus * 100) if total_focus > 0 else 100
    print(f"  {'-'*15} {'-'*8} {'-'*8} {'-'*7}")
    print(f"  {'FUNCTIONAL':<15s} {total_focus_covered:>8d} {total_focus:>8d} {focus_pct:>6.1f}%")

    # CRITICAL: uncovered branch keywords
    branch_uncov = by_cat[CAT_BRANCH]['uncovered']
    if branch_uncov:
        print(f"\n  {'='*78}")
        print(f"  CRITICAL — Uncovered branch-determining strings ({len(branch_uncov)})")
        print(f"  These strings trigger logic paths in the .so. Missing = missed branch.")
        print(f"  {'='*78}")
        seen = set()
        for so_file, r in sorted(branch_uncov, key=lambda x: x[1]['string']):
            s = r['string']
            if s in seen:
                continue
            seen.add(s)
            print(f"  [{mod:20s}]  {s}")

    # WARNING: uncovered PM3 commands
    pm3_uncov = by_cat[CAT_PM3_CMD]['uncovered']
    if pm3_uncov:
        print(f"\n  {'='*78}")
        print(f"  WARNING — Uncovered PM3 commands ({len(pm3_uncov)})")
        print(f"  {'='*78}")
        seen = set()
        for so_file, r in sorted(pm3_uncov, key=lambda x: x[1]['string']):
            s = r['string']
            if s in seen:
                continue
            seen.add(s)
            print(f"  [{mod:20s}]  {s}")

    # INFO: uncovered regex patterns
    regex_uncov = by_cat[CAT_REGEX]['uncovered']
    if regex_uncov:
        print(f"\n  {'='*78}")
        print(f"  INFO — Uncovered regex patterns ({len(regex_uncov)})")
        print(f"  {'='*78}")
        seen = set()
        for so_file, r in sorted(regex_uncov, key=lambda x: x[1]['string']):
            s = r['string']
            if s in seen:
                continue
            seen.add(s)
            print(f"  [{mod:20s}]  {s}")

    # Per-module breakdown
    print(f"\n  {'='*78}")
    print(f"  PER-MODULE BREAKDOWN")
    print(f"  {'='*78}")
    for so_file in sorted(all_results.keys()):
        results = all_results[so_file]
        # Count only functional strings (not internals)
        func = [r for r in results if r['category'] not in (CAT_INTERNAL, CAT_DEBUG)]
        covered = sum(1 for r in func if r['covered'])
        total = len(func)
        pct = (covered / total * 100) if total > 0 else 100
        bar = '#' * int(pct / 5) + '.' * (20 - int(pct / 5))
        print(f"  {mod:25s}  {covered:3d}/{total:3d}  [{bar}] {pct:5.1f}%")

    print(f"\n  {'='*78}")
    print(f"  RESULT: {scope_cfg['description']} — {focus_pct:.1f}% functional coverage")
    print(f"  CRITICAL gaps: {len(by_cat[CAT_BRANCH]['uncovered'])}")
    print(f"  PM3 cmd gaps:  {len(by_cat[CAT_PM3_CMD]['uncovered'])}")
    print(f"  {'='*78}")

    return focus_pct


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description='Step 4 Verification: .so string coverage')
    parser.add_argument('--scope', required=True, choices=list(SCOPES.keys()) + ['all'],
                        help='Which flow to verify')
    parser.add_argument('--json', type=str, help='Write results to JSON file')
    args = parser.parse_args()

    if args.scope == 'all':
        scopes_to_check = list(SCOPES.keys())
    else:
        scopes_to_check = [args.scope]

    for scope_name in scopes_to_check:
        scope_cfg = SCOPES[scope_name]

        # Load fixtures for this scope
        fixture_cmds, fixture_text = load_fixtures(scope_cfg['fixture_indexes'])

        # Check each module
        all_results = {}
        for so_file in scope_cfg['modules']:
            results = check_coverage(so_file, fixture_cmds, fixture_text)
            if results is not None:
                all_results[so_file] = results

        pct = report(scope_name, scope_cfg, all_results)

        if args.json:
            # Export detailed results
            export = {
                'scope': scope_name,
                'coverage_pct': pct,
                'modules': {}
            }
            for so_file, results in all_results.items():
                uncov = [r for r in results if not r['covered'] and r['category'] not in (CAT_INTERNAL, CAT_DEBUG)]
                export['modules'][so_file] = {
                    'total_functional': len([r for r in results if r['category'] not in (CAT_INTERNAL, CAT_DEBUG)]),
                    'covered': len([r for r in results if r['covered'] and r['category'] not in (CAT_INTERNAL, CAT_DEBUG)]),
                    'uncovered': [{'string': r['string'], 'category': r['category'], 'severity': r['severity']} for r in uncov]
                }
            Path(args.json).write_text(json.dumps(export, indent=2))
            print(f"\n  Detailed results written to: {args.json}")

        if len(scopes_to_check) > 1:
            print()


if __name__ == '__main__':
    main()
