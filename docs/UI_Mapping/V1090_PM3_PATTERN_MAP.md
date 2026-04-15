# v1.0.90 PM3 Output Pattern Map

Extracted directly from compiled .so binaries (ground truth).
Every regex and keyword comparison the firmware uses to parse PM3 output.

## hf14ainfo.so — HF 14443-A Tag Identification

### Regex patterns (applied to `hf 14a info` output):
```
.*UID:(.*)\n                     → Extract UID hex string
.*ATQA:(.*)\n                    → Extract ATQA hex string
.*SAK:(.*)\[.*\n                 → Extract SAK hex string
.*Prng detection: (.*)\n         → Extract PRNG type ("weak"/"hard")
.*ATS:(.*)                       → Extract ATS hex string
.*MANUFACTURER:(.*)              → Extract manufacturer string
```

### Keyword checks (hasKeyword):
```
Multiple tags detected            → return {found:True, hasMulti:True}
Card doesn't support standard iso14443-3 anticollision → return {found:False}
BCC0 incorrect                    → return {found:True, bbcErr:True}
MIFARE Ultralight                 → return {found:True, isUL:True}
NTAG                              → return {found:True, isUL:True}
MIFARE DESFire                    → type=39 (if no Classic 1K/4K)
MIFARE Mini                       → type=25
MIFARE Classic 4K                 → type=0 (4B) or 41 (7B)
MIFARE Plus 4K                    → type=0 (4B) or 41 (7B)
MIFARE Classic 1K                 → type=1 (4B) or 42 (7B)
MIFARE Classic                    → type=43 (4B) or 44 (7B) [bare, with PRNG]
MIFARE Plus                       → type=43 (4B) or 44 (7B) [bare, with PRNG]
Static nonce: yes                 → static nonce flag
Prng detection                    → PRNG present flag
Magic capabilities : Gen 1a       → gen1a magic card
Magic capabilities : Gen 2 / CUID → gen2 magic card
```

## hfsearch.so — HF Tag Search

### Keyword checks (applied to `hf sea` output):
```
No known/supported 13.56 MHz tags found → return {found:False}
Valid iCLASS tag                  → return {found:True, isIclass:True}
Valid ISO15693                    → type=19 or 46
Valid LEGIC Prime                 → type=20
Valid ISO14443-B                  → type=22
MIFARE                            → return {found:True, isMifare:True}
Valid Topaz                       → type=27
ST Microelectronics SA France     → type=46 (ISO15693_ST_SA)
```

### Regex patterns:
```
.*UID.*:(.*)                      → Extract UID for ISO15693
.*UID:\s(.*)                      → Extract UID
.*MCD:\s(.*)                      → Extract MCD for LEGIC
.*MSN:\s(.*)                      → Extract MSN for LEGIC
.*ATQA.*:(.*)                     → Extract ATQA for Topaz
.*ATQB.*:(.*)                     → Extract ATQB for ISO14443-B
```

## lfsearch.so — LF Tag Search

### Keyword checks (applied to `lf sea` output):
```
No data found!                    → return {found:False}
No known 125/134 kHz tags found!  → return {found:True, isT55XX:True}
Valid EM410x ID                   → type=8
Valid HID Prox ID                 → type=9
Valid AWID ID                     → type=11
Valid IO Prox ID                  → type=12
Valid Indala ID                   → type=10
Valid Viking ID                   → type=15
Valid Pyramid ID                  → type=16
Valid Jablotron ID                → type=30
Valid NEDAP ID                    → type=32
Valid Guardall G-Prox II ID       → type=13
Valid FDX-B ID                    → type=28
Valid Securakey ID                → type=14
Valid KERI ID                     → type=31
Valid PAC/Stanley ID              → type=34
Valid Paradox ID                  → type=35
Valid NexWatch ID                 → type=45
Valid Visa2000 ID                 → type=37
Valid GALLAGHER ID                → type=29
Valid Noralsy ID                  → type=33
Valid Presco ID                   → type=36
Valid Hitag                       → type=38
Chipset detection                 → chipset info
Chipset detection: EM4x05 / EM4x69 → EM4x05 chipset
```

### Regex patterns:
```
EM TAG ID\s+:[\s]+([xX0-9a-fA-F]+)    → EM410x ID
HID Prox - ([xX0-9a-fA-F]+)           → HID raw data
(?:Card|ID|id|CARD|ID|UID|uid|Uid)\s*:*\s*([xX0-9a-fA-F ]+)  → Generic UID
.*(?:Raw|Raw|RAW|hex|HEX|Hex)\s*:*\s*([xX0-9a-fA-F ]+)       → Raw data
(XSF\(.*?\).*?:[xX0-9a-fA-F]+)        → IO Prox XSF format
FC:*\s+([xX0-9a-fA-F]+)               → Facility Code
(CN|Card|Card ID):*\s+(\d+)           → Card Number
(len|Len|LEN|format|Format):*\s+(\d+) → Data length
customer code:*\s+(\d+)               → Customer code
subtype:*\s+(\d+)                      → Subtype
.*ID\s+([xX0-9A-Fa-f\-]{2,})          → Generic ID
Chipset detection:\s(.*)               → Chipset name
```

## hfmfkeys.so — MIFARE Classic Key Recovery

### Regex patterns (applied to `hf mf fchk` output):
```
\|\s+Sec\s+\|\s+([0-9a-fA-F-]{12})\s+\|\s+(\d)\s+\|\s+([0-9a-fA-F-]{12})\s+\|\s+(\d)\s+\|
→ Parse key table: sector | keyA | resultA | keyB | resultB
→ Result '1' = key found, '0' = not found
```

### Keyword/regex (applied to `hf mf darkside` output):
```
found valid key                   → darkside attack succeeded
found valid key.*([a-zA-Z0-9]{12}).* → Extract found key (12 hex chars)
Can't select card \(ALL\)        → card selection failed
```

### Regex (applied to `hf mf nested` output):
```
found valid key.*([a-zA-Z0-9]{12}).* → Extract recovered key
.*worst case {2}([0-9\\.]+) seconds.* → Extract time estimate
```

### Regex (applied to `hf mf fchk` key extraction):
```
([a-fA-F0-9]{12})                → 12-char hex key
.*([a-fA-F0-9]{12}).*            → Key anywhere in line
[a-fA-F0-9]{12}                  → Key pattern match
```

## hfmfread.so — MIFARE Classic Data Read

### Regex (applied to `hf mf rdsc` output):
```
\s\|\s([a-fA-F0-9\s]{47})        → Sector data (47-char hex block)
data:\s([a-fA-F0-9\s]{47})       → Alternate sector data format
```

## hfmfwrite.so — MIFARE Classic Write

### Keyword checks:
```
isOk:01                           → Block write success
Card loaded \d+ blocks from file  → Gen1a cload success (regex)
UID                               → UID-related operation
```

### Regex:
```
Serial\s*:\s*([a-fA-F0-9]+)      → Serial number extraction
Card loaded \d+ blocks from file  → cload result
```

## hfmfuread.so — Ultralight/NTAG Read

### Keyword check (applied to `hf mfu dump` output):
```
Partial dump created              → Partial success (some pages read)
```

## hfmfuwrite.so — Ultralight/NTAG Write

### Keyword check (applied to `hf mfu restore` output callback):
```
failed to write block             → Block write failure (checked in real-time callback)
```

## hf15write.so — ISO15693 Write

### Keyword checks (applied to `hf 15 restore` output):
```
Write OK                          → Write success
restore failed                    → Write failure
setting new UID \(ok\)            → UID write success (regex)
```

## hficlass.so — iCLASS Operations

### Regex patterns:
```
CSN:*\s([A-Fa-f0-9 ]+)           → Card Serial Number
Found valid key (.*)              → Key check result
 : ([a-fA-F0-9 ]+)               → Generic hex data
Serial\s*:\s*([a-fA-F0-9]+)      → Serial extraction
Bit#:([0-9]+)                     → Bit count
Bits#:([0-1]+)                    → Binary bits
Blk7#:([0-9a-fA-F]+)             → Block 7 data
FC#:([0-9]+)                      → Facility Code
Hex#:([0-9a-fA-F]+)              → Hex data
ID#:([0-9]+)                      → ID number
wiedata#:([0-1]+)                 → Wiegand data
```

## iclassread.so — iCLASS Read

### Keyword check (applied to `hf iclass dump` output):
```
saving dump file - 19 blocks read → Dump success (19 blocks for Legacy)
```

## iclasswrite.so — iCLASS Write

### Regex (applied to `hf iclass calcnewkey` output):
```
Xor div key : ([0-9A-Fa-f ]+)    → Calculated XOR diversified key
```

## lft55xx.so — T5577 Operations

### Regex patterns:
```
.*Block0.*:(.*)                   → Block0 config word
.*Chip Type.*:(.*)                → Chip type identification
.*Modulation.*:(.*)               → Modulation type
Block0         : 0x([A-Fa-f0-9]+) → Block0 hex value
[0-9]{2} \| ([A-Fa-f0-9 ]+) \|   → Dump table row data
Found valid password: \[([ a-fA-F0-9]+)\] → T5577 password found
Password       : ([A-Fa-f0-9 ]+) → Password value
loaded ([\d]+) keys               → Key file loaded count
([a-fA-F0-9]{8})                  → 8-char hex block data
[a-fA-F0-9]{8}                    → Block data pattern
```

### Keyword:
```
--------                          → T55xx unknown modulation marker
```

## lfem4x05.so — EM4x05 Operations

### Regex patterns:
```
.*Chip Type.*\|(.*)               → Chip type
.*ConfigWord:(.*)\(.*             → Config word
.*Serial.*:(.*)                   → Serial number
\| ([a-fA-F0-9]+) -              → Block data from dump table
```

## sniff.so — Sniff Operations

### Regex patterns (applied to sniff/trace output):
```
trace len = (\d+)                 → Trace length
Reading (\d+) bytes from device memory → Bytes being read
Default pwd write\s+\|\s+([A-Fa-f0-9]{8})\s\| → T5577 default password write
Default write\s+\|\s+([A-Fa-f0-9]{8})\s\|     → T5577 default write
Leading [0-9a-zA-Z]* pwd write\s+\|\s+([A-Fa-f0-9]{8})\s\| → Leading password write
key\s+([A-Fa-f0-9]+)             → Recovered key
\|\s*{}\s*\|\s*([a-fA-F0-9 !]+)\s*\|\s*{}\s*\|\s*{} → Trace table row
```

## executor.so — PM3 Communication

### Protocol markers:
```
Nikola.D.CMD = {}                 → Command request format
Nikola.D.CTL = {}                 → Control request format
Nikola.D.OFFLINE                  → PM3 offline marker
Nikola.D.PLT                      → Platform command marker
Nikola.D:                         → Response end marker (regex: Nikola\.D:\s*-?\d+)
pm3 -->                           → PM3 prompt (end of response)
[\S]+                             → Non-whitespace token match
```

## activity_main.so — UI Activity Layer

### Erase-specific:
```
\[.\]wipe block ([0-9]+)          → Wipe progress per block
Card wiped successfully            → Wipe complete
```
