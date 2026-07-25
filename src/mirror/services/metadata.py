"""A file for dealing with metadata for albums and photos"""

import csv
import json
import os
import re
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Iterator, Optional, Protocol, Sequence, TypedDict

from jsonschema import ValidationError, validate

from mirror.commons.constants import (
    ALBUM_ROW_MIN_CELLS,
    ALBUM_TABLE_HEADERS,
    LEGACY_ALBUM_DPATHS,
    MEDIA_ROW_MIN_CELLS,
    MEDIA_TABLE_HEADERS,
)
from mirror.commons.utils import is_miscellaneous_dpath
from mirror.models.album import AlbumMetadataModel
from mirror.models.photo import PhotoMetadataModel, PhotoMetadataSummaryModel
from mirror.models.video import VideoMetadataSummaryModel

from .database import SqliteDatabase

type MediaSummaryModel = PhotoMetadataSummaryModel | VideoMetadataSummaryModel


def write_atomically(path: str, body: str) -> None:
    """Write body to path atomically: write to a temp file then rename, so the
    original is never truncated if writing fails mid-way."""
    target_dir = os.path.dirname(os.path.abspath(path))
    descriptor, tmp_path = tempfile.mkstemp(dir=target_dir, suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(body)
        os.replace(tmp_path, path)
    except Exception:
        os.unlink(tmp_path)
        raise


def split_cell(cell: str) -> list[str]:
    """Split a comma-separated markdown cell into a list of values."""
    return re.split(r"\s*,\s*", cell) if cell else []


def emit_markdown_table(
    headers: Sequence[str], rows: Iterator[list[str]], output_path: str | None
) -> None:
    """Render a markdown table, then write it atomically or print when no path is given."""
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")

    body = "\n".join(lines) + "\n"
    if output_path is not None:
        write_atomically(output_path, body)
    else:
        print(body, end="")


def check_markdown_header(reader, fpath: str, label: str) -> None:
    """Consume and check a markdown table's header and separator rows."""
    try:
        headers = next(reader)[1:-1]
    except StopIteration:
        raise ValueError(f"{label} metadata file is empty: {fpath}") from None

    if not headers or headers[0].strip() != "embedding":
        raise ValueError(f"Invalid header in Markdown table: {headers}")

    try:
        next(reader)
    except StopIteration:
        raise ValueError(f"{label} metadata file is missing separator row: {fpath}") from None


def read_markdown_rows(fpath: str, label: str, min_cells: int) -> Iterator[list[str]]:
    """Check a markdown table's header and separator rows, then yield stripped body rows."""
    with open(fpath) as file:
        reader = csv.reader(file, delimiter="|")
        check_markdown_header(reader, fpath, label)

        for row in reader:
            if len(row) < min_cells:
                continue
            yield [cell.strip() for cell in row]


def validate_item(item: dict, schema: dict) -> None:
    """Validate against a JSON schema, dumping the failing item before raising."""
    try:
        validate(item, schema)
    except ValidationError as err:
        print(json.dumps(item, indent=2))
        raise ValueError(str(err.message)) from None


# Protocols defining how metadata can be communicated to/from other locations
class IAlbumMetadataReader(Protocol):
    """Interface for listing out album metadata"""

    def list_album_metadata(self, db: SqliteDatabase) -> Iterator[AlbumMetadataModel]: ...


class IAlbumMetadataWriter(Protocol):
    """Interface for storing album metadata"""

    def write_album_metadata(
        self, db: SqliteDatabase, *, output_path: str | None = None
    ) -> None: ...


class IPhotoMetadataReader(Protocol):
    """Interface for listing out photo metadata"""

    def list_photo_metadata(self, db: SqliteDatabase) -> Iterator[PhotoMetadataModel]: ...


class IPhotoMetadataWriter(Protocol):
    """Interface for storing photo metadata"""

    def write_photo_metadata(
        self, db: SqliteDatabase, *, output_path: str | None = None
    ) -> None: ...


class AlbumFieldsDict(TypedDict):
    """Albums.md fields collected for one album."""

    embedding: Optional[str]
    summary: Optional[str]
    country: list[str]
    permalink: Optional[str]
    title: Optional[str]


def blank_album_fields() -> AlbumFieldsDict:
    """An empty albums.md field-set."""
    return {"embedding": None, "summary": "", "country": [], "permalink": "", "title": ""}


def list_contentful_albums(db: SqliteDatabase) -> set[str]:
    """Retrieve a set of album paths that have content in the database"""
    albums = set()

    for data in db.album_data_view().list():
        if is_miscellaneous_dpath(data.dpath):
            continue

        if data.photos_count > 0 or data.videos_count > 0:
            albums.add(data.dpath)

    return albums


def seed_album_fields(db: SqliteDatabase, published_albums: set[str]) -> dict[str, AlbumFieldsDict]:
    """Start each published album's fields from its thumbnail."""
    by_album: dict[str, AlbumFieldsDict] = defaultdict(blank_album_fields)

    for dpath in published_albums:
        # find an embedding as a minimum
        album_data = db.album_data_view().get_album_data_by_dpath(dpath)

        fields = blank_album_fields()
        fields["embedding"] = album_data.thumbnail_url if album_data else None
        by_album[dpath] = fields

    return by_album


def apply_album_relations(
    db: SqliteDatabase, by_album: dict[str, AlbumFieldsDict], published_albums: set[str]
) -> None:
    """Overlay albums.md-derived relations onto the seeded album fields."""
    album_data_table = db.album_data_view()

    # For every album with metadata saved from the albums metadata file,
    # map this data into a dpath -> dict structure
    albums = list(db.media_metadata_table().list_albums())

    for data in sorted(albums, key=lambda album: album.src):
        # skip non-published albums
        if data.src not in published_albums:
            continue

        album_data = album_data_table.get_album_data_by_dpath(data.src)
        # not ideal, as it requires manually nominating a cover file first
        if not album_data:
            continue

        by_album[data.src]["embedding"] = album_data.thumbnail_url
        if data.relation in {"county", "country"}:
            by_album[data.src]["country"] = split_cell(data.target)
        else:
            by_album[data.src][data.relation] = data.target


def album_table_rows(by_album: dict[str, AlbumFieldsDict]) -> Iterator[list[str]]:
    """Render albums.md rows, sorted by file-path."""
    for dpath, album_data in sorted(by_album.items(), key=lambda pair: pair[0]):
        if not album_data["embedding"]:
            continue

        # Fall back to the folder name (parent of Published/) when no title is set
        title = album_data["title"] or Path(dpath).parent.name
        yield [
            f"![]({album_data['embedding']})",
            title,
            album_data["permalink"] or "",
            ",".join(album_data["country"]) if album_data["country"] else "",
            album_data["summary"] or "",
        ]


class MarkdownAlbumMetadataWriter(IAlbumMetadataWriter):
    @staticmethod
    def write_album_metadata(db: SqliteDatabase, *, output_path: str | None = None) -> None:
        published_albums = list_contentful_albums(db)
        by_album = seed_album_fields(db, published_albums)
        apply_album_relations(db, by_album, published_albums)

        emit_markdown_table(ALBUM_TABLE_HEADERS, album_table_rows(by_album), output_path)


def resolve_album_dpath(album_data, embedding: str, permalink: str) -> str:
    """Resolve a row's dpath from its thumbnail, with overrides for legacy albums."""
    if permalink in LEGACY_ALBUM_DPATHS:
        return LEGACY_ALBUM_DPATHS[permalink]

    thumbnail_url = embedding[4:-1]
    return album_data.album_dpath_from_thumbnail_url(thumbnail_url)


def album_metadata_models(item: dict) -> Iterator[AlbumMetadataModel]:
    """Expand one albums.md row into per-relation metadata models."""
    for key, val in item.items():
        if key == "fpath":
            continue

        yield AlbumMetadataModel(
            src=item["fpath"],
            src_type="photo",
            # sign
            relation="county" if key == "country" else key,
            target=",".join(val) if isinstance(val, list) else val,
        )


class MarkdownAlbumMetadataReader(IAlbumMetadataReader):
    fpath: str

    def __init__(self, fpath: str):
        self.fpath = fpath

    def list_album_metadata(self, db: SqliteDatabase) -> Iterator[AlbumMetadataModel]:
        album_data = db.album_data_view()

        for row in read_markdown_rows(self.fpath, "albums", ALBUM_ROW_MIN_CELLS):
            _, embedding, title, permalink, country, summary, _ = row

            item = {
                "fpath": resolve_album_dpath(album_data, embedding, permalink),
                "title": title,
                "permalink": permalink,
                "country": split_cell(country),
                "summary": summary or "",
            }

            validate_item(item, AlbumMetadataModel.schema())

            if not item["fpath"]:
                continue

            yield from album_metadata_models(item)


def merge_media_summary(merged: dict[str, dict], summary: MediaSummaryModel, name: str) -> None:
    """Accumulate one summary row into the per-url merged metadata."""
    fields = merged.setdefault(
        summary.url,
        {
            "url": summary.url,
            "name": name,
            "genre": set(),
            "rating": "",
            "places": set(),
            "description": "",
            "subjects": set(),
            "covers": set(),
        },
    )

    if summary.genre:
        fields["genre"].update(summary.genre)
    if summary.places:
        fields["places"].update(summary.places)
    if summary.subjects:
        fields["subjects"].update(summary.subjects)
    if summary.covers:
        fields["covers"].update(summary.covers)

    if summary.description and not fields["description"]:
        fields["description"] = summary.description

    if summary.rating and not fields["rating"]:
        fields["rating"] = summary.rating


def media_table_rows(merged: dict[str, dict]) -> Iterator[list[str]]:
    """Render photos.md / videos.md rows from merged metadata."""
    for url, data in merged.items():
        yield [
            f"![]({url})",
            data["name"],
            ",".join(sorted(data["genre"])),
            data["rating"],
            ",".join(sorted(data["places"])),
            data["description"],
            ",".join(sorted(data["subjects"])),
            ",".join(sorted(data["covers"])),
        ]


def derive_photo_album_name(summary: PhotoMetadataSummaryModel) -> str:
    """Album name for a photo, falling back to the folder name above Published/."""
    if summary.name:
        return summary.name

    if not summary.fpath:
        raise ValueError(f"Photo missing an album name and fpath: {summary.url}")

    # Fall back to the folder name two levels up from the photo file
    # e.g. .../AlbumName/Published/photo.jpg → AlbumName
    name = Path(summary.fpath).parent.parent.name
    if not name:
        raise ValueError(f"Could not derive album name from fpath: {summary.fpath}")

    return name


class MarkdownTablePhotoMetadataWriter:
    @staticmethod
    def write_photo_metadata(db: SqliteDatabase, *, output_path: str | None = None) -> None:
        merged: dict[str, dict] = {}

        for summary in db.photo_metadata_summary_view().list():
            merge_media_summary(merged, summary, derive_photo_album_name(summary))

        emit_markdown_table(MEDIA_TABLE_HEADERS, media_table_rows(merged), output_path)


class MarkdownTableVideoMetadataWriter:
    @staticmethod
    def write_video_metadata(db: SqliteDatabase, *, output_path: str | None = None) -> None:
        merged: dict[str, dict] = {}

        for summary in db.video_metadata_summary_view().list():
            merge_media_summary(merged, summary, summary.name or "")

        emit_markdown_table(MEDIA_TABLE_HEADERS, media_table_rows(merged), output_path)


def parse_media_cells(row: list[str]) -> dict:
    """Unpack a photos.md / videos.md row into named fields."""
    _, embedding, title, genre, rating, places, description, subjects, cover, _ = row

    return {
        "url": embedding[4:-1],
        "name": title,
        "genre": split_cell(genre),
        "rating": rating or None,
        "places": split_cell(places),
        "description": description or "",
        "subjects": split_cell(subjects),
        "covers": split_cell(cover),
    }


def photo_schema_item(cells: dict) -> dict:
    """Map parsed cells onto the photo summary schema's field names."""
    return {
        "thumbnail_url": cells["url"],
        "album": cells["name"],
        "genre": cells["genre"],
        "places": cells["places"],
        "rating": cells["rating"],
        "subjects": cells["subjects"],
        "description": cells["description"],
        "covers": cells["covers"],
    }


def check_photo_uniqueness(cells: dict, unique_urls: set, unique_covers: set) -> None:
    """Reject duplicate photo urls and competing cover claims."""
    if cells["url"] in unique_urls:
        raise ValueError(f"Duplicate photo URL in metadata: {cells['url']}")
    unique_urls.add(cells["url"])

    for cover in cells["covers"]:
        if cover in unique_covers:
            raise ValueError(f"Multiple images claiming to be cover for {cover}")
        unique_covers.add(cover)


class MarkdownTablePhotoMetadataReader:
    fpath: str

    def __init__(self, fpath: str):
        self.fpath = fpath

    def read_photo_metadata(self, db: SqliteDatabase) -> Iterator[PhotoMetadataSummaryModel]:
        """Read photo metadata from a Markdown table"""
        unique_urls: set[str] = set()
        unique_covers: set[str] = set()

        for row in read_markdown_rows(self.fpath, "photos", MEDIA_ROW_MIN_CELLS):
            cells = parse_media_cells(row)
            check_photo_uniqueness(cells, unique_urls, unique_covers)

            validate_item(photo_schema_item(cells), PhotoMetadataSummaryModel.schema())

            yield PhotoMetadataSummaryModel(**cells)


class MarkdownTableVideoMetadataReader:
    fpath: str

    def __init__(self, fpath: str):
        self.fpath = fpath

    def read_video_metadata(self, db: SqliteDatabase) -> Iterator[VideoMetadataSummaryModel]:
        """Read video metadata from a Markdown table"""
        unique_urls: set[str] = set()

        for row in read_markdown_rows(self.fpath, "videos", MEDIA_ROW_MIN_CELLS):
            cells = parse_media_cells(row)

            if cells["url"] in unique_urls:
                raise ValueError(f"Duplicate video poster URL in metadata: {cells['url']}")
            unique_urls.add(cells["url"])

            yield VideoMetadataSummaryModel(**cells)
