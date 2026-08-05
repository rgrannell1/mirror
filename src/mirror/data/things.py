from functools import cache
from pathlib import Path
from typing import Iterator

import tomllib

from mirror.commons.constants import URN_PREFIX
from mirror.data.types import SemanticTriple


@cache
def place_feature_to_places(things_file: str = "things.toml") -> dict[str, list[str]]:
    """Return mapping of place_feature URN → list of place URNs with that feature."""
    with open(Path(things_file), "rb") as fh:
        data = tomllib.load(fh)

    mapping: dict[str, list[str]] = {}
    for place in data.get("places", []):
        for feature_urn in place.get("features", []):
            mapping.setdefault(feature_urn, []).append(place["id"])
    return mapping


@cache
def trip_to_albums(things_file: str = "things.toml") -> dict[str, tuple[str, ...]]:
    """Return mapping of trip URN → album URNs the trip contains."""
    with open(Path(things_file), "rb") as fh:
        data = tomllib.load(fh)

    return {trip["id"]: tuple(trip.get("contains_album", [])) for trip in data.get("trips", [])}


@cache
def trip_titles(things_file: str = "things.toml") -> dict[str, str]:
    """Return mapping of trip URN → trip title."""
    with open(Path(things_file), "rb") as fh:
        data = tomllib.load(fh)

    return {trip["id"]: trip["title"] for trip in data.get("trips", []) if trip.get("title")}


@cache
def named_thing_ids(things_file: str = "things.toml") -> frozenset[str]:
    """Return the ids of things.toml entries that carry a non-empty name."""
    with open(Path(things_file), "rb") as fh:
        data = tomllib.load(fh)

    ids = {
        entry["id"]
        for entries in data.values()
        for entry in entries
        if isinstance(entry, dict) and entry.get("id") and entry.get("name")
    }
    return frozenset(ids)


@cache
def binomial_types(things_file: str = "things.toml") -> frozenset[str]:
    """Subject types whose ids are latin binomials, from the top-level binomial_types list."""
    with open(Path(things_file), "rb") as fh:
        data = tomllib.load(fh)

    return frozenset(data.get("binomial_types", []))


@cache
def animal_types(things_file: str = "things.toml") -> tuple[str, ...]:
    """Animal URN nouns, from the top-level animal_types list."""
    with open(Path(things_file), "rb") as fh:
        data = tomllib.load(fh)

    return tuple(data.get("animal_types", []))


@cache
def unlisted_types(things_file: str = "things.toml") -> frozenset[str]:
    """Subject types that never get a site listing, from the top-level unlisted_types list."""
    with open(Path(things_file), "rb") as fh:
        data = tomllib.load(fh)

    return frozenset(data.get("unlisted_types", []))


@cache
def banner_fpaths(things_file: str = "things.toml") -> frozenset[str]:
    """Source photos that receive the banner rendition, from the banners section."""
    with open(Path(things_file), "rb") as fh:
        data = tomllib.load(fh)

    return frozenset(entry["fpath"] for entry in data.get("banners", []))


@cache
def legacy_album_dpaths(things_file: str = "things.toml") -> dict[str, str]:
    """Permalink → dpath overrides for albums whose thumbnail no longer resolves."""
    with open(Path(things_file), "rb") as fh:
        data = tomllib.load(fh)

    return {entry["permalink"]: entry["dpath"] for entry in data.get("legacy_albums", [])}


@cache
def listing_labels(things_file: str = "things.toml") -> dict[str, str]:
    """Map each URN noun to a plural display label derived from its section header.

    The section header is the plural ('birds', 'place_features'); the noun comes from the
    section's first entry id ('urn:ró:bird:…' → 'bird')."""
    with open(Path(things_file), "rb") as fh:
        data = tomllib.load(fh)

    labels: dict[str, str] = {}
    for section, entries in data.items():
        if not isinstance(entries, list) or not entries or not isinstance(entries[0], dict):
            continue
        first_id = entries[0].get("id", "")
        if not first_id.startswith(URN_PREFIX):
            continue
        noun = first_id.removeprefix(URN_PREFIX).split(":")[0]
        labels[noun] = section.replace("_", " ").title()
    return labels


@cache
def country_slug_to_urn(things_file: str = "things.toml") -> dict[str, str]:
    """Return a mapping of slugified country name → place URN for country-type places.

    Country names from album flags (e.g. "Ireland") are lowercased and
    hyphenated to form a slug ("ireland"), which is looked up here to resolve
    the canonical numeric place URN ("urn:ró:place:156").
    """
    with open(Path(things_file), "rb") as fh:
        data = tomllib.load(fh)

    lookup: dict[str, str] = {}
    for place in data.get("places", []):
        features = place.get("features", [])
        if "urn:ró:place_feature:country" not in features:
            continue
        name: str = place.get("name", "")
        slug = name.lower().replace(" ", "-")
        lookup[slug] = place["id"]

    return lookup


class ThingsReader:
    """Read general things information from a things.toml file"""

    def __init__(self, things_file: str = "things.toml"):
        self.things_file = things_file

    @staticmethod
    def to_triples(item: dict) -> Iterator[SemanticTriple]:
        src = item["id"]

        for relation, tgt_vals in item.items():
            if relation == "id":
                continue

            if isinstance(tgt_vals, list):
                for val in tgt_vals:
                    yield SemanticTriple(source=src, relation=relation, target=val)
            else:
                yield SemanticTriple(source=src, relation=relation, target=tgt_vals)

    def read(self, db) -> Iterator[SemanticTriple]:
        """Read TOML information and yield semantic triples"""

        things_path = Path(self.things_file)

        if not things_path.exists():
            return

        with open(things_path, "rb") as conn:
            data = tomllib.load(conn)

        # TODO validate these against a schema based on type
        # config keys (binomial_types) and id-less sections (banners) hold no things
        for urn_info in data.values():
            for item in urn_info:
                if isinstance(item, dict) and "id" in item:
                    yield from self.to_triples(item)


class WildlifeReader(ThingsReader):
    """Read the Irish wildlife life-list catalogue (bird/mammal species) as triples.

    Same TOML shape as things.toml: each species item's `id` is its URN and every
    other key becomes a relation. Provides the species spine for the life-list page."""

    def __init__(self, wildlife_file: str = "wildlife.llm.toml"):
        super().__init__(wildlife_file)

    def to_triples(self, item: dict) -> Iterator[SemanticTriple]:
        yield from super().to_triples(item)
        # every catalogue species is Irish; the site reads this marker
        yield SemanticTriple(source=item["id"], relation="irish", target="true")
