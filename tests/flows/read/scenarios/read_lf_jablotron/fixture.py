# jablotron read success
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
[+] Jablotron - Card: 7270a18, Raw: FFFF011999900079
[+] Printed: 1410-01-1999-9000

[+] Valid Jablotron ID found!

Couldn't identify a chipset
'''),
    'lf jablotron read': (0, '''[usb] pm3 --> lf jablotron read

[+] Jablotron - Card: FF010201234568, Raw: 1234567800112233
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 30
