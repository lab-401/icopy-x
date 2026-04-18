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

"""Audio playback and volume control.

OSS reimplementation of audio.so, post-asset-swap revision.

Two layers:

  1) System sounds — five short .ogg files in res/audio/ wired into
     the standard UI events (list navigation, button click, startup,
     shutdown, toast).  Each event has a thin helper here; call
     sites in keymap.py / hmi_driver.py / application.py / widget.py
     invoke the helpers.

  2) Generic playback — play(name) / playOfVolume(name, v) for any
     other asset.  The legacy named-event stubs (playTagfound,
     playSniffStep1, etc.) are retained as no-ops for source
     compatibility with code that still calls them; they no longer
     attempt to look up the old numbered .wav corpus that was
     removed.

Playback path: pygame.mixer.Sound (decodes WAV + OGG via SDL_mixer
— mp3 is NOT supported by Sound, only by the single-stream
mixer.music API, so all assets are .ogg) → no-op log when pygame
unavailable (QEMU / no sound HW).

DRM note: The original audio.so contained DRM license checks.
Per project rules, DRM gate functions are replaced with pass-throughs.
"""

import logging
import os
import subprocess

logger = logging.getLogger(__name__)

# Module state
# _volume_pct holds the ALSA percentage (0/30/65/100) — written by
# setVolume() and read by play() as the per-Sound playback volume.
# Default 65 = level 2 (Middle).
_volume_pct = 65
_key_audio_enabled = True
_initialized = False
_mixer_available = False  # True if pygame.mixer initialized successfully

# Hardware mixer controls to try, in order.  This device exposes only
# 'Line Out' (the dev cable provides a 3.5mm jack pre-amped through
# the wm8960); the device-tree variant on other H3 boards uses
# 'Speaker'.  We sset whichever one exists — silent on miss.
_AMIXER_CONTROLS = ('Line Out', 'Speaker')

# Audio file base path (real device).  Falls back to a relative path
# resolved against the lib's parent directory if the device path is
# absent (development / QEMU runs from the source tree).
_AUDIO_BASE = '/home/pi/ipk_app_main/res/audio'
if not os.path.isdir(_AUDIO_BASE):
    _AUDIO_BASE = os.path.normpath(
        os.path.join(os.path.dirname(__file__), '..', '..', 'res', 'audio'))

# Named system sounds (post-asset-swap).  Volume preview reuses the
# toast tone because the new asset set has no dedicated calibration
# tone — toast is short, distinct, and at a comfortable level.
_SOUND_NAV_TAP        = 'navigate_tap.ogg'
_SOUND_NAV_CLICK      = 'navigate_click.ogg'
_SOUND_SYSTEM_START   = 'system_start.ogg'
_SOUND_SYSTEM_SHUTDOWN = 'system_shutdown.ogg'
_SOUND_SYSTEM_TOAST   = 'system_toast.ogg'
_VOLUME_EXAM_FILE     = _SOUND_SYSTEM_TOAST


# =====================================================================
# Init / volume control
# =====================================================================

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
    """Apply system-wide volume.

    Args:
        v: int ALSA volume percentage (0/30/65/100) — caller already
           converted from UI level via settings.fromLevelGetVolume().

    Three side-effects, all best-effort:
      1. Cache `v` so future per-Sound playback scales correctly.
      2. Push to the ALSA hardware mixer so non-pygame audio (and
         the rest of pygame's session output level) follows.
      3. Re-set the looping music channel if a track is currently
         playing — pygame.mixer.music.set_volume() takes effect
         immediately and is the only way the running scroller hears
         the change.
    """
    global _volume_pct
    _volume_pct = max(0, min(100, int(v)))
    pct = '%d%%' % _volume_pct
    for control in _AMIXER_CONTROLS:
        try:
            r = subprocess.run(
                ['amixer', 'sset', control, pct],
                capture_output=True, timeout=5,
            )
            if r.returncode == 0:
                logger.debug("audio.setVolume(%s) -> amixer %s %s",
                             v, control, pct)
                break
        except FileNotFoundError:
            logger.debug("audio.setVolume(%s) — amixer not found (QEMU)", v)
            break
        except Exception as e:
            logger.debug("audio.setVolume(%s) — amixer %s error: %s",
                         v, control, e)
    if _mixer_available:
        try:
            import pygame
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.set_volume(_volume_pct / 100.0)
        except Exception:
            pass


def setKeyAudioEnable(enable):
    """Enable or disable key press click sounds.

    Ground truth: VolumeActivity sets False when level=0 (Off),
    True for all other levels.
    """
    global _key_audio_enabled
    _key_audio_enabled = bool(enable)
    logger.debug("audio.setKeyAudioEnable(%s)", enable)


def get_framerate(name):
    """Get framerate of named audio file.  Default 44100 (CD quality)."""
    return 44100


# =====================================================================
# Generic playback (used by the named system-sound helpers below)
# =====================================================================

def play(name):
    """Play named audio file at current volume."""
    vol = _volume_pct
    playOfVolumeImpl(name, vol)


def playOfVolume(name, volume):
    """Play named audio file at specified volume (0-100)."""
    playOfVolumeImpl(name, volume)


def playOfVolumeImpl(n, v):
    """Internal implementation of named-asset playback.

    pygame.mixer.Sound is the only path; it decodes WAV + OGG via
    SDL_mixer.  When pygame is unavailable (QEMU) the call
    gracefully no-ops.
    """
    wav = os.path.join(_AUDIO_BASE, n) if not os.path.isabs(n) else n
    if not os.path.exists(wav):
        logger.debug("audio.playOfVolumeImpl(%s) — file not found: %s", n, wav)
        return
    if not _mixer_available:
        logger.debug("audio.playOfVolumeImpl(%s) — no mixer", n)
        return
    try:
        import pygame
        snd = pygame.mixer.Sound(wav)
        snd.set_volume(max(0.0, min(1.0, v / 100.0)))
        snd.play()
    except Exception as e:
        logger.debug("audio.playOfVolumeImpl(%s) — pygame error: %s", n, e)


def playVolumeExam(v=100, chk=False):
    """Play volume preview/calibration tone.

    Used by VolumeActivity on UP/DOWN to preview the new volume.
    Plays the system-toast tone at the explicit volume `v` (overrides
    the global level so the user hears what the proposed level sounds
    like before committing).
    """
    logger.debug("audio.playVolumeExam(v=%s, chk=%s)", v, chk)
    playOfVolumeImpl(_VOLUME_EXAM_FILE, v)


# =====================================================================
# Named system sounds — wired to UI events
# =====================================================================

def playNavTap():
    """List navigation tap (UP/DOWN keys).  Wired in keymap.py."""
    if not _key_audio_enabled:
        return
    play(_SOUND_NAV_TAP)


def playNavClick():
    """Mapped-button click (OK/M1/M2 after the actbase active gate).
    Wired in keymap.py."""
    if not _key_audio_enabled:
        return
    play(_SOUND_NAV_CLICK)


def playSystemStart():
    """UI startup sound.  Wired in application.startApp() after the
    Tk root is created and audio.init() has run."""
    play(_SOUND_SYSTEM_START)


def playSystemShutdown():
    """Shutdown sound.  Wired in hmi_driver when GD32 sends the
    'shutdown' command (PWR long-press), played BEFORE the
    'shutdowning' ack so the user hears it while the screen still
    holds.  Synchronous-blocking play would race the shutdown; we
    fire-and-forget like every other sound."""
    play(_SOUND_SYSTEM_SHUTDOWN)


def playSystemToast():
    """Toast overlay fires.  Wired in widget.Toast.show()."""
    play(_SOUND_SYSTEM_TOAST)


# =====================================================================
# Legacy named-stub compatibility
# =====================================================================
# The original audio.so exposed ~31 named event functions whose .wav
# mappings lived in the closed-source binary.  Call sites still
# reference these names (actbase.playKeyEnable/Disable, batteryui.
# playChargingAudio, activity_tools.playStartExma, activity_main.
# playTagfound/playTagNotfound, etc.).  We retain the names as
# no-ops so those call sites keep working without churn.  When a
# given event acquires a real asset assignment, route it here.

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


# =====================================================================
# Scroller music (looped .ogg playback) — used by AboutActivity
# =====================================================================
# pygame.mixer.music is the single-stream music API and shares the
# audio device with pygame.mixer.Sound (both go through SDL_mixer's
# already-open ALSA handle), so we avoid the "device busy" contention
# that an external player like xmp hits on this device.  A pre-rendered
# scroller.ogg lives in res/audio/ — playback is a one-liner.


def startScrollerMusic(ogg_path):
    """Start looping background music for the About scroller easter
    egg.  No-op if pygame mixer is unavailable or the file is missing."""
    if not _mixer_available:
        logger.debug("startScrollerMusic — no mixer")
        return
    if not os.path.isfile(ogg_path):
        logger.debug("startScrollerMusic — missing: %s", ogg_path)
        return
    try:
        import pygame
        vol = _volume_pct
        pygame.mixer.music.load(ogg_path)
        pygame.mixer.music.set_volume(max(0.0, min(1.0, vol / 100.0)))
        pygame.mixer.music.play(loops=-1)
    except Exception as e:
        logger.debug("startScrollerMusic — pygame error: %s", e)


def stopScrollerMusic():
    """Stop the scroller music.  Safe to call when nothing is playing."""
    if not _mixer_available:
        return
    try:
        import pygame
        pygame.mixer.music.stop()
    except Exception as e:
        logger.debug("stopScrollerMusic — pygame error: %s", e)
