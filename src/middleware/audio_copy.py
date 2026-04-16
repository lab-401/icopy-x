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

"""Audio copy notification — replaces audio_copy.so.

Exports:
    playReadyForCopy(chk=False, infos=None) — play audio cue when AutoCopy
        has finished reading and is ready to write.

Source: docs/V1090_MODULE_AUDIT.txt (lines 967-974),
        decompiled/audio_copy_ghidra_raw.txt (5040 lines),
        archive/lib_transliterated/audio_copy.py

String table (from Ghidra):
    playReadyForCopy, __audio_file_ext, __audio_dir, get_audio_typ,
    containermap, filesubid, contcons, audio, container, play

Dependencies: audio (play), container (get_audio_typ)

Call site: activity_main.py AutoCopyActivity._onReadComplete():
    audio_copy.playReadyForCopy()  # no args — defaults apply

Original Cython source path:
    C:\\Users\\ADMINI~1\\AppData\\Local\\Temp\\1\\tmpe2a5lml_\\audio_copy.py

Cython version: 0.29.23
"""

import logging

logger = logging.getLogger(__name__)

try:
    import audio
except ImportError:
    audio = None

try:
    import container
except ImportError:
    container = None


def playReadyForCopy(chk=False, infos=None):
    """Play the 'ready to copy' audio cue based on tag container type.

    Looks up the container type for the given tag info and plays the
    corresponding audio file (ready_{audio_id}.wav).

    Args:
        chk: bool — DRM license check flag (ignored, DRM bypassed).
        infos: dict with 'type' key containing tag type ID, or None.

    If infos is None or audio/container modules are unavailable, this
    is a silent no-op.  All exceptions are caught and suppressed
    (matching the original .so behaviour and the try/except at the
    call site in AutoCopyActivity).
    """
    if audio is None or container is None:
        return
    if infos is None:
        return

    try:
        container_info = container.get_audio_typ(infos)
        if container_info is not None:
            audio_id = container_info[2]
            if audio_id is not None:
                audio.play('ready_%s.wav' % audio_id)
    except Exception:
        pass
