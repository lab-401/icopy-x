# install.so — Complete String & Function Analysis

Source: `/home/pi/ipk_app_main/main/install.so` (98,188 bytes, ARM ELF32)
Compiled with: Cython 0.29.23, GCC Linaro 7.5
Original source: `C:\Users\ADMINI~1\AppData\Local\Temp\1\tmptkzydnoh\install.py`

## Functions (6 exported, module-level)

| Function | Address | Signature |
|----------|---------|-----------|
| `install_font` | 0x000166e4 | `install_font(unpkg_path, callback)` |
| `install_lua_dep` | 0x00019768 | `install_lua_dep(unpkg_path, callback)` |
| `update_permission` | 0x00015cbc | `update_permission(unpkg_path, callback)` |
| `install_app` | 0x0001b348 | `install_app(unpkg_path, callback)` |
| `restart_app` | 0x0001541c | `restart_app(callback)` |
| `install` | 0x0001d370 | `install(unpkg_path, callback)` — orchestrator |

## Callback Messages (Ground Truth — from binary strings + framebuffer captures)

### install_font(unpkg_path, callback)
Copies fonts from `unpkg_path/res/font/*.ttf` to device font directory.
Runs `sudo fc-cache -fsv` after copying.

| Condition | Callback message |
|-----------|-----------------|
| Fonts found, installing | `" Font will install..."` (note leading space) |
| Fonts installed | `" Font installed."` (note leading space) |
| No fonts to install | `"No Font can install."` |

### update_permission(unpkg_path, callback)
Runs `chmod 777 -R {}` on unpkg_path.

| Condition | Callback message |
|-----------|-----------------|
| Running | `"Permission Updating..."` |

### install_lua_dep(unpkg_path, callback)
Extracts lua.zip, copies lualibs and luascripts.

| Condition | Callback message |
|-----------|-----------------|
| Installing | `"LUA dep installing..."` |
| Already exists | `"LUA dep exists..."` |
| Done | `"LUA dep install done."` |
| lua.zip not found | `"lua.zip no found..."` (sic — original typo) |

### install_app(unpkg_path, callback)
Moves unpkg files to `/home/pi/ipk_app_new`.

| Condition | Callback message |
|-----------|-----------------|
| Installing | `"App installing..."` |
| Done | `"App installed!"` |
| Files copied | `"copy files finished!"` |

### restart_app(callback)
Calls `sudo service icopy restart &`.

| Condition | Callback message |
|-----------|-----------------|
| Restarting | `"App restarting..."` |

## Execution Order (confirmed by framebuffer capture 2026-04-10)

The `install()` orchestrator calls functions in this order:

```
1. install_font(unpkg_path, callback)
2. update_permission(unpkg_path, callback)
3. install_lua_dep(unpkg_path, callback)
4. install_app(unpkg_path, callback)
5. restart_app(callback)
```

## Internal Variables

| Variable | Purpose |
|----------|---------|
| `unpkg_path` | Source directory (extracted IPK) |
| `unpkg_path_name` | Name portion of path |
| `target_path` | Destination base path |
| `target_path_new_pkg` | `/home/pi/ipk_app_new` |
| `target_path_unpkg` | Unpacked target path |
| `source_font_path` | Font source directory |
| `source_font_file` | Individual font file |
| `target_font_path` | Font destination directory |
| `old_fonts` | Existing font list |
| `new_fonts` | New font list |
| `new_font` | Individual new font |
| `font_suffix` | `.ttf` extension check |
| `font_install` | Font install flag |
| `font_no_install_list` | Fonts that couldn't install |
| `path_lua_zip` | Path to lua.zip |
| `path_lua_libs` | Lua libs destination |
| `path_lua_scripts` | Lua scripts destination |
| `dir_lualibs` | `lualibs` directory name |
| `dir_luascripts` | `luascripts` directory name |
| `path_upan` | `/mnt/upan` base path |

## System Commands

| Command | Used by |
|---------|---------|
| `sudo fc-cache -fsv` | `install_font()` — refreshes font cache |
| `chmod 777 -R {}` | `update_permission()` — via `format()` + `os.system()` |
| `sudo service icopy restart &` | `restart_app()` — via `os.system()` |

## Imports

`shutil` (copy, move, rmtree, rename), `os` (system, exists, listdir, isfile, path.join, path.split, path.basename), `time` (sleep), `zipfile` (unpack_archive)
