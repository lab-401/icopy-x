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

"""About Scroller — embedded version for the iCopy-X About easter egg.

Adapted from the standalone scroller at /home/qx/scroller/scroller.py.
Renders a parallax auto-scrolling scene with sprites, animated GIFs,
a contributor list, and a fade-to-white ending into a tkinter Canvas
widget that is embedded into the About activity via create_window().

Assets live in res/about/ (spritesheet, animated GIFs, canvas background,
contributors.txt).
"""

import os
import sys
import time
import tkinter as tk

from PIL import Image, ImageTk

# ── Asset directory resolution ───────────────────────────────────
def _find_about_dir():
    """Find the res/about directory at dev time or on the device."""
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, '..', '..', 'res', 'about'),
        os.path.join(os.getcwd(), 'res', 'about'),
        '/E/res/about',
    ]
    for p in sys.path:
        candidates.append(os.path.join(p, 'res', 'about'))
        candidates.append(os.path.join(p, '..', 'res', 'about'))
    for c in candidates:
        norm = os.path.normpath(c)
        if os.path.isdir(norm):
            return norm
    return os.path.normpath(os.path.join(here, '..', '..', 'res', 'about'))

_ABOUT_DIR = _find_about_dir()

# ── Paths ─────────────────────────────────────────────────────────
SPRITE_DIR = _ABOUT_DIR
CONTRIBUTORS_FILE = os.path.join(_ABOUT_DIR, "contributors.txt")

# ── Viewport & Canvas ─────────────────────────────────────────────
VIEWPORT_WIDTH = 240
VIEWPORT_HEIGHT = 240   # full screen — no title bar on scroller page
CANVAS_WIDTH = 256
CANVAS_HEIGHT = 2250
CROP_LEFT = (CANVAS_WIDTH - VIEWPORT_WIDTH) // 2  # 8px each side

# ── Scrolling ─────────────────────────────────────────────────────
SCROLL_SPEED = 50  # pixels per second
MAX_SCROLL = CANVAS_HEIGHT - VIEWPORT_HEIGHT
SCROLL_START_DELAY = 1.0  # seconds to pause before scrolling begins

# ── Contributors list ─────────────────────────────────────────────
CONTRIBUTORS_START_Y = CANVAS_HEIGHT - 270
CONTRIBUTORS_LINE_HEIGHT = 12
CONTRIBUTORS_DIVIDER_X = 120

# ── Fade out ──────────────────────────────────────────────────────
FADE_DURATION = 1.5
FADE_STEPS = 30

# ── Timing ────────────────────────────────────────────────────────
TARGET_FPS = 60
FRAME_MS = 1000 // TARGET_FPS

# ── Parallax factors ──────────────────────────────────────────────
PARALLAX_FG = 1.08
PARALLAX_BG = 0.95

# ── Plane drift ───────────────────────────────────────────────────
PLANE_DRIFT_SPEED = 10

# ── Sprite sheet ──────────────────────────────────────────────────
SPRITESHEET_FILE = os.path.join(SPRITE_DIR, "spritesheet.png")

SHEET_REGIONS = {
    "sprite-greets.png":       (0, 366, 190, 22),
    "sprite-logo.png":         (0, 282,  47, 47),
    "sprite-plane.png":        (0, 388,  16, 16),
    "sprite-clouds.png":       (0, 189, 256, 93),
    "sprite-roof-overlay.png": (0, 329, 256, 37),
    "sprite-qx.png":           (0, 404,  59,  9),
    "sprite-doegox.png":       (0, 413,  41,  9),
    "sprite-train.png":        (0,   0, 496, 189),
    "sprite-nono.png":         (0, 458,  23,  5),
    "sprite-kombi.png":        (0, 422,  33,  9),
    "sprite-dxl.png":          (0, 431,  23,  9),
    "sprite-proxgrind.png":    (0, 440,  57,  9),
    "sprite-proxmark.png":     (0, 449, 125,  9),
}

# ── Layer types ───────────────────────────────────────────────────
LAYER_FIXED = "fixed"
LAYER_PARALLAX_FG = "parallax_fg"
LAYER_PARALLAX_BG = "parallax_bg"
LAYER_OVERLAY = "overlay"
LAYER_ANIM_GIF = "anim_gif"

# ── X-axis animation types ────────────────────────────────────────
XANIM_NONE = None
XANIM_DRIFT_RIGHT = "drift_right"
XANIM_SWEEP_LEFT = "sweep_left"

# ── GIF animation modes ───────────────────────────────────────────
ANIM_LOOP = "loop"
ANIM_TRIGGERED = "triggered"

# ── Triggers ──────────────────────────────────────────────────────
TRIGGERS = [
    {
        "watch": "sprite-train.png",
        "at_progress": 2 / 3,
        "target": "animated-sprite-metro.gif",
    },
]

# ── Sprite definitions ────────────────────────────────────────────
SPRITE_DEFS = [
    {"file": "animated-sprite-sewer.gif",
     "x": 0, "y": 726, "layer": LAYER_ANIM_GIF, "z": 5, "xanim": XANIM_NONE},
    {"file": "animated-sprite-metro.gif",
     "x": 0, "y": 916, "layer": LAYER_ANIM_GIF, "z": 5, "xanim": XANIM_NONE,
     "anim_mode": ANIM_TRIGGERED},
    {"file": "animated-sprite-cellar.gif",
     "x": 0, "y": 1238, "layer": LAYER_ANIM_GIF, "z": 5, "xanim": XANIM_NONE},
    {"file": "animated-sprite-cave.gif",
     "x": 0, "y": 1622, "layer": LAYER_ANIM_GIF, "z": 5, "xanim": XANIM_NONE},

    {"file": "sprite-clouds.png",
     "x": 0, "y": 384, "layer": LAYER_PARALLAX_FG, "z": 10, "xanim": XANIM_NONE},

    {"file": "sprite-greets.png",
     "x": 41, "y": 47, "layer": LAYER_PARALLAX_FG, "z": 15, "xanim": XANIM_NONE},
    {"file": "sprite-logo.png",
     "x": 105, "y": 203, "layer": LAYER_PARALLAX_FG, "z": 15, "xanim": XANIM_NONE},
    {"file": "sprite-plane.png",
     "x": 113, "y": 332, "layer": LAYER_PARALLAX_BG, "z": 15, "xanim": XANIM_DRIFT_RIGHT},
    {"file": "sprite-qx.png",
     "x": 142, "y": 755, "layer": LAYER_PARALLAX_FG, "z": 15, "xanim": XANIM_NONE},
    {"file": "sprite-doegox.png",
     "x": 111, "y": 981, "layer": LAYER_PARALLAX_FG, "z": 15, "xanim": XANIM_NONE},
    {"file": "sprite-nono.png",
     "x": 118, "y": 1370, "layer": LAYER_FIXED, "z": 15, "xanim": XANIM_NONE},
    {"file": "sprite-kombi.png",
     "x": 181, "y": 1702, "layer": LAYER_PARALLAX_FG, "z": 15, "xanim": XANIM_NONE},
    {"file": "sprite-dxl.png",
     "x": 14, "y": 1750, "layer": LAYER_PARALLAX_FG, "z": 15, "xanim": XANIM_NONE},
    {"file": "sprite-proxgrind.png",
     "x": 117, "y": 1804, "layer": LAYER_PARALLAX_FG, "z": 15, "xanim": XANIM_NONE},
    {"file": "sprite-proxmark.png",
     "x": 66, "y": 1933, "layer": LAYER_PARALLAX_FG, "z": 15, "xanim": XANIM_NONE},

    {"file": "sprite-train.png",
     "x": 0, "y": 940, "layer": LAYER_FIXED, "z": 20, "xanim": XANIM_SWEEP_LEFT,
     "sweep_fraction": 0.25, "enter_fully": True},

    {"file": "sprite-roof-overlay.png",
     "x": 0, "y": 454, "layer": LAYER_OVERLAY, "z": 25, "xanim": XANIM_NONE},
]


# ═════════════════════════════════════════════════════════════════
# Sprite classes
# ═════════════════════════════════════════════════════════════════

_spritesheet = None


def _get_spritesheet():
    """Lazy-load the sprite sheet on first access."""
    global _spritesheet
    if _spritesheet is None:
        _spritesheet = Image.open(SPRITESHEET_FILE).convert("RGBA")
    return _spritesheet


def parallax_factor_for_layer(layer):
    if layer == LAYER_PARALLAX_FG:
        return PARALLAX_FG
    if layer == LAYER_PARALLAX_BG:
        return PARALLAX_BG
    return 1.0


def calc_screen_y(canvas_y, scroll_offset, parallax_factor):
    base_y = canvas_y - scroll_offset
    if parallax_factor == 1.0:
        return base_y
    centre = VIEWPORT_HEIGHT / 2.0
    return base_y + (base_y - centre) * (parallax_factor - 1.0)


def calc_plane_x(base_canvas_x, view_enter_time, elapsed_time):
    if view_enter_time is None:
        return base_canvas_x - CROP_LEFT
    dt = elapsed_time - view_enter_time
    return base_canvas_x + dt * PLANE_DRIFT_SPEED - CROP_LEFT


def calc_train_x(sprite_width, canvas_y, sprite_height,
                 view_enter_time, elapsed_time, sweep_fraction=0.5):
    if view_enter_time is None:
        return CANVAS_WIDTH
    enter_scroll = canvas_y - VIEWPORT_HEIGHT
    exit_scroll = canvas_y + sprite_height
    total_view_time = (exit_scroll - enter_scroll) / SCROLL_SPEED
    sweep_duration = total_view_time * sweep_fraction
    t = elapsed_time - view_enter_time
    progress = min(1.0, t / sweep_duration) if sweep_duration > 0 else 1.0
    start_x = CANVAS_WIDTH
    end_x = -sprite_width
    return start_x + (end_x - start_x) * progress - CROP_LEFT


def calc_sweep_progress(sprite_width, canvas_y, sprite_height,
                        view_enter_time, elapsed_time, sweep_fraction=0.5):
    if view_enter_time is None:
        return None
    enter_scroll = canvas_y - VIEWPORT_HEIGHT
    exit_scroll = canvas_y + sprite_height
    total_view_time = (exit_scroll - enter_scroll) / SCROLL_SPEED
    sweep_duration = total_view_time * sweep_fraction
    t = elapsed_time - view_enter_time
    return min(1.0, t / sweep_duration) if sweep_duration > 0 else 1.0


class Sprite:
    def __init__(self, definition, canvas=None):
        self.canvas_x = definition["x"]
        self.canvas_y = definition["y"]
        self.layer = definition["layer"]
        self.z = definition["z"]
        self.xanim = definition.get("xanim")
        self.file = definition["file"]
        self.parallax = parallax_factor_for_layer(self.layer)
        self.sweep_fraction = definition.get("sweep_fraction", 0.5)
        self.enter_fully = definition.get("enter_fully", False)
        self.in_view = False
        self.view_enter_time = None
        self._last_elapsed = 0.0
        self._load_assets()
        self._init_canvas(canvas)

    def _load_assets(self):
        region = SHEET_REGIONS.get(self.file)
        if region is not None:
            rx, ry, rw, rh = region
            self.pil_image = _get_spritesheet().crop((rx, ry, rx + rw, ry + rh))
        else:
            path = os.path.join(SPRITE_DIR, self.file)
            self.pil_image = Image.open(path).convert("RGBA")
        self.width = self.pil_image.width
        self.height = self.pil_image.height

    def _init_canvas(self, canvas):
        self._canvas = canvas
        self._canvas_id = None
        if canvas is not None:
            self._photo = ImageTk.PhotoImage(self.pil_image)
            self._canvas_id = canvas.create_image(
                -1000, -1000, image=self._photo, anchor="nw",
            )

    def screen_pos(self, scroll_offset, elapsed_time):
        sy = calc_screen_y(self.canvas_y, scroll_offset, self.parallax)
        if self.xanim == XANIM_DRIFT_RIGHT:
            sx = calc_plane_x(self.canvas_x, self.view_enter_time, elapsed_time)
        elif self.xanim == XANIM_SWEEP_LEFT:
            sx = calc_train_x(
                self.width, self.canvas_y, self.height,
                self.view_enter_time, elapsed_time, self.sweep_fraction,
            )
        else:
            sx = self.canvas_x - CROP_LEFT
        return sx, sy

    @property
    def sweep_progress(self):
        if self.xanim != XANIM_SWEEP_LEFT:
            return None
        return calc_sweep_progress(
            self.width, self.canvas_y, self.height,
            self.view_enter_time, self._last_elapsed, self.sweep_fraction,
        )

    def is_visible(self, scroll_offset):
        base_y = self.canvas_y - scroll_offset
        margin = 20
        return (base_y + self.height > -margin) and (base_y < VIEWPORT_HEIGHT + margin)

    def is_fully_visible(self, scroll_offset):
        base_y = self.canvas_y - scroll_offset
        return base_y >= 0 and (base_y + self.height) <= VIEWPORT_HEIGHT

    def update(self, scroll_offset, elapsed_time, dt_ms):
        self._last_elapsed = elapsed_time
        visible = self.is_visible(scroll_offset)
        if visible and not self.in_view:
            self.in_view = True
            if not self.enter_fully:
                self.view_enter_time = elapsed_time
        elif not visible and self.in_view:
            self.in_view = False
            self.view_enter_time = None
        if self.enter_fully and self.in_view and self.view_enter_time is None:
            if self.is_fully_visible(scroll_offset):
                self.view_enter_time = elapsed_time
        if self._canvas is None:
            return
        if visible:
            sx, sy = self.screen_pos(scroll_offset, elapsed_time)
            self._canvas.coords(self._canvas_id, sx, sy)
        else:
            self._canvas.coords(self._canvas_id, -1000, -1000)


class AnimatedGifSprite(Sprite):
    def __init__(self, definition, canvas=None):
        self.anim_mode = definition.get("anim_mode", ANIM_LOOP)
        self._triggered = False
        self._play_finished = False
        super().__init__(definition, canvas)

    def _load_assets(self):
        path = os.path.join(SPRITE_DIR, self.file)
        img = Image.open(path)
        self._frames = []
        self._durations = []
        for i in range(img.n_frames):
            img.seek(i)
            self._frames.append(img.convert("RGBA"))
            self._durations.append(img.info.get("duration", 100))
        self.width = self._frames[0].width
        self.height = self._frames[0].height
        self._current_frame = 0
        self._frame_elapsed = 0.0

    def _init_canvas(self, canvas):
        self._canvas = canvas
        self._canvas_id = None
        if canvas is not None:
            self._photos = [ImageTk.PhotoImage(f) for f in self._frames]
            self._canvas_id = canvas.create_image(
                -1000, -1000, image=self._photos[0], anchor="nw",
            )

    def trigger(self):
        if self._triggered:
            return
        self._triggered = True
        self._play_finished = False
        self._current_frame = 0
        self._frame_elapsed = 0.0

    def _should_animate(self):
        if self.anim_mode == ANIM_LOOP:
            return True
        return self._triggered and not self._play_finished

    def update(self, scroll_offset, elapsed_time, dt_ms):
        self._last_elapsed = elapsed_time
        visible = self.is_visible(scroll_offset)
        if visible and not self.in_view:
            self.in_view = True
            self.view_enter_time = elapsed_time
            if self.anim_mode == ANIM_LOOP:
                self._current_frame = 0
                self._frame_elapsed = 0.0
        elif not visible and self.in_view:
            self.in_view = False
            self.view_enter_time = None
        if visible and self._should_animate():
            self._frame_elapsed += dt_ms
            dur = self._durations[self._current_frame]
            while self._frame_elapsed >= dur:
                self._frame_elapsed -= dur
                next_frame = self._current_frame + 1
                if next_frame >= len(self._frames):
                    if self.anim_mode == ANIM_TRIGGERED:
                        self._play_finished = True
                        self._current_frame = len(self._frames) - 1
                        break
                    next_frame = 0
                self._current_frame = next_frame
                dur = self._durations[self._current_frame]
        if self._canvas is None:
            return
        if visible:
            sx, sy = self.screen_pos(scroll_offset, elapsed_time)
            self._canvas.coords(self._canvas_id, sx, sy)
            self._canvas.itemconfig(
                self._canvas_id, image=self._photos[self._current_frame],
            )
        else:
            self._canvas.coords(self._canvas_id, -1000, -1000)


def create_sprite(definition, canvas=None):
    if definition["layer"] == LAYER_ANIM_GIF:
        return AnimatedGifSprite(definition, canvas)
    return Sprite(definition, canvas)


# ═════════════════════════════════════════════════════════════════
# Embeddable scroller
# ═════════════════════════════════════════════════════════════════

class EmbeddedScroller:
    """Scroller that renders into its own Canvas widget.

    The caller embeds ``self.canvas`` into an activity canvas via
    ``create_window()`` and controls the lifecycle with ``start()``
    and ``stop()``.
    """

    def __init__(self, parent):
        self.canvas = tk.Canvas(
            parent,
            width=VIEWPORT_WIDTH,
            height=VIEWPORT_HEIGHT,
            highlightthickness=0,
            bg="black",
        )

        # ── Background image ──────────────────────────────────────
        bg_pil = Image.open(os.path.join(SPRITE_DIR, "canvas.png")).convert("RGBA")
        self._bg_photo = ImageTk.PhotoImage(bg_pil)
        self._bg_id = self.canvas.create_image(
            -CROP_LEFT, 0, image=self._bg_photo, anchor="nw",
        )

        # ── Sprites ───────────────────────────────────────────────
        sorted_defs = sorted(SPRITE_DEFS, key=lambda d: (d["z"], d["y"]))
        self.sprites = [create_sprite(d, self.canvas) for d in sorted_defs]
        self._sprites_by_name = {s.file: s for s in self.sprites}

        # ── Triggers ──────────────────────────────────────────────
        self._triggers = [{**t, "fired": False} for t in TRIGGERS]

        # ── Contributors list ─────────────────────────────────────
        self._contributors = self._parse_contributors()
        self._contributor_items = self._create_contributor_text()
        self._list_bottom_y = (
            CONTRIBUTORS_START_Y
            + len(self._contributors) * CONTRIBUTORS_LINE_HEIGHT
        )

        # ── Fade overlay ──────────────────────────────────────────
        self._fade_photos = self._generate_fade_frames()
        self._fade_id = self.canvas.create_image(
            0, 0, image=self._fade_photos[0], anchor="nw",
        )
        self._fade_start_time = None

        # ── Timing state ──────────────────────────────────────────
        self._start_time = None
        self._last_time = None
        self._total_scroll = 0.0
        self.scroll_offset = 0.0
        self.running = False

    @staticmethod
    def _parse_contributors():
        entries = []
        try:
            with open(CONTRIBUTORS_FILE, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if "`" not in line:
                        continue
                    name, rest = line.split("`", 1)
                    count = rest.replace(" commits", "").replace(" commit", "").strip()
                    entries.append((name, count))
        except FileNotFoundError:
            pass
        return entries

    def _create_contributor_text(self):
        font_bold = ("Consolas", -9, "bold")
        font_normal = ("Consolas", -9)
        dx = CONTRIBUTORS_DIVIDER_X
        items = []
        for i, (name, count) in enumerate(self._contributors):
            canvas_y = CONTRIBUTORS_START_Y + i * CONTRIBUTORS_LINE_HEIGHT
            name_id = self.canvas.create_text(
                -1000, -1000,
                text=name, fill="red", font=font_bold, anchor="ne",
            )
            count_id = self.canvas.create_text(
                -1000, -1000,
                text=f": {count}", fill="white", font=font_normal, anchor="nw",
            )
            items.append((name_id, count_id, canvas_y))
        return items

    @staticmethod
    def _generate_fade_frames():
        frames = []
        for i in range(FADE_STEPS + 1):
            alpha = int(255 * i / FADE_STEPS)
            img = Image.new(
                "RGBA",
                (VIEWPORT_WIDTH, VIEWPORT_HEIGHT),
                (255, 255, 255, alpha),
            )
            frames.append(ImageTk.PhotoImage(img))
        return frames

    def start(self):
        """Begin the auto-scroll animation."""
        self._start_time = None
        self._last_time = None
        self._total_scroll = 0.0
        self.scroll_offset = 0.0
        self.running = True
        self.canvas.after(1, self._loop)

    def stop(self):
        """Stop the animation loop."""
        self.running = False

    def _loop(self):
        if not self.running:
            return

        now = time.monotonic()
        if self._start_time is None:
            self._start_time = now
            self._last_time = now

        dt = now - self._last_time
        elapsed = now - self._start_time
        dt_ms = dt * 1000.0
        self._last_time = now

        scroll_time = max(0.0, elapsed - SCROLL_START_DELAY)
        self._total_scroll = scroll_time * SCROLL_SPEED
        self.scroll_offset = min(self._total_scroll, MAX_SCROLL)

        self.canvas.coords(self._bg_id, -CROP_LEFT, -self.scroll_offset)

        for sprite in self.sprites:
            sprite.update(self.scroll_offset, elapsed, dt_ms)

        for trig in self._triggers:
            if trig["fired"]:
                continue
            source = self._sprites_by_name.get(trig["watch"])
            if source is None:
                continue
            progress = source.sweep_progress
            if progress is not None and progress >= trig["at_progress"]:
                target = self._sprites_by_name.get(trig["target"])
                if target is not None and hasattr(target, "trigger"):
                    target.trigger()
                    trig["fired"] = True

        dx = CONTRIBUTORS_DIVIDER_X
        for name_id, count_id, cy in self._contributor_items:
            sy = cy - self._total_scroll
            if -20 < sy < VIEWPORT_HEIGHT + 20:
                self.canvas.coords(name_id, dx - 2, sy)
                self.canvas.coords(count_id, dx + 2, sy)
            else:
                self.canvas.coords(name_id, -1000, -1000)
                self.canvas.coords(count_id, -1000, -1000)

        if self._total_scroll > self._list_bottom_y and self._fade_start_time is None:
            self._fade_start_time = elapsed

        if self._fade_start_time is not None:
            t = min(1.0, (elapsed - self._fade_start_time) / FADE_DURATION)
            idx = min(int(t * FADE_STEPS), FADE_STEPS)
            self.canvas.itemconfig(self._fade_id, image=self._fade_photos[idx])
            if t >= 1.0:
                self.running = False
                return

        self.canvas.after(FRAME_MS, self._loop)


# ── Standalone entry point (for testing) ──────────────────────────

if __name__ == "__main__":
    root = tk.Tk()
    root.title("About Scroller")
    root.resizable(False, False)
    scroller = EmbeddedScroller(root)
    scroller.canvas.pack()
    scroller.start()
    root.mainloop()
