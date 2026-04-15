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

"""Top-level conftest — shared pytest configuration."""

import sys
import os

def pytest_addoption(parser):
    parser.addoption(
        "--target",
        choices=["current", "original"],
        default="current",
        help="Which implementation to test: 'current' (src/lib) or 'original' (.so)",
    )


def pytest_configure(config):
    target = config.getoption("--target", default="current")
    if target == "current":
        lib_path = os.path.join(os.path.dirname(__file__), "src", "lib")
        if lib_path not in sys.path:
            sys.path.insert(0, lib_path)
        # Also add src/ so 'from lib.X import Y' works (source modules use
        # package-qualified imports internally).  The lib.__init__.py dedup
        # hook ensures 'lib.X' and 'X' share the same module object.
        src_path = os.path.join(os.path.dirname(__file__), "src")
        if src_path not in sys.path:
            sys.path.insert(0, src_path)

        # Add src/middleware so deferred imports of scan, erase, update,
        # executor resolve to the OSS Python reimplementations.
        mw_path = os.path.join(os.path.dirname(__file__), "src", "middleware")
        if mw_path not in sys.path:
            sys.path.insert(0, mw_path)

        # Pre-load core modules as bare imports so the dedup hook in
        # lib/__init__.py can alias 'lib.X' -> 'X' when activity code
        # later does 'from lib.X import ...'.  This prevents the dual-
        # module identity bug where test code and activity code get
        # different module objects for the same .py file.
        import _constants       # noqa: F401
        import actstack         # noqa: F401
        import actbase          # noqa: F401
        import widget           # noqa: F401
        import resources        # noqa: F401
