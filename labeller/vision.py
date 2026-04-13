"""Gemini vision integration for species and model identification."""

import os
from pathlib import Path


PROMPT = (
    "Identify the main subject of this image for photo tagging purposes. "
    "For animals, return a URN tag in the format urn:ró:<category>:<latin-binomial> "
    "where <category> is one of: bird, mammal, insect, fish, reptile, and <latin-binomial> is the "
    "species name lowercased with a hyphen, followed by ?context=wild for insects or "
    "?context=captivity for all other animal categories "
    "(e.g. urn:ró:bird:hirundo-rustica?context=captivity, "
    "urn:ró:mammal:vulpes-vulpes?context=captivity, urn:ró:insect:vanessa-atalanta?context=wild). "
    "For non-animals, give the most specific name possible (e.g. 'Shinkansen N700S', 'Boeing 737-800'). "
    "Return only a comma-separated list of tags, most specific first, no explanation."
)


def label_image(fpath: str | None, url: str | None) -> list[str]:
    """Return identification tags for an image using Gemini vision.

    Tries the local file path first; falls back to fetching the URL.
    Returns an empty list if no source is available or on API error.
    """
    import google.generativeai as genai

    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel("gemini-2.5-flash")

    if fpath and Path(fpath).exists():
        image_part = {
            "mime_type": _mime_type(fpath),
            "data": Path(fpath).read_bytes(),
        }
    elif url:
        import requests
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        image_part = {
            "mime_type": response.headers.get("content-type", "image/jpeg").split(";")[0],
            "data": response.content,
        }
    else:
        return []

    result = model.generate_content([PROMPT, image_part])
    raw = result.text.strip()
    return [tag.strip() for tag in raw.split(",") if tag.strip()]


def _mime_type(fpath: str) -> str:
    suffix = Path(fpath).suffix.lower()
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(suffix, "image/jpeg")
