# Write EM410x (LF T55xx-based) via write_id — success path.
# Seed file: EM410x-ID_0F0368568B_1.txt → bundle: {data: '0F0368568B', type: 8}
# PM3 commands (trace lines 61-83):
#   lf t55xx wipe p 20206666 → lf t55xx detect → lf em 410x_write <UID> 1 →
#   lf t55xx detect → lf t55xx write b 7 d 20206666 → lf t55xx write b 0 d 00148050 →
#   lf t55xx detect p 20206666 → lf sea → lf em 410x_read → lf sea → lf em 410x_read
# Ground truth: docs/Real_Hardware_Intel/trace_dump_files_em410x_t55xx_write_20260405.txt
# NOTE: write.so uses `lf em 410x_write` (NOT `_clone`).
#       Block 0 config written as 00148050 (password flag 0x10 set).
#       lf sea and lf em 410x_read each called TWICE (inline + explicit verify).
SCENARIO_RESPONSES = {
    'lf t55xx wipe': (1, '\n\n[=] Begin wiping T55x7 tag\n\n[=] Default configation block 000880E0\n[=] Writing page 0  block: 00  data: 0x000880E0 pwd: 0x20206666\n[=] Writing page 0  block: 01  data: 0x00000000 \n[=] Writing page 0  block: 02  data: 0x00000000 \n[=] Writing page 0  block: 03  data: 0x00000000 \n[=] Writing page 0  block: 04  data: 0x00000000 \n[=] Writing page 0  block: 05  data: 0x00000000 \n[=] Writing page 0  block: 06  data: 0x00000000 \n[=] Writing page 0  block: 07  data: 0x00000000 \n'),
    'lf t55xx detect p 20206666': (1, '\n[=]      Chip Type      : T55x7\n[=]      Modulation     : ASK\n[=]      Bit Rate       : 5 - RF/64\n[=]      Inverted       : No\n[=]      Offset         : 33\n[=]      Seq. Term.     : Yes\n[=]      Block0         : 0x00148050\n[=]      Downlink Mode  : default/fixed bit length\n[=]      Password Set   : Yes\n[=]      Password       : 20206666\n\n'),
    'lf t55xx detect': [
        # 1st: post-wipe — ASK/RF32, Block0=000880E0
        (1, '\n[=]      Chip Type      : T55x7\n[=]      Modulation     : ASK\n[=]      Bit Rate       : 2 - RF/32\n[=]      Inverted       : No\n[=]      Offset         : 33\n[=]      Seq. Term.     : Yes\n[=]      Block0         : 0x000880E0\n[=]      Downlink Mode  : default/fixed bit length\n[=]      Password Set   : No\n\n'),
        # 2nd: post-write — ASK/RF64, Block0=00148040
        (1, '\n[=]      Chip Type      : T55x7\n[=]      Modulation     : ASK\n[=]      Bit Rate       : 5 - RF/64\n[=]      Inverted       : No\n[=]      Offset         : 33\n[=]      Seq. Term.     : Yes\n[=]      Block0         : 0x00148040\n[=]      Downlink Mode  : default/fixed bit length\n[=]      Password Set   : No\n\n'),
    ],
    'lf em 410x_write': (1, '\n[+] Writing T55x7 tag with UID 0x0f0368568b (clock rate: 64)\n[#] Clock rate: 64\n[#] Tag T55x7 written with 0xff818003d23660b8\n\n[+] Done\n'),
    'lf t55xx write b 7': (1, '\n[=] Writing page 0  block: 07  data: 0x20206666 \n'),
    'lf t55xx write b 0': (1, '\n[=] Writing page 0  block: 00  data: 0x00148050 \n'),
    'lf em 410x_read': (1, '\n[+] EM410x pattern found\n\nEM TAG ID      : 0F0368568B\n\nPossible de-scramble patterns\n\nUnique TAG ID  : F000C6A1D1\nHoneyWell IdentKey {\nDEZ 8          : 06841995\nDEZ 10         : 0006841995\nDEZ 5.5        : 00872.22923\nDEZ 3.5A       : 003.22923\nDEZ 3.5B       : 104.22923\nDEZ 3.5C       : 872.22923\nDEZ 14/IK2     : 00064847116939\nDEZ 15/IK3     : 000065157422603\nDEZ 20/ZK      : 15000003060805080611\n}\nOther          : 22923_872_06841995\nPattern Paxton : 409387403 [0x1868568B]\nPattern 1      : 7034507 [0x6B568B]\nPattern Sebury : 22923 872 6841995  [0x598B 0x368 0x368568B]\n'),
    'lf sea': [
        # 1st call: inline verify after password-detect
        (1, '\n\n[=] NOTE: some demods output possible binary\n[=] if it finds something that looks like a tag\n[=] False Positives ARE possible\n[=] \n[=] Checking for known tags...\n[=] \n[+] EM410x pattern found\n\nEM TAG ID      : 0F0368568B\n\nPossible de-scramble patterns\n\nUnique TAG ID  : F000C6A1D1\nHoneyWell IdentKey {\nDEZ 8          : 06841995\nDEZ 10         : 0006841995\nDEZ 5.5        : 00872.22923\nDEZ 3.5A       : 003.22923\nDEZ 3.5B       : 104.22923\nDEZ 3.5C       : 872.22923\nDEZ 14/IK2     : 00064847116939\nDEZ 15/IK3     : 000065157422603\nDEZ 20/ZK      : 15000003060805080611\n}\nOther          : 22923_872_06841995\nPattern Paxton : 409387403 [0x1868568B]\nPattern 1      : 7034507 [0x6B568B]\nPattern Sebury : 22923 872 6841995  [0x598B 0x368 0x368568B]\n\n[+] Valid EM410x ID found!\n\n[+] Chipset detection: T55xx\n'),
        # 2nd call: explicit verify
        (1, '\n\n[=] NOTE: some demods output possible binary\n[=] if it finds something that looks like a tag\n[=] False Positives ARE possible\n[=] \n[=] Checking for known tags...\n[=] \n[+] EM410x pattern found\n\nEM TAG ID      : 0F0368568B\n\nPossible de-scramble patterns\n\nUnique TAG ID  : F000C6A1D1\nHoneyWell IdentKey {\nDEZ 8          : 06841995\nDEZ 10         : 0006841995\nDEZ 5.5        : 00872.22923\nDEZ 3.5A       : 003.22923\nDEZ 3.5B       : 104.22923\nDEZ 3.5C       : 872.22923\nDEZ 14/IK2     : 00064847116939\nDEZ 15/IK3     : 000065157422603\nDEZ 20/ZK      : 15000003060805080611\n}\nOther          : 22923_872_06841995\nPattern Paxton : 409387403 [0x1868568B]\nPattern 1      : 7034507 [0x6B568B]\nPattern Sebury : 22923 872 6841995  [0x598B 0x368 0x368568B]\n\n[+] Valid EM410x ID found!\n\n[+] Chipset detection: T55xx\n'),
    ],
}
DEFAULT_RETURN = 1
