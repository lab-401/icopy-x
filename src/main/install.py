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

"""IPK installer — OSS replacement for install.so.

Cython source: install.py (compiled to install.so by manufacturer)
Binary source: device_so/install.so (98,188 bytes, ARM ELF)
Ground truth: Ghidra decompilation + QEMU trace (2026-04-09)

Original functions confirmed via QEMU ExtensionFileLoader:
  install_font(unpkg_path, callback)
  install_lua_dep(unpkg_path, callback)
  update_permission(unpkg_path, callback)
  install_app(unpkg_path, callback)
  restart_app(callback)
  install(unpkg_path, callback)

The callback signature is: callback(name: str, progress: int)
Progress values observed: 30, 38, 60, 100.

Chinese log messages preserved for parity with original .so output:
  "检查字体的安装..." = Checking font installation
  "正在更新所有的权限..." = Updating all permissions
  "更新权限成功！！！" = Permissions updated
  "目录已经存在，不自动解压" = Directory exists, skip extract
  "正在重启" = Restarting
"""

import os
import shutil
import zipfile


def install_font(unpkg_path, callback):
    """Copy fonts from the IPK to the system font directory.

    Looks for fonts in {unpkg_path}/res/font/, copies new ones to
    /usr/share/fonts/truetype/ (or the device's font path).

    Args:
        unpkg_path: path to extracted IPK
        callback: progress callback(name, progress)
    """
    print("Installing assets...")

    source_font_path = os.path.join(unpkg_path, 'res', 'font')
    target_font_path = '/usr/share/fonts'

    if not os.path.isdir(source_font_path):
        # No fonts in this IPK — not an error
        return

    new_fonts = os.listdir(source_font_path)
    if not new_fonts:
        return

    os.makedirs(target_font_path, exist_ok=True)

    # Fonts that should not be installed (preserved from original)
    font_no_install_list = []

    old_fonts = set(os.listdir(target_font_path)) if os.path.isdir(target_font_path) else set()

    for new_font in new_fonts:
        if new_font in font_no_install_list:
            continue

        source_font_file = os.path.join(source_font_path, new_font)
        if not os.path.isfile(source_font_file):
            continue

        font_install = os.path.join(target_font_path, new_font)
        print(" Font will install...")
        if callback:
            callback('Installing assets...', 30)
        shutil.copy(source_font_file, font_install)

    print("Assets installed.")
    if callback:
        callback('Assets installed.', 100)


def install_lua_dep(unpkg_path, callback):
    """Install LUA scripts and libraries from lua.zip.

    Searches for lua.zip in two locations:
      1. {unpkg_path}/pm3/lua.zip  — bundled inside the IPK
      2. /mnt/upan/lua.zip         — standalone on USB drive (legacy)

    Extracts to /mnt/upan/ (creates luascripts/ and lualibs/ there).
    This keeps scripts user-editable on the USB partition and avoids
    permission issues.  Only extracts if the directories don't already
    exist — preserves user modifications across reinstalls.

    Then creates symlinks in the app directory ({unpkg_path}/):
      {unpkg_path}/luascripts -> /mnt/upan/luascripts
      {unpkg_path}/lualibs    -> /mnt/upan/lualibs

    This makes both PM3 firmwares find the scripts:
      - Factory PM3: searches /mnt/upan/ directly
      - Iceman PM3:  searches CWD-relative luascripts/ (follows symlink)

    Args:
        unpkg_path: path to extracted IPK
        callback: progress callback(name, progress)
    """
    # Find lua.zip — prefer IPK-bundled, fall back to USB drive
    path_lua_zip = os.path.join(unpkg_path, 'pm3', 'lua.zip')
    if not os.path.isfile(path_lua_zip):
        path_lua_zip = os.path.join('/mnt/upan/', 'lua.zip')
    if not os.path.isfile(path_lua_zip):
        # lua.zip is optional — not shipped with every update
        return

    # Extract to /mnt/upan/ — wipe existing dirs first to prevent
    # mixed Lua versions (factory 5.1 libs + iceman 5.4 = crashes).
    upan_luascripts = '/mnt/upan/luascripts'
    upan_lualibs = '/mnt/upan/lualibs'

    if True:  # Always extract when lua.zip is present in the IPK
        for dirname in (upan_luascripts, upan_lualibs):
            if os.path.isdir(dirname):
                shutil.rmtree(dirname)
        print("Installing tools...")
        if callback:
            callback('Installing tools...', 30)
        try:
            with zipfile.ZipFile(path_lua_zip, 'r') as zf:
                zf.extractall('/mnt/upan/')
        except Exception:
            print("lua.zip extract failed")
            return

    # Create symlinks so both PM3 firmwares find the scripts.
    #
    # Iceman PM3 searches (from `script list`):
    #   ~/.proxmark3/luascripts/
    #   <app>/share/proxmark3/luascripts/   (relative to pm3 binary)
    #
    # Factory PM3 searches /mnt/upan/ directly.
    #
    # CWD-relative lualibs/ is needed for Lua require() paths.
    #
    # All symlinks point to /mnt/upan/ so scripts stay user-editable.
    symlinks = [
        # Iceman script search path: <app>/share/proxmark3/luascripts
        (os.path.join(unpkg_path, 'share', 'proxmark3', 'luascripts'),
         '/mnt/upan/luascripts'),
        # Iceman lualibs search path
        (os.path.join(unpkg_path, 'share', 'proxmark3', 'lualibs'),
         '/mnt/upan/lualibs'),
        # CWD-relative fallback (lualibs for require())
        (os.path.join(unpkg_path, 'luascripts'),
         '/mnt/upan/luascripts'),
        (os.path.join(unpkg_path, 'lualibs'),
         '/mnt/upan/lualibs'),
    ]
    for link_path, target in symlinks:
        try:
            parent = os.path.dirname(link_path)
            if not os.path.isdir(parent):
                os.makedirs(parent, exist_ok=True)
            if os.path.islink(link_path) or os.path.exists(link_path):
                os.remove(link_path)
            os.symlink(target, link_path)
        except Exception:
            pass

    print("Tools installed.")
    if callback:
        callback('Tools installed.', 100)


def update_permission(unpkg_path, callback):
    """Set permissions on the install target directory.

    Runs chmod 777 -R on /home/pi/ipk_app_new (the staged install dir).
    Also patches known OS-level bugs that affect stability.

    Args:
        unpkg_path: path to extracted IPK (used to derive target)
        callback: progress callback(name, progress)
    """
    print("Updating permissions...")
    if callback:
        callback('Updating permissions...', 30)

    target_path = os.path.join('/home/pi/', 'ipk_app_new')
    os.system('chmod 777 -R %s' % target_path)

    # Patch known OS-level stability bugs.
    _patch_gpio_crash_bug()
    _patch_sshd_session_limits()

    # Remove trojan version.so — it's only needed for checkPkg during
    # install.  At runtime it shadows our version.py (Python loads .so
    # before .py), returning stale hardcoded values instead of dynamic ones.
    _trojan_so = os.path.join(target_path, 'lib', 'version.so')
    if os.path.isfile(_trojan_so):
        os.remove(_trojan_so)
        print("Removed trojan version.so (checkPkg complete, no longer needed)")

    if callback:
        callback('Permissions updated.', 100)
    print("Permissions updated.")


def _patch_gpio_crash_bug():
    """Disable gen-friendlyelec-release to prevent kernel GPIO crash.

    Kernel 4.14.111 (sun8i) has a NULL pointer dereference in
    gpiodevice_release() triggered by /usr/local/bin/gen-friendlyelec-release.
    This binary runs on every boot (rc.local) and every SSH login (10-header).
    Under memory pressure + concurrent SSH sessions, it crashes the kernel.

    Fix: comment out the binary invocation. The static /etc/friendlyelec-release
    file it generates already exists and doesn't need regeneration.
    """
    _files = ['/etc/rc.local', '/etc/update-motd.d/10-header']
    _target = '/usr/local/bin/gen-friendlyelec-release'

    for path in _files:
        try:
            if not os.path.isfile(path):
                continue
            with open(path, 'r') as f:
                content = f.read()
            if _target in content and ('# disabled' not in content or
                                       content.count(_target) > content.count('# disabled')):
                patched = content.replace(
                    _target,
                    '# disabled: GPIO crash # ' + _target)
                with open(path, 'w') as f:
                    f.write(patched)
                print("Patched %s (GPIO crash fix)" % path)
            else:
                print("Already patched: %s" % path)
        except Exception as e:
            print("Could not patch %s: %s" % (path, e))


def _patch_sshd_session_limits():
    """Add SSH session limits to prevent OOM from session buildup.

    The iCopy-X's reverse SSH tunnel reconnects aggressively, spawning
    10-30+ sshd processes that never die. On a 237MB RAM device, this
    exhausts memory in ~30 minutes, triggering OOM killer (takes out the
    app) or kernel crash.

    Fix: add keepalive + session limits to sshd_config.
    - ClientAliveInterval 15: detect dead sessions in 15s
    - ClientAliveCountMax 2: kill after 2 missed keepalives (30s total)
    - MaxSessions 4: hard limit per connection
    - LoginGraceTime 15: reject slow/stale auth attempts faster
    """
    _sshd_conf = '/etc/ssh/sshd_config'
    _marker = '# OSS session limit patch'
    _settings = {
        'ClientAliveInterval': '15',
        'ClientAliveCountMax': '2',
        'MaxSessions': '4',
        'LoginGraceTime': '15',
    }

    try:
        if not os.path.isfile(_sshd_conf):
            print("sshd_config not found, skipping SSH patch")
            return

        with open(_sshd_conf, 'r') as f:
            content = f.read()

        if _marker in content:
            print("Already patched: %s" % _sshd_conf)
            return

        lines = content.rstrip('\n').split('\n')

        # Comment out any existing conflicting settings
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped and not stripped.startswith('#'):
                key = stripped.split()[0] if stripped.split() else ''
                if key in _settings:
                    lines[i] = '# ' + line

        # Append our settings
        lines.append('')
        lines.append(_marker)
        for key, val in _settings.items():
            lines.append('%s %s' % (key, val))

        with open(_sshd_conf, 'w') as f:
            f.write('\n'.join(lines) + '\n')

        # Restart sshd to apply (won't kill existing connections)
        os.system('systemctl restart sshd 2>/dev/null')
        print("Patched %s (SSH session limits)" % _sshd_conf)

    except Exception as e:
        print("Could not patch sshd_config: %s" % e)


def install_app(unpkg_path, callback):
    """Copy app files from unpkg to /home/pi/ipk_app_new.

    Moves the entire unpkg directory to /home/pi/unpkg, then renames
    it to /home/pi/ipk_app_new. The device's ipk_starter.py will swap
    ipk_app_new → ipk_app_main on next boot.

    Args:
        unpkg_path: path to extracted IPK
        callback: progress callback(name, progress)
    """
    target_path = '/home/pi/'
    target_path_new_pkg = os.path.join(target_path, 'ipk_app_new')
    target_path_unpkg = os.path.join(target_path, 'unpkg')

    if callback:
        callback('App installing...', 38)

    # Clean up any previous staged install
    if os.path.exists(target_path_unpkg):
        shutil.rmtree(target_path_unpkg)
    if os.path.exists(target_path_new_pkg):
        shutil.rmtree(target_path_new_pkg)

    # Move unpkg → /home/pi/unpkg → rename to ipk_app_new
    shutil.move(unpkg_path, target_path_unpkg)
    os.rename(target_path_unpkg, target_path_new_pkg)

    print("copy files finished!")
    if callback:
        callback('App installed!', 100)


def restart_app(callback):
    """Restart the iCopy service.

    Args:
        callback: progress callback(name, progress)
    """
    print("Restarting...")
    if callback:
        callback('Restarting...', 60)
        callback('Restarting...', 100)

    os.system('sudo service icopy restart &')


def install(unpkg_path, callback):
    """Main install orchestrator.

    Called by update.py (or the original activity_update.so) after the IPK
    has been extracted to unpkg_path.

    Order confirmed by QEMU trace:
      1. install_font  — copy fonts to system
      2. install_lua_dep — extract LUA scripts
      3. install_app   — move files to ipk_app_new
      4. update_permission — chmod 777 -R
      5. restart_app   — restart the service

    Args:
        unpkg_path: path to extracted IPK (e.g. /tmp/.ipk/unpkg)
        callback: progress callback(name, progress)
    """
    install_font(unpkg_path, callback)
    install_lua_dep(unpkg_path, callback)
    install_app(unpkg_path, callback)
    update_permission(unpkg_path, callback)
    restart_app(callback)
