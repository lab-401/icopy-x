# Erase MF Classic 1K Gen1a (magic) card via cwipe — success
# Source: trace_erase_flow_20260330.txt lines 6-15
# Gen1a detected via hf mf cgetblk 0 returning block data (isOk:01).
# Then hf mf cwipe wipes blocks 0-63. Post-verify confirms UID reset.
SCENARIO_RESPONSES = {
    'hf 14a info': (0, '''
[+]  UID: 42 EC BF B9
[+] ATQA: 00 04
[+]  SAK: 08 [2]
[+] Possible types:
[+]    MIFARE Classic 1K / Classic 1K CL2
[+] Magic capabilities : Gen 1a
[=] proprietary non iso14443-4 card found, RATS not supported
[+] Prng detection: weak
'''),
    'hf mf cgetblk': (0, '''[+] Block 0: 42ECBFB99C08040001020304050607
[+] isOk:01
'''),
    'hf mf cwipe': (0, '''
[|]wipe block 0[/]wipe block 1[-]wipe block 2[\\]wipe block 3[|]wipe block 4[/]wipe block 5[-]wipe block 6[\\]wipe block 7[|]wipe block 8[/]wipe block 9[-]wipe block 10[\\]wipe block 11[|]wipe block 12[/]wipe block 13[-]wipe block 14[\\]wipe block 15[|]wipe block 16[/]wipe block 17[-]wipe block 18[\\]wipe block 19[|]wipe block 20[/]wipe block 21[-]wipe block 22[\\]wipe block 23[|]wipe block 24[/]wipe block 25[-]wipe block 26[\\]wipe block 27[|]wipe block 28[/]wipe block 29[-]wipe block 30[\\]wipe block 31[|]wipe block 32[/]wipe block 33[-]wipe block 34[\\]wipe block 35[|]wipe block 36[/]wipe block 37[-]wipe block 38[\\]wipe block 39[|]wipe block 40[/]wipe block 41[-]wipe block 42[\\]wipe block 43[|]wipe block 44[/]wipe block 45[-]wipe block 46[\\]wipe block 47[|]wipe block 48[/]wipe block 49[-]wipe block 50[\\]wipe block 51[|]wipe block 52[/]wipe block 53[-]wipe block 54[\\]wipe block 55[|]wipe block 56[/]wipe block 57[-]wipe block 58[\\]wipe block 59[|]wipe block 60[/]wipe block 61[-]wipe block 62[\\]wipe block 63
Card wiped successfully
'''),
}
DEFAULT_RETURN = 1
