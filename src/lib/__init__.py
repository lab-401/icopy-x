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

"""lib package — dedup hook for dual sys.path (src + src/lib).

When both ``src/`` and ``src/lib/`` are on ``sys.path``, the same .py file
can be imported under two names (``actstack`` vs ``lib.actstack``), creating
two independent module objects.  This breaks singleton state such as
``actstack._canvas_factory``.

The import hook below ensures that ``lib.<name>`` and ``<name>`` always
resolve to the **same** module object.
"""

import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import os
import sys


# Names of modules that live in src/lib/ (auto-detected at import time).
_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
_LIB_MODULES = frozenset(
    f[:-3] for f in os.listdir(_LIB_DIR)
    if f.endswith(".py") and f != "__init__.py"
)


class _AliasLoader(importlib.abc.Loader):
    """Loader that returns an already-loaded module from sys.modules."""

    def __init__(self, source_name):
        self._source_name = source_name

    def create_module(self, spec):
        return sys.modules[self._source_name]

    def exec_module(self, module):
        # Module is already fully loaded — nothing to execute.
        pass


class _LibDedup(importlib.abc.MetaPathFinder):
    """Unifies ``lib.<name>`` with bare ``<name>`` modules.

    Handles both directions:
      1. ``lib.X`` requested, bare ``X`` already loaded -> alias.
      2. bare ``X`` requested, ``lib.X`` already loaded -> alias.
    """

    def find_spec(self, fullname, path, target=None):
        # Direction 1: lib.X -> X
        if fullname.startswith("lib.") and fullname.count(".") == 1:
            bare = fullname[4:]
            if bare in sys.modules and fullname not in sys.modules:
                return importlib.util.spec_from_loader(
                    fullname, _AliasLoader(bare))

        # Direction 2: bare X -> lib.X
        if "." not in fullname and fullname in _LIB_MODULES:
            qualified = f"lib.{fullname}"
            if qualified in sys.modules and fullname not in sys.modules:
                return importlib.util.spec_from_loader(
                    fullname, _AliasLoader(qualified))

        return None


# Install once at package init time.
if not any(isinstance(f, _LibDedup) for f in sys.meta_path):
    sys.meta_path.insert(0, _LibDedup())
