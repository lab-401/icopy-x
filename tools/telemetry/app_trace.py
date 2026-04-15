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

# Python app telemetry — deploy as sitecustomize.py
# Appends to /mnt/upan/app_trace.log. Lightweight, survives crashes.
import threading, time, sys, os

def _go():
    LOG = '/mnt/upan/app_trace.log'
    t0 = time.time()
    pid = os.getpid()

    def lg(m):
        try:
            with open(LOG, 'a') as f:
                f.write('[%8.3f] [pid=%d] %s\n' % (time.time() - t0, pid, m))
                f.flush()
        except:
            pass

    lg('sitecustomize start argv=%s' % sys.argv)

    # Wait for app process
    for i in range(120):
        if 'application' in sys.modules:
            lg('application found at poll %d' % i)
            break
        time.sleep(0.5)
    else:
        return

    # Fatal exception hook — install IMMEDIATELY
    _orig_excepthook = sys.excepthook
    def _crash_hook(exc_type, exc_val, exc_tb):
        try:
            import traceback
            tb = ''.join(traceback.format_exception(exc_type, exc_val, exc_tb))
            lg('FATAL EXCEPTION:\n%s' % tb)
        except:
            pass
        _orig_excepthook(exc_type, exc_val, exc_tb)
    sys.excepthook = _crash_hook
    lg('excepthook installed')

    time.sleep(5)
    lg('=== SESSION START ===')

    try:
        import actstack, executor
    except Exception as e:
        lg('import failed: %s' % e)
        return

    # pm3_compat state (if available)
    try:
        import pm3_compat
        lg('pm3_compat version=%s translation=%s' % (
            pm3_compat.get_version(), pm3_compat.needs_translation()))
    except Exception as e:
        lg('pm3_compat: %s' % e)

    # ── GD32 serial bus: hook ALL serial writes and reads ──
    try:
        import hmi_driver

        # Hook all writes to GD32
        _orig_ser_write = hmi_driver._ser_write
        def _traced_ser_write(cmd):
            lg('GD32_TX> %s' % cmd)
            return _orig_ser_write(cmd)
        hmi_driver._ser_write = _traced_ser_write

        # Hook setbaklight separately (uses raw _ser.write)
        if hasattr(hmi_driver, 'setbaklight'):
            _orig_setbaklight = hmi_driver.setbaklight
            def _traced_setbaklight(level):
                lg('GD32_TX> setbaklight(%s)' % level)
                return _orig_setbaklight(level)
            hmi_driver.setbaklight = _traced_setbaklight

        # Hook all reads from GD32 (the serial key/event handler)
        _orig_key_handle = hmi_driver._serial_key_handle
        def _traced_key_handle(keycode):
            lg('GD32_RX< %s' % keycode)
            return _orig_key_handle(keycode)
        hmi_driver._serial_key_handle = _traced_key_handle

        lg('GD32 serial hooks OK')
    except Exception as e:
        lg('GD32 serial hooks failed: %s' % e)

    # ── PM3 bus: hook executor send/receive ──
    try:
        # Hook PM3 commands (sent via executor)
        _orig_startPM3Task = executor.startPM3Task
        def _traced_startPM3Task(*a, **kw):
            cmd = str(a[0])[:200] if a else '?'
            timeout = a[1] if len(a) > 1 else kw.get('timeout', '?')
            lg('PM3_TX> %s (timeout=%s)' % (cmd, timeout))
            t = time.time()
            r = _orig_startPM3Task(*a, **kw)
            elapsed = time.time() - t
            try:
                cache = executor.CONTENT_OUT_IN__TXT_CACHE or ''
                lg('PM3_RX< ret=%s %.1fs len=%d %s' % (
                    r, elapsed, len(cache),
                    cache.replace(chr(10), '\\n')[:500]))
            except:
                lg('PM3_RX< ret=%s %.1fs' % (r, elapsed))
            return r
        executor.startPM3Task = _traced_startPM3Task

        # Hook PM3 rework
        _orig_rework = executor.reworkPM3All
        def _tr(*a, **kw):
            lg('PM3 !!! REWORK !!!')
            r = _orig_rework(*a, **kw)
            lg('PM3 REWORK done socket=%s' % (executor._socket_instance is not None))
            return r
        executor.reworkPM3All = _tr

        # Hook PM3 connect
        _orig_connect = executor.connect2PM3
        def _tc(*a, **kw):
            lg('PM3 CONNECT')
            r = _orig_connect(*a, **kw)
            lg('PM3 CONNECT result=%s' % r)
            return r
        executor.connect2PM3 = _tc

        lg('PM3 bus hooks OK')
    except Exception as e:
        lg('PM3 bus hooks failed: %s' % e)

    # ── Activity transitions ──
    try:
        o1 = actstack.start_activity
        def t1(*a, **kw):
            try:
                names = [x.__name__ if hasattr(x, '__name__') else repr(x) for x in a]
                lg('START(%s)' % ', '.join(names))
            except:
                pass
            return o1(*a, **kw)
        actstack.start_activity = t1

        o2 = actstack.finish_activity
        def t2(*a, **kw):
            try:
                lg('FINISH(top=%s d=%d)' % (
                    type(actstack._ACTIVITY_STACK[-1]).__name__,
                    len(actstack._ACTIVITY_STACK)))
            except:
                pass
            return o2(*a, **kw)
        actstack.finish_activity = t2
        lg('activity hooks OK')
    except Exception as e:
        lg('activity hooks failed: %s' % e)

    # ── Thread + memory health monitor (every 60s) ──
    def _health():
        while True:
            try:
                tc = threading.active_count()
                names = [t.name for t in threading.enumerate()]
                # Memory from /proc
                with open('/proc/meminfo') as f:
                    memlines = f.read()
                memfree = ''
                for line in memlines.split('\n'):
                    if 'MemAvailable' in line:
                        memfree = line.strip()
                        break
                lg('HEALTH threads=%d mem=%s names=%s' % (tc, memfree, names))
            except:
                pass
            time.sleep(60)
    threading.Thread(target=_health, daemon=True).start()

    lg('=== ALL HOOKS INSTALLED ===')

threading.Thread(target=_go, daemon=True).start()
