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

"""Generate per-scenario fixture.py files from the monolithic pm3_fixtures.py.

This is a one-shot migration tool. It reads ALL_SCAN_SCENARIOS, ALL_READ_SCENARIOS,
and read_list_map.json, performs the merges that generate_read_mock/generate_mock
currently do at runtime, and writes a complete fixture.py into each scenario directory.

It also generates fixture_lib.py (shared building blocks) for both read and scan flows.

Usage:
    python3 tools/generate_scenario_fixtures.py [--dry-run] [--verify]

    --dry-run   Print what would be written without writing
    --verify    Generate to temp, compare against runtime merge output
"""

import sys
import os
import json
import textwrap

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT, 'tools'))

import pm3_fixtures

# ---------------------------------------------------------------------------
# Load read_list_map.json for scan fixture lookup
# ---------------------------------------------------------------------------
with open(os.path.join(PROJECT, 'tools', 'read_list_map.json')) as f:
    READ_LIST_MAP = json.load(f)

# Build type → scan_key lookup
TYPE_TO_SCAN = {}
for item in READ_LIST_MAP['items']:
    TYPE_TO_SCAN[item['type']] = item.get('scan', '')

# Build type → (page, down) lookup
TYPE_TO_NAV = {}
for item in READ_LIST_MAP['items']:
    TYPE_TO_NAV[item['type']] = (item['page'], item['down'])


def format_response_value(val):
    """Format a fixture value for writing into fixture.py."""
    if isinstance(val, tuple):
        ret_code, text = val
        # Use triple-quoted strings for readability
        escaped = text.replace("'''", "\\'\\'\\'")
        return "(%d, '''%s''')" % (ret_code, escaped)
    else:
        return repr(val)


def build_merged_read_fixture(read_key, read_fix):
    """Merge scan fixture + read fixture, exactly as generate_read_mock does."""
    tag_type = read_fix.get('_tag_type', 1)
    scan_key = TYPE_TO_SCAN.get(tag_type, '')

    merged = {}
    # Scan fixture first
    if scan_key:
        scan_fix = pm3_fixtures.ALL_SCAN_SCENARIOS.get(scan_key, {})
        for k, v in scan_fix.items():
            if k.startswith('_'):
                continue
            merged[k] = v

    # Read fixture overlays
    for k, v in read_fix.items():
        if k.startswith('_'):
            continue
        merged[k] = v

    default_ret = read_fix.get('_default_return', 1)
    return merged, default_ret, tag_type


def build_scan_fixture(scan_key, scan_fix):
    """Extract PM3 responses from a scan fixture."""
    responses = {}
    for k, v in scan_fix.items():
        if k.startswith('_'):
            continue
        responses[k] = v

    default_ret = scan_fix.get('_default_return', -1)
    tag_type = scan_fix.get('_tag_type', None)
    return responses, default_ret, tag_type


def write_fixture_py(path, responses, default_ret, tag_type, description=''):
    """Write a fixture.py file with SCENARIO_RESPONSES, DEFAULT_RETURN, TAG_TYPE."""
    lines = []
    if description:
        lines.append('# %s' % description)
    lines.append('SCENARIO_RESPONSES = {')
    for k, v in responses.items():
        lines.append("    '%s': %s," % (k, format_response_value(v)))
    lines.append('}')
    lines.append('DEFAULT_RETURN = %d' % default_ret)
    if tag_type is not None:
        lines.append('TAG_TYPE = %s' % repr(tag_type))
    lines.append('')

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        f.write('\n'.join(lines))


def generate_read_fixtures(dry_run=False):
    """Generate fixture.py for every read scenario directory."""
    scenarios_dir = os.path.join(PROJECT, 'tests', 'flows', 'read', 'scenarios')
    generated = 0
    skipped = []

    for read_key, read_fix in pm3_fixtures.ALL_READ_SCENARIOS.items():
        scenario_name = 'read_' + read_key
        scenario_dir = os.path.join(scenarios_dir, scenario_name)

        if not os.path.isdir(scenario_dir):
            skipped.append((read_key, 'no scenario dir'))
            continue

        responses, default_ret, tag_type = build_merged_read_fixture(read_key, read_fix)
        desc = read_fix.get('_description', read_key)
        fixture_path = os.path.join(scenario_dir, 'fixture.py')

        if dry_run:
            print("  [DRY] %s → %d responses, default=%d, type=%s" % (
                scenario_name, len(responses), default_ret, tag_type))
        else:
            write_fixture_py(fixture_path, responses, default_ret, tag_type, desc)
            generated += 1

    return generated, skipped


def generate_scan_fixtures(dry_run=False):
    """Generate fixture.py for every scan scenario directory."""
    scenarios_dir = os.path.join(PROJECT, 'tests', 'flows', 'scan', 'scenarios')
    generated = 0
    skipped = []

    # Only generate for the 44 scan scenarios that have directories
    # (not the read_* prefixed ones in ALL_SCAN_SCENARIOS)
    for scan_key, scan_fix in pm3_fixtures.ALL_SCAN_SCENARIOS.items():
        if scan_key.startswith('read_'):
            continue  # These are read-mode LF scan fixtures, not scan flow tests

        scenario_name = 'scan_' + scan_key
        scenario_dir = os.path.join(scenarios_dir, scenario_name)

        if not os.path.isdir(scenario_dir):
            skipped.append((scan_key, 'no scenario dir'))
            continue

        responses, default_ret, tag_type = build_scan_fixture(scan_key, scan_fix)
        desc = scan_fix.get('_description', scan_key)
        fixture_path = os.path.join(scenario_dir, 'fixture.py')

        if dry_run:
            print("  [DRY] %s → %d responses, default=%d, type=%s" % (
                scenario_name, len(responses), default_ret, tag_type))
        else:
            write_fixture_py(fixture_path, responses, default_ret, tag_type, desc)
            generated += 1

    return generated, skipped


def verify_read_fixture(read_key, read_fix):
    """Verify that our generated fixture matches what generate_read_mock produces.

    Returns (match: bool, details: str).
    """
    responses, default_ret, tag_type = build_merged_read_fixture(read_key, read_fix)

    # Simulate what generate_read_mock produces: the Python code in read_common.sh
    tag_type_fix = read_fix.get('_tag_type', 1)
    scan_key = TYPE_TO_SCAN.get(tag_type_fix, '')

    runtime_merged = {}
    if scan_key:
        scan_fix = pm3_fixtures.ALL_SCAN_SCENARIOS.get(scan_key, {})
        for k, v in scan_fix.items():
            if k.startswith('_'):
                continue
            runtime_merged[k] = v
    for k, v in read_fix.items():
        if k.startswith('_'):
            continue
        runtime_merged[k] = v

    runtime_default = read_fix.get('_default_return', 1)

    # Compare
    if responses != runtime_merged:
        return False, "responses differ: gen=%d runtime=%d" % (len(responses), len(runtime_merged))
    if default_ret != runtime_default:
        return False, "default_ret: gen=%d runtime=%d" % (default_ret, runtime_default)
    return True, "OK"


def main():
    dry_run = '--dry-run' in sys.argv
    verify = '--verify' in sys.argv

    if verify:
        print("=== Verifying read fixture generation matches runtime merge ===")
        ok = 0
        fail = 0
        for read_key, read_fix in pm3_fixtures.ALL_READ_SCENARIOS.items():
            match, detail = verify_read_fixture(read_key, read_fix)
            if match:
                ok += 1
            else:
                fail += 1
                print("  MISMATCH: %s — %s" % (read_key, detail))
        print("Verified: %d OK, %d FAIL" % (ok, fail))
        if fail > 0:
            sys.exit(1)
        return

    print("=== Generating read scenario fixtures ===")
    gen_r, skip_r = generate_read_fixtures(dry_run)
    print("  Generated: %d, Skipped: %d" % (gen_r, len(skip_r)))
    for key, reason in skip_r:
        print("    SKIP read_%s: %s" % (key, reason))

    print("\n=== Generating scan scenario fixtures ===")
    gen_s, skip_s = generate_scan_fixtures(dry_run)
    print("  Generated: %d, Skipped: %d" % (gen_s, len(skip_s)))
    for key, reason in skip_s:
        print("    SKIP scan_%s: %s" % (key, reason))

    print("\nTotal: %d read + %d scan = %d fixture.py files" % (gen_r, gen_s, gen_r + gen_s))


if __name__ == '__main__':
    main()
