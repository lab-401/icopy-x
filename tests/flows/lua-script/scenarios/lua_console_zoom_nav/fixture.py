# LUA Script console zoom + navigation test
# Extended output to ensure enough content for scroll testing.
# Needs: >30 lines (vertical scroll) + >40 char lines (horizontal scroll)
# Source: based on real device trace session 2 (20260330) with extended output
SCENARIO_RESPONSES = {
    'script run': (1, '''[usb|script] pm3 --> script run hf_read
[+] executing lua /mnt/upan/luascripts/hf_read.lua
[+] args ''
WORK IN PROGRESS - not expected to be functional yet
Waiting for card... press Enter to quit
Reading with
1
Tag info
    ats : 00
    uid : 3AF73501
    data : :5
    manufacturer : Advanced Film Device Inc. Japan
    atqa : 0400
    sak : 8
    name : NXP MIFARE CLASSIC 1k | Plus 2k
Block 00 : 3A F7 35 01 27 08 04 00 62 63 64 65 66 67 68 69
Block 01 : 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
Block 02 : 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
Block 03 : FF FF FF FF FF FF FF 07 80 69 FF FF FF FF FF FF
Block 04 : 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
Block 05 : 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
Block 06 : 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
Block 07 : FF FF FF FF FF FF FF 07 80 69 FF FF FF FF FF FF
Block 08 : 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
Block 09 : 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
Block 10 : 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
Block 11 : FF FF FF FF FF FF FF 07 80 69 FF FF FF FF FF FF
Block 12 : 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
Block 13 : 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
Block 14 : 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
Block 15 : FF FF FF FF FF FF FF 07 80 69 FF FF FF FF FF FF
[+] finished hf_read

Nikola.D: 0
'''),
}
DEFAULT_RETURN = 1
