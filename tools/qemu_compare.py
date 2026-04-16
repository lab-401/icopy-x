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

"""Compare UI state between original .so and our Python implementation.

For each activity, extracts the canonical UI state (title, buttons,
content text, canvas item counts, colors, positions) and produces a
structured diff.  This is the offline comparison tool -- it works on
state dump JSON files produced by the flow test infrastructure.

Usage:
    # Compare a single scenario's state dumps
    python3 tools/qemu_compare.py \\
        tests/flows/_results/backlight/scenarios/backlight_save_high_to_low/scenario_states.json \\
        tests/flows/_results_newui/backlight/scenarios/backlight_save_high_to_low/scenario_states.json

    # Compare all scenarios in two result directories
    python3 tools/qemu_compare.py --dir tests/flows/_results tests/flows/_results_newui

Output:
    For each state in the scenario, prints a side-by-side comparison:
      - Title match / mismatch
      - M1/M2 button label match
      - Content text items (ordered by y, then x)
      - Toast text match
      - Canvas item count (rect, text, image, line)
      - Color mismatches for known elements (title bar, selection, etc.)

Exit code:
    0 = all states match
    1 = at least one mismatch found
"""

import argparse
import json
import os
import sys
from pathlib import Path


def extract_ui_state(state_entry):
    """Extract a canonical UI state dict from a scenario_states.json entry.

    Returns a dict with normalized keys for comparison:
        title: str or None
        M1: str or None
        M2: str or None
        toast: str or None
        activity: str or None
        activity_stack: list[str]
        content_text: list[dict] with 'text', 'x', 'y', 'fill'
        item_counts: dict of type -> count
        colors: dict of element -> color
    """
    result = {
        'title': state_entry.get('title'),
        'M1': state_entry.get('M1'),
        'M2': state_entry.get('M2'),
        'toast': state_entry.get('toast'),
        'activity': state_entry.get('activity'),
        'activity_stack': state_entry.get('activity_stack', []),
        'content_text': [],
        'item_counts': {},
        'colors': {},
    }

    # Normalize content text (sort by y, then x for deterministic order)
    for ct in state_entry.get('content_text', []):
        result['content_text'].append({
            'text': ct.get('text', ''),
            'x': round(float(ct.get('x', 0)), 1),
            'y': round(float(ct.get('y', 0)), 1),
            'fill': ct.get('fill', ''),
        })
    result['content_text'].sort(key=lambda c: (c['y'], c['x']))

    # Count canvas items by type
    for item in state_entry.get('canvas_items', []):
        itype = item.get('type', 'unknown')
        result['item_counts'][itype] = result['item_counts'].get(itype, 0) + 1

    # Extract known color values from canvas items
    for item in state_entry.get('canvas_items', []):
        tags = item.get('tags', [])
        for tag in tags:
            tl = tag.lower()
            if 'title' in tl and item.get('type') == 'rectangle':
                result['colors']['title_bar'] = item.get('fill', '')
            elif 'btn_bg' in tl and item.get('type') == 'rectangle':
                result['colors']['button_bar'] = item.get('fill', '')

    return result


def compare_states(state_a, state_b):
    """Compare two extracted UI states.

    Returns a list of (field, expected, actual) tuples for mismatches.
    Empty list means perfect match.
    """
    diffs = []

    # Simple field comparisons
    for field in ('title', 'M1', 'M2', 'toast', 'activity'):
        va = state_a.get(field)
        vb = state_b.get(field)
        if va != vb:
            diffs.append((field, va, vb))

    # Activity stack comparison
    stack_a = state_a.get('activity_stack', [])
    stack_b = state_b.get('activity_stack', [])
    if stack_a != stack_b:
        diffs.append(('activity_stack', stack_a, stack_b))

    # Content text comparison (order-independent: compare sorted lists)
    texts_a = sorted(ct['text'] for ct in state_a.get('content_text', []))
    texts_b = sorted(ct['text'] for ct in state_b.get('content_text', []))
    if texts_a != texts_b:
        diffs.append(('content_text', texts_a, texts_b))

    # Item count comparison (allow minor differences)
    counts_a = state_a.get('item_counts', {})
    counts_b = state_b.get('item_counts', {})
    all_types = set(counts_a) | set(counts_b)
    for itype in sorted(all_types):
        ca = counts_a.get(itype, 0)
        cb = counts_b.get(itype, 0)
        if abs(ca - cb) > 2:  # Allow up to 2 items difference (battery, etc.)
            diffs.append((f'item_count:{itype}', ca, cb))

    # Color comparison
    colors_a = state_a.get('colors', {})
    colors_b = state_b.get('colors', {})
    for key in sorted(set(colors_a) | set(colors_b)):
        ca = colors_a.get(key, '')
        cb = colors_b.get(key, '')
        if ca.lower() != cb.lower():
            diffs.append((f'color:{key}', ca, cb))

    return diffs


def compare_scenario_files(path_a, path_b):
    """Compare two scenario_states.json files.

    Returns (total_states, mismatched_states, all_diffs).
    """
    with open(path_a) as f:
        data_a = json.load(f)
    with open(path_b) as f:
        data_b = json.load(f)

    states_a = data_a.get('states', [])
    states_b = data_b.get('states', [])

    total = max(len(states_a), len(states_b))
    mismatched = 0
    all_diffs = []

    for i in range(total):
        if i >= len(states_a):
            all_diffs.append((i + 1, [('missing_in_original', None, 'present')]))
            mismatched += 1
            continue
        if i >= len(states_b):
            all_diffs.append((i + 1, [('missing_in_new', 'present', None)]))
            mismatched += 1
            continue

        sa = extract_ui_state(states_a[i])
        sb = extract_ui_state(states_b[i])
        diffs = compare_states(sa, sb)
        if diffs:
            mismatched += 1
            all_diffs.append((i + 1, diffs))

    return total, mismatched, all_diffs


def print_comparison(path_a, path_b, total, mismatched, all_diffs):
    """Print a human-readable comparison report."""
    scenario_a = os.path.basename(os.path.dirname(path_a))
    scenario_b = os.path.basename(os.path.dirname(path_b))

    print(f"\n{'='*60}")
    print(f"  Scenario: {scenario_a}")
    print(f"  Original: {path_a}")
    print(f"  New UI:   {path_b}")
    print(f"  States: {total}, Matched: {total - mismatched}, "
          f"Mismatched: {mismatched}")
    print(f"{'='*60}")

    if not all_diffs:
        print("  PASS -- all states match")
        return

    for state_idx, diffs in all_diffs:
        print(f"\n  State {state_idx}:")
        for field, expected, actual in diffs:
            print(f"    {field}:")
            print(f"      original: {expected}")
            print(f"      new_ui:   {actual}")


def compare_directories(dir_a, dir_b):
    """Compare all scenario_states.json files in two result trees.

    Returns total mismatch count.
    """
    total_mismatches = 0
    total_scenarios = 0

    for root, dirs, files in os.walk(dir_a):
        for fname in files:
            if fname != 'scenario_states.json':
                continue

            path_a = os.path.join(root, fname)
            # Compute relative path and find counterpart in dir_b
            rel = os.path.relpath(path_a, dir_a)
            path_b = os.path.join(dir_b, rel)

            if not os.path.exists(path_b):
                print(f"\n  SKIP: {rel} -- not found in {dir_b}")
                continue

            total_scenarios += 1
            total, mismatched, all_diffs = compare_scenario_files(path_a, path_b)
            print_comparison(path_a, path_b, total, mismatched, all_diffs)
            total_mismatches += mismatched

    print(f"\n{'='*60}")
    print(f"  TOTAL: {total_scenarios} scenarios compared, "
          f"{total_mismatches} state mismatches")
    print(f"{'='*60}")
    return total_mismatches


def main():
    parser = argparse.ArgumentParser(
        description='Compare UI state dumps between original and new UI')
    parser.add_argument('path_a', help='First scenario_states.json or result dir')
    parser.add_argument('path_b', help='Second scenario_states.json or result dir')
    parser.add_argument('--dir', action='store_true',
                        help='Compare directories recursively')
    args = parser.parse_args()

    if args.dir or (os.path.isdir(args.path_a) and os.path.isdir(args.path_b)):
        mismatches = compare_directories(args.path_a, args.path_b)
        sys.exit(1 if mismatches > 0 else 0)
    else:
        total, mismatched, all_diffs = compare_scenario_files(
            args.path_a, args.path_b)
        print_comparison(args.path_a, args.path_b, total, mismatched, all_diffs)
        sys.exit(1 if mismatched > 0 else 0)


if __name__ == '__main__':
    main()
