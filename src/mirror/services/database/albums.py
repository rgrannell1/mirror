"""Album-related views and media metadata."""

import sqlite3
from typing import Iterator, Optional

from mirror.commons.tables import ALBUM_CONTENTS_VIEW, ALBUM_DATA_VIEW
from mirror.models.album import AlbumDataModel, AlbumMetadataModel


class AlbumContentsView:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.conn.execute(ALBUM_CONTENTS_VIEW)


class AlbumDataView:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        # Ensure view definition stays up-to-date with the code.
        # (SQLite can't reliably "replace" views in all versions.)
        try:
            self.conn.execute("DROP VIEW IF EXISTS view_album_data;")
            self.conn.execute(ALBUM_DATA_VIEW)
        except sqlite3.OperationalError as err:
            # Handle race condition: another connection may have created the view
            if "already exists" in str(err):
                pass
            else:
                raise

    def list(self) -> Iterator[AlbumDataModel]:
        query = "select * from view_album_data"

        for row in self.conn.execute(query):
            yield AlbumDataModel.from_row(row)

    def get_album_data_by_dpath(self, dpath: str) -> Optional[AlbumDataModel]:
        query = "select * from view_album_data where dpath = ?"

        for row in self.conn.execute(query, (dpath,)):
            return AlbumDataModel.from_row(row)

        return None

    def album_dpath_from_thumbnail_url(self, thumbnail_url: str) -> Optional[str]:
        query = "select dpath from view_album_data where thumbnail_url = ?"

        for row in self.conn.execute(query, (thumbnail_url,)):
            return row[0]

        return None


class MediaMetadataTable:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        # define the table

    def clean(self) -> None:
        self.conn.execute("delete from media_metadata_table")
        self.conn.commit()

    def list_albums(self) -> Iterator[AlbumMetadataModel]:
        for row in self.conn.execute("select * from media_metadata_table where src_type = 'album'"):
            yield AlbumMetadataModel.from_row(row)
