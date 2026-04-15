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

"""DOOM Plugin -- launches doomgeneric as a subprocess.

This is a canvas_mode plugin: it renders directly to the X display
rather than using the JSON UI schema.  The CanvasModeActivity in
plugin_activity.py handles the subprocess launching and key
translation via the manifest.json key_map.

PWR always kills the process and returns to the main UI
(framework-enforced, non-overridable).

Binary assets required (not included in source control):
    doom   -- ARM doomgeneric binary (built for iCopy-X)
    doom1.wad -- DOOM Episode 1 shareware WAD
"""

import os
import json
import subprocess
import signal

_PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_manifest():
    """Load manifest.json from the plugin directory."""
    path = os.path.join(_PLUGIN_DIR, 'manifest.json')
    with open(path, 'r') as fh:
        return json.load(fh)


class DoomPlugin(object):
    """DOOM plugin lifecycle manager.

    For canvas_mode plugins, the CanvasModeActivity handles most of
    the lifecycle (subprocess launch, key translation, PWR exit).
    This class provides the start/stop/send_key interface that
    CanvasModeActivity delegates to.
    """

    def __init__(self, host=None, display=':99'):
        self.host = host
        self.manifest = _load_manifest()
        self.display = display
        self.process = None
        self.key_map = self.manifest.get('key_map', {})
        self._running = False

    def start(self):
        """Launch DOOM as a subprocess."""
        binary = os.path.join(_PLUGIN_DIR, self.manifest['binary'])
        args = self.manifest.get('args', [])

        if not os.path.isfile(binary):
            raise FileNotFoundError('DOOM binary not found: %s' % binary)

        wad = os.path.join(_PLUGIN_DIR, 'doom1.wad')
        if not os.path.isfile(wad):
            raise FileNotFoundError('doom1.wad not found: %s' % wad)

        # Build command -- run under QEMU for ARM binary
        cmd = ['qemu-arm-static', binary] + args

        env = os.environ.copy()
        env['DISPLAY'] = self.display
        env['QEMU_LD_PREFIX'] = '/mnt/sdcard/root2/root'
        env['QEMU_SET_ENV'] = (
            'LD_LIBRARY_PATH='
            '/mnt/sdcard/root2/root/usr/lib/arm-linux-gnueabihf:'
            '/mnt/sdcard/root2/root/lib/arm-linux-gnueabihf:'
            '/mnt/sdcard/root1/usr/lib/arm-linux-gnueabihf:'
            '/mnt/sdcard/root1/lib/arm-linux-gnueabihf'
        )

        self.process = subprocess.Popen(
            cmd,
            cwd=_PLUGIN_DIR,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._running = True
        print('[DOOM] Started PID=%d' % self.process.pid)

    def send_key(self, key_name):
        """Translate a device key name to an X11 keypress for DOOM.

        Args:
            key_name: device key ('UP', 'DOWN', 'LEFT', 'RIGHT',
                      'OK', 'M1', 'M2')
        """
        if not self._running or self.process is None:
            return

        x11_key = self.key_map.get(key_name)
        if x11_key:
            try:
                subprocess.Popen(
                    ['xdotool', 'key', '--clearmodifiers', x11_key],
                    env={'DISPLAY': self.display},
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass

    def stop(self):
        """Kill DOOM process.  Called by PWR key (framework-enforced)."""
        self._running = False
        if self.process:
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass
            try:
                self.process.kill()
            except Exception:
                pass
            try:
                self.process.wait(timeout=3)
            except Exception:
                pass
            self.process = None
            print('[DOOM] Stopped')

    @property
    def is_running(self):
        """Check if the DOOM subprocess is still alive."""
        if self.process is None:
            return False
        return self.process.poll() is None
