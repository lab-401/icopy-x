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

# RFID middleware — Python reimplementations of Cython .so modules.
#
# Each module shadows its .so counterpart via sys.path priority:
#   src/middleware/ is inserted BEFORE the QEMU rootfs .so paths,
#   so `import erase` finds erase.py here first.
#
# Convention:
#   - Module name matches original .so name (e.g. write.py → import write)
#   - New modules (no .so counterpart) use descriptive names (e.g. erase.py)
#   - Each module calls executor.startPM3Task() for PM3 commands
#   - Modules do NOT touch UI (no canvas, no toast, no activity state)
#   - Modules return results; activities handle UI updates
