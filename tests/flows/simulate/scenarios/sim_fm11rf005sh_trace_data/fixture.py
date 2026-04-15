# Simulate scenario: sim_fm11rf005sh_trace_data
# HF FM11RF005SH (type 9): sim with trace data
# Ground truth: V1090_SIMULATION_FLOW_COMPLETE.md §4
#
# PM3 command sequence:
#   hf 14a sim t 9 u {edited_uid} (simulation)
#   hf 14a list (trace decode after stop)

SCENARIO_RESPONSES = {
    'hf 14a sim': (1, ''),
    'hf 14a list': (1, '''[+] Recorded Activity (TraceLen = 128 bytes)
[=] Start = Start of traced data
[=]        = End of traced data
[+] trace len = 128
-----+--------+-----+-----+----------+-----+
 # | time | src | data |
-----+--------+-----+-----+----------+-----+
  1 |       0 | Rdr |93 20          |
  2 |    2228 | Tag |88 04         |
  3 |   10848 | Rdr |93 70 88 04 5A 7B 3C E1 F2 |
  4 |    6958 | Tag |04 DA        |
-----+--------+-----+-----+----------+-----+
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 9
SIM_INDEX = 4
