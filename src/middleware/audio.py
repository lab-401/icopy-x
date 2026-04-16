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

"""Audio playback and volume control.

OSS reimplementation of audio.so.
Binary source: audio.so (Cython, pygame + subprocess)
Ground truth: V1090_MODULE_AUDIT.txt lines 913-961

The original module uses pygame.mixer for audio playback and
subprocess calls to amixer for system volume control.
On real hardware, amixer controls ALSA Speaker volume.
In QEMU/test mode, audio functions gracefully no-op (no sound hardware).

DRM note: The original audio.so contains DRM license checks.
Per project rules, DRM gate functions are replaced with pass-throughs.
"""

import logging
import os
import subprocess

logger = logging.getLogger(__name__)

# Module state
_volume_level = 2       # 0=Off, 1=Low, 2=Middle, 3=High
_key_audio_enabled = True
_initialized = False
_mixer_available = False  # True if pygame.mixer initialized successfully

# Volume percentage map: UI level -> ALSA percentage string
# Ground truth: settings.fromLevelGetVolume() returns 0/30/65/100
_VOLUME_PCT = {0: '0%', 1: '30%', 2: '65%', 3: '100%'}

# Audio file base path (real device)
_AUDIO_BASE = '/home/pi/ipk_app_main/res/audio'

# Volume preview file — audio.so uses res/audio/11.4.wav
# (string literal found in audio_strings.txt line 1670)
_VOLUME_EXAM_FILE = '11.4.wav'


def _has_command(cmd):
    """Check if a system command exists on PATH."""
    try:
        subprocess.run(['which', cmd], capture_output=True, timeout=2)
        return True
    except Exception:
        return False


def init():
    """Initialize audio subsystem.

    Original: pygame.mixer.init() + load sound files.
    Gracefully no-ops if pygame or sound hardware is unavailable (QEMU).
    """
    global _initialized, _mixer_available
    _initialized = True
    try:
        import pygame
        pygame.mixer.init()
        _mixer_available = True
        logger.debug("audio.init() — pygame.mixer initialized")
    except Exception as e:
        _mixer_available = False
        logger.debug("audio.init() — no mixer: %s", e)


def setVolume(v):
    """Set system volume via ALSA amixer.

    Ground truth (trace_original_backlight_volume_20260410.txt):
    audio.setVolume receives the ALSA percentage directly (0/20/50/100),
    NOT the UI level index. The caller (VolumeActivity) converts via
    settings.fromLevelGetVolume() before calling.

    Args:
        v: int ALSA volume percentage (0, 20, 50, 100)
    """
    global _volume_level
    _volume_level = v
    pct = '%d%%' % int(v)
    try:
        subprocess.run(
            ['amixer', 'sset', 'Speaker', pct],
            capture_output=True, timeout=5,
        )
        logger.debug("audio.setVolume(%s) -> amixer Speaker %s", v, pct)
    except FileNotFoundError:
        logger.debug("audio.setVolume(%s) — amixer not found (QEMU)", v)
    except Exception as e:
        logger.debug("audio.setVolume(%s) — amixer error: %s", v, e)


def playVolumeExam(v=100, chk=False):
    """Play volume preview/calibration tone.

    Original: plays res/audio/11.4.wav at current volume via pygame.mixer.
    Falls back to aplay if pygame unavailable, no-ops if neither works.

    Args:
        v: volume percentage (default 100)
        chk: check DRM license (pass-through, always succeeds)
    """
    logger.debug("audio.playVolumeExam(v=%s, chk=%s)", v, chk)
    wav = os.path.join(_AUDIO_BASE, _VOLUME_EXAM_FILE)
    if not os.path.exists(wav):
        logger.debug("playVolumeExam — wav not found: %s", wav)
        return
    # Try pygame.mixer first (matches original .so)
    if _mixer_available:
        try:
            import pygame
            pygame.mixer.music.load(wav)
            pygame.mixer.music.set_volume(v / 100.0)
            pygame.mixer.music.play()
            return
        except Exception as e:
            logger.debug("playVolumeExam — pygame error: %s", e)
    # Fallback: aplay (non-blocking)
    try:
        subprocess.Popen(
            ['aplay', '-q', wav],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        logger.debug("playVolumeExam — aplay not found (QEMU)")
    except Exception as e:
        logger.debug("playVolumeExam — aplay error: %s", e)


def setKeyAudioEnable(enable):
    """Enable or disable key press click sounds.

    Ground truth: VolumeActivity sets False when level=0 (Off),
    True for all other levels.

    Args:
        enable: bool — True to enable key click sounds
    """
    global _key_audio_enabled
    _key_audio_enabled = bool(enable)
    logger.debug("audio.setKeyAudioEnable(%s)", enable)


def playOfVolume(name, volume):
    """Play named audio file at specified volume.

    Args:
        name: audio file name (e.g. '11.4.wav')
        volume: playback volume (0-100)
    """
    logger.debug("audio.playOfVolume(%s, %s)", name, volume)
    playOfVolumeImpl(name, volume)


def playOfVolumeImpl(n, v):
    """Internal implementation of volume playback.

    Tries pygame.mixer first, falls back to aplay.
    """
    logger.debug("audio.playOfVolumeImpl(%s, %s)", n, v)
    wav = os.path.join(_AUDIO_BASE, n) if not os.path.isabs(n) else n
    if not os.path.exists(wav):
        return
    if _mixer_available:
        try:
            import pygame
            snd = pygame.mixer.Sound(wav)
            snd.set_volume(v / 100.0)
            snd.play()
            return
        except Exception as e:
            logger.debug("playOfVolumeImpl — pygame error: %s", e)
    try:
        subprocess.Popen(
            ['aplay', '-q', wav],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def play(name):
    """Play named audio file at current volume."""
    logger.debug("audio.play(%s)", name)
    # Map volume level to percentage for playback
    pct_map = {0: 0, 1: 30, 2: 65, 3: 100}
    vol = pct_map.get(_volume_level, 65)
    playOfVolumeImpl(name, vol)


def get_framerate(name):
    """Get framerate of named audio file.

    Returns:
        int: framerate (default 44100)
    """
    return 44100


# === Sound effect functions (all no-ops in QEMU) ===
# Ground truth: V1090_MODULE_AUDIT.txt lines 920-953

def playCancel(chk=False): logger.debug("audio.playCancel()")
def playChargingAudio(chk=False): logger.debug("audio.playChargingAudio()")
def playKeyDisable(chk=False): logger.debug("audio.playKeyDisable()")
def playKeyEnable(chk=False): logger.debug("audio.playKeyEnable()")
def playMissingKey(chk=False): logger.debug("audio.playMissingKey()")
def playMultiCard(chk=False): logger.debug("audio.playMultiCard()")
def playNoValidKeyHF(chk=False): logger.debug("audio.playNoValidKeyHF()")
def playNoValidKeyLF(chk=False): logger.debug("audio.playNoValidKeyLF()")
def playPCModeRunning(chk=False): logger.debug("audio.playPCModeRunning()")
def playProcessing(chk=False): logger.debug("audio.playProcessing()")
def playReadAll(chk=False): logger.debug("audio.playReadAll()")
def playReadFail(chk=False): logger.debug("audio.playReadFail()")
def playReadPart(chk=False): logger.debug("audio.playReadPart()")
def playReading1p32(chk=False): logger.debug("audio.playReading1p32()")
def playReadingKeys(chk=False): logger.debug("audio.playReadingKeys()")
def playResultOnRight(chk=False): logger.debug("audio.playResultOnRight()")
def playResultOnWrong(chk=False): logger.debug("audio.playResultOnWrong()")
def playScanning(chk=False): logger.debug("audio.playScanning()")
def playSimulating(chk=False): logger.debug("audio.playSimulating()")
def playSniffStep1(chk=False): logger.debug("audio.playSniffStep1()")
def playSniffStep2(chk=False): logger.debug("audio.playSniffStep2()")
def playSniffStep3(chk=False): logger.debug("audio.playSniffStep3()")
def playSniffStep4(chk=False): logger.debug("audio.playSniffStep4()")
def playSniffing(chk=False): logger.debug("audio.playSniffing()")
def playStartExma(chk=False, force=False): logger.debug("audio.playStartExma()")
def playTagNotfound(chk=False): logger.debug("audio.playTagNotfound()")
def playTagfound(chk=False): logger.debug("audio.playTagfound()")
def playTraceFileSaved(chk=False): logger.debug("audio.playTraceFileSaved()")
def playVerifiFail(chk=False): logger.debug("audio.playVerifiFail()")
def playVerifiSuccess(chk=False): logger.debug("audio.playVerifiSuccess()")
def playVerifying(chk=False): logger.debug("audio.playVerifying()")
