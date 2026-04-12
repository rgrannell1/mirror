"""Fetch and cache thumbnail images from URLs, returning PIL Images."""

import io
from functools import lru_cache

import requests
from PIL import Image


@lru_cache(maxsize=128)
def fetch_image(url: str) -> Image.Image | None:
    """Download an image from url and return it as a PIL Image, or None on failure."""
    try:
        response = requests.get(url, timeout=8)
        response.raise_for_status()
        return Image.open(io.BytesIO(response.content)).convert("RGB")
    except Exception:
        return None


def fit_image(image: Image.Image, max_width: int, max_height: int) -> Image.Image:
    """
    Resize image to fit within max_width × max_height terminal character cells.
    Each cell renders two vertical pixel rows via half-block characters, so the
    pixel height passed to Pixels should be max_height * 2.
    """
    pixel_width = max_width
    pixel_height = max_height * 2
    image.thumbnail((pixel_width, pixel_height), Image.LANCZOS)
    return image
