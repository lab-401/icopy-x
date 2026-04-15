#!/usr/bin/env python3
"""Write scenario state validator.

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


def check_title(states, expect, errors):
    """At least one state has the expected title."""
    for key in ("warning_title", "write_title"):
        val = expect.get(key)
        if val is None:
            continue
        found = any(s.get("title") and val in s["title"] for s in states)
        if not found:
            errors.append("%s: expected %r, never seen" % (key.upper(), val))


def check_toast(states, expect, errors):
    """Each expected toast appears in at least one state."""
    for key in ("write_toast", "verify_toast"):
        val = expect.get(key)
        if val is None:
            continue
        found = any(s.get("toast") and val in s["toast"] for s in states)
        if not found:
            actual = [s["toast"] for s in states if s.get("toast")]
            errors.append("%s: expected %r, found %r" % (key.upper(), val, actual))


def check_result_buttons(states, expect, errors):
    """At least one state has the expected button labels and active states."""
    spec = expect.get("result_buttons")
    if not spec:
        return

    for s in states:
        m1_ok = spec.get("M1") is None or s.get("M1") == spec["M1"]
        m2_ok = spec.get("M2") is None or s.get("M2") == spec["M2"]
        m1a_ok = "M1_active" not in spec or _coerce_eq(s.get("M1_active"), spec["M1_active"])
        m2a_ok = "M2_active" not in spec or _coerce_eq(s.get("M2_active"), spec["M2_active"])
        if m1_ok and m2_ok and m1a_ok and m2a_ok:
            return

    errors.append(
        "BUTTONS: expected M1=%r(%s) M2=%r(%s), never seen together"
        % (spec.get("M1"), spec.get("M1_active", "?"),
           spec.get("M2"), spec.get("M2_active", "?"))
    )


def check_warning(states, expect, errors):
    """Warning screen appeared with expected buttons."""
    spec = expect.get("warning")
    if not spec:
        return

    for s in states:
        m1_ok = spec.get("M1") is None or s.get("M1") == spec["M1"]
        m2_ok = spec.get("M2") is None or s.get("M2") == spec["M2"]
        if m1_ok and m2_ok:
            return

    errors.append(
        "WARNING: expected M1=%r M2=%r, never seen together"
        % (spec.get("M1"), spec.get("M2"))
    )


def check_content(states, expect, errors):
    """Each expected content string appears in at least one state."""
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
    check_warning(states, expect, errors)
    check_content(states, expect, errors)

    if errors:
        print("VALIDATE_FAIL %s: %d check(s) failed" % (scenario, len(errors)))
        for e in errors:
            print("  - %s" % e)
        sys.exit(1)
    else:
        checks = sum(
            1 for k in ("warning_title", "write_title", "write_toast",
                        "verify_toast", "result_buttons", "warning",
                        "content_contains")
            if k in expect
        )
        print("VALIDATE_PASS %s: %d check(s) validated" % (scenario, checks))
        sys.exit(0)


if __name__ == "__main__":
    main()
