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

"""Battery UI polling module -- replaces batteryui.so.

Polls hmi_driver.readbatpercent() and hmi_driver.requestChargeState()
on a background thread and pushes updates to all registered BatteryBar
widgets via setBattery() / setCharging().

Original .so API (from V1090_MODULE_AUDIT.txt):
    register(battery_bar)
    unregister(battery_bar)
    start()
    pause()
    notifyCharging(is_charging)

String table analysis reveals:
    __BATTERY_BAR   -- list of registered BatteryBar widgets
    __BATTERY_RUN   -- run flag for background thread
    __BATTERY_VALUE -- cached battery percent
    __BATTERY_UPDATE -- threading.Event for poll interval
    __CHARGING_STATE -- cached charging state
    __UPDATING      -- guard against concurrent __update_views
    __EVENT         -- threading.Event used for wait(10)
    __pyx_int_10    -- poll interval = 10 seconds

Import: hmi_driver, threading, audio (for playChargingAudio)

Source: decompiled batteryui.so string table + Ghidra function list
"""

import logging
import threading

logger = logging.getLogger(__name__)

# ── Module-level state (matches original .so globals) ──────────
__BATTERY_BAR = []          # Registered BatteryBar widgets
__BATTERY_RUN = False       # Background thread run flag
__BATTERY_VALUE = 100       # Cached battery percent (0-100)
__CHARGING_STATE = False    # Cached charging state
__UPDATING = False          # Guard against concurrent updates
__EVENT = threading.Event() # Poll interval wait handle
_thread = None              # Background polling thread


def register(battery_bar):
    """Register a BatteryBar widget to receive periodic updates.

    Called by BaseActivity._showBatteryBar() during onResume.

    Args:
        battery_bar: widget.BatteryBar instance with setBattery()/setCharging().
    """
    if battery_bar not in __BATTERY_BAR:
        __BATTERY_BAR.append(battery_bar)
        # Push current state immediately so the bar renders correctly
        try:
            battery_bar.setBattery(__BATTERY_VALUE)
            battery_bar.setCharging(__CHARGING_STATE)
        except Exception:
            pass
    logger.debug("batteryui.register: %d bars registered", len(__BATTERY_BAR))


def unregister(battery_bar):
    """Unregister a BatteryBar widget.

    Called by BaseActivity._hideBatteryBar() during onPause.

    Args:
        battery_bar: widget.BatteryBar instance to remove.
    """
    try:
        __BATTERY_BAR.remove(battery_bar)
    except ValueError:
        pass
    logger.debug("batteryui.unregister: %d bars registered", len(__BATTERY_BAR))


def start():
    """Start the background battery polling thread.

    Spawns a daemon thread that polls hmi_driver every 10 seconds.
    Safe to call multiple times -- only one thread runs at a time.
    """
    global __BATTERY_RUN, _thread
    if __BATTERY_RUN:
        return
    __BATTERY_RUN = True
    __EVENT.clear()
    _thread = threading.Thread(target=__run__, daemon=True, name="batteryui")
    _thread.start()
    logger.info("batteryui: polling started")


def pause():
    """Stop the background polling thread.

    Sets __BATTERY_RUN = False and signals __EVENT to wake the thread.
    """
    global __BATTERY_RUN
    __BATTERY_RUN = False
    __EVENT.set()  # Wake thread so it exits promptly
    logger.info("batteryui: polling paused")


def notifyCharging(is_charging):
    """Notify that charging state changed (from hmi_driver status event).

    Updates cached state and pushes to all registered bars immediately.
    The original .so also calls audio.playChargingAudio() here.

    Args:
        is_charging: bool -- True if charger connected.
    """
    global __CHARGING_STATE
    __CHARGING_STATE = bool(is_charging)

    # Play charging audio (non-critical)
    try:
        import audio
        audio.playChargingAudio()
    except Exception:
        pass

    # Push to all registered bars via Tk main thread
    _schedule_update_views(__BATTERY_VALUE, __CHARGING_STATE)


def __run__():
    """Background polling loop.

    Polls hmi_driver.readbatpercent() and requestChargeState() every 10
    seconds, then pushes updates to all registered BatteryBar widgets.

    Uses threading.Event.wait(10) so the thread wakes promptly when
    pause() is called.
    """
    global __BATTERY_VALUE, __CHARGING_STATE
    logger.debug("batteryui.__run__: entered")

    while __BATTERY_RUN:
        # Poll battery state from HMI driver
        try:
            import hmi_driver
            battery = hmi_driver.readbatpercent()
            charging = hmi_driver.requestChargeState()
        except ImportError:
            battery = 100
            charging = False
        except Exception as e:
            logger.debug("batteryui: poll error: %s", e)
            battery = __BATTERY_VALUE
            charging = __CHARGING_STATE

        __BATTERY_VALUE = battery
        __CHARGING_STATE = charging

        # Push updates to registered bars
        _schedule_update_views(battery, charging)

        # Wait 10 seconds (or until signalled by pause())
        __EVENT.wait(10)
        __EVENT.clear()

    logger.debug("batteryui.__run__: exited")


def _schedule_update_views(battery, charging):
    """Schedule __update_views on the Tk main thread.

    BatteryBar.setBattery() and setCharging() modify canvas items,
    which must happen on the Tk main thread.
    """
    try:
        from lib import actstack
        if actstack._root is not None:
            actstack._root.after(0, __update_views, battery, charging)
        else:
            __update_views(battery, charging)
    except Exception:
        # Fallback: call directly (may be in test/no-Tk context)
        __update_views(battery, charging)


def __update_views(battery, charging):
    """Push battery state to all registered BatteryBar widgets.

    Iterates __BATTERY_BAR and calls setBattery()/setCharging() on each.
    Guards against concurrent calls via __UPDATING flag.
    Removes destroyed bars from the list.

    Args:
        battery: int 0-100
        charging: bool
    """
    global __UPDATING
    if __UPDATING:
        return
    __UPDATING = True

    try:
        dead = []
        for bar in __BATTERY_BAR:
            try:
                if bar.isDestroy():
                    dead.append(bar)
                    continue
                bar.setBattery(battery)
                bar.setCharging(charging)
            except Exception as e:
                logger.debug("batteryui: update error: %s", e)
                dead.append(bar)

        # Clean up destroyed bars
        for bar in dead:
            try:
                __BATTERY_BAR.remove(bar)
            except ValueError:
                pass
    finally:
        __UPDATING = False
