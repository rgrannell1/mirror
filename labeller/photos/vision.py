"""Gemini vision integration for species and model identification."""

import os
from pathlib import Path


PROMPT = (
    "Identify the main subject of this image for photo tagging purposes. "
    "For animals, return a URN tag in the format urn:ró:<category>:<latin-binomial> "
    "where <category> is one of: bird, mammal, insect, fish, reptile, amphibian, and <latin-binomial> is the "
    "species name lowercased with a hyphen, followed by ?context=wild for insects and amphibians or "
    "?context=captivity for all other animal categories "
    "(e.g. urn:ró:bird:hirundo-rustica?context=captivity, "
    "urn:ró:mammal:vulpes-vulpes?context=captivity, urn:ró:insect:vanessa-atalanta?context=wild, "
    "urn:ró:amphibian:rana-temporaria?context=wild). "
    "For cars, return a URN tag in the format urn:ró:car:<make>-<model> with make and model lowercased "
    "and hyphenated (e.g. urn:ró:car:ferrari-f40, urn:ró:car:volkswagen-beetle, urn:ró:car:ford-mustang). "
    "For trains, return a URN tag in the format urn:ró:train:<operator>-<model> lowercased and hyphenated "
    "(e.g. urn:ró:train:jr-shinkansen-n700s, urn:ró:train:eurostar-e320, urn:ró:train:dart-arrow). "
    "For other non-animals, give the most specific name possible (e.g. 'Shinkansen N700S', 'Boeing 737-800'). "
    "Return only a comma-separated list of tags, most specific first, no explanation."
)


def label_image(fpath: str | None, url: str | None) -> list[str]:
    """Return identification tags for an image using Gemini vision.

    Tries the local file path first; falls back to fetching the URL.
    Returns an empty list if no source is available or on API error.
    """
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    if fpath and Path(fpath).exists():
        image_part = types.Part.from_bytes(
            data=Path(fpath).read_bytes(),
            mime_type=_mime_type(fpath),
        )
    elif url:
        import requests

        response = requests.get(url, timeout=10)
        response.raise_for_status()
        mime = response.headers.get("content-type", "image/jpeg").split(";")[0]
        image_part = types.Part.from_bytes(data=response.content, mime_type=mime)
    else:
        return []

    result = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[PROMPT, image_part],
    )
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
