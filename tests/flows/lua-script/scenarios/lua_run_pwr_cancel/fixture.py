# LUA Script PWR cancel — script response that will be interrupted by PWR
# Source: real device trace session 1 (20260330): PM3-CTRL> stop → ret=-1
# PM3_DELAY=10 ensures the mock sleeps long enough for PWR to cancel.
# If cancel reaches before mock returns, the task yields ret=-1.
# If mock returns first, the full output will be present and PWR dismisses the result.
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
[+] finished hf_read

'''),
}
DEFAULT_RETURN = 1
