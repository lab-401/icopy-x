# 14A Sniff — real hf mf sniff format trace (UID 9b 30 52 81)
# Real trace data from user
# PM3 commands: hf 14a sniff + hf list mf
# trace_len=383, compact mf sniff output format (RDR/TAG indexed)
SCENARIO_RESPONSES = {
    'hf 14a sniff': (1, '\n'),
    'hf list mf': (1, '''[=] downloading tracelog data from device
[+] Recorded activity (trace len = 383 bytes)
[=] start = start of start frame end = end of frame. src = source of transfer
[=] ISO14443A - all times are in carrier periods (1/13.56MHz)

received trace len: 383 packages: 1

tag select uid:9b 30 52 81  atqa:0x0004 sak:0x08

RDR(0):60 03 6e 49
TAG(1):62 90 ba 99

RDR(2):57 98 b7 de d7 44 07 39
TAG(3):3d 53 7e 54

RDR(4):70 73 28 2a
TAG(5):cc b3 db b3 33 47 08 81 3c df 65 bd 6f 60 f7 07 3e 8d

RDR(6):df ac d5 43
TAG(7):60 04 9e d5 a8 4d 50 99 30 10 04 ad 36 05 6c 40 b3 7f

RDR(8):02 64 b9 fa
TAG(9):b6 3b d2 fb

RDR(10):b5 02 67 75 3f d6 63 45
TAG(11):b8 af c4 e0

RDR(12):fc a2 f3 d0
TAG(13):f9 01 ac 8e 5c 43 18 36 a1 3c f0 92 8c bb 80 d0 f4 18

RDR(14):48 b8 78 05
TAG(15):8f 3c 91 cf 24 c8 59 26 eb 5d af f8 e2 9f da ae 68 70

RDR(16):94 41 8d 76
TAG(17):d8 54 9f 3a 1e cd 92 9b d4 90 ea 97 4b 12 c1 42 f1 11

tag select uid:9b 30 52 81  atqa:0x0004 sak:0x08

RDR(18):50 00 57 cd
'''),
}
DEFAULT_RETURN = 1
