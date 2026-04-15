"""URN → display name lookups and autocomplete suggestions from things.toml."""

from functools import cache

from .loader import load_raw

_ANIMAL_TYPES = ("bird", "mammal", "reptile", "amphibian", "fish", "insect")
_CONTEXT_VALUES = ("wild", "captive")
_UNKNOWN_ANIMAL_TYPES = ("bird", "mammal", "reptile", "insect", "amphibian", "fish")


def _latin_to_display(latin_dashes: str) -> str:
    words = latin_dashes.replace("-", " ").split()
    if words:
        words[0] = words[0].capitalize()
    return " ".join(words)


def _names_for_places(data: dict) -> dict[str, str]:
    return {
        place["id"]: place.get("name", place["id"]).strip()
        for place in data.get("places", [])
    }


def _names_for_animals(data: dict) -> dict[str, str]:
    names: dict[str, str] = {}
    for section in ("birds", "mammals", "reptiles", "amphibians", "fish", "insects"):
        for entry in data.get(section, []):
            urn = entry["id"]
            if "name" in entry:
                names[urn] = entry["name"]
            else:
                category = urn.split(":")[2]
                names[urn] = _latin_to_display(urn.removeprefix(f"urn:ró:{category}:"))
    return names


def _names_for_transport(data: dict) -> dict[str, str]:
    names: dict[str, str] = {}
    for section in ("planes", "cars", "trains"):
        for entry in data.get(section, []):
            urn = entry["id"]
            if "name" in entry:
                names[urn] = entry["name"]
            else:
                category = urn.split(":")[2]
                names[urn] = _latin_to_display(urn.removeprefix(f"urn:ró:{category}:"))
    return names


@cache
def load_urn_names() -> dict[str, str]:
    """Return {base_urn: display_name} for all known entities."""
    data = load_raw()
    return {
        **_names_for_places(data),
        **_names_for_animals(data),
        **_names_for_transport(data),
    }


@cache
def load_urn_suggestions() -> list[tuple[str, str]]:
    """Return [(display_label, urn), ...] sorted by label, with wild/captive variants for animals."""
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
