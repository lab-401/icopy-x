##########################################################################
# Required Notice: Copyright ETOILE401 SAS (http://www.lab401.com)
#
# Copyright (c) 2026: ETOILE401 SAS & https://github.com/quantum-x/
# Copyright (c) 2026: Vost02
#
# This software is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this software for commercial purposes.
#
# A copy of the license is available at:
# https://polyformproject.org/licenses/noncommercial/1.0.0
#
# This entire header "Required Notice" must remain in place.
##########################################################################

"""Chameleon Dump -- move iCopy-X dumps to/from a Chameleon.

Auto-detects a **Chameleon Ultra** or a **Chameleon Tiny** on the iCopy-X
USB host port and dispatches to the matching backend (``ultra_backend`` /
``tiny_backend``).  The Tiny backend speaks the ChameleonMini command set,
so a **Chameleon Mini** should work too -- untested (no hardware to
verify).  Both directions are supported:

    Write   load an iCopy-X dump into a Chameleon slot
    Read    save a Chameleon slot back out as an iCopy-X dump

The two backends share the same UI state names, so a single ``ui.json``
drives both; only the protocol underneath differs.  Detection reuses each
backend's own handshake (the Ultra's binary ``GET_APP_VERSION`` and the
Tiny's text ``VERSION?`` ignore each other, so at most one matches).
"""

import importlib.util
import os

_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_backend(name):
    path = os.path.join(_DIR, name + '.py')
    spec = importlib.util.spec_from_file_location(
        'chameleon_dump_' + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_ultra = _load_backend('ultra_backend')
_tiny = _load_backend('tiny_backend')

# (label, module, entry class, device finder)
_BACKENDS = (
    ('Ultra', _ultra, 'UltraBackend', '_find_ultra'),
    ('Tiny', _tiny, 'TinyBackend', '_find_tiny'),
)


class ChameleonDumpPlugin(object):
    """Entry class: detect the device, then delegate to its backend."""

    def __init__(self, host=None):
        self.host = host
        self._impl = None
        self._device = None

    # -- host helpers --------------------------------------------------

    def _set(self, key, value):
        if self.host is not None:
            self.host.set_var(key, value)

    def tr(self, text):
        translator = getattr(self.host, 'tr', None)
        return translator(text) if translator is not None else text

    # -- lifecycle -----------------------------------------------------

    def on_destroy(self):
        if self._impl is not None:
            self._impl.on_destroy()

    # -- device detection ---------------------------------------------

    def _detect(self):
        """Find the connected Chameleon.

        Returns ``(backend_instance, (handle, port, version), label)`` or
        ``(None, None, None)`` with ``error_msg`` set.
        """
        last = 'no serial device found'
        for label, module, cls_name, find_name in _BACKENDS:
            try:
                device = getattr(module, find_name)()
            except Exception as exc:
                last = '%s: %s' % (label, exc)
                continue
            impl = getattr(module, cls_name)(self.host)
            return impl, device, label
        self._set('error_msg',
                  self.tr('No Chameleon found.\n\n%s') % last)
        return None, None, None

    def _begin(self, method):
        self._set('error_msg', '')
        self._set('progress_value', 0)
        self._set('progress_message', '')
        self._impl = None
        impl, device, label = self._detect()
        if impl is None:
            return {'status': 'error'}
        self._impl = impl
        self._device = label
        result = getattr(impl, method)(device=device)
        if not isinstance(result, dict) or result.get('status') != 'ready':
            # Release the port opened for detection; the backend may not
            # have taken ownership of it on an early error return.
            impl.on_destroy()
        return result

    # -- UI entry points (run:<method>) --------------------------------

    def start(self):
        return self._begin('start')

    def start_read(self):
        return self._begin('start_read')

    def choose_dump(self):
        return self._delegate('choose_dump')

    def choose_slot(self):
        return self._delegate('choose_slot')

    def do_write(self):
        return self._delegate('do_write')

    def choose_read_slot(self):
        return self._delegate('choose_read_slot')

    def do_read(self):
        return self._delegate('do_read')

    def _delegate(self, method):
        if self._impl is None:
            self._set('error_msg', self.tr('No Chameleon found.'))
            return {'status': 'error'}
        return getattr(self._impl, method)()
