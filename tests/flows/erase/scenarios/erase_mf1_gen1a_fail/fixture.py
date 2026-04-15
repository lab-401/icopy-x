# Erase MF Classic 1K Gen1a (magic) card via cwipe — failure
# Source: derived from .so binary analysis (cwipe returns -1 = timeout)
# Gen1a detected via hf mf cgetblk 0 returning block data (isOk:01).
# Then hf mf cwipe times out (-1).
SCENARIO_RESPONSES = {
    'hf 14a info': (0, '''
[+]  UID: 42 EC BF B9
[+] ATQA: 00 04
[+]  SAK: 08 [2]
[+] Possible types:
[+]    MIFARE Classic 1K / Classic 1K CL2
[+] Magic capabilities : Gen 1a
[=] proprietary non iso14443-4 card found, RATS not supported
[+] Prng detection: weak
'''),
    'hf mf cgetblk': (0, '''[+] Block 0: 42ECBFB99C08040001020304050607
[+] isOk:01
'''),
    'hf mf cwipe': (-1, ''),
}
DEFAULT_RETURN = 1
