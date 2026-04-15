# Auto-Copy scenario: autocopy_scan_multi_tag
# Multiple tags detected - hf 14a info returns collision, toast: Multiple tags detected
# Ground truth: V1090_AUTOCOPY_FLOW_COMPLETE.md Section 3 (Scan Failures)
#
# PM3 command sequence:
#   hf 14a info -> Multiple tags detected

SCENARIO_RESPONSES = {
    'hf 14a info': (1, '''
[!] Multiple tags detected. Collision after bit 32
'''),
}
DEFAULT_RETURN = -1
TAG_TYPE = -1
