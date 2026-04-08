"""Video-related tables and views."""

import os
import sqlite3
from typing import Iterator

from mirror.commons.tables import ENCODED_VIDEO_TABLE, VIDEO_DATA_VIEW, VIDEOS_TABLE
from mirror.models.video import EncodedVideoModel, VideoModel


class VideoDataTable:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.conn.execute(VIDEO_DATA_VIEW)

    def list(self) -> Iterator[VideoModel]:
        for row in self.conn.execute("select * from view_video_data"):
            yield VideoModel.from_row(row)


class VideosTable:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.conn.execute(VIDEOS_TABLE)

    def add(self, fpath: str) -> None:
        dpath = os.path.dirname(fpath)
        self.conn.execute("insert or ignore into videos (fpath, dpath) values (?, ?)", (fpath, dpath))
        self.conn.commit()

    def delete(self, fpath: str) -> None:
        self.conn.execute("delete from videos where fpath = ?", (fpath,))
        self.conn.commit()

    def list(self) -> Iterator[str]:
        for row in self.conn.execute("select fpath from videos"):
            yield row[0]


class EncodedVideosTable:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.conn.execute(ENCODED_VIDEO_TABLE)

    def add(self, fpath: str, url: str, role: str, format: str) -> None:
        mimetype = f"video/{format}"

        self.conn.execute(
            "insert or ignore into encoded_videos (fpath, mimetype, role, url) values (?, ?, ?, ?)",
            (fpath, mimetype, role, url),
        )
        self.conn.commit()

    def list_for_file(self, fpath: str) -> Iterator[EncodedVideoModel]:
        for row in self.conn.execute(
            "select fpath, mimetype, role, url from encoded_videos where fpath = ?",
            (fpath,),
        ):
            yield EncodedVideoModel.from_row(row)

    def get_by_fpath_and_role(self, fpath: str, role: str) -> EncodedVideoModel:
        for row in self.conn.execute(
            "select fpath, mimetype, role, url from encoded_videos where fpath = ? and role = ?",
            (fpath, role),
        ):
            return EncodedVideoModel.from_row(row)

        raise ValueError(f"No encoded video found for fpath={fpath}, role={role}")
