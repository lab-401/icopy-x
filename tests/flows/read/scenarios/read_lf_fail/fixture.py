# LF EM410x: scan finds tag, but read command times out → "Read Failed!"
SCENARIO_RESPONSES = {
    'hf 14a info': (1, '''
'''),
    'lf sea': (0, '''[usb] pm3 --> lf search

[=] NOTE: some demods output possible binary
[=] if it finds something that looks like a tag
[=] False Positives ARE possible
[=]
[=] Checking for known tags...
[=]

[+] EM410x pattern found

EM TAG ID      : 0F0368568B

Possible de-scramble patterns

Unique TAG ID  : F0C016A5D1
HoneyWell IdentKey {
DEZ 8          : 06903435
DEZ 10         : 0867656267
}
Other          : 22155_003_06903435
Pattern Paxton : 1642715 [0x190F8B]

[+] Valid EM410x ID found!
'''),
    # Read command times out — tag was detected but read fails
    'lf em 410x': (-1, ''''''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 8
