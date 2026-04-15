# Simulate scenario: sim_ultralight_trace_empty
# HF Ultralight (type 7): sim with empty trace
# Ground truth: V1090_SIMULATION_FLOW_COMPLETE.md §4
#
# PM3 command sequence:
#   hf 14a sim t 7 u {edited_uid} (simulation)
#   hf 14a list (trace decode after stop — no reader interaction)

SCENARIO_RESPONSES = {
    'hf 14a sim': (1, ''),
    'hf 14a list': (1, '''[+] Recorded Activity (TraceLen = 0 bytes)
[+] trace len = 0
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 7
SIM_INDEX = 2
