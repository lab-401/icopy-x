# Simulate scenario: sim_m1_s70_4k_trace_data
# HF M1 S70 4K (type 2): sim with trace data
# Ground truth: V1090_SIMULATION_FLOW_COMPLETE.md §4
#
# PM3 command sequence:
#   hf 14a sim t 2 u {edited_uid} (simulation)
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
  2 |    2228 | Tag |04 68          |
  3 |   10848 | Rdr |93 70 04 68 2C AD C2 72 AF |
  4 |    6958 | Tag |18 B6 DD      |
-----+--------+-----+-----+----------+-----+
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 2
SIM_INDEX = 1
