"""ProgressBar must survive its canvas being destroyed while it is animating.

Regression test for the field symptom: pressing exit during Auto Copy left
``Exception in Tkinter callback ... TclError: invalid command name ".!canvas2"``
in widget._redraw, and then ``Exception in thread Thread-3`` because scan.so's
error path calls ``ProgressBar.complete()`` on the same dead widget.

Tk ``after()`` timers outlive the widget they were scheduled from, so both
paths can reach a destroyed canvas.  Losing the canvas has to be terminal, never
fatal.
"""

import pytest

from lib import widget as widget_mod
from lib.widget import ProgressBar


class Canvas:
    """Canvas double that dies like a real tkinter one.

    tkinter raises TclError from ``winfo_exists()`` (and every other call) once
    the widget is destroyed, which is exactly what we reproduce here.
    """

    def __init__(self):
        self.alive = True
        self.items = {}
        self.next_id = 1
        self.timers = {}
        self.next_timer = 1
        self.ops = 0
        # Fail drawing while the widget still reports that it exists - the
        # state a real Tk canvas is in when its item commands were torn down
        # but the window path survives long enough to answer winfo_exists().
        self.render_error = False

    # -- lifecycle ---------------------------------------------------
    def _guard(self):
        if not self.alive:
            raise widget_mod._TclError('invalid command name ".!canvas2"')

    def destroy(self):
        self.alive = False

    def winfo_exists(self):
        self._guard()
        return 1

    # -- timers ------------------------------------------------------
    def after(self, ms, func=None, *args):
        self._guard()
        timer_id = 'after#%d' % self.next_timer
        self.next_timer += 1
        self.timers[timer_id] = (func, args)
        return timer_id

    def after_cancel(self, timer_id):
        self._guard()
        self.timers.pop(timer_id, None)

    def run_pending(self):
        """Fire every scheduled timer (one pass, like the Tk event loop)."""
        timers, self.timers = self.timers, {}
        for func, args in timers.values():
            func(*args)

    # -- drawing -----------------------------------------------------
    def _draw_guard(self):
        self._guard()
        if self.render_error:
            raise widget_mod._TclError('bad window path name ".!canvas2"')

    def create_rectangle(self, *args, **kwargs):
        self._draw_guard()
        self.ops += 1
        item_id = self.next_id
        self.next_id += 1
        self.items[item_id] = kwargs.get('tags', ())
        return item_id

    def create_text(self, *args, **kwargs):
        return self.create_rectangle(*args, **kwargs)

    def find_withtag(self, tag):
        self._guard()
        return [i for i, tags in self.items.items()
                if tags == tag or (isinstance(tags, (tuple, list)) and tag in tags)]

    def coords(self, *args, **kwargs):
        self._draw_guard()
        self.ops += 1

    def itemconfig(self, *args, **kwargs):
        self._draw_guard()
        self.ops += 1

    def delete(self, tag):
        self._draw_guard()
        self.ops += 1
        for item_id in self.find_withtag(tag):
            self.items.pop(item_id, None)


@pytest.fixture
def bar():
    canvas = Canvas()
    progress = ProgressBar(canvas)
    progress.show()
    return progress, canvas


def test_progress_update_after_canvas_destroyed_does_not_raise(bar):
    progress, canvas = bar
    progress.setProgress(40)
    ops_before = canvas.ops

    canvas.destroy()          # activity popped out from under us

    progress.setProgress(90)  # must not raise
    progress.setMessage('later')
    assert canvas.ops == ops_before, 'dead canvas must not be touched'


def test_animation_in_flight_stops_when_canvas_dies(bar):
    progress, canvas = bar
    progress.setProgress(100)               # 10 steps of animation scheduled
    assert canvas.timers, 'animation should have queued a step'

    canvas.destroy()
    canvas.run_pending()                    # the stale step still fires

    assert progress._dead, 'bar should go terminal after losing its canvas'


def test_complete_does_not_fire_callback_when_canvas_gone(bar):
    progress, canvas = bar
    progress.setProgress(30)
    canvas.destroy()

    fired = []
    progress.complete(lambda: fired.append(True))

    assert fired == [], 'transition callback must not run on a dead screen'


def test_hide_and_dispose_are_safe_after_destroy(bar):
    progress, canvas = bar
    canvas.destroy()

    progress.hide()      # must not raise
    progress.dispose()   # must not raise
    assert progress._dead


def test_complete_does_not_fire_the_callback_when_the_redraw_fails(bar):
    """A full bar whose drawing raises must go terminal *and* stay silent.

    Field path: ``scan.so`` calls complete() when a scan ends. If the screen is
    being torn down, winfo_exists() can still answer while the canvas refuses
    to draw; the failed redraw makes the bar terminal, so the transition must
    not run on the screen the caller is leaving.
    """
    progress, canvas = bar
    progress._setProgressImmediate(progress.getMax())   # already full, shown
    canvas.render_error = True                          # existence still answers

    fired = []
    progress.complete(lambda: fired.append(True))

    assert progress._dead, 'a failed redraw has to be terminal'
    assert fired == [], 'the callback must not follow the bar into the teardown'


def test_complete_fires_exactly_once_for_a_live_full_bar(bar):
    """The suppression above must not eat a legitimate completion."""
    progress, canvas = bar
    progress._setProgressImmediate(progress.getMax())

    fired = []
    progress.complete(lambda: fired.append(True))

    assert fired == [True]
    assert not progress._dead


def test_complete_fires_for_a_hidden_bar_whose_canvas_is_alive(bar):
    """hide() is a visual change; it keeps the completion callback."""
    progress, canvas = bar
    progress.hide()

    fired = []
    progress.complete(lambda: fired.append(True))

    assert fired == [True]


def test_a_real_tk_canvas_teardown_suppresses_completion():
    """Real Tk: a destroyed child answers winfo_exists() with 0, not TclError."""
    tk = pytest.importorskip('tkinter')
    try:
        root = tk.Tk()
    except Exception as exc:            # no display (CI)
        pytest.skip('no display: %s' % exc)
    try:
        root.withdraw()
        canvas = tk.Canvas(root)
        progress = ProgressBar(canvas)
        progress.show()

        canvas.destroy()

        fired = []
        progress.complete(lambda: fired.append(True))

        assert progress._dead
        assert fired == []
    finally:
        try:
            root.destroy()
        except Exception:
            pass
