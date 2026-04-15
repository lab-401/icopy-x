# Write scenario: write_em4305_dump_success
# EM4305 (type 24): write_dump_em4x05 writes 16 blocks, then reads back to verify.
# The verify uses getContentFromRegexG('\\| ([a-fA-F0-9]+) -', 1) on each read response.
# Data must match generate_write_dump.py output:
#   Block 0: 600150E0, Blocks 1-13: 000000XX, Block 14: AABBCCDD, Block 15: 00000000
SCENARIO_RESPONSES = {
    'hf 14a info': (1, '''
'''),
    'lf sea': (1, '''
[=] NOTE: some demods output possible binary
[=] if it finds something that looks like a tag
[=] False Positives ARE possible
[=] 
[=] Checking for known tags...
[=] 
[+] EM410x pattern found

EM TAG ID      : 1111000000

Possible de-scramble patterns

Unique TAG ID  : 8888000000
HoneyWell IdentKey {
DEZ 8          : 00000000
DEZ 10         : 0285212672
DEZ 5.5        : 04352.00000
DEZ 3.5A       : 017.00000
DEZ 3.5B       : 017.00000
DEZ 3.5C       : 000.00000
DEZ 14/IK2     : 00073299656704
DEZ 15/IK3     : 000586397253632
DEZ 20/ZK      : 08080808000000000000
}
Other          : 00000_000_00000000
Pattern Paxton : 286539264 [0x11143E00]
Pattern 1      : 0 [0x0]
Pattern Sebury : 0 0 0  [0x0 0x0 0x0]

[+] Valid EM410x ID found!

Couldn't identify a chipset
'''),
    'lf em 4x05_write': (0, '''[usb] pm3 --> lf em 4x05_write

[+] Success writing to tag
'''),
    'lf em 4x05_info': (0, '''Chip Type  | EM4x05/EM4x69
ConfigWord: 600150E0 (xx)
Serial : AABBCCDD
'''),
    'lf em 4x05_dump': (0, '''[usb] pm3 --> lf em 4x05_dump

[+] saved 64 bytes to binary file
'''),
    # Verify readback: must match what the .so actually wrote (from dump created by mock).
    # Mock dump handler creates: block 0 = serial (AABBCCDD), blocks 1-15 = 00000000.
    # The .so writes these values then reads back to verify.
    'lf em 4x05_read': [
        (0, 'Block  0 | AABBCCDD - r/w\n'),
        (0, 'Block  1 | 00000000 - r/w\n'),
        (0, 'Block  2 | 00000000 - r/w\n'),
        (0, 'Block  3 | 00000000 - r/w\n'),
        (0, 'Block  4 | 00000000 - r/w\n'),
        (0, 'Block  5 | 00000000 - r/w\n'),
        (0, 'Block  6 | 00000000 - r/w\n'),
        (0, 'Block  7 | 00000000 - r/w\n'),
        (0, 'Block  8 | 00000000 - r/w\n'),
        (0, 'Block  9 | 00000000 - r/w\n'),
        (0, 'Block 10 | 00000000 - r/w\n'),
        (0, 'Block 11 | 00000000 - r/w\n'),
        (0, 'Block 12 | 00000000 - r/w\n'),
        (0, 'Block 13 | 00000000 - r/w\n'),
        (0, 'Block 14 | 00000000 - r/w\n'),
        (0, 'Block 15 | 00000000 - r/w\n'),
    ],
}
DEFAULT_RETURN = 1
TAG_TYPE = 24
