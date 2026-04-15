# Multiple tags detected (collision)
# hf14ainfo.so → hasKeyword("Multiple tags detected") → CODE_TAG_MULT (-3)
# Ground truth: hf14ainfo_strings.txt line 593, scan.so CODE_TAG_MULT=-3
SCENARIO_RESPONSES = {
    'hf 14a info': (1, '''
[!] Multiple tags detected. Collision after bit 32
[!] Multiple tags detected
'''),
}
DEFAULT_RETURN = 1
