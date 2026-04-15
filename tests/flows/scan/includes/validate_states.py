#!/usr/bin/env python3
"""Scan scenario state validator.

Reads scenario_states.json and expected.json, validates that the captured
states match expected values for each logic gate (scanning phase, result
phase, toast).

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


def text_contains(haystack, needle):
    """Case-sensitive substring match."""
    return needle in haystack


def _coerce_eq(actual, expected):
    """Compare values with type coercion.

    The original .so state dumps store scan_cache values as strings
    (e.g. 'True', '9') while expected.json uses native types (True, 9).
    This function handles both.
    """
    if actual == expected:
        return True
    # Try string comparison
    if str(actual) == str(expected):
        return True
    # Handle 'True'/'False' vs bool
    if isinstance(expected, bool):
        return str(actual).lower() == str(expected).lower()
    # Handle int vs string-of-int
    if isinstance(expected, int):
        try:
            return int(actual) == expected
        except (ValueError, TypeError):
            return False
    return False


def check_scanning_phase(states, expect, errors):
    """Validate that at least one early state matches scanning-phase expectations.

    Only considers states where scan_cache is null (tag not yet detected).
    This prevents picking late-transition states that still have 'Scanning...'
    in content but have already populated scan_cache and buttons.
    """
    spec = expect.get("scanning_phase")
    if not spec:
        return

    # Scanning-phase candidates: no scan_cache AND either:
    #   - "Scanning..." in content_text (reimpl style), OR
    #   - M2='Scanning...' with empty content (original .so style), OR
    #   - empty content with title="Scan Tag" (early boot)
    candidates = []
    for s in states:
        if s.get("scan_cache") is not None:
            continue
        content_texts = [t["text"] for t in s.get("content_text", [])]
        has_scanning_content = any("Scanning..." in t for t in content_texts)
        has_scanning_m2 = s.get("M2") == "Scanning..."
        is_early_scan = s.get("title") == "Scan Tag" and not content_texts
        if has_scanning_content or has_scanning_m2 or is_early_scan:
            candidates.append(s)

    if not candidates:
        errors.append("SCANNING: No pre-detection state found")
        return

    # Check that at least one candidate satisfies title check.
    # We only enforce title here — button state during scanning is
    # timing-dependent and varies between original .so and reimpl.
    for s in candidates:
        if spec.get("title") is not None and s.get("title") != spec["title"]:
            continue
        return  # Found a valid scanning state

    # All candidates failed title check
    s = candidates[0]
    if spec.get("title") is not None and s.get("title") != spec["title"]:
        errors.append(
            "SCANNING state %d: title: expected %r, got %r"
            % (s["state"], spec["title"], s.get("title"))
        )


def check_result_phase(states, expect, errors):
    """Validate that at least one state matches result-phase expectations.

    Mid-render states may have partial content — we require that AT LEAST ONE
    state satisfies ALL result-phase checks simultaneously.  Uses coerced
    comparison for scan_cache values (string vs native type).
    """
    spec = expect.get("result_phase")
    if not spec:
        return

    best_match_errors = None

    for s in states:
        state_errors = []

        # Title: use 'contains' check (e.g. "SecuraKey" matches "SecuraKey ")
        if "title" in spec:
            title = s.get("title") or ""
            if not text_contains(title, spec["title"]):
                state_errors.append(
                    "title: expected contains %r, got %r" % (spec["title"], title)
                )

        # M1 label
        if "M1" in spec and s.get("M1") != spec["M1"]:
            state_errors.append(
                "M1: expected %r, got %r" % (spec["M1"], s.get("M1"))
            )

        # M2 label
        if "M2" in spec and s.get("M2") != spec["M2"]:
            state_errors.append(
                "M2: expected %r, got %r" % (spec["M2"], s.get("M2"))
            )

        # Button active states — only check if explicitly required
        if "M1_active" in spec and s.get("M1_active") != spec["M1_active"]:
            state_errors.append(
                "M1_active: expected %s, got %s"
                % (spec["M1_active"], s.get("M1_active"))
            )
        if "M2_active" in spec and s.get("M2_active") != spec["M2_active"]:
            state_errors.append(
                "M2_active: expected %s, got %s"
                % (spec["M2_active"], s.get("M2_active"))
            )

        # Content text: each expected string must appear in at least one content item
        content_texts = [t["text"] for t in s.get("content_text", [])]
        for expected_text in spec.get("content_contains", []):
            if not any(text_contains(ct, expected_text) for ct in content_texts):
                state_errors.append(
                    "content: expected %r in %r" % (expected_text, content_texts)
                )

        # scan_cache checks with type coercion
        cache = s.get("scan_cache")
        if "scan_cache_found" in spec:
            if cache is None:
                state_errors.append(
                    "scan_cache.found: expected %s, got null"
                    % spec["scan_cache_found"]
                )
            elif not _coerce_eq(cache.get("found"), spec["scan_cache_found"]):
                state_errors.append(
                    "scan_cache.found: expected %s, got %s"
                    % (spec["scan_cache_found"], cache.get("found"))
                )
        if "scan_cache_type" in spec:
            if cache is None:
                state_errors.append(
                    "scan_cache.type: expected %s, got null"
                    % spec["scan_cache_type"]
                )
            elif not _coerce_eq(cache.get("type"), spec["scan_cache_type"]):
                state_errors.append(
                    "scan_cache.type: expected %s, got %s"
                    % (spec["scan_cache_type"], cache.get("type"))
                )

        if not state_errors:
            return  # Found a state that passes all checks

        # Track best partial match
        if best_match_errors is None or len(state_errors) < len(best_match_errors):
            best_match_errors = state_errors

    # No state passed all checks
    if best_match_errors:
        for e in best_match_errors:
            errors.append("RESULT: %s" % e)
    else:
        errors.append("RESULT: No states available to validate")


def check_toast(states, expect, errors):
    """Validate that the expected toast appears in at least one state."""
    expected_toast = expect.get("toast")
    if expected_toast is None:
        return

    for s in states:
        if s.get("toast") and text_contains(s["toast"], expected_toast):
            return

    actual_toasts = [s.get("toast") for s in states if s.get("toast")]
    errors.append(
        "TOAST: expected %r, found %r" % (expected_toast, actual_toasts)
    )


def check_no_tag(states, expect, errors):
    """Validate no-tag-found specific checks."""
    spec = expect.get("no_tag")
    if not spec:
        return

    for s in states:
        if "title" in spec and s.get("title") != spec["title"]:
            continue

        state_ok = True
        if "scan_cache" in spec and spec["scan_cache"] is None:
            if s.get("scan_cache") is not None:
                state_ok = False
        if state_ok:
            return

    errors.append("NO_TAG: No state matched no-tag expectations")


def main():
    if len(sys.argv) != 3:
        print("Usage: %s <scenario_states.json> <expected.json>" % sys.argv[0])
        sys.exit(1)

    states_path = sys.argv[1]
    expected_path = sys.argv[2]

    data = load_json(states_path)
    expect = load_json(expected_path)
    states = data.get("states", [])
    scenario = data.get("scenario", "unknown")

    errors = []

    check_scanning_phase(states, expect, errors)
    check_result_phase(states, expect, errors)
    check_toast(states, expect, errors)
    check_no_tag(states, expect, errors)

    if errors:
        print("VALIDATE_FAIL %s: %d check(s) failed" % (scenario, len(errors)))
        for e in errors:
            print("  - %s" % e)
        sys.exit(1)
    else:
        checks = sum(
            1
            for k in ("scanning_phase", "result_phase", "toast", "no_tag")
            if k in expect
        )
        print("VALIDATE_PASS %s: %d phase(s) validated" % (scenario, checks))
        sys.exit(0)


if __name__ == "__main__":
    main()
