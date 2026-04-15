# fdxb read success
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
[+] FDX-B / ISO 11784/5 Animal
[+] Animal ID          0060-030207938416
[+] National Code      030207938416 (0x708888F70)
[+] Country Code       0060
[+] Reserved/RFU       14339 (0x3803)
[+]   Animal bit set?  True
[+]       Data block?  True  [value 0x800000]
[+] CRC-16             0xCE2B (ok)
[+] Raw                0E F1 11 10 E0 F0 E0 0F 

[+] Valid FDX-B ID found!

Couldn't identify a chipset
'''),
    'lf fdx read': (0, '''[usb] pm3 --> lf fdx read

[+] Valid FDX-B ID found!
[+] Animal ID          999-000012345678
[+] FDXB - Raw: 0103E820C00103E820C0
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 28
