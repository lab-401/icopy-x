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

"""Application lifecycle bootstrap — replaces application.so.

Exports:
    setWindows(window)  — optional pre-configuration of the Tk root window
    startApp()          — create Tk root, init actstack, push MainActivity,
                          wire keymap, enter mainloop (blocks)

Source: decompiled/application_ghidra_raw.txt (7361 lines, 2 public functions)

String table (from Ghidra):
    setWindows: tkinter, platform, Windows, ctypes, windll, user32, shcore,
                SetProcessDpiAwareness, SetProcessDPIAware, geometry, 240x240,
                resizable, scaling, mononoki, cursor, option_add, config, window
    startApp:   tkinter, actstack, actmain, MainActivity, start_activity,
                mainloop, onKey

Original Cython source path (embedded in .so):
    C:\\Users\\usertest\\AppData\\Local\\Temp\\tmpg_iuwagn\\application.py

Cython version: 0.29.21
"""

import platform as _platform

# Module-level state
_root = None
_window_config = None


def setWindows(window=None):
    """Configure window properties before startApp().

    Optional pre-configuration.  If called before startApp(), the provided
    settings override defaults.  If not called, startApp() uses device
    defaults (240x240, mononoki font, no cursor).

    Args:
        window: dict with optional keys:
            geometry  (str):   Window size, default '240x240'
            scaling   (float): Tk scaling factor
            font      (str):   Default font family, default 'mononoki'
            cursor    (str):   Cursor style ('' to hide)
            resizable (bool):  Window resizable, default False

    Platform behaviour (from decompiled .so):
        Windows: sets DPI awareness via ctypes.windll (shcore/user32)
        Linux/ARM: DPI setup is a no-op (device has fixed 240x240 LCD)
    """
    global _window_config
    _window_config = window or {}

    # Windows DPI awareness — original .so checks platform.system() == 'Windows'
    # and calls SetProcessDpiAwareness(2) via ctypes.  On the ARM device this
    # is always a no-op, but we preserve the behaviour for dev-machine compat.
    if _platform.system() == 'Windows':
        try:
            import ctypes
            awareness = ctypes.c_int()
            ctypes.windll.shcore.GetProcessDpiAwareness(
                0, ctypes.byref(awareness))
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                import ctypes
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass


def startApp():
    """Bootstrap and launch the iCopy-X application.

    Creates the tkinter root window, initialises the activity stack,
    pushes MainActivity, wires keymap auto-dispatch on stack changes,
    and enters mainloop.  Blocks until the application exits.

    This reproduces the exact sequence from the decompiled startApp():
        1. import tkinter → Tk() → configure geometry/font/cursor
        2. import actstack → actstack.init(root)
        3. import actmain → actstack.start_activity(actmain.MainActivity)
        4. Wire keymap.key.bind() to update on every stack change
        5. root.mainloop()
    """
    global _root
    import tkinter

    # ── 1. Create & configure root window ──────────────────────────
    root = tkinter.Tk()
    _root = root

    cfg = _window_config or {}

    root.geometry(cfg.get('geometry', '240x240'))
    root.resizable(
        cfg.get('resizable', False),
        cfg.get('resizable', False),
    )

    # Default font — original .so uses 'mononoki'
    font = cfg.get('font', 'mononoki')
    root.option_add('*Font', font)

    # Tk scaling factor (original reads from config module on Windows)
    scaling = cfg.get('scaling')
    if scaling is not None:
        root.tk.call('tk', 'scaling', scaling)

    # Hide cursor on device (original checks platform)
    cursor = cfg.get('cursor')
    if cursor is not None:
        root.configure(cursor=cursor)

    # ── 2. Initialise activity stack ───────────────────────────────
    import actstack
    actstack.init(root)

    # ── 2b. Discover plugins ──────────────────────────────────────
    # Must run before MainActivity is created so that the main menu
    # includes promoted plugin entries and the "Plugins" submenu.
    import actmain
    try:
        actmain.init_plugins()
    except Exception:
        pass

    # ── 3. Push MainActivity ───────────────────────────────────────
    actstack.start_activity(actmain.MainActivity)

    # ── 4. Wire keymap target to top-of-stack activity ─────────────
    # The original application.so patches the activity stack so that
    # every start/finish automatically re-binds keymap.key to the
    # current top activity.  Reproducing that here.
    import keymap

    def _update_key_target():
        """Set keymap target to the current top-of-stack activity."""
        try:
            if actstack._ACTIVITY_STACK:
                keymap.key.bind(actstack._ACTIVITY_STACK[-1])
        except Exception:
            pass

    _orig_start = actstack.start_activity
    def _patched_start(*a, **kw):
        result = _orig_start(*a, **kw)
        _update_key_target()
        return result
    actstack.start_activity = _patched_start

    _orig_finish = actstack.finish_activity
    def _patched_finish(*a, **kw):
        result = _orig_finish(*a, **kw)
        _update_key_target()
        return result
    actstack.finish_activity = _patched_finish

    # Set initial target
    _update_key_target()

    # ── 5. Start battery UI polling ───────────────────────────────
    # Original firmware starts batteryui polling during app init so
    # BatteryBar widgets receive periodic updates from hmi_driver.
    try:
        import batteryui
        batteryui.start()
    except Exception:
        pass

    # ── 6. Start screen mirror service if configured ────────────────
    try:
        import settings
        if settings.getScreenMirror():
            from lib.mirror_service import get_service
            get_service().start()
    except Exception:
        pass

    # ── 7. Post-UI PM3 version check ─────────────────────────────
    # Original middleware runs PM3 checks AFTER the UI is visible,
    # showing a "Processing..." toast during the check (ground truth:
    # application.so string table contains "Processing").
    # This avoids a 30+ second startup block if PM3 is slow.
    import threading as _threading

    def _post_ui_pm3_check():
        """Show 'Processing...' toast, run PM3 version check in background."""
        current = actstack.get_current_activity()
        if current is None:
            return

        canvas = current.getCanvas()
        if canvas is None:
            return

        from lib.widget import Toast
        from lib import resources
        _toast = Toast(canvas, duration_ms=0)
        _toast.show(resources.get_str('processing'), duration_ms=0)

        def _check():
            try:
                # Import with device-compatible fallback (lib/ not middleware/)
                try:
                    from middleware import pm3_flash
                except ImportError:
                    import pm3_flash
                try:
                    import pm3_compat
                except ImportError:
                    pm3_compat = None
                try:
                    import executor
                except ImportError:
                    executor = None

                import os as _os
                _app_dir = _os.path.dirname(
                    _os.path.dirname(_os.path.abspath(__file__)))

                # Fast path: if no firmware manifest, nothing to do
                _manifest = _os.path.join(
                    _app_dir, 'res', 'firmware', 'pm3', 'manifest.json')
                image_ver = pm3_flash.get_image_version(_manifest)
                if image_ver is None:
                    print('[app] No firmware manifest — skip PM3 check',
                          flush=True)
                    root.after(0, _on_check_complete, False)
                    return

                # Quick probe: single hw version, no reworks.
                # If PM3 subprocess crashed (e.g. client/firmware capabilities
                # mismatch), this returns immediately instead of waiting 30s+
                # through 3 retry cycles.
                ver_info = None
                if executor is not None:
                    try:
                        ret = executor.startPM3Task(
                            'hw version', timeout=5000, rework_max=0)
                        if ret == 1:
                            output = executor.getPrintContent()
                            if output:
                                ver_info = pm3_flash._parse_hw_version(
                                    output)
                    except Exception as e:
                        print('[app] PM3 probe failed: %s' % e, flush=True)

                # Set pm3_compat version from result
                if pm3_compat is not None:
                    if ver_info is not None:
                        if ver_info.get('nikola', ''):
                            pm3_compat._current_version = \
                                pm3_compat.PM3_VERSION_ORIGINAL
                        else:
                            pm3_compat._current_version = \
                                pm3_compat.PM3_VERSION_ICEMAN
                        print('[app] PM3 version: %s' %
                              pm3_compat.get_version(), flush=True)
                        # One-time iceman configuration (BCC ignore etc.)
                        try:
                            pm3_compat.configure_iceman()
                        except Exception:
                            pass
                    else:
                        print('[app] PM3 not responding', flush=True)

                # Determine if flash is needed
                flash_needed = False
                target = image_ver.get('pm3_firmware_version', '')
                if target:
                    if ver_info is None:
                        flash_needed = True
                    else:
                        running_os = ver_info.get('os', '')
                        if not running_os or target not in running_os:
                            flash_needed = True

                root.after(0, _on_check_complete, flash_needed)
            except Exception as e:
                print('[app] post-UI PM3 check error: %s' % e, flush=True)
                root.after(0, _on_check_complete, False)

        def _on_check_complete(flash_needed):
            _toast.cancel()
            if flash_needed:
                try:
                    from lib.activity_main import FWUpdateActivity
                except ImportError:
                    from activity_main import FWUpdateActivity
                actstack.start_activity(FWUpdateActivity)
                _update_key_target()
                print('[app] PM3 firmware mismatch — FWUpdateActivity pushed',
                      flush=True)

        _threading.Thread(target=_check, daemon=True).start()

    root.after(100, _post_ui_pm3_check)

    # ── 8. Enter mainloop (blocks) ─────────────────────────────────
    root.mainloop()
