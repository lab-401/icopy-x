# LUA Script hf_read — no card present, iso14443a card select failed
# Source: real device trace session 1 (20260330)
# PM3 command: script run hf_read (via startPM3Task, timeout=-1)
# Script runs, attempts 3 read strategies, all fail with no card
SCENARIO_RESPONSES = {
    'script run': (1, '''
[+] executing lua /mnt/upan/luascripts/hf_read.lua
[+] args ''
WORK IN PROGRESS - not expected to be functional yet
Waiting for card... press Enter to quit
Reading with
1
iso14443a card select failed
Reading with
2
No response from card
No response from card
Reading with
3
CRC
CRC failed
CRC failed
'''),
}
DEFAULT_RETURN = 1
