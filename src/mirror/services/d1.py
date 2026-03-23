"""Build the D1 SQLite snapshot used for social-card metadata."""

import os

from mirror.commons.config import D1_DATABASE_PATH
from mirror.services.database import D1SqliteDatabase, SqliteDatabase


class D1Builder:
    """Populate the D1 cache DB from the main media index for social cards."""

    def __init__(self, db: SqliteDatabase) -> None:
        self.db = db

    def build(self) -> None:
        d1 = D1SqliteDatabase(D1_DATABASE_PATH)

        encoded_photos = self.db.encoded_photos_table()
        media_metadata = self.db.media_metadata_table()
        albums = media_metadata.list_albums()

        dpath_to_details: dict = {}
        for album in albums:
            if album.src not in dpath_to_details:
                dpath_to_details[album.src] = {}

            if album.relation == "summary":
                dpath_to_details[album.src]["description"] = album.target

            if album.relation == "permalink":
                dpath_to_details[album.src]["path"] = f"/album/{album.target}"

            if album.relation == "title":
                dpath_to_details[album.src]["title"] = album.target

        album_covers = list(encoded_photos.list_by_role("social_card"))
        for album_cover in album_covers:
            dpath = os.path.dirname(album_cover.fpath)

            if dpath_to_details.get(dpath):
                dpath_to_details[dpath]["image_url"] = album_cover.url

        socials = d1.social_card_table()

        for details in dpath_to_details.values():
            socials.add(
                path=details["path"],
                description=details["description"],
                title=details["title"],
                image_url=details["image_url"],
            )

        d1.dump()
