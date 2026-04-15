# Auto-Copy scenario: autocopy_scan_no_tag
# No tag found - all scan phases timeout, toast: No tag found
# Ground truth: V1090_AUTOCOPY_FLOW_COMPLETE.md Section 3 (Scan Failures)
#
# PM3 command sequence:
#   hf 14a info -> timeout
#   hf sea -> timeout
#   lf sea -> timeout

SCENARIO_RESPONSES = {
}
DEFAULT_RETURN = -1
TAG_TYPE = -1
