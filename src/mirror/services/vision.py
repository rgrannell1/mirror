"""Gemini vision integration for species and model identification."""

import os
from pathlib import Path

import requests
from google import genai
from google.genai import types

from mirror.commons.constants import GEMINI_VISION_MODEL
from mirror.data.things import animal_contexts

THINGS_PATH = Path(__file__).parents[3] / "things.toml"


def format_context_guidance(contexts: dict[str, str]) -> str:
    """Describe configured animal contexts for the image labelling prompt."""
    types_by_context: dict[str, list[str]] = {}
    for animal_type, context in contexts.items():
        types_by_context.setdefault(context, []).append(animal_type)
    parts = [
        f"use ?context={context} for {', '.join(animal_types)}"
        for context, animal_types in types_by_context.items()
    ]
    return "; ".join(parts)


def base_prompt() -> str:
    """The tagging prompt; animal categories come from things.toml."""
    contexts = animal_contexts(str(THINGS_PATH))
    categories = ", ".join(contexts)
    context_guidance = format_context_guidance(contexts)
    return (
        "Identify the main subject of this image for photo tagging purposes. "
        "For animals, return a URN tag in the format urn:ró:<category>:<latin-binomial> "
        f"where <category> is one of: {categories}, and "
        "<latin-binomial> is the species name lowercased with a hyphen, followed by "
        f"the configured context: {context_guidance}. "
        "For cars, return a URN tag in the format urn:ró:car:<make>-<model> with make and "
        "model lowercased and hyphenated "
        "(e.g. urn:ró:car:ferrari-f40, urn:ró:car:volkswagen-beetle, urn:ró:car:ford-mustang). "
        "For trains, return a URN tag in the format urn:ró:train:<operator>-<model> "
        "lowercased and hyphenated "
        "(e.g. urn:ró:train:jr-shinkansen-n700s, urn:ró:train:eurostar-e320, "
        "urn:ró:train:dart-arrow). "
        "For other non-animals, give the most specific name possible "
        "(e.g. 'Shinkansen N700S', 'Boeing 737-800'). "
        "Return only the single tag for the main subject — nothing else. "
        "Never add extra tags for places, scenery, colours, materials, or other details. "
        "No explanation."
    )


def build_prompt(album_title: str | None, place_names: list[str]) -> str:
    """Build a prompt with optional album and place context prepended."""
    context_parts = []
    if album_title:
        context_parts.append(f"Album: {album_title}")
    if place_names:
        context_parts.append(f"Location: {', '.join(place_names)}")
    if not context_parts:
        return base_prompt()
    context = " | ".join(context_parts)
    return f"Context — {context}.\n\n{base_prompt()}"


def load_image_part(fpath: str | None, url: str | None) -> types.Part | None:
    """Load the image as a genai Part, from disk first then the URL."""
    if fpath and Path(fpath).exists():
        return types.Part.from_bytes(
            data=Path(fpath).read_bytes(),
            mime_type=mime_type(fpath),
        )
    if url:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        mime = response.headers.get("content-type", "image/jpeg").split(";")[0]
        return types.Part.from_bytes(data=response.content, mime_type=mime)
    return None


def label_image(
    fpath: str | None,
    url: str | None,
    album_title: str | None = None,
    place_names: list[str] | None = None,
) -> list[str]:
    """Return identification tags for an image using Gemini vision.

    Tries the local file path first; falls back to fetching the URL.
    Returns an empty list if no source is available or on API error.
    """
    image_part = load_image_part(fpath, url)
    if image_part is None:
        return []

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    prompt = build_prompt(album_title, place_names or [])
    result = client.models.generate_content(
        model=GEMINI_VISION_MODEL,
        contents=[prompt, image_part],
    )
    raw = (result.text or "").strip()
    return [tag.strip() for tag in raw.split(",") if tag.strip()]


def mime_type(fpath: str) -> str:
    """Map a file suffix to its image MIME type, defaulting to JPEG."""
    suffix = Path(fpath).suffix.lower()
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(suffix, "image/jpeg")
