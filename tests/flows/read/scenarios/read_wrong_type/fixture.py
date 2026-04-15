# Read: user selects M1 1K but scan finds EM410x → wrong type → "No tag found Or Wrong type found!"
# The scan succeeds, but the detected type (EM410x=8) doesn't match selected type (M1 1K=1)
SCENARIO_RESPONSES = {
    'hf 14a info': (1, '''
'''),
    'hf sea': (0, '''[usb] pm3 --> hf search
[!] No known/supported 13.56 MHz tags found
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

[+] Valid EM410x ID found!
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 1
