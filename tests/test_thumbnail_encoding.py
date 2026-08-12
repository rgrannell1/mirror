"""Tests for the thumbnail encode settings.

Grid tiles stretch well past the source width, so the thumbnail size and quality
are a deliberate trade rather than an arbitrary default. These pin that trade.
"""

from mirror.commons.constants import (
    IMAGE_ENCODINGS,
    THUMBNAIL_HEIGHT,
    THUMBNAIL_WIDTH,
    TUI_THUMBNAIL_HEIGHT,
    TUI_THUMBNAIL_WIDTH,
)

# Largest tile the photo grid renders, at a viewport near 1059px.
MAX_TILE_WIDTH = 810

# Upscale we accept at the worst-case tile width.
MAX_UPSCALE = 1.4


def test_thumbnail_source_covers_the_widest_tile():
    """Proves the thumbnail source is large enough that the grid never upscales
    it past the accepted factor."""
    assert MAX_TILE_WIDTH / THUMBNAIL_WIDTH <= MAX_UPSCALE


def test_web_thumbnail_is_square_and_sized_from_the_constants():
    """Proves the website thumbnail tracks the shared size constants."""
    params = IMAGE_ENCODINGS["thumbnail_lossy"]

    assert params["width"] == THUMBNAIL_WIDTH
    assert params["height"] == THUMBNAIL_HEIGHT


def test_tui_thumbnail_keeps_its_own_smaller_size():
    """Proves the lossless TUI thumbnail does not follow the website thumbnail
    upward, which would more than double its bytes."""
    params = IMAGE_ENCODINGS["thumbnail_webp"]

    assert params["width"] == TUI_THUMBNAIL_WIDTH
    assert params["height"] == TUI_THUMBNAIL_HEIGHT
    assert TUI_THUMBNAIL_WIDTH < THUMBNAIL_WIDTH


def test_lossy_thumbnail_quality_stays_below_the_wasteful_range():
    """Proves the AVIF thumbnail does not return to a near-lossless quality,
    which doubles bytes for under 1dB."""
    assert IMAGE_ENCODINGS["thumbnail_lossy"]["quality"] == 80
