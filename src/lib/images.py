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

"""Icon loading with recolor support — replaces images.so.

Loads PNG icon images from ``res/img/`` and optionally recolors
pixels (used by ListView to swap icon grey for white/black depending
on the selection state).

In headless / QEMU environments where Pillow or tkinter may not be
available, ``load()`` returns ``None`` gracefully.  The ListView
already handles ``None`` icons.

Source: decompiled images.so + widget.so ``setIcons`` pattern
"""

import logging
import os
import sys

logger = logging.getLogger(__name__)

# ───────────────────────────────────────────────────
# Image cache — prevents garbage-collection of
# PhotoImage references (tkinter requirement)
# ───────────────────────────────────────────────────
_image_cache = {}

# Base directory for icon assets (resolved once at import time).
# On the real device this is ``/E/res/img/``;  in development it is
# ``<project>/res/img/``.
_BASE_DIR = None


def _resolve_base_dir():
    """Find the res/img directory relative to the application root."""
    global _BASE_DIR
    if _BASE_DIR is not None:
        return _BASE_DIR

    # Try common locations
    candidates = []

    # 1. Relative to this file: src/lib/images.py -> src/../res/img
    here = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(here, '..', '..', 'res', 'img'))
    # 2. Relative to cwd
    candidates.append(os.path.join(os.getcwd(), 'res', 'img'))
    # 3. Device path
    candidates.append('/E/res/img')
    # 4. From sys.path entries
    for p in sys.path:
        candidates.append(os.path.join(p, 'res', 'img'))
        candidates.append(os.path.join(p, '..', 'res', 'img'))

    for c in candidates:
        norm = os.path.normpath(c)
        if os.path.isdir(norm):
            _BASE_DIR = norm
            logger.debug("Image base dir: %s", _BASE_DIR)
            return _BASE_DIR

    # No directory found — will cause load() to return None
    _BASE_DIR = ''
    return _BASE_DIR


def _find_image_path(name):
    """Locate the image file on disk.

    Searches:
      1. Absolute path if *name* contains a path separator
      2. ``res/img/{name}.png``
      3. ``res/img/{name}`` (if already has extension)

    Returns the resolved path string, or ``None`` if not found.
    """
    if not name:
        return None

    # Absolute / explicit path
    if os.sep in name or (os.altsep and os.altsep in name):
        if os.path.isfile(name):
            return name
        # Try adding .png
        with_ext = name + '.png'
        if os.path.isfile(with_ext):
            return with_ext
        return None

    base = _resolve_base_dir()
    if not base:
        return None

    # With .png extension
    path_with_ext = os.path.join(base, name + '.png')
    if os.path.isfile(path_with_ext):
        return path_with_ext

    # As-is (name might already include extension)
    path_as_is = os.path.join(base, name)
    if os.path.isfile(path_as_is):
        return path_as_is

    return None


def _recolor(image, source_rgb, target_rgb):
    """Replace pixels of *source_rgb* with *target_rgb* in a PIL Image.

    Operates in-place on the image and returns it.

    *source_rgb* and *target_rgb* are ``(r, g, b)`` tuples with
    integer values 0-255.

    Only exact matches are replaced (no tolerance).
    """
    if image is None:
        return None

    try:
        pixels = image.load()
        w, h = image.size
        sr, sg, sb = source_rgb
        tr, tg, tb = target_rgb

        for y in range(h):
            for x in range(w):
                px = pixels[x, y]
                # Handle RGBA and RGB
                if len(px) == 4:
                    r, g, b, a = px
                    if r == sr and g == sg and b == sb:
                        pixels[x, y] = (tr, tg, tb, a)
                elif len(px) == 3:
                    r, g, b = px
                    if r == sr and g == sg and b == sb:
                        pixels[x, y] = (tr, tg, tb)
    except Exception:
        logger.exception("Recolor failed")

    return image


def load(name, rgb=None):
    """Load icon image by name.

    Args:
        name: Icon filename (without extension, or with ``.png``).
        rgb:  Optional recolor tuple ``((r1,g1,b1), (r2,g2,b2))``.
              Pixels matching ``(r1,g1,b1)`` are replaced with
              ``(r2,g2,b2)``.

    Returns:
        A ``tkinter.PhotoImage`` (when tk is available) or
        ``PIL.Image`` object, or ``None`` if not found or if
        imaging libraries are unavailable.

    Search paths:
        1. ``res/img/{name}.png`` (relative to app dir)
        2. Absolute path if *name* contains ``/``
    """
    # Build a cache key that includes the recolor params
    cache_key = (name, rgb)
    if cache_key in _image_cache:
        return _image_cache[cache_key]

    path = _find_image_path(name)
    if path is None:
        return None

    image = None

    # Try PIL/Pillow first (works headless)
    try:
        from PIL import Image as PILImage
        pil_img = PILImage.open(path).convert('RGBA')

        if rgb is not None:
            source_rgb, target_rgb = rgb
            _recolor(pil_img, source_rgb, target_rgb)

        # Try to convert to PhotoImage for tkinter compatibility
        try:
            from PIL import ImageTk
            image = ImageTk.PhotoImage(pil_img)
        except Exception:
            # No tk display — return raw PIL image
            image = pil_img

    except ImportError:
        # No PIL — try raw tkinter PhotoImage (no recolor support)
        try:
            import tkinter as tk
            image = tk.PhotoImage(file=path)
        except Exception:
            logger.debug("No imaging library available for %s", name)
            return None
    except Exception:
        logger.debug("Failed to load image %s from %s", name, path)
        return None

    if image is not None:
        _image_cache[cache_key] = image

    return image
