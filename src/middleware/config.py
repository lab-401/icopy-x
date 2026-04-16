##########################################################################
# Required Notice: Copyright ETOILE401 SAS (http://www.lab401.com)
#
# Initial author: ETOILE401 SAS & https://github.com/quantum-x/ as of April 16, 2026
#
# Since this date, each contribution is under the copyright of its respective author.
#
# Copyright of each contribution is tracked by the Git history. See the output of git shortlog -nse for a full list or git log --pretty=short --follow <path/to/sourcefile> |git shortlog -ne to track a specific file.
#
# A mailmap is maintained to map author and committer names and email addresses to canonical names and email addresses.
# If by accident a copyright was removed from a file and is not directly deducible from the Git history, please submit a PR.
#
#
# This software is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this software for commercial purposes.
#
# A copy of the license is available at:
# https://polyformproject.org/licenses/noncommercial/1.0.0
#
# This entire header "Required Notice" must remain in place.
##########################################################################

"""Configuration persistence via conf.ini.

OSS reimplementation of config.so.
Binary source: config.so (Cython, configparser + os)
Ground truth: V1090_MODULE_AUDIT.txt lines 314-326

Functions:
    getConf()              — read all config as dict
    getValue(key, default) — read single key
    setConf(conf)          — write entire config dict
    setKeyValue(k, v)      — write single key-value pair

Storage: /mnt/sdcard/root2/root/home/pi/ipk_app_main/data/conf.ini
Section: [DEFAULT]
"""

import configparser
import os

# Default settings from original config.so constants
DEFAULT_SETTINGS = {'backlight': '2', 'volume': '2', 'screen_mirror': '0'}

# Config file path — same as original firmware
_CONF_PATH = '/mnt/sdcard/root2/root/home/pi/ipk_app_main/data/conf.ini'


def _read_config():
    """Read conf.ini into a configparser object."""
    cp = configparser.ConfigParser()
    if os.path.exists(_CONF_PATH):
        cp.read(_CONF_PATH)
    return cp


def _write_config(cp):
    """Write configparser object back to conf.ini."""
    conf_dir = os.path.dirname(_CONF_PATH)
    if not os.path.isdir(conf_dir):
        os.makedirs(conf_dir, exist_ok=True)
    with open(_CONF_PATH, 'w') as f:
        cp.write(f)


def getConf():
    """Read all config values as a dict.

    Returns dict of all keys in [DEFAULT] section.
    """
    cp = _read_config()
    result = dict(DEFAULT_SETTINGS)
    if cp.defaults():
        result.update(dict(cp.defaults()))
    return result


def getValue(key, default=None):
    """Read a single config value by key.

    Args:
        key: config key name (e.g. 'backlight', 'volume')
        default: fallback if key not found

    Returns:
        str: the config value, or default
    """
    cp = _read_config()
    try:
        return cp.get('DEFAULT', key)
    except (configparser.NoSectionError, configparser.NoOptionError):
        if default is not None:
            return default
        return DEFAULT_SETTINGS.get(key)


def setConf(conf):
    """Write entire config dict to conf.ini.

    Args:
        conf: dict of key-value pairs to write
    """
    cp = configparser.ConfigParser()
    for k, v in conf.items():
        cp.set('DEFAULT', k, str(v))
    _write_config(cp)


def setKeyValue(k, v):
    """Write a single key-value pair to conf.ini.

    Args:
        k: config key name
        v: value to write (will be converted to string)
    """
    cp = _read_config()
    cp.set('DEFAULT', k, str(v))
    _write_config(cp)
