#!/usr/bin/env python3

##########################################################################
# Required Notice: Copyright ETOILE401 SAS (http://www.lab401.com)
#
# Initial author: ETOILE401 SAS & https://github.com/quantum-x/ as of April 16, 2026
#
# Since this date, each contribution is under the copyright of its respective author.
#
# Copyright of each contribution is tracked by the Git history. See the output of git shortlog -nse for a full list or git log --pretty=short --follow <path/to/sourcefile> |git shortlog -ne to track a specific file.
#
# A mailmap is maintained to map author and committer names and email addresses to canonical names and email addresses.
# If by accident a copyright was removed from a file and is not directly deducible from the Git history, please submit a PR.
#
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
