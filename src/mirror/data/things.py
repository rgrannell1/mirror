from functools import cache
from pathlib import Path
from typing import Iterator

import tomllib

from mirror.commons.constants import UNPUBLISHED_THINGS_RELATIONS, URN_PREFIX
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
def thing_names(things_file: str = "things.toml") -> dict[str, str]:
    """Return mapping of thing URN → display name, for entries that carry one."""
    with open(Path(things_file), "rb") as fh:
        data = tomllib.load(fh)

    return {
        entry["id"]: entry["name"]
        for entries in data.values()
        for entry in entries
        if isinstance(entry, dict) and entry.get("id") and entry.get("name")
    }


@cache
def binomial_types(things_file: str = "things.toml") -> frozenset[str]:
    """Return subject types whose identifiers are binomials."""
    with open(Path(things_file), "rb") as fh:
        data = tomllib.load(fh)

    return frozenset(
        entry["noun"] for entry in data.get("subject_types", []) if entry.get("binomial")
    )


@cache
def animal_types(things_file: str = "things.toml") -> tuple[str, ...]:
    """Return subject types marked as animals."""
    with open(Path(things_file), "rb") as fh:
        data = tomllib.load(fh)

    return tuple(entry["noun"] for entry in data.get("subject_types", []) if entry.get("animal"))


@cache
def animal_contexts(things_file: str = "things.toml") -> dict[str, str]:
    """Return the required context for each animal subject type."""
    with open(Path(things_file), "rb") as fh:
        data = tomllib.load(fh)

    return {
        entry["noun"]: entry["context"]
        for entry in data.get("subject_types", [])
        if entry.get("animal") and entry.get("context")
    }


@cache
def unlisted_types(things_file: str = "things.toml") -> frozenset[str]:
    """Return subject types excluded from site listings."""
    with open(Path(things_file), "rb") as fh:
        data = tomllib.load(fh)

    return frozenset(
        entry["noun"]
        for entry in data.get("subject_types", [])
        if entry.get("listed", True) is False
    )


@cache
def listing_type_config(things_file: str = "things.toml") -> dict[str, dict]:
    """Per-noun labels and site behaviour flags for non-subject listing types."""
    with open(Path(things_file), "rb") as fh:
        data = tomllib.load(fh)

    return {entry["noun"]: entry for entry in data.get("listing_types", [])}


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
def rating_ids(things_file: str = "things.toml") -> tuple[str, ...]:
    """Rating URN ids in ascending order, from the ratings section."""
    with open(Path(things_file), "rb") as fh:
        data = tomllib.load(fh)

    ratings = sorted(data.get("ratings", []), key=lambda entry: entry["rank"])
    return tuple(entry["id"] for entry in ratings)


@cache
def rating_names(things_file: str = "things.toml") -> tuple[str, ...]:
    """Rating display names (star strings) in ascending order, from the ratings section."""
    with open(Path(things_file), "rb") as fh:
        data = tomllib.load(fh)

    ratings = sorted(data.get("ratings", []), key=lambda entry: entry["rank"])
    return tuple(entry["name"] for entry in ratings)


@cache
def rating_urns_by_name(things_file: str = "things.toml") -> dict[str, str]:
    """Return rating display names mapped to their URNs."""
    with open(Path(things_file), "rb") as fh:
        data = tomllib.load(fh)

    return {entry["name"]: entry["id"] for entry in data.get("ratings", [])}


@cache
def rating_ranks(things_file: str = "things.toml") -> dict[str, int]:
    """Return rating display names mapped to their numeric rank."""
    with open(Path(things_file), "rb") as fh:
        data = tomllib.load(fh)

    return {entry["name"]: entry["rank"] for entry in data.get("ratings", [])}


@cache
def feature_urn_for_role(role: str, things_file: str = "things.toml") -> str:
    """Return the place-feature URN assigned to a domain role."""
    with open(Path(things_file), "rb") as fh:
        data = tomllib.load(fh)

    matches = [
        entry["id"] for entry in data.get("place_features", []) if role in entry.get("roles", [])
    ]
    if len(matches) != 1:
        raise ValueError(f"Expected one place feature with role {role!r}, found {len(matches)}")
    return matches[0]


@cache
def genre_cover_priorities(scope: str, things_file: str = "things.toml") -> dict[str, int]:
    """Return genre cover priorities for one publication scope."""
    with open(Path(things_file), "rb") as fh:
        data = tomllib.load(fh)

    return {
        entry["id"]: entry["cover_priority"][scope]
        for entry in data.get("genres", [])
        if scope in entry.get("cover_priority", {})
    }


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

    country_feature = feature_urn_for_role("country", things_file)
    lookup: dict[str, str] = {}
    for place in data.get("places", []):
        features = place.get("features", [])
        if country_feature not in features:
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
            if relation == "id" or relation in UNPUBLISHED_THINGS_RELATIONS:
                continue

            if isinstance(tgt_vals, list):
                for val in tgt_vals:
                    yield SemanticTriple(source=src, relation=relation, target=val)
            else:
                yield SemanticTriple(source=src, relation=relation, target=tgt_vals)

        # a BirdWatch page exists only for Irish-list species; publish the marker
        if item.get("birdwatch_url"):
            yield SemanticTriple(source=src, relation="irish", target="true")

    def read(self, db) -> Iterator[SemanticTriple]:
        """Read TOML information and yield semantic triples"""

        things_path = Path(self.things_file)

        if not things_path.exists():
            return

        with open(things_path, "rb") as conn:
            data = tomllib.load(conn)

        # TODO validate these against a schema based on type
        # configuration entries and id-less sections hold no publishable things
        for urn_info in data.values():
            for item in urn_info:
                item_id = item.get("id") if isinstance(item, dict) else None
                if isinstance(item_id, str) and item_id.startswith(URN_PREFIX):
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
