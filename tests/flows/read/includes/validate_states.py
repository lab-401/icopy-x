#!/usr/bin/env python3
"""Read scenario state validator.

Reads scenario_states.json and expected.json, validates that the captured
states match expected values for each logic gate.

Exit codes:
  0 = all checks passed
  1 = one or more checks failed (details printed to stdout)

Usage:
  python3 validate_states.py <scenario_states.json> <expected.json>
"""

import json
import sys


def load_json(path):
    with open(path) as f:
        return json.load(f)


def _coerce_eq(actual, expected):
    """Compare with type coercion (string '9' == int 9, string 'True' == bool True)."""
    if actual == expected:
        return True
    if str(actual) == str(expected):
        return True
    if isinstance(expected, bool):
        return str(actual).lower() == str(expected).lower()
    if isinstance(expected, int):
        try:
            return int(actual) == expected
        except (ValueError, TypeError):
            return False
    return False


def check_toast(states, expect, errors):
    """Validate that the expected toast appears in at least one state."""
    expected_toast = expect.get("toast")
    if expected_toast is None:
        return

    for s in states:
        if s.get("toast") and expected_toast in s["toast"]:
            return

    actual_toasts = [s.get("toast") for s in states if s.get("toast")]
    errors.append(
        "TOAST: expected %r, found %r" % (expected_toast, actual_toasts)
    )


def check_result_buttons(states, expect, errors):
    """Validate that at least one state has the expected button labels."""
    spec = expect.get("result_buttons")
    if not spec:
        return

    expected_m1 = spec.get("M1")
    expected_m2 = spec.get("M2")

    for s in states:
        m1_ok = expected_m1 is None or s.get("M1") == expected_m1
        m2_ok = expected_m2 is None or s.get("M2") == expected_m2
        if m1_ok and m2_ok:
            return

    errors.append(
        "BUTTONS: expected M1=%r M2=%r, never seen together"
        % (expected_m1, expected_m2)
    )


def check_title(states, expect, errors):
    """Validate that at least one state has the expected title."""
    expected_title = expect.get("title")
    if expected_title is None:
        return

    for s in states:
        if s.get("title") == expected_title:
            return

    actual_titles = list(set(s.get("title") for s in states if s.get("title")))
    errors.append(
        "TITLE: expected %r, found %r" % (expected_title, actual_titles)
    )


def check_scan_cache(states, expect, errors):
    """Validate scan_cache.type in at least one state."""
    spec = expect.get("scan_cache")
    if not spec:
        return

    expected_type = spec.get("type")
    if expected_type is None:
        return

    for s in states:
        cache = s.get("scan_cache")
        if cache and _coerce_eq(cache.get("type"), expected_type):
            return

    actual_types = list(set(
        str(s.get("scan_cache", {}).get("type"))
        for s in states if s.get("scan_cache")
    ))
    errors.append(
        "SCAN_CACHE: expected type=%s, found %r" % (expected_type, actual_types)
    )


def check_warning_screen(states, expect, errors):
    """Validate that the Warning/Sniff screen appeared."""
    spec = expect.get("warning_screen")
    if not spec:
        return

    expected_m1 = spec.get("M1")
    if expected_m1 is None:
        return

    for s in states:
        if s.get("M1") == expected_m1:
            return

    errors.append(
        "WARNING: expected M1=%r, never seen" % expected_m1
    )


def main():
    if len(sys.argv) != 3:
        print("Usage: %s <scenario_states.json> <expected.json>" % sys.argv[0])
        sys.exit(1)

    data = load_json(sys.argv[1])
    expect = load_json(sys.argv[2])
    states = data.get("states", [])
    scenario = data.get("scenario", "unknown")

    errors = []

    check_title(states, expect, errors)
    check_toast(states, expect, errors)
    check_result_buttons(states, expect, errors)
    check_scan_cache(states, expect, errors)
    check_warning_screen(states, expect, errors)

    if errors:
        print("VALIDATE_FAIL %s: %d check(s) failed" % (scenario, len(errors)))
        for e in errors:
            print("  - %s" % e)
        sys.exit(1)
    else:
        checks = sum(
            1 for k in ("title", "toast", "result_buttons", "scan_cache", "warning_screen")
            if k in expect
        )
        print("VALIDATE_PASS %s: %d check(s) validated" % (scenario, checks))
        sys.exit(0)


if __name__ == "__main__":
    main()
