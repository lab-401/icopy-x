"""Small ARM/Tk acceptance profile. Hardware boundaries are explicit below.

Scanner workers, executor, translation, parsers, activity decisions and Tk stay
real. PM3 transport is a finite transcript. Reader dispatch is observed without
performing a card read. Audio/HMI/serial boundaries cannot touch hardware.
"""
from contextlib import ExitStack
import copy
import json
from pathlib import Path
import threading
import time
from types import SimpleNamespace
from unittest.mock import patch
import uuid  # noqa: F401 - initialize stdlib's real `uname -p` probe before process guards

from strict_transport import Transcript


PROFILE = json.loads(Path(__file__).with_name('critical_cases.json').read_text())
CASE_IDS = tuple(PROFILE['cases'])


def run(root, output, variant, callback_errors):
    import actmain
    import actstack
    import activity_main
    import activity_read
    import audio
    import executor
    import glob
    import hmi_driver
    import ics_decoder
    import os
    import pm3_compat
    import read
    import scan
    import serial
    import socket
    import subprocess
    from _constants import KEY_OK, KEY_M2, KEY_PWR, KEY_RIGHT

    assert pm3_compat.LEGACY_COMPAT, 'Factory compatibility must remain enabled'
    fixture_path = Path(__file__).with_name('transcripts.json')
    fixtures = json.loads(fixture_path.read_text())
    firmware = 'original' if variant == 'noflash' else 'iceman'
    rows = [dict(id=name, status='INCOMPLETE') for name in CASE_IDS]
    report = dict(profile='critical-v1', firmware_profile=firmware,
                  status='INCOMPLETE', cases=rows, fixture_provenance=fixtures['provenance'],
                  substitutions=['executor TCP socket: exact finite PM3 transcript',
                                 'pm3_compat._current_version: declared firmware profile',
                                 'read.Reader: dispatch observer; no card read',
                                 'HMI abort: release the held transport response',
                                 'audio playback: silent sink',
                                 'decoder serial enumeration: empty inventory'],
                  forbidden_operations='unscripted transport, serial open, subprocess, os.system')

    def save():
        (output / 'critical.json').write_text(json.dumps(report, indent=2) + '\n')

    def pump(predicate, timeout=5):
        """Run the real Tk event loop until an observable condition or deadline."""
        errors = []
        timer = [None]
        deadline = time.monotonic() + timeout

        def poll():
            try:
                if callback_errors:
                    raise AssertionError(callback_errors)
                if predicate():
                    root.quit()
                    return
                if time.monotonic() >= deadline:
                    raise AssertionError('Timed out waiting for critical-flow condition')
                timer[0] = root.after(5, poll)
            except BaseException as error:
                errors.append(error)
                root.quit()

        timer[0] = root.after(0, poll)
        root.mainloop()
        root.after_cancel(timer[0])
        if errors:
            raise errors[0]

    def drain():
        until = time.monotonic() + .35
        pump(lambda: time.monotonic() >= until)

    def texts(activity):
        canvas = activity.getCanvas()
        return [canvas.itemcget(item, 'text') for item in canvas.find_all()
                if canvas.type(item) == 'text' and canvas.itemcget(item, 'state') != 'hidden']

    def visible_text(activity):
        # Real Tk may wrap a toast into several canvas text items.
        return ' '.join(' '.join(texts(activity)).split())

    def no_tag_steps():
        return copy.deepcopy(fixtures[firmware]['no_tag'])

    def found_steps():
        return copy.deepcopy(fixtures[firmware]['found'])

    save()
    for row in rows:
        name = row['id']
        before_threads = set(threading.enumerate())
        failures, reads, aborts, scan_results = [], [], [], []
        if name == 'no_tag_rescan':
            steps = no_tag_steps() * 2
        elif name == 'collision_refuses_reader':
            steps = [dict(command='hf 14a info', response='Multiple tags detected\nNikola.D: 0\n')]
        elif name in ('single_tag_reader_dispatch', 'console_roundtrip', 'cancel_inflight_found'):
            steps = found_steps()
        elif name in ('cancel_inflight_empty', 'exit_reenter'):
            steps = no_tag_steps()[:1]
            if name == 'exit_reenter':
                steps += no_tag_steps()
        else:
            steps = []
        if name.startswith('cancel_') or name == 'exit_reenter':
            # Hold the Gen1 probe after UID parsing for a real late-found result.
            # Holding the initial info command would make cancellation return a
            # timeout before parsing, duplicating the late-empty case instead.
            index = -1 if name == 'cancel_inflight_found' else 0
            steps[index]['blocked'] = True
        transport = Transcript(steps)
        started = time.monotonic()
        error = None

        def forbidden(*args, **kwargs):
            failures.append('Unexpected hardware/process operation: ' + repr(args))
            raise AssertionError(failures[-1])

        class ReaderObserver:
            def start(self, tag_type, bundle):
                reads.append((tag_type, copy.deepcopy(bundle)))

            def is_reading(self):
                return True

            def stop(self):
                pass

        def abort():
            aborts.append('presspm3')
            transport.release.set()

        def socket_factory(family, kind):
            if family != socket.AF_INET or kind != socket.SOCK_STREAM:
                forbidden('unexpected socket family/type', family, kind)
            return transport

        socket_api = SimpleNamespace(socket=socket_factory, AF_INET=socket.AF_INET,
                                     SOCK_STREAM=socket.SOCK_STREAM, timeout=socket.timeout)
        original_finish = activity_read.ReadActivity.onScanFinish

        def observe_finish(activity, result, scan_token=None):
            scan_results.append(copy.deepcopy(result))
            return original_finish(activity, result, scan_token=scan_token)

        with ExitStack() as stack:
            for module, attribute, value in (
                (executor, '_socket_instance', None),
                (executor, '_pipeline_needs_cleanup', False),
                (executor, 'LABEL_PM3_CMD_TASK_RUNNING', False),
                (executor, 'LABEL_PM3_CMD_TASK_STOPPING', False),
                (executor, 'CONTENT_OUT_IN__TXT_CACHE', ''),
                (executor, 'socket', socket_api),
                (pm3_compat, '_current_version', firmware),
                (read, 'Reader', ReaderObserver),
                (activity_read.ReadActivity, 'onScanFinish', observe_finish),
                (hmi_driver, 'presspm3', abort),
                (hmi_driver, 'restartpm3', forbidden),
                (subprocess, 'Popen', forbidden),
                (os, 'system', forbidden),
                (serial, 'Serial', forbidden),
                (threading, 'excepthook', lambda args: failures.append(str(args.exc_value))),
            ):
                stack.enter_context(patch.object(module, attribute, value))
            for attribute in dir(audio):
                if attribute.startswith('play') and callable(getattr(audio, attribute)):
                    stack.enter_context(patch.object(audio, attribute, lambda *a, **kw: None))
            scan.clearScanCahe()
            executor.resetReworkCount()
            try:
                main = actstack.start_activity(actmain.MainActivity)
                root.update()
                if name == 'decoder_absent':
                    # Replace enumeration only: the actual detector and UI worker run.
                    original_glob = glob.glob

                    def ports(pattern, *args, **kwargs):
                        if pattern in ('/dev/ttyACM*', '/dev/ttyUSB*'):
                            return []
                        return original_glob(pattern, *args, **kwargs)

                    stack.enter_context(patch.object(ics_decoder.glob, 'glob', ports))
                    activity = actstack.start_activity(activity_main.ICSDecoderActivity)
                    activity.callKeyEvent(KEY_OK)
                    pump(lambda: 'No decoder found!' in texts(activity))
                    assert 'Check USB connection' in texts(activity)
                    activity.callKeyEvent(KEY_PWR)
                    root.update()
                    assert actstack.get_current_activity() is activity
                    assert activity._state == activity.STATE_HOME
                    assert 'Read Credential' in visible_text(activity)
                else:
                    activity = actstack.start_activity(activity_read.ReadActivity, {'tag_type': 1})
                    if name.startswith('cancel_') or name == 'exit_reenter':
                        pump(transport.entered.is_set)
                        activity.callKeyEvent(KEY_PWR)
                        assert activity.life.destroyed and actstack.get_current_activity() is main
                        # Run the late Scanner callback through Tk before assessing it.
                        pump(lambda: not (set(threading.enumerate()) - before_threads))
                        drain()
                        assert reads == [] and aborts == ['presspm3'], (reads, aborts)
                        assert len(scan_results) == 1, scan_results
                        assert scan_results[0]['found'] is (name == 'cancel_inflight_found'), scan_results
                        if name == 'exit_reenter':
                            activity = actstack.start_activity(activity_read.ReadActivity, {'tag_type': 1})
                            pump(lambda: activity.state == 'no_tag')
                            assert 'No tag found' in visible_text(activity)
                    elif name in ('single_tag_reader_dispatch', 'console_roundtrip'):
                        pump(lambda: activity.state == 'reading' and bool(reads))
                        assert len(reads) == 1 and reads[0][0] == 1, reads
                        info = reads[0][1]['infos']
                        assert info['uid'] == '5E5BCE4C' and info['type'] == 1, info
                        assert reads[0][1]['force'] is False
                        if name == 'console_roundtrip':
                            activity.callKeyEvent(KEY_RIGHT)
                            root.update()
                            assert activity._console_showing
                            activity.callKeyEvent(KEY_PWR)
                            root.update()
                            assert not activity._console_showing
                            assert actstack.get_current_activity() is activity and activity.state == 'reading'
                    else:
                        pump(lambda: activity.state == 'no_tag')
                        expected = 'Multiple tags detected!' if name == 'collision_refuses_reader' else 'No tag found'
                        assert expected in visible_text(activity), texts(activity)
                        assert reads == []
                        if name == 'no_tag_rescan':
                            activity.callKeyEvent(KEY_M2)
                            pump(lambda: activity.state == 'no_tag')
                            assert 'No tag found' in visible_text(activity) and not reads
                if not activity.life.destroyed:
                    activity.callKeyEvent(KEY_PWR)
                assert actstack.get_current_activity() is main
                transport.verify()
                assert not failures and not callback_errors, (failures, callback_errors)
            except BaseException as caught:
                error = caught
            finally:
                transport.release.set()
                try:
                    while actstack.get_current_activity() is not None:
                        actstack.finish_activity()
                    pump(lambda: not (set(threading.enumerate()) - before_threads))
                    drain()
                    assert not root.tk.call('after', 'info'), 'Activity left pending Tk callbacks'
                    assert not failures and not callback_errors, (failures, callback_errors)
                except BaseException as cleanup_error:
                    row['cleanup_error'] = repr(cleanup_error)
                    if error is None:
                        error = cleanup_error
                row.update(status='FAIL' if error else 'PASS', commands=transport.commands,
                           connections=transport.connections, reader_dispatches=reads,
                           scan_results=scan_results,
                           transport_errors=transport.violations, forbidden_operations=failures,
                           seconds=round(time.monotonic() - started, 3))
                if error is not None:
                    row['error'] = repr(error)
                    report['status'] = 'FAIL'
                save()
            if error is not None:
                raise error
        print('PASS: critical/' + name, flush=True)
    report['status'] = 'PASS'
    save()
    return report
