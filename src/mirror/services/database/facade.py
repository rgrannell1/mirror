"""Main application SQLite database facade."""

import sqlite3
from typing import Set

from mirror.services.database.albums import AlbumContentsView, AlbumDataView, MediaMetadataTable
from mirror.services.database.knowledge import BinomialsWikidataIdTable, GeonameTable, WikidataTable
from mirror.services.database.photos import (
    EncodedPhotosTable,
    ExifTable,
    PhotoDataView,
    PhotoIconTable,
    PhotoMetadataSummaryView,
    PhotoMetadataTable,
    PhotoMetadataView,
    PhashesTable,
    PhotosTable,
)
from mirror.services.database.videos import EncodedVideosTable, VideoDataTable, VideosTable


class SqliteDatabase:
    """A SQLite database to store information about albums."""

    conn: sqlite3.Connection

    def __init__(self, fpath: str) -> None:
        self.conn = sqlite3.connect(fpath)
        # WAL-mode for concurrent reads and writes
        self.conn.execute("PRAGMA journal_mode=WAL;")
        # We do want foreign key constraints
        self.conn.execute("PRAGMA foreign_keys=ON;")
        # Not too long to wait
        self.conn.execute("PRAGMA busy_timeout=5000;")

    def delete_views(self) -> None:
        self.conn.execute("drop view if exists view_album_contents")
        self.conn.execute("drop view if exists view_album_data")
        self.conn.execute("drop view if exists view_photo_data")
        self.conn.execute("drop view if exists view_video_data")
        self.conn.execute("drop view if exists view_photo_metadata")
        self.conn.execute("drop view if exists view_photo_metadata_summary")
        self.conn.commit()

    def photo_icon_table(self):
        return PhotoIconTable(self.conn)

    def photos_table(self):
        return PhotosTable(self.conn)

    def photo_data_table(self):
        return PhotoDataView(self.conn)

    def video_data_table(self):
        return VideoDataTable(self.conn)

    def phashes_table(self):
        return PhashesTable(self.conn)

    def videos_table(self):
        return VideosTable(self.conn)

    def exif_table(self):
        return ExifTable(self.conn)

    def encoded_photos_table(self):
        return EncodedPhotosTable(self.conn)

    def encoded_videos_table(self):
        return EncodedVideosTable(self.conn)

    def album_data_view(self):
        return AlbumDataView(self.conn)

    def geoname_table(self):
        return GeonameTable(self.conn)

    def wikidata_table(self):
        return WikidataTable(self.conn)

    def binomials_wikidata_id_table(self):
        return BinomialsWikidataIdTable(self.conn)

    def media_metadata_table(self):
        return MediaMetadataTable(self.conn)

    def photo_metadata_table(self):
        return PhotoMetadataTable(self.conn)

    def photo_metadata_summary_view(self):
        return PhotoMetadataSummaryView(self.conn)

    def photo_metadata_view(self):
        return PhotoMetadataView(self.conn)

    def album_contents_view(self):
        return AlbumContentsView(self.conn)

    # TODO move
    def remove_deleted_photos(self, fpaths: Set[str]) -> None:
        """
        Remove rows from the DB for photos that no longer exist on disk.

        This intentionally does not touch videos because there is known coupling elsewhere.
        """
        photos_table = self.photos_table()
        exif_table = self.exif_table()
        phashes_table = self.phashes_table()
        icons_table = self.photo_icon_table()
        encoded_photos_table = self.encoded_photos_table()

        for fpath in photos_table.list():
            if fpath in fpaths:
                continue

            photos_table.delete(fpath)
            exif_table.delete(fpath)
            phashes_table.delete(fpath)
            icons_table.delete(fpath)
            encoded_photos_table.delete(fpath)

    # TODO move
    def remove_deleted_files(self, fpaths: Set[str]) -> None:
        for fpath in self.photos_table().list():
            if fpath not in fpaths:
                self.photos_table().delete(fpath)
                self.exif_table().delete(fpath)

        for fpath in self.videos_table().list():
            if fpath not in fpaths:
                self.videos_table().delete(fpath)

        for row in self.conn.execute("""
            select *
            from encoded_photos
            left join phashes on encoded_photos.fpath = phashes.fpath
            where encoded_photos.role = 'thumbnail_data_url'
            and phashes.fpath is null;
        """):
            fpath = row[0]
            self.encoded_photos_table().delete(fpath)
