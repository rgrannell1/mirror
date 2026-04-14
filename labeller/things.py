"""Parse things.toml into URN → name lookups and autocomplete suggestion lists."""

import tomllib
from functools import cache
from pathlib import Path

THINGS_PATH = Path(__file__).parent.parent / "things.toml"

_ANIMAL_TYPES = ("bird", "mammal", "reptile", "amphibian", "fish", "insect")
_CONTEXT_VALUES = ("wild", "captive")
_UNKNOWN_ANIMAL_TYPES = ("bird", "mammal", "reptile", "insect", "amphibian", "fish")


def _latin_to_display(latin_dashes: str) -> str:
    """'milvus-milvus' → 'Milvus milvus'"""
    words = latin_dashes.replace("-", " ").split()
    if words:
        words[0] = words[0].capitalize()
    return " ".join(words)


@cache
def load_urn_names() -> dict[str, str]:
    """Return {base_urn: display_name} for all known entities in things.toml.

    Strips any ?context= suffix before indexing, so callers should do the same
    when looking up a stored URN.
    """
    raw = THINGS_PATH.read_text(encoding="utf-8")
    # things.toml uses [[`]] as the header for the first places entry — invalid
    # TOML (backtick is not a valid key character).  Replace it with [[places]]
    # so tomllib sees a consistent array-of-tables section.
    cleaned = raw.replace("[[`]]", "[[places]]")
    data = tomllib.loads(cleaned)

    names: dict[str, str] = {}

    for place in data.get("places", []):
        names[place["id"]] = place.get("name", place["id"]).strip()

    for bird in data.get("birds", []):
        urn = bird["id"]
        if "name" in bird:
            names[urn] = bird["name"]
        else:
            latin = urn.removeprefix("urn:ró:bird:")
            names[urn] = _latin_to_display(latin)

    for section in ("mammals", "reptiles", "amphibians", "fish", "insects", "planes", "cars", "trains"):
        for entry in data.get(section, []):
            urn = entry["id"]
            if "name" in entry:
                names[urn] = entry["name"]
            else:
                category = urn.split(":")[2]
                names[urn] = _latin_to_display(urn.removeprefix(f"urn:ró:{category}:"))

    return names


@cache
def load_urn_suggestions() -> list[tuple[str, str]]:
    """Return [(display_label, urn), ...] sorted by display label.

    Birds and mammals get wild/captive variants since those URNs carry a
    ?context= qualifier in practice.
    """
    names = load_urn_names()
    suggestions: list[tuple[str, str]] = []

    for urn, name in names.items():
        animal_type = next(
            (kind for kind in _ANIMAL_TYPES if urn.startswith(f"urn:ró:{kind}:")),
            None,
        )
        if animal_type:
            for context in _CONTEXT_VALUES:
                suggestions.append((f"{name} ({context})", f"{urn}?context={context}"))
        else:
            suggestions.append((name, urn))

    for animal_type in _UNKNOWN_ANIMAL_TYPES:
        for context in _CONTEXT_VALUES:
            suggestions.append((
                f"Unknown {animal_type} ({context})",
                f"urn:ró:{animal_type}:unknown?context={context}",
            ))

    suggestions.sort(key=lambda pair: pair[0].casefold())
    return suggestions


def resolve_urn(urn: str) -> str | None:
    """Return the display name for a URN, ignoring any ?context= qualifier."""
    base = urn.split("?")[0]
    return load_urn_names().get(base)
