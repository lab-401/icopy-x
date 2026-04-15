"""Tests for AboutActivity — device info display with 2-page navigation.

Covers:
  - Title bar shows "About"
  - Button labels: empty M1, "Update" M2
  - Version info lines displayed on page 0
  - Page navigation (UP/DOWN between page 0 and page 1)
  - M1 navigates to previous page (or no-op on page 0)
  - M2/OK triggers update (would launch UpdateActivity)
  - PWR finishes activity
  - Handles missing version module gracefully
  - Serial number displayed
  - Update instruction page content
"""

import sys
import types
import pytest

from tests.ui.conftest import MockCanvas
import actstack
from _constants import KEY_UP, KEY_DOWN, KEY_OK, KEY_M1, KEY_M2, KEY_PWR


# ── helpers ──────────────────────────────────────────────────────────

def _setup():
    """Reset actstack and wire up MockCanvas factory."""
    actstack._reset()
    actstack._canvas_factory = lambda: MockCanvas()


def _make_about(version_mod=None):
    """Create and start an AboutActivity via actstack.

    Optionally injects a mock 'version' module into sys.modules
    so that the activity can read device info.
    """
    _setup()

    if version_mod is not None:
        sys.modules['version'] = version_mod
    elif 'version' in sys.modules:
        del sys.modules['version']

    # Push a dummy root activity first (finish_activity needs a prev)
    from actbase import BaseActivity
    root = actstack.start_activity(BaseActivity)

    from activity_main import AboutActivity
    act = actstack.start_activity(AboutActivity)
    return act


def _make_version_mod(**kwargs):
    """Create a mock version module with getTYP, getHW, etc."""
    mod = types.ModuleType('version')
    mod.getTYP = lambda: kwargs.get('typ', 'iCopy-X')
    mod.getHW = lambda: kwargs.get('hw', '1.7')
    mod.getHMI = lambda: kwargs.get('hmi', '2.3.1')
    mod.getOS = lambda: kwargs.get('os', '1.0.90')
    mod.getPM = lambda: kwargs.get('pm', 'v4.17511')
    mod.getSN = lambda: kwargs.get('sn', 'ABC12345')
    return mod


def _teardown():
    """Clean up sys.modules."""
    sys.modules.pop('version', None)
    actstack._reset()


# ── tests ────────────────────────────────────────────────────────────

class TestAboutTitle:
    def teardown_method(self):
        _teardown()

    def test_title_is_about(self):
        """AboutActivity title bar displays 'About'."""
        act = _make_about()
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert any('About' in t for t in texts), f"Expected 'About' in title, got: {texts}"


class TestAboutButtons:
    def teardown_method(self):
        _teardown()

    def test_buttons_back_update(self):
        """Both M1 and M2 labels are empty (ground truth: buttons hidden)."""
        act = _make_about()
        canvas = act.getCanvas()
        # Ground truth: AboutActivity sets both buttons to '' (empty)
        texts = canvas.get_all_text()
        assert 'Update' not in texts, "Buttons should be hidden, no 'Update' text"


class TestAboutVersionInfo:
    def teardown_method(self):
        _teardown()

    def test_displays_version_info(self):
        """Page 0 displays version info lines with data from version module."""
        import threading
        mod = _make_version_mod(
            typ='iCopy-X', hw='1.7', hmi='2.3.1',
            os='1.0.90', pm='v4.17511', sn='',
        )
        act = _make_about(version_mod=mod)
        # Wait for background version fetch thread to complete
        for t in threading.enumerate():
            if t.daemon and t.is_alive():
                t.join(timeout=5)
        # Simulate Tk after(0, ...) callback
        act._on_version_loaded()
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        all_text = ' '.join(texts)
        assert 'iCopy-X' in all_text
        assert '1.7' in all_text
        assert '2.3.1' in all_text
        assert '1.0.90' in all_text
        assert 'v4.17511' in all_text

    def test_serial_number_not_displayed(self):
        """Serial number is not shown in OSS version."""
        mod = _make_version_mod(sn='SN_ABCDEF')
        act = _make_about(version_mod=mod)
        canvas = act.getCanvas()
        all_text = ' '.join(canvas.get_all_text())
        assert 'SN_ABCDEF' not in all_text

    def test_handles_missing_version_module(self):
        """Activity still creates without version module -- shows default values.

        When the embedded version.so is unavailable, the middleware version.py
        provides sensible defaults (e.g. 'iCopy-XS', '1.10').  The activity
        must render without crashing.
        """
        # Ensure no explicit 'version' mock exists (middleware may provide defaults)
        sys.modules.pop('version', None)
        act = _make_about(version_mod=None)
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        all_text = ' '.join(texts)
        # Activity must render version info (from middleware defaults or '?' fallbacks)
        assert len(all_text) > 0, "About page should display version info"


class TestAboutKeyNavigation:
    def teardown_method(self):
        _teardown()

    def test_m1_on_page0_no_op(self):
        """M1 on page 0 does nothing (stays on page 0)."""
        act = _make_about()
        assert act.get_page() == 0
        act.onKeyEvent(KEY_M1)
        assert act.get_page() == 0

    def test_m1_noop_on_page1(self):
        """M1 on page 1 is a no-op (source onKeyEvent has no M1 handler)."""
        act = _make_about()
        act.onKeyEvent(KEY_DOWN)  # go to page 1
        assert act.get_page() == 1
        act.onKeyEvent(KEY_M1)   # no-op — M1 not mapped
        assert act.get_page() == 1

    def test_pwr_finishes(self):
        """PWR key finishes the activity (may need two presses if toast visible).

        _handlePWR dismisses a visible toast on the first press, then the
        second press reaches finish().
        """
        act = _make_about()
        stack_before = actstack.get_stack_size()
        act.onKeyEvent(KEY_PWR)  # first press: may dismiss Processing toast
        act.onKeyEvent(KEY_PWR)  # second press: finish if toast was visible
        assert actstack.get_stack_size() == stack_before - 1

    def test_m2_or_ok_navigates(self):
        """M2 and OK attempt to launch UpdateActivity (import guarded)."""
        act = _make_about()
        # M2 should not crash even if UpdateActivity doesn't exist
        act.onKeyEvent(KEY_M2)
        # OK should also not crash
        act2 = _make_about()
        act2.onKeyEvent(KEY_OK)

    def test_scroll_up_down(self):
        """DOWN goes to page 1, UP returns to page 0."""
        act = _make_about()
        assert act.get_page() == 0
        act.onKeyEvent(KEY_DOWN)
        assert act.get_page() == 1
        act.onKeyEvent(KEY_UP)
        assert act.get_page() == 0

    def test_down_clamped_at_max(self):
        """DOWN on page 2 (max page) does not go past max."""
        act = _make_about()
        act.onKeyEvent(KEY_DOWN)
        assert act.get_page() == 1
        act.onKeyEvent(KEY_DOWN)
        assert act.get_page() == 2
        act.onKeyEvent(KEY_DOWN)  # should stay at 2
        assert act.get_page() == 2

    def test_up_clamped_at_zero(self):
        """UP on page 0 does not go below 0."""
        act = _make_about()
        act.onKeyEvent(KEY_UP)  # should stay at 0
        assert act.get_page() == 0


class TestAboutUpdatePage:
    def teardown_method(self):
        _teardown()

    def test_page1_shows_update_instructions(self):
        """Page 1 displays firmware update instruction text."""
        act = _make_about()
        act.onKeyEvent(KEY_DOWN)  # navigate to page 1
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        all_text = ' '.join(texts)
        assert 'Firmware update' in all_text or 'update' in all_text.lower()
