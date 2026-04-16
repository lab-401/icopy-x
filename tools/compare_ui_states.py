#!/usr/bin/env python3

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

"""Compare original vs current state dumps for pixel-level UI parity.

Usage:
    python3 tools/compare_ui_states.py --flow about [--scenario about_page1]
    python3 tools/compare_ui_states.py --flow scan --all
    python3 tools/compare_ui_states.py --flow scan --all --baseline original_current_ui --target current

Compares state dumps between two targets for pixel-level UI parity:
- text: exact match
- x, y: within ±2px tolerance
- fill: exact match (color)
- font: size match only (face ignored — mononoki vs monospace acceptable)
- scan_cache: type, found fields
- canvas_items: rectangles (progress bars, etc.)

Exits 0 if no diffs, 1 if diffs found.
"""

import argparse
import json
import os
import re
import sys
import glob


def extract_font_size(font_str):
    """Extract numeric font size from font string like 'mononoki 13'.

    Returns None for opaque font names like 'font1', 'font2' (internal
    InputMethods references where the number is an ID, not a size).
    """
    if not font_str:
        return None
    # Skip opaque font IDs (fontN where N is 1-9)
    if re.match(r'^font\d+$', font_str):
        return None
    m = re.search(r'(\d+)', font_str)
    return int(m.group(1)) if m else None


def compare_content_text(orig_items, curr_items, state_idx):
    """Compare two content_text arrays. Returns list of diff strings."""
    diffs = []

    if len(orig_items) != len(curr_items):
        diffs.append(f'  content_text count: original={len(orig_items)}, current={len(curr_items)}')

    for i in range(min(len(orig_items), len(curr_items))):
        o = orig_items[i]
        c = curr_items[i]

        o_text = o.get('text', '')
        c_text = c.get('text', '')
        if o_text != c_text:
            diffs.append(f'  [{i}] text: orig={repr(o_text[:40])}, curr={repr(c_text[:40])}')

        # Position (±2px tolerance)
        for coord in ('x', 'y'):
            ov = o.get(coord)
            cv = c.get(coord)
            if ov is not None and cv is not None:
                if abs(float(ov) - float(cv)) > 2.0:
                    diffs.append(f'  [{i}] {coord}: orig={ov}, curr={cv}')

        # Fill color (normalize aliases)
        color_map = {'#000000': 'black', '#ffffff': 'white', '#fff': 'white'}
        o_fill = (o.get('fill') or '').lower()
        c_fill = (c.get('fill') or '').lower()
        o_fill = color_map.get(o_fill, o_fill)
        c_fill = color_map.get(c_fill, c_fill)
        if o_fill and c_fill and o_fill != c_fill:
            diffs.append(f'  [{i}] fill: orig={o_fill}, curr={c_fill}')

        # Font size (ignore face)
        o_size = extract_font_size(o.get('font', ''))
        c_size = extract_font_size(c.get('font', ''))
        if o_size and c_size and o_size != c_size:
            diffs.append(f'  [{i}] font_size: orig={o_size}, curr={c_size}')

    return diffs


def compare_scenario(flow, scenario, results_base, baseline='original', target='current'):
    """Compare a single scenario. Returns list of diff strings."""
    orig_path = os.path.join(results_base, baseline, flow, 'scenarios', scenario, 'scenario_states.json')
    curr_path = os.path.join(results_base, target, flow, 'scenarios', scenario, 'scenario_states.json')

    if not os.path.exists(orig_path):
        return [f'  MISSING: {baseline} state dump']
    if not os.path.exists(curr_path):
        return [f'  MISSING: {target} state dump']

    with open(orig_path) as f:
        orig = json.load(f)
    with open(curr_path) as f:
        curr = json.load(f)

    orig_states = orig.get('states', [])
    curr_states = curr.get('states', [])

    all_diffs = []

    for si in range(min(len(orig_states), len(curr_states))):
        os_state = orig_states[si]
        cs_state = curr_states[si]

        # Compare title
        ot = os_state.get('title', '')
        ct = cs_state.get('title', '')
        if ot != ct:
            all_diffs.append(f'  STATE {si+1} title: orig={repr(ot)}, curr={repr(ct)}')

        # Compare M1/M2
        for btn in ('M1', 'M2'):
            ob = os_state.get(btn)
            cb = cs_state.get(btn)
            if str(ob) != str(cb):
                all_diffs.append(f'  STATE {si+1} {btn}: orig={repr(ob)}, curr={repr(cb)}')

        # Compare toast
        otoast = os_state.get('toast') or ''
        ctoast = cs_state.get('toast') or ''
        if str(otoast) != str(ctoast):
            all_diffs.append(f'  STATE {si+1} toast: orig={repr(str(otoast)[:40])}, curr={repr(str(ctoast)[:40])}')

        # Compare content_text items
        o_ct = os_state.get('content_text', [])
        c_ct = cs_state.get('content_text', [])
        ct_diffs = compare_content_text(o_ct, c_ct, si + 1)
        for d in ct_diffs:
            all_diffs.append(f'  STATE {si+1} {d}')

        # Compare scan_cache
        o_sc = os_state.get('scan_cache') or {}
        c_sc = cs_state.get('scan_cache') or {}
        if o_sc or c_sc:
            for key in ('type', 'found', 'uid', 'sak', 'atqa'):
                ov = o_sc.get(key)
                cv = c_sc.get(key)
                if str(ov) != str(cv):
                    all_diffs.append(f'  STATE {si+1} scan_cache.{key}: {baseline}={repr(ov)}, {target}={repr(cv)}')

        # Compare canvas_items (rectangles for progress bars, etc.)
        o_ci = os_state.get('canvas_items', [])
        c_ci = cs_state.get('canvas_items', [])
        o_rects = [x for x in o_ci if x.get('type') == 'rectangle']
        c_rects = [x for x in c_ci if x.get('type') == 'rectangle']
        if len(o_rects) != len(c_rects):
            all_diffs.append(f'  STATE {si+1} rectangles: {baseline}={len(o_rects)}, {target}={len(c_rects)}')

    if len(orig_states) != len(curr_states):
        all_diffs.append(f'  state_count: {baseline}={len(orig_states)}, {target}={len(curr_states)}')

    return all_diffs


def main():
    parser = argparse.ArgumentParser(description='Compare UI state dumps between targets')
    parser.add_argument('--flow', required=True, help='Flow name (scan, about, time_settings, pc_mode)')
    parser.add_argument('--scenario', help='Specific scenario name')
    parser.add_argument('--all', action='store_true', help='Compare all scenarios')
    parser.add_argument('--results', default='tests/flows/_results', help='Results base dir')
    parser.add_argument('--baseline', default='original', help='Baseline target (default: original)')
    parser.add_argument('--target', default='current', help='Target to compare (default: current)')
    args = parser.parse_args()

    results_base = args.results
    baseline = args.baseline
    target = args.target
    total_diffs = 0

    if args.scenario:
        scenarios = [args.scenario]
    elif args.all:
        pattern = os.path.join(results_base, baseline, args.flow, 'scenarios', '*', 'scenario_states.json')
        scenarios = sorted(os.path.basename(os.path.dirname(p)) for p in glob.glob(pattern))
    else:
        parser.error('Specify --scenario or --all')

    print(f'Comparing {baseline} vs {target} for flow={args.flow}\n')

    for scenario in scenarios:
        diffs = compare_scenario(args.flow, scenario, results_base, baseline, target)
        if diffs:
            print(f'DIFF: {args.flow}/{scenario}')
            for d in diffs:
                print(d)
            print()
            total_diffs += len(diffs)
        else:
            print(f'OK: {args.flow}/{scenario}')

    print(f'\nTotal differences: {total_diffs}')
    sys.exit(1 if total_diffs > 0 else 0)


if __name__ == '__main__':
    main()
