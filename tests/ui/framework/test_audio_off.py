import sys
from types import SimpleNamespace

import audio


class FakeSound:
    def __init__(self, path, played):
        self.played = played

    def set_volume(self, value):
        pass

    def play(self):
        self.played.append('sound')


class FakeMusic:
    def __init__(self, played):
        self.played = played

    def get_busy(self):
        return False

    def load(self, path):
        self.played.append('load')

    def set_volume(self, value):
        pass

    def play(self, loops):
        self.played.append('music')

    def stop(self):
        self.played.append('stop music')


def test_persisted_audio_off_blocks_all_application_playback(monkeypatch):
    played = []
    music = FakeMusic(played)
    mixer = SimpleNamespace(
        init=lambda: None,
        Sound=lambda path: FakeSound(path, played),
        music=music,
        stop=lambda: played.append('stop channels'),
    )
    monkeypatch.setitem(sys.modules, 'pygame', SimpleNamespace(mixer=mixer))
    monkeypatch.setattr(audio.os.path, 'exists', lambda path: True)
    monkeypatch.setattr(audio.os.path, 'isfile', lambda path: True)
    import settings
    monkeypatch.setattr(settings, 'getVolume', lambda: 0)
    audio.init()
    try:
        assert audio._volume_pct == 0
        assert not audio._key_audio_enabled
        audio.playNavTap()
        audio.playNavClick()
        audio.playSystemStart()
        audio.playSystemToast()
        audio.playSystemShutdown()
        audio.play('ready_1.wav')
        audio.playOfVolume('ready_1.wav', 100)
        audio.playVolumeExam(100)
        audio.startScrollerMusic('scroller.ogg')
        assert played == []
    finally:
        audio._volume_pct = 65
        audio._key_audio_enabled = True
        audio._mixer_available = False


def test_enabled_audio_plays_and_turning_off_stops_current_sound(monkeypatch):
    played = []
    mixer = SimpleNamespace(
        Sound=lambda path: FakeSound(path, played),
        music=FakeMusic(played),
        stop=lambda: played.append('stop channels'),
    )
    monkeypatch.setitem(sys.modules, 'pygame', SimpleNamespace(mixer=mixer))
    monkeypatch.setattr(audio.os.path, 'exists', lambda path: True)
    monkeypatch.setattr(audio.subprocess, 'run', lambda *args, **kwargs: SimpleNamespace(returncode=0))
    audio._mixer_available = True
    audio._volume_pct = 65
    audio._key_audio_enabled = True
    try:
        audio.playSystemToast()
        assert played == ['sound']
        audio.setVolume(0)
        audio.setKeyAudioEnable(False)
        audio.playSystemToast()
        assert played == ['sound', 'stop channels', 'stop music']
    finally:
        audio._volume_pct = 65
        audio._key_audio_enabled = True
        audio._mixer_available = False
