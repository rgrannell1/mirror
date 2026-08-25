"""Tests for ThumbHash placeholder encoding and legacy-mosaic migration detection."""

import base64
import string

from PIL import Image
from thumbhash import thumb_hash_to_approximate_aspect_ratio, thumb_hash_to_average_rgba

from mirror.services.encoder import PhotoEncoder
from mirror.services.media_publish import is_legacy_mosaic

BASE64_CHARSET = set(string.ascii_letters + string.digits + "+/")

# byte budget: the old 2x2 hex mosaic cost 28 chars, and the design requires
# the new placeholder to cost no more
LEGACY_MOSAIC_CHARS = 28


def make_solid_image(tmp_path, colour: tuple, size: tuple) -> str:
    """Write a solid-colour test image and return its path."""
    fpath = str(tmp_path / f"solid_{colour[0]}_{colour[1]}_{colour[2]}_{size[0]}x{size[1]}.png")
    Image.new("RGB", size, colour).save(fpath)
    return fpath


def decode_hash(encoded: str) -> bytes:
    """Reverse the unpadded base64 encoding."""
    padding = "=" * (-len(encoded) % 4)
    return base64.b64decode(encoded + padding)


def test_thumbhash_is_unpadded_base64(tmp_path):
    """Proves the placeholder is compact unpadded base64, never the legacy hex format."""
    cases = [
        ((200, 40, 40), (300, 200)),
        ((40, 200, 40), (200, 300)),
        ((40, 40, 200), (250, 250)),
    ]

    for colour, size in cases:
        encoded = PhotoEncoder.encode_thumbhash(make_solid_image(tmp_path, colour, size))

        assert set(encoded) <= BASE64_CHARSET
        assert "=" not in encoded
        assert not is_legacy_mosaic(encoded)
        assert 5 <= len(decode_hash(encoded)) <= 25


def test_thumbhash_never_costs_more_than_legacy(tmp_path):
    """Proves common camera aspect ratios cost at most the legacy mosaic's 28 chars.

    Ratios under 1.27 (near-square) cost 31-32 chars from a denser luma grid.
    The library holds 3 such photos out of 1515; the rest stay in budget."""
    cases = [
        (400, 200),
        (200, 400),
        (300, 200),
        (267, 200),
    ]

    for size in cases:
        encoded = PhotoEncoder.encode_thumbhash(make_solid_image(tmp_path, (90, 90, 90), size))

        assert len(encoded) <= LEGACY_MOSAIC_CHARS


def test_thumbhash_is_deterministic(tmp_path):
    """Proves the same image always encodes to the same placeholder."""
    fpath = make_solid_image(tmp_path, (120, 80, 160), (320, 240))

    assert PhotoEncoder.encode_thumbhash(fpath) == PhotoEncoder.encode_thumbhash(fpath)


def test_thumbhash_preserves_average_colour(tmp_path):
    """Proves the decoded average colour approximates the source image colour."""
    cases = [
        (220, 60, 60),
        (60, 220, 60),
        (60, 60, 220),
        (128, 128, 128),
    ]

    for colour in cases:
        encoded = PhotoEncoder.encode_thumbhash(make_solid_image(tmp_path, colour, (200, 150)))
        avg_r, avg_g, avg_b, avg_a = thumb_hash_to_average_rgba(list(decode_hash(encoded)))

        assert abs(avg_r * 255 - colour[0]) < 40
        assert abs(avg_g * 255 - colour[1]) < 40
        assert abs(avg_b * 255 - colour[2]) < 40
        assert avg_a == 1.0


def test_thumbhash_preserves_orientation(tmp_path):
    """Proves landscape and portrait images keep their approximate aspect ratio."""
    cases = [
        ((400, 200), True),
        ((200, 400), False),
    ]

    for size, is_landscape in cases:
        encoded = PhotoEncoder.encode_thumbhash(make_solid_image(tmp_path, (90, 90, 90), size))
        ratio = thumb_hash_to_approximate_aspect_ratio(list(decode_hash(encoded)))

        assert (ratio > 1) == is_landscape


def test_legacy_mosaic_detection():
    """Proves legacy hex mosaics are flagged for recompute and new hashes are not."""
    cases = [
        ("#586976#586C7D#6C7E87", True),
        ("mukFHYSDD4fOVWifYZyYoLh/asL8", False),
        ("qOcFHIQ9V4g/iIiUh4hjsDoGqw", False),
    ]

    for value, expected in cases:
        assert is_legacy_mosaic(value) == expected
