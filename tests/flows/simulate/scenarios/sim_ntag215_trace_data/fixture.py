# Simulate scenario: sim_ntag215_trace_data
# HF Ntag215 (type 8): sim with trace data
# Ground truth: V1090_SIMULATION_FLOW_COMPLETE.md §4
#
# PM3 command sequence:
#   hf 14a sim t 8 u {edited_uid} (simulation)
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
  2 |    2228 | Tag |04 A3 B5      |
  3 |   10848 | Rdr |93 70 04 A3 B5 C7 D9 E1 F2 |
  4 |    6958 | Tag |04 DA        |
  5 |   12000 | Rdr |30 04         |
  6 |    3500 | Tag |01 02 03 04 05 06 07 08 09 0A 0B 0C 0D 0E 0F 10 |
-----+--------+-----+-----+----------+-----+
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 8
SIM_INDEX = 3
