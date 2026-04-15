# LUA Script console no-title — reuse hf_read success fixture
# Source: real device trace session 2 (20260330)
SCENARIO_RESPONSES = {
    'script run': (1, '''
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

[+] finished hf_read

'''),
}
DEFAULT_RETURN = 1
