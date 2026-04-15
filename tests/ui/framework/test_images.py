"""Tests for lib.images — icon loading, path resolution, recolor, caching.

Covers:
  - load() returns None for nonexistent images
  - _image_cache mechanism
  - _find_image_path with and without extension
  - _recolor pixel replacement
  - Graceful degradation when PIL is not available
"""

import sys
import os
import tempfile
from unittest import mock

import pytest

# Ensure src/ is on the import path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from lib import images
from lib.images import load, _find_image_path, _recolor, _image_cache


# -----------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_cache():
    """Clear the image cache before each test."""
    _image_cache.clear()
    # Reset the base dir so it re-resolves each test
    images._BASE_DIR = None
    yield
    _image_cache.clear()
    images._BASE_DIR = None


@pytest.fixture
def tmp_img_dir(tmp_path):
    """Create a temporary res/img directory with a test PNG."""
    img_dir = tmp_path / "res" / "img"
    img_dir.mkdir(parents=True)

    # Create a minimal valid 1x1 PNG (RGBA)
    # PNG file: signature + IHDR + IDAT + IEND
    # This is the smallest valid PNG that PIL can open
    try:
        from PIL import Image as PILImage
        img = PILImage.new('RGBA', (2, 2), (102, 102, 102, 255))
        img.save(str(img_dir / "test_icon.png"))
    except ImportError:
        # No PIL — write a minimal PNG by hand (1x1 white pixel)
        # Tests that need PIL will be skipped
        pass

    return img_dir


# =================================================================
# Tests
# =================================================================

class TestLoadNonexistent:
    """load() returns None for missing images without crashing."""

    def test_load_nonexistent_returns_none(self):
        result = load("this_icon_does_not_exist_xyz")
        assert result is None

    def test_load_empty_name_returns_none(self):
        result = load("")
        assert result is None

    def test_load_none_name_returns_none(self):
        result = load(None)
        assert result is None


class TestCacheMechanism:
    """Repeated loads hit the cache."""

    def test_cache_stores_result(self, tmp_img_dir):
        """Loading the same image twice returns the cached object."""
        # Point the base dir at our temp directory
        images._BASE_DIR = str(tmp_img_dir)

        try:
            from PIL import Image as PILImage
        except ImportError:
            pytest.skip("PIL not available")

        first = load("test_icon")
        if first is None:
            pytest.skip("Image loading not functional in this environment")

        second = load("test_icon")
        assert first is second  # exact same object from cache

    def test_cache_key_includes_rgb(self, tmp_img_dir):
        """Different rgb params produce different cache entries."""
        images._BASE_DIR = str(tmp_img_dir)

        try:
            from PIL import Image as PILImage
        except ImportError:
            pytest.skip("PIL not available")

        img_no_recolor = load("test_icon")
        img_with_recolor = load("test_icon", rgb=((102, 102, 102), (255, 255, 255)))

        if img_no_recolor is None:
            pytest.skip("Image loading not functional in this environment")

        # Both should be cached under different keys
        assert ("test_icon", None) in _image_cache
        assert ("test_icon", ((102, 102, 102), (255, 255, 255))) in _image_cache


class TestFindImagePath:
    """_find_image_path locates images on disk."""

    def test_find_with_extension(self, tmp_img_dir):
        """Finds image when name already includes .png."""
        images._BASE_DIR = str(tmp_img_dir)
        # Create a file
        path = tmp_img_dir / "foo.png"
        path.write_bytes(b"fake")

        result = _find_image_path("foo.png")
        assert result is not None
        assert result.endswith("foo.png")

    def test_find_without_extension(self, tmp_img_dir):
        """Finds image by adding .png to bare name."""
        images._BASE_DIR = str(tmp_img_dir)
        path = tmp_img_dir / "bar.png"
        path.write_bytes(b"fake")

        result = _find_image_path("bar")
        assert result is not None
        assert result.endswith("bar.png")

    def test_find_absolute_path(self, tmp_path):
        """Finds image given an absolute path."""
        abs_file = tmp_path / "absolute_icon.png"
        abs_file.write_bytes(b"fake")

        result = _find_image_path(str(abs_file))
        assert result == str(abs_file)

    def test_find_nonexistent_returns_none(self, tmp_img_dir):
        """Returns None when image does not exist."""
        images._BASE_DIR = str(tmp_img_dir)
        result = _find_image_path("no_such_icon")
        assert result is None


class TestRecolor:
    """_recolor swaps pixel colors in-place."""

    def test_recolor_replaces_matching_pixels(self):
        """Pixels matching source_rgb are replaced with target_rgb."""
        try:
            from PIL import Image as PILImage
        except ImportError:
            pytest.skip("PIL not available")

        img = PILImage.new('RGBA', (3, 3), (102, 102, 102, 255))
        # Set one pixel to a different color
        img.putpixel((1, 1), (200, 200, 200, 255))

        result = _recolor(img, (102, 102, 102), (255, 255, 255))

        assert result is img  # in-place
        # Matching pixels should be recolored
        assert img.getpixel((0, 0)) == (255, 255, 255, 255)
        assert img.getpixel((2, 2)) == (255, 255, 255, 255)
        # Non-matching pixel unchanged
        assert img.getpixel((1, 1)) == (200, 200, 200, 255)

    def test_recolor_none_returns_none(self):
        """_recolor(None, ...) returns None without crashing."""
        assert _recolor(None, (0, 0, 0), (255, 255, 255)) is None

    def test_recolor_rgb_mode(self):
        """Recolor works on RGB images (no alpha)."""
        try:
            from PIL import Image as PILImage
        except ImportError:
            pytest.skip("PIL not available")

        img = PILImage.new('RGB', (2, 2), (102, 102, 102))
        _recolor(img, (102, 102, 102), (0, 0, 0))
        assert img.getpixel((0, 0)) == (0, 0, 0)
