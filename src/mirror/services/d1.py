"""Build the D1 SQLite snapshot used for social-card metadata."""

import os

from mirror.commons.config import D1_DATABASE_PATH
from mirror.services.database import D1SqliteDatabase, SqliteDatabase


def map_album_details(albums) -> dict:
    """Collect per-album social-card fields, keyed by dpath."""
    dpath_to_details: dict = {}

    for album in albums:
        details = dpath_to_details.setdefault(album.src, {})

        if album.relation == "summary":
            details["description"] = album.target

        if album.relation == "permalink":
            details["path"] = f"/album/{album.target}"

        if album.relation == "title":
            details["title"] = album.target

    return dpath_to_details


def attach_cover_urls(dpath_to_details: dict, album_covers) -> None:
    """Attach each album's social-card image url."""
    for album_cover in album_covers:
        dpath = os.path.dirname(album_cover.fpath)

        if dpath_to_details.get(dpath):
            dpath_to_details[dpath]["image_url"] = album_cover.url


class D1Builder:
    """Populate the D1 cache DB from the main media index for social cards."""

    def __init__(self, db: SqliteDatabase) -> None:
        self.db = db

    def build(self) -> None:
        d1 = D1SqliteDatabase(D1_DATABASE_PATH)

        dpath_to_details = map_album_details(self.db.media_metadata_table().list_albums())

        album_covers = self.db.encoded_photos_table().list_by_role("social_card")
        attach_cover_urls(dpath_to_details, album_covers)

        socials = d1.social_card_table()
        for details in dpath_to_details.values():
            socials.add(
                path=details["path"],
                description=details["description"],
                title=details["title"],
                image_url=details["image_url"],
            )

        d1.dump()
