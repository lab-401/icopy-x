"""ARM guest: use packaged app modules only, and real Tk/Pillow/device fonts.

Does not call the installed boot/service chain or hardware operations.
"""
import hashlib
import importlib
import json
import os
from pathlib import Path
import struct
import sys
import traceback


app = Path(sys.argv[1]).resolve()
output = Path(sys.argv[2]).resolve()
harness = Path(__file__).resolve()
profile, variant = sys.argv[3:5] if len(sys.argv) == 5 else ('smoke', 'noflash')
assert profile in ('smoke', 'critical') and variant in ('flash', 'noflash')
harness_paths = {harness}
sys.dont_write_bytecode = True
rootfs = Path(os.environ['QEMU_LD_PREFIX']).resolve()
stdlib = rootfs / 'usr' / 'local' / 'python-3.8.0' / 'lib'
site = rootfs / 'home' / 'pi' / '.local' / 'lib' / 'python3.8' / 'site-packages'
assert struct.calcsize('P') == 4 and sys.version_info[:2] == (3, 8)
sys.path[:] = [p for p in sys.path if p and str(Path(p).resolve()).startswith(str(stdlib) + '/')]
sys.path.insert(0, str(site))
# Load real pygame before application audio.py can shadow pygame internals.
import pygame  # noqa: F401
from PIL import Image, ImageTk  # noqa: F401
import tkinter
from tkinter import font

sys.path[:0] = [str(app / 'lib'), str(app / 'main'), str(app)]
os.chdir(str(app))

# Compile every packaged Python file using the device interpreter.
compiled = 0
for source in app.rglob('*.py'):
    compile(source.read_bytes(), str(source), 'exec')
    compiled += 1
assert compiled > 0
for document in app.rglob('*.json'):
    json.loads(document.read_text())

required = ('actmain', 'actstack', 'activity_main', 'activity_read', 'application',
            'executor', 'pm3_compat', 'scan', 'read', 'write', 'ics_decoder',
            'version', 'main', 'rftask')
for name in required:
    importlib.import_module(name)

# Redirect device configuration storage only; no application decisions, scan
# results, serial, subprocess, encryption or exit functions are replaced.
import config
config._CONF_PATH = str(app / 'data' / 'conf.ini')
import actstack
import actmain
from _constants import KEY_DOWN, KEY_OK, KEY_PWR
root = tkinter.Tk()
root.geometry('240x240')
tcl_version = root.tk.call('info', 'patchlevel')
errors = []
root.report_callback_exception = lambda *exc: errors.append(''.join(traceback.format_exception(*exc)))
root.tk.createcommand('bgerror', errors.append)
assert 'mononoki' in [f.lower() for f in font.families(root)]
face = font.Font(root, family='mononoki', size=12)
assert face.actual('family').lower() == 'mononoki' and face.measure('Settings') > 0

critical = None
try:
    actstack.init(root)
    main = actstack.start_activity(actmain.MainActivity)
    root.update()
    assert actstack.get_current_activity() is main
    assert main.getCanvas().winfo_ismapped()
    main_text = [main.getCanvas().itemcget(i, 'text')
                 for i in main.getCanvas().find_all() if main.getCanvas().type(i) == 'text']
    assert any(text.startswith('Main Page') for text in main_text), main_text
    items = main._menu_items
    actions = [item[2] for item in items]
    assert all(action in actions for action in ('scan', 'read_list', 'iclass_se'))
    # Normal activity key dispatch: enter Read Tag's type list, then return.
    for _ in range(actions.index('read_list')):
        main.callKeyEvent(KEY_DOWN)
    main.callKeyEvent(KEY_OK)
    root.update()
    read_list = actstack.get_current_activity()
    assert read_list.__class__.__name__ == 'ReadListActivity', type(read_list)
    visible_text = [read_list.getCanvas().itemcget(i, 'text')
                    for i in read_list.getCanvas().find_all()
                    if read_list.getCanvas().type(i) == 'text']
    assert 'Read Tag' in visible_text and any('M1 S50' in text for text in visible_text)
    read_list.callKeyEvent(KEY_PWR)
    root.update()
    assert read_list.life.destroyed and actstack.get_current_activity() is main
    # Finish owned activities and drain delayed callbacks before assessing errors.
    while actstack.get_current_activity() is not None:
        actstack.finish_activity()
    root.after(250, root.quit)
    root.mainloop()
    assert not errors, errors
    if profile == 'critical':
        sys.path.insert(0, str(harness.parent))
        try:
            import critical_flows
        finally:
            sys.path.pop(0)
        harness_paths.update(harness.parent / name for name in
                             ('critical_flows.py', 'strict_transport.py', 'ultralight_cases.py'))
        critical = critical_flows.run(root, output, variant, errors)
finally:
    root.destroy()
assert not errors, errors

modules = {}
dependencies = {}
for name, module in list(sys.modules.items()):
    filename = getattr(module, '__file__', None)
    if not filename:
        continue
    path = Path(filename).resolve()
    if path in harness_paths:
        continue
    if app in path.parents:
        modules[name] = dict(relative_path=str(path.relative_to(app)),
                             sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    elif stdlib in path.parents or site in path.parents:
        dependencies[name] = str(path)
    else:
        raise AssertionError('Module escaped artifact/runtime paths: %s: %s' % (name, path))
assert all(name in modules for name in required), modules.keys()
result = dict(status='PASS', compiled_python_files=compiled, modules=modules,
              dependencies=dependencies, python=sys.version, tcl=tcl_version,
              cases=['packaged imports', 'main menu renders', 'read-list navigation and teardown'],
              path_redirects={'config._CONF_PATH': config._CONF_PATH},
              hardware_mocks=[], boot_chain_executed=False)
if critical is not None:
    result.update(critical=critical, hardware_mocks=critical['substitutions'])
(output / 'guest.json').write_text(json.dumps(result, indent=2) + '\n')
print('PASS: packaged modules and real Tk navigation', flush=True)
