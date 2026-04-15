#!/usr/bin/env python3
"""Shared scenario state validator for all flows.

Reads scenario_states.json and expected.json, validates that captured
states match expected values. Supports all check types used across
scan, read, write, auto-copy, and settings flows.

Exit codes:
  0 = all checks passed
  1 = one or more checks failed

Usage:
  python3 validate_common.py <scenario_states.json> <expected.json>
"""

import json
import sys


def load_json(path):
    with open(path) as f:
        return json.load(f)


def _coerce_eq(actual, expected):
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


def check_titles(states, expect, errors):
    """Each expected title string appears in at least one state."""
    for key in [k for k in expect if k.endswith("_title") or k == "title"]:
        val = expect[key]
        if val is None:
            continue
        found = any(s.get("title") and val in s["title"] for s in states)
        if not found:
            errors.append("%s: expected %r, never seen" % (key.upper(), val))


def check_toasts(states, expect, errors):
    """Each expected toast string appears in at least one state."""
    for key in [k for k in expect if k.endswith("_toast") or k == "toast"]:
        val = expect[key]
        if val is None:
            continue
        found = any(s.get("toast") and val in s["toast"] for s in states)
        if not found:
            actual = list(set(s["toast"] for s in states if s.get("toast")))
            errors.append("%s: expected %r, found %r" % (key.upper(), val, actual))


def check_buttons(states, expect, errors):
    """Each button spec has at least one matching state."""
    for key in [k for k in expect if k.endswith("_buttons") or k == "buttons"]:
        spec = expect[key]
        if not spec:
            continue
        for s in states:
            m1_ok = spec.get("M1") is None or s.get("M1") == spec["M1"]
            m2_ok = spec.get("M2") is None or s.get("M2") == spec["M2"]
            m1a_ok = "M1_active" not in spec or _coerce_eq(s.get("M1_active"), spec["M1_active"])
            m2a_ok = "M2_active" not in spec or _coerce_eq(s.get("M2_active"), spec["M2_active"])
            if m1_ok and m2_ok and m1a_ok and m2a_ok:
                break
        else:
            errors.append(
                "%s: M1=%r(%s) M2=%r(%s) never seen"
                % (key.upper(), spec.get("M1"), spec.get("M1_active", "?"),
                   spec.get("M2"), spec.get("M2_active", "?"))
            )


def check_content(states, expect, errors):
    """Each expected content string appears in at least one state's content_text."""
    for text in expect.get("content_contains", []):
        found = False
        for s in states:
            for item in s.get("content_text", []):
                if text in item.get("text", ""):
                    found = True
                    break
            if found:
                break
        if not found:
            errors.append("CONTENT: expected %r, never seen" % text)


def check_scan_cache(states, expect, errors):
    """scan_cache.type matches in at least one state."""
    spec = expect.get("scan_cache")
    if not spec or "type" not in spec:
        return
    et = spec["type"]
    for s in states:
        cache = s.get("scan_cache")
        if cache and _coerce_eq(cache.get("type"), et):
            return
    errors.append("SCAN_CACHE: expected type=%s, not found" % et)


def main():
    if len(sys.argv) != 3:
        print("Usage: %s <scenario_states.json> <expected.json>" % sys.argv[0])
        sys.exit(1)

    data = load_json(sys.argv[1])
    expect = load_json(sys.argv[2])
    states = data.get("states", [])
    scenario = data.get("scenario", "unknown")

    errors = []

    check_titles(states, expect, errors)
    check_toasts(states, expect, errors)
    check_buttons(states, expect, errors)
    check_content(states, expect, errors)
    check_scan_cache(states, expect, errors)

    if errors:
        print("VALIDATE_FAIL %s: %d check(s) failed" % (scenario, len(errors)))
        for e in errors:
            print("  - %s" % e)
        sys.exit(1)
    else:
        check_count = sum(1 for k in expect if expect[k] is not None and k != "content_contains") + (1 if expect.get("content_contains") else 0)
        print("VALIDATE_PASS %s: %d check(s) validated" % (scenario, check_count))
        sys.exit(0)


if __name__ == "__main__":
    main()
