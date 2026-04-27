"""Pure helpers for publish: artifact content and listing. No workflow/job logic."""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Iterator

from dateutil import tz

from mirror.commons.config import PHOTOS_URL
from mirror.commons.urn import is_mirror_urn, parse_mirror_urn
from mirror.commons.utils import deterministic_hash_str
from mirror.data.geoname import GeonameMetadataReader
from mirror.data.photo_relations import PhotoRelationsReader
from mirror.data.semantic_triples import (
    AlbumBannerReader,
    AlbumTriples,
    AnimalFirstSeenReader,
    ExifTriplesReader,
    ListingCoverReader,
    PhotosCountryReader,
    PhotoTriples,
    PlaceFeatureCoverReader,
    ThingCoverReader,
    VideosReader,
)
from mirror.data.things import ThingsReader
from mirror.data.types import SemanticTriple
from mirror.data.unesco import UnescoReader
from mirror.data.wikidata import WikidataMetadataReader
from mirror.models.photo import PhotoMetadataModel
from mirror.services.database import SqliteDatabase

# CURIE prefixes for triples (https://en.wikipedia.org/wiki/CURIE)
CURIE = {
    "urn:ró:": "i",
    "https://birdwatchireland.ie/birds/": "birdwatch",
    "https://photos-cdn.rgrannell.xyz/": "photos",
    "https://en.wikipedia.org/wiki/": "wiki",
}

ARTIFACT_NAMES_CLEAN = {"stats", "triples", "tribbles"}
TIME_FORMAT = "%Y:%m:%d %H:%M:%S"


def publication_id() -> str:
    """Generate a unique publication id."""
    return deterministic_hash_str(str(datetime.now(tz.UTC)))


def remove_artifacts(dpath: str) -> None:
    """Remove existing artifact files from the output directory."""
    if not os.path.isdir(dpath):
        return
    removeable = [f for f in os.listdir(dpath) if any(f.startswith(prefix) for prefix in ARTIFACT_NAMES_CLEAN)]
    for f in removeable:
        os.remove(os.path.join(dpath, f))


def env_content(publication_id: str) -> str:
    """Build env artifact content."""
    return json.dumps({"photos_url": PHOTOS_URL, "publication_id": publication_id})


def validate_stats(data: dict) -> None:
    countries = data["countries"]
    if countries < 10 or countries > 50:
        raise ValueError("broken countries count")


def _count_type(type_name: str, subjects: list[PhotoMetadataModel]) -> int:
    unique = set()
    for subject in subjects:
        value = subject.target
        if not is_mirror_urn(value):
            continue
        parsed = parse_mirror_urn(value)
        if parsed["type"] == type_name:
            unique.add(parsed["id"])
    return len(unique)


def _count_unesco_sites(places: list[PhotoMetadataModel], db: SqliteDatabase) -> int:
    unesco_places = set()
    for thing in ThingsReader().read(db):
        if thing.relation == "features" and thing.target == "urn:ró:place_feature:unesco":
            unesco_places.add(thing.source)
    return len({p.target for p in places if p.target in unesco_places})


def _count_countries(albums: list) -> int:
    return len({flag for album in albums for flag in album.flags})


def _count_years(albums: list) -> int:
    min_date = None
    max_date = None
    for album in albums:
        if album.min_date is None or album.max_date is None:
            continue
        if min_date is None or max_date is None:
            min_date = datetime.strptime(album.min_date, TIME_FORMAT)
            max_date = datetime.strptime(album.max_date, TIME_FORMAT)
        min_date = min(min_date, datetime.strptime(album.min_date, TIME_FORMAT))
        max_date = max(max_date, datetime.strptime(album.max_date, TIME_FORMAT))
    if not min_date or not max_date:
        raise ValueError("No albums found or albums have no dates")
    return max_date.year - min_date.year


def stats_content(db: SqliteDatabase) -> str:
    """Build stats artifact content."""
    albums = list(db.album_data_view().list())
    subjects = list(db.photo_metadata_table().list_by_relation("subject"))
    places = list(db.photo_metadata_table().list_by_relation("location"))
    data = {
        "photos": sum(a.photos_count for a in albums),
        "videos": sum(a.videos_count for a in albums),
        "albums": len(albums),
        "years": _count_years(albums),
        "countries": _count_countries(albums),
        "bird_species": _count_type("bird", subjects),
        "mammal_species": _count_type("mammal", subjects),
        "reptile_species": _count_type("reptile", subjects),
        "amphibian_species": _count_type("amphibian", subjects),
        "fish_species": _count_type("fish", subjects),
        "unesco_sites": _count_unesco_sites(places, db),
    }
    validate_stats(data)
    return json.dumps(data, separators=(",", ":"), ensure_ascii=False)


def _simplify_curie(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    for prefix, curie in CURIE.items():
        if value.startswith(prefix):
            mapped = f"[{value.replace(prefix, curie + ':')}]"
            if "[i::" in mapped:
                raise ValueError(f"Invalid curie generated {value} -> {mapped}")
            return mapped
    return value


def _camel_case(value: str) -> str:
    parts = value.split("_")
    return parts[0] + "".join(word.capitalize() for word in parts[1:])


def _process_triple(triple: SemanticTriple) -> list[list]:
    return [[_simplify_curie(triple.source), _camel_case(triple.relation), _simplify_curie(triple.target)]]


def read_triples(db: SqliteDatabase) -> Iterator[list]:
    """Yield triples as [source, relation, target] (for artifact JSON and Neo4j)."""
    readers = [
        AlbumTriples(),
        PhotoTriples(),
        ExifTriplesReader(),
        VideosReader(),
        GeonameMetadataReader(),
        ThingsReader(),
        UnescoReader(),
        WikidataMetadataReader(),
        PhotoRelationsReader(),
        PhotosCountryReader(),
        AlbumBannerReader(),
        ListingCoverReader(),
        ThingCoverReader(),
        PlaceFeatureCoverReader(),
        AnimalFirstSeenReader(),
    ]
    seen: set[int] = set()
    for long, alias in CURIE.items():
        yield [long, "curie", alias]
    for reader in readers:
        for triple in reader.read(db):
            for processed in _process_triple(triple):
                triple_hash = hash(tuple(processed))
                if triple_hash not in seen:
                    seen.add(triple_hash)
                    yield processed


def triples_content(db: SqliteDatabase) -> str:
    """Build triples artifact content."""
    triples = list(read_triples(db))
    return json.dumps(triples, separators=(",", ":"), ensure_ascii=False)
