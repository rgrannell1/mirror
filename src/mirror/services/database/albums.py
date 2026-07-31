"""Album-related views and media metadata."""

import sqlite3
from typing import Iterator, Optional

from mirror.commons.tables import ALBUM_CONTENTS_VIEW
from mirror.models.album import AlbumDataModel, AlbumMetadataModel


class AlbumContentsView:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.conn.execute(ALBUM_CONTENTS_VIEW)


class AlbumDataView:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        # DDL lives in `SqliteDatabase.refresh_dependent_views` so parallel jobs
        # do not contend on DROP/CREATE (see `views.refresh_dependent_views`).

    def list(self) -> Iterator[AlbumDataModel]:
        query = "select * from view_album_data"

        for row in self.conn.execute(query):
            yield AlbumDataModel.from_row(row)

    def get_album_data_by_dpath(self, dpath: str) -> Optional[AlbumDataModel]:
        query = "select * from view_album_data where dpath = ?"

        for row in self.conn.execute(query, (dpath,)):
            return AlbumDataModel.from_row(row)

        return None

    def album_dpaths_by_thumbnail_url(self) -> dict[str, str]:
        """Every thumbnail url mapped to its album dpath.

        Build this once when resolving a whole markdown table. The view aggregates, so one
        query per row is slow."""
        query = "select thumbnail_url, dpath from view_album_data where thumbnail_url is not null"
        return {row[0]: row[1] for row in self.conn.execute(query)}


class MediaMetadataTable:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        # define the table

    def list_albums(self) -> Iterator[AlbumMetadataModel]:
        for row in self.conn.execute("select * from media_metadata_table where src_type = 'album'"):
            yield AlbumMetadataModel.from_row(row)
