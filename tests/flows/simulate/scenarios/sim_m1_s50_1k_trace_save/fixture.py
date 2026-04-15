# Simulate scenario: sim_m1_s50_1k_trace_save
# HF M1 S50 1K (type 1): sim with trace data, then save trace
# Ground truth: V1090_SIMULATION_FLOW_COMPLETE.md §4
#
# PM3 command sequence:
#   hf 14a sim t 1 u {edited_uid} (simulation)
#   hf 14a list (trace decode after stop)
#   trace save (M2 press in trace view)

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
  4 |    6958 | Tag |08 B6 DD      |
-----+--------+-----+-----+----------+-----+
'''),
    'trace save': (1, '[+] Trace file saved to /mnt/upan/trace/trace_20260329_120000.pm3'),
}
DEFAULT_RETURN = 1
TAG_TYPE = 1
SIM_INDEX = 0
