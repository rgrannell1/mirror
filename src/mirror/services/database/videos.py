"""Video-related tables and views."""

import os
import sqlite3
from typing import Iterator, List

from mirror.commons.tables import ENCODED_VIDEO_TABLE, VIDEO_DATA_VIEW, VIDEO_METADATA_SUMMARY, VIDEO_METADATA_TABLE, VIDEO_METADATA_VIEW, VIDEOS_TABLE
from mirror.models.video import EncodedVideoModel, VideoMetadataSummaryModel, VideoModel


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


class VideoMetadataTable:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.conn.execute(VIDEO_METADATA_TABLE)

    def add(self, fpath: str, src_type: str, relation: str, target: str) -> None:
        self.conn.execute(
            "insert or replace into video_metadata_table (fpath, src_type, relation, target) values (?, ?, ?, ?)",
            (fpath, src_type, relation, target),
        )
        self.conn.commit()

    def add_genre(self, fpath: str, genres: List[str]) -> None:
        for genre in set(genres):
            if not genre.strip():
                continue
            self.add(fpath, "video", "style", genre)

    def add_place(self, fpath: str, places: List[str]) -> None:
        for place in set(places):
            if not place.strip():
                continue
            self.add(fpath, "video", "location", place)

    def add_subject(self, fpath: str, subjects: List[str]) -> None:
        for subject in set(subjects):
            if not subject.strip():
                continue
            self.add(fpath, "video", "subject", subject)

    def add_description(self, fpath: str, description: str) -> None:
        if description.strip():
            self.add(fpath, "video", "summary", description)

    def add_rating(self, fpath: str, rating: str) -> None:
        if rating.strip():
            self.add(fpath, "video", "rating", rating)

    def add_covers(self, fpath: str, covers: List[str]) -> None:
        for cover in set(covers):
            if not cover.strip():
                continue
            if not cover.startswith("urn:ró:"):
                raise ValueError("cover must start with 'urn:ró:'")
            self.add(fpath, "video", "cover", cover)

    def _clear_relation(self, fpath: str, src_type: str, relation: str) -> None:
        self.conn.execute(
            "DELETE FROM video_metadata_table WHERE fpath = ? AND src_type = ? AND relation = ?",
            (fpath, src_type, relation),
        )

    def add_summary(self, fpath: str, metadata: VideoMetadataSummaryModel) -> None:
        for relation in ("style", "location", "subject", "summary", "rating"):
            self._clear_relation(fpath, "video", relation)
        self.add_genre(fpath, metadata.genre or [])
        self.add_place(fpath, metadata.places or [])
        self.add_subject(fpath, metadata.subjects or [])
        self.add_description(fpath, metadata.description or "")
        self.add_rating(fpath, metadata.rating or "")
        self.add_covers(fpath, metadata.covers or [])


class VideoMetadataSummaryView:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.conn.execute(VIDEO_METADATA_TABLE)
        self.conn.execute(VIDEO_METADATA_VIEW)
        self.conn.execute(VIDEO_METADATA_SUMMARY)

    def list(self) -> Iterator[VideoMetadataSummaryModel]:
        for row in self.conn.execute("select * from view_video_metadata_summary"):
            yield VideoMetadataSummaryModel.from_row(row)
