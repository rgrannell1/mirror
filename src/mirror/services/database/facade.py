"""Main application SQLite database facade."""

import sqlite3

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
from mirror.services.database.views import refresh_dependent_views as rebuild_dependent_views
from mirror.services.database.videos import (
    EncodedVideosTable,
    VideoDataTable,
    VideoMetadataTable,
    VideoMetadataSummaryView,
    VideosTable,
)


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

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def delete_views(self) -> None:
        self.conn.execute("drop view if exists view_album_contents")
        self.conn.execute("drop view if exists view_album_data")
        self.conn.execute("drop view if exists view_photo_data")
        self.conn.execute("drop view if exists view_video_data")
        self.conn.execute("drop view if exists view_photo_metadata")
        self.conn.execute("drop view if exists view_photo_metadata_summary")
        self.conn.execute("drop view if exists view_video_metadata")
        self.conn.execute("drop view if exists view_video_metadata_summary")
        self.conn.commit()

    def refresh_dependent_views(self) -> None:
        """Recreate all derived views; safe for concurrent reads only after this commits."""
        rebuild_dependent_views(self.conn)

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

    def video_metadata_table(self):
        return VideoMetadataTable(self.conn)

    def video_metadata_summary_view(self):
        return VideoMetadataSummaryView(self.conn)

    def album_contents_view(self):
        return AlbumContentsView(self.conn)
