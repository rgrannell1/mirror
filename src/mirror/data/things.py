from functools import cache
from pathlib import Path
from typing import Iterator

import tomllib

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

    def to_triples(self, item: dict) -> Iterator[SemanticTriple]:
        src = item["id"]

        for relation in item:
            if relation == "id":
                continue

            tgt_vals = item[relation]

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
        for urn_info in data.values():
            for item in urn_info:
                yield from self.to_triples(item)
