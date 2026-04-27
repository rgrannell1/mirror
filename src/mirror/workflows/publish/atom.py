"""Atom feed generation: builds paginated XML feed files from photo and video entries."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import List, TypedDict

from feedgen.feed import FeedGenerator

from mirror.commons.utils import deterministic_hash_str
from mirror.data.things import ThingsReader
from mirror.models.photo import PhotoMetadataSummaryModel, PhotoModel
from mirror.models.video import VideoMetadataSummaryModel, VideoModel
from mirror.services.database import SqliteDatabase

# Base URL for the published site
ATOM_BASE_URL = "https://photos.rgrannell.xyz"

# Number of entries per feed page
ATOM_PAGE_SIZE = 20


class AtomEntry(TypedDict):
    """A single feed entry, derived from a photo or video."""

    id: str
    created_at: datetime
    url: str | None
    title: str
    content_html: str


def _build_name_lookup(db: SqliteDatabase) -> dict[str, str]:
    """Map thing URNs to human-readable names from things.toml."""
    return {triple.source: triple.target for triple in ThingsReader().read(db) if triple.relation == "name"}


def _resolve_names(urns: list[str], names: dict[str, str]) -> list[str]:
    """Resolve a list of URNs to human-readable names, dropping any not in the lookup."""
    return [names[urn] for urn in urns if urn in names]


def _atom_entry_title(description: str, subjects: list[str], album_name: str, fallback: str) -> str:
    """Pick the most meaningful title: per-item description > subject names > album name."""
    if description:
        return description
    if subjects:
        return ", ".join(subjects)
    return album_name or fallback


def _atom_photo_content_html(
    photo: PhotoModel, summary: PhotoMetadataSummaryModel | None, names: dict[str, str]
) -> str:
    parts = [f'<img src="{photo.mid_image_lossy_url}"/>']
    if summary is not None:
        if summary.description:
            parts.append(f"<p>{summary.description}</p>")
        places = _resolve_names(summary.places, names)
        if places:
            parts.append(f"<p>{', '.join(places)}</p>")
        subjects = _resolve_names(summary.subjects, names)
        if subjects:
            parts.append(f"<p>{', '.join(subjects)}</p>")
        if summary.rating:
            parts.append(f"<p>{summary.rating}</p>")
    return "\n".join(parts)


def _atom_video_content_html(
    video: VideoModel, summary: VideoMetadataSummaryModel | None, names: dict[str, str]
) -> str:
    parts = [f'<video controls><source src="{video.video_url_1080p}" type="video/mp4"></video>']
    if video.description:
        parts.append(f"<p>{video.description}</p>")
    if summary is not None:
        places = _resolve_names(summary.places, names)
        if places:
            parts.append(f"<p>{', '.join(places)}</p>")
        subjects = _resolve_names(summary.subjects, names)
        if subjects:
            parts.append(f"<p>{', '.join(subjects)}</p>")
        if summary.rating:
            parts.append(f"<p>{summary.rating}</p>")
    return "\n".join(parts)


def _atom_photo_entry(photo: PhotoModel, summary: PhotoMetadataSummaryModel | None, names: dict[str, str]) -> AtomEntry:
    subjects = _resolve_names(summary.subjects if summary else [], names)
    title = _atom_entry_title(
        summary.description if summary else "",
        subjects,
        summary.name if summary else "",
        "Photo",
    )
    return {
        "id": photo.thumbnail_url,
        "created_at": photo.get_ctime(),
        "url": photo.thumbnail_url,
        "title": title,
        "content_html": _atom_photo_content_html(photo, summary, names),
    }


def _atom_video_entry(video: VideoModel, summary: VideoMetadataSummaryModel | None, names: dict[str, str]) -> AtomEntry:
    subjects = _resolve_names(summary.subjects if summary else [], names)
    title = _atom_entry_title(
        video.description,
        subjects,
        summary.name if summary else "",
        "Video",
    )
    return {
        "id": video.poster_url,
        "created_at": datetime.fromtimestamp(os.path.getmtime(video.fpath), tz=timezone.utc),
        "url": video.video_url_unscaled,
        "title": title,
        "content_html": _atom_video_content_html(video, summary, names),
    }


def atom_media(db: SqliteDatabase) -> List[AtomEntry]:
    """Collect photos and videos for the Atom feed, sorted newest-first."""
    names = _build_name_lookup(db)
    photo_summaries = {summary.fpath: summary for summary in db.photo_metadata_summary_view().list()}
    video_summaries = {summary.fpath: summary for summary in db.video_metadata_summary_view().list()}
    entries: List[AtomEntry] = [
        _atom_video_entry(video, video_summaries.get(video.fpath), names) for video in db.video_data_table().list()
    ]
    entries += [
        _atom_photo_entry(photo, photo_summaries.get(photo.fpath), names) for photo in db.photo_data_table().list()
    ]
    entries.sort(key=lambda entry: entry["created_at"], reverse=True)
    return entries


def _atom_paginate(entries: List[AtomEntry], page_size: int) -> List[List[AtomEntry]]:
    return [entries[idx : idx + page_size] for idx in range(0, len(entries), page_size)]


def _atom_page_filename(entries: List[AtomEntry]) -> str:
    ids = ",".join(entry["id"] for entry in entries)
    hash_suffix = deterministic_hash_str(ids)[:8]
    return f"atom-page-{hash_suffix}.xml"


def _atom_page_url(entries: List[AtomEntry]) -> str:
    return f"{ATOM_BASE_URL}/manifest/atom/{_atom_page_filename(entries)}"


def _atom_make_feed(self_url: str, next_url: str | None) -> FeedGenerator:
    fg = FeedGenerator()
    fg.id(self_url)
    fg.title("Photos.rgrannell.xyz")
    fg.author({"name": "Róisín"})
    fg.link(href=self_url, rel="self")
    if next_url is not None:
        fg.link(href=next_url, rel="next")
    return fg


def _atom_populate_entries(fg: FeedGenerator, entries: List[AtomEntry]) -> None:
    """Add entries to a feed and set the feed's updated timestamp."""
    for entry in entries:
        fe = fg.add_entry()
        fe.id(entry["id"])
        fe.title(entry["title"])
        if entry["url"] is not None:
            fe.link(href=entry["url"])
        fe.content(entry["content_html"], type="html")
    fg.updated(max(entry["created_at"] for entry in entries))


def _atom_write_page(entries: List[AtomEntry], next_entries: List[AtomEntry] | None, output_dir: str) -> None:
    self_url = _atom_page_url(entries)
    next_url = _atom_page_url(next_entries) if next_entries is not None else None
    fg = _atom_make_feed(self_url, next_url)
    _atom_populate_entries(fg, entries)
    file_path = os.path.join(output_dir, "atom", _atom_page_filename(entries))
    fg.atom_file(file_path)


def atom_feed(entries: List[AtomEntry], output_dir: str) -> None:
    """Write Atom feed index and paginated sub-pages to output_dir."""
    if not entries:
        return
    page_size = ATOM_PAGE_SIZE
    pages = _atom_paginate(entries, page_size)
    atom_dir = os.path.join(output_dir, "atom")
    os.makedirs(atom_dir, exist_ok=True)

    for idx in range(1, len(pages)):
        next_page = pages[idx + 1] if idx + 1 < len(pages) else None
        _atom_write_page(pages[idx], next_page, output_dir)

    index_url = f"{ATOM_BASE_URL}/manifest/atom/atom-index.xml"
    next_url = _atom_page_url(pages[1]) if len(pages) > 1 else None
    index = _atom_make_feed(index_url, next_url)
    index.subtitle("A feed of my videos and images!")
    _atom_populate_entries(index, pages[0])
    index.atom_file(os.path.join(atom_dir, "atom-index.xml"))
