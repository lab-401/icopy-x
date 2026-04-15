#!/usr/bin/env python3

##########################################################################
# Required Notice: Copyright ETOILE401 SAS (http://www.lab401.com)
#
# Copyright (c) 2026: ETOILE401 SAS & https://github.com/quantum-x/
#
# This software is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this software for commercial purposes.
#
# A copy of the license is available at:
# https://polyformproject.org/licenses/noncommercial/1.0.0
#
# This entire header "Required Notice" must remain in place.
##########################################################################

"""iCopy-X application entry point.

Verbatim reproduction of the original app.py from v1.0.90 firmware.
Source: docs/ORIGINAL_ANALYSIS.md Section 2 (Boot Sequence).

Boot chain:
    ipk_starter.py → app.py → main.main() → application.startApp()
"""
import sys

if __name__ == '__main__':
    sys.path.append("main")
    sys.path.append("lib")
    try:
        from main import main
        main.main()
    except Exception as e:
        print("\u542f\u52a8\u811a\u672c\u65e0\u6cd5\u542f\u52a8\u7a0b\u5e8f\uff0c\u51fa\u73b0\u5f02\u5e38: ", e)
        exit(44)
