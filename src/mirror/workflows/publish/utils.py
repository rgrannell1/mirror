"""Pure helpers for publish: artifact content, listing, and full build. No workflow/job logic."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Iterator, List

from dateutil import tz
from feedgen.feed import FeedGenerator

from mirror.commons.config import PHOTOS_URL
from mirror.data.geoname import GeonameMetadataReader
from mirror.data.mirror import (
    AlbumTriples,
    ExifReader,
    PhotoTriples,
    PhotosCountryReader,
    VideosReader,
)
from mirror.data.photo_relations import PhotoRelationsReader
from mirror.data.things import ThingsReader
from mirror.data.types import SemanticTriple
from mirror.data.unesco import UnescoReader
from mirror.data.wikidata import WikidataMetadataReader
from mirror.services.database import SqliteDatabase
from mirror.photo import PhotoMetadataModel, PhotoModel
from mirror.services.things import Things
from mirror.utils import deterministic_hash_str
from mirror.video import VideoModel


# CURIE prefixes for triples (https://en.wikipedia.org/wiki/CURIE)
CURIE = {
    "urn:ró:": "i",
    "https://birdwatchireland.ie/birds/": "birdwatch",
    "https://photos-cdn.rgrannell.xyz/": "photos",
    "https://en.wikipedia.org/wiki/": "wiki",
}

ARTIFACT_NAMES_CLEAN = {"stats", "triples", "tribbles"}
ATOM_BASE_URL = "https://photos.rgrannell.xyz"
TIME_FORMAT = "%Y:%m:%d %H:%M:%S"


def publication_id() -> str:
    """Generate a unique publication id."""
    return deterministic_hash_str(str(datetime.now(tz.UTC)))


def remove_artifacts(dpath: str) -> None:
    """Remove existing artifact files from the output directory."""
    if not os.path.isdir(dpath):
        return
    removeable = [
        f for f in os.listdir(dpath)
        if any(f.startswith(prefix) for prefix in ARTIFACT_NAMES_CLEAN)
    ]
    for f in removeable:
        os.remove(os.path.join(dpath, f))


def env_content(publication_id: str) -> str:
    """Build env artifact content."""
    return json.dumps({"photos_url": PHOTOS_URL, "publication_id": publication_id})


def _atom_image_html(photo: PhotoModel) -> str:
    return f'<img src="{photo.mid_image_lossy_url}"/>'


def _atom_video_html(video: VideoModel) -> str:
    return f'<video controls><source src="{video.video_url_1080p}" type="video/mp4"></video>'


def atom_media(db: SqliteDatabase) -> List[dict]:
    """Collect photos and videos for the Atom feed, sorted by created_at."""
    photos = db.photo_data_table().list()
    videos = db.video_data_table().list()
    media: List[dict] = []
    db.video_data_table()
    db.album_data_view()
    for video in videos:
        media.append({
            "id": video.poster_url,
            "created_at": datetime.fromtimestamp(os.path.getmtime(video.fpath), tz=timezone.utc),
            "url": video.video_url_unscaled,
            "image": video.poster_url,
            "content_html": _atom_video_html(video),
        })
    for photo in photos:
        media.append({
            "id": photo.thumbnail_url,
            "created_at": photo.get_ctime(),
            "url": photo.thumbnail_url,
            "image": photo.thumbnail_url,
            "content_html": _atom_image_html(photo),
        })
    return sorted(media, key=lambda item: item["created_at"])


def _atom_paginate(items: List[dict], page_size: int) -> List[List[dict]]:
    return [items[idx : idx + page_size] for idx in range(0, len(items), page_size)]


def _atom_subpage_filename(items: List[dict]) -> str:
    ids = ",".join(item["id"] for item in items)
    hash_suffix = deterministic_hash_str(ids)[:8]
    return f"atom-page-{hash_suffix}.xml"


def _atom_page_url(page: List[dict]) -> str:
    next_file_url = os.path.join("/manifest/atom", _atom_subpage_filename(page))
    return f"{ATOM_BASE_URL}{next_file_url}"


def _atom_write_page(
    page: List[dict],
    next_page: List[dict] | None,
    output_dir: str,
) -> None:
    fg = FeedGenerator()
    fg.id(f"/{_atom_subpage_filename(page)}")
    fg.title("Photos.rgrannell.xyz")
    fg.author({"name": "Róisín"})
    fg.link(href=_atom_page_url(page), rel="self")
    if next_page is not None:
        fg.link(href=_atom_page_url(next_page), rel="next")
    max_time = None
    for item in page:
        if not max_time or item["created_at"] > max_time:
            max_time = item["created_at"]
        entry = fg.add_entry()
        entry.id(item["id"])
        entry.title("Video" if "<video>" in item["content_html"] else "Photo")
        if item["url"] is not None:
            entry.link(href=item["url"])
        entry.content(item["content_html"], type="html")
    fg.updated(max_time)
    file_path = os.path.join(output_dir, "atom", _atom_subpage_filename(page))
    fg.atom_file(file_path)


def atom_feed(media: List[dict], output_dir: str) -> None:
    """Write Atom feed and paginated pages to output_dir."""
    page_size = 20
    pages = _atom_paginate(media, page_size)
    atom_dir = os.path.join(output_dir, "atom")
    os.makedirs(atom_dir, exist_ok=True)
    for idx, page in enumerate(pages[1:]):
        next_page = pages[idx + 2] if idx + 2 < len(pages) else None
        _atom_write_page(page, next_page, output_dir)
    index_path = os.path.join(atom_dir, "atom-index.xml")
    index = FeedGenerator()
    index.title("Photos.rgrannell.xyz")
    index.id(f"{ATOM_BASE_URL}/atom-index.xml")
    index.subtitle("A feed of my videos and images!")
    index.author({"name": "Róisín"})
    index.link(href=f"{ATOM_BASE_URL}/atom-index.xml", rel="self")
    index.link(href=_atom_page_url(pages[0]), rel="next")
    max_time = None
    for item in pages[0]:
        if not max_time or item["created_at"] > max_time:
            max_time = item["created_at"]
        entry = index.add_entry()
        entry.id(item["id"])
        entry.title("Video" if "<video>" in item["content_html"] else "Photo")
        entry.link(href=item["url"])
        entry.content(item["content_html"], type="html")
    index.updated(max_time)
    index.atom_file(index_path)


def validate_stats(data: dict) -> None:
    countries = data["countries"]
    if countries < 10 or countries > 50:
        raise ValueError("broken countries count")


def _count_type(type_name: str, subjects: List[PhotoMetadataModel]) -> int:
    unique = set()
    for subject in subjects:
        value = subject.target
        if not Things.is_urn(value):
            continue
        parsed = Things.from_urn(value)
        if value.startswith(f"urn:ró:{type_name}:"):
            unique.add(parsed["id"])
    return len(unique)


def _count_unesco_sites(places: List[PhotoMetadataModel], db: SqliteDatabase) -> int:
    unesco_places = set()
    for thing in ThingsReader().read(db):
        if thing.relation == "feature" and thing.target == "urn:ró:place_feature:unesco":
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


def _process_triple(triple: SemanticTriple) -> List[list]:
    return [[_simplify_curie(triple.source), _camel_case(triple.relation), _simplify_curie(triple.target)]]


def read_triples(db: SqliteDatabase) -> Iterator[list]:
    """Yield triples as [source, relation, target] (for artifact JSON and Neo4j)."""
    readers = [
        AlbumTriples(),
        PhotoTriples(),
        ExifReader(),
        VideosReader(),
        GeonameMetadataReader(),
        ThingsReader(),
        UnescoReader(),
        WikidataMetadataReader(),
        PhotoRelationsReader(),
        PhotosCountryReader(),
    ]
    for long, alias in CURIE.items():
        yield [long, "curie", alias]
    for reader in readers:
        for triple in reader.read(db):
            yield from _process_triple(triple)


def triples_content(db: SqliteDatabase) -> str:
    """Build triples artifact content."""
    triples = list(read_triples(db))
    return json.dumps(triples, separators=(",", ":"), ensure_ascii=False)


def build(db: SqliteDatabase, output_dir: str) -> str:
    """Run full publish: remove old artifacts, write env, atom, stats, triples. Returns publication_id."""
    pid = publication_id()
    remove_artifacts(output_dir)
    print(f"{output_dir}/albums.{pid}.json")
    with open(os.path.join(output_dir, "env.json"), "w") as f:
        f.write(env_content(pid))
    atom_feed(atom_media(db), output_dir)
    with open(os.path.join(output_dir, "stats.{}.json".format(pid)), "w") as f:
        f.write(stats_content(db))
    with open(os.path.join(output_dir, "triples.{}.json".format(pid)), "w") as f:
        f.write(triples_content(db))
    return pid
