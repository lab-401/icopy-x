# ioprx read success
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
[+] IO Prox - XSF(00)00:00273, Raw: 0078402010188ff7 (ok)

[+] Valid IO Prox ID found!

Couldn't identify a chipset
'''),
    'lf io read': (0, '''[usb] pm3 --> lf io read

[+] Valid IO Prox ID
[+] XSF(01)01:12345
[+] FC: 01, CN: 12345
[+] Raw: 007E0180A5
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 12
