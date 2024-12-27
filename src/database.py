"""A SQLite database to store information about albums."""

import os
import sqlite3
from typing import Iterator, Protocol, Set
from src.exif import PhotoExifData
from src.phash import PhashData
from src.media import IMedia
from src.photo import Photo, EncodedPhotoModel, PhotoModel, PhotoMetadataModel
from src.video import EncodedVideoModel, VideoModel
from src.album import AlbumModel
from src.tables import (
    ENCODED_PHOTOS_TABLE,
    ENCODED_VIDEO_TABLE,
    PHOTOS_TABLE,
    EXIF_TABLE,
    VIDEO_DATA_VIEW,
    VIDEOS_TABLE,
    ALBUM_DATA_VIEW,
    ALBUM_CONTENTS_TABLE,
    PHOTO_DATA_VIEW,
    MEDIA_METADATA_TABLE,
    PHASHES_TABLE,
    PHOTO_METADATA_TABLE,
)
from src.video import Video
from src.linnaeus import AlbumAnswerModel


class IDatabase(Protocol):
    """To save time, information about albums is stored in a database."""

    def list_album_data(self) -> Iterator[AlbumModel]:
        pass

    def list_photo_data(self) -> Iterator[PhotoModel]:
        pass

    def list_video_data(self) -> Iterator[VideoModel]:
        pass

    def list_video_encodings(self, fpath: str) -> Iterator[EncodedVideoModel]:
        pass

    def list_photo_encodings(self, fpath: str) -> Iterator[EncodedPhotoModel]:
        pass

    def list_photo_metadata(self) -> Iterator[PhotoMetadataModel]:
        pass

    def has_exif(self, fpath: str) -> bool:
        pass

    def has_phash(self, fpath: str) -> bool:
        pass

    def write_media(self, media: Iterator[IMedia]) -> None:
        pass

    def write_phash(self, phashes: Iterator[PhashData]) -> None:
        pass

    def write_exif(self, exifs: Iterator[PhotoExifData]) -> None:
        pass

    def list_photos(self) -> Iterator[str]:
        pass

    def list_videos(self) -> Iterator[str]:
        pass

    def add_photo_encoding(self, fpath: str, url: str, role: str, format: str) -> None:
        pass

    def add_video_encoding(self, fpath: str, url: str, role: str, format: str) -> None:
        pass


class SqliteDatabase(IDatabase):
    """A SQLite database to store information about albums."""

    TABLES = {
        PHOTOS_TABLE,
        EXIF_TABLE,
        VIDEOS_TABLE,
        ALBUM_DATA_VIEW,
        ENCODED_PHOTOS_TABLE,
        ENCODED_VIDEO_TABLE,
        ALBUM_CONTENTS_TABLE,
        PHOTO_DATA_VIEW,
        VIDEO_DATA_VIEW,
        MEDIA_METADATA_TABLE,
        PHASHES_TABLE,
        PHOTO_METADATA_TABLE,
    }
    conn: sqlite3.Connection

    def __init__(self, fpath: str) -> None:
        self.conn = sqlite3.connect(fpath)

        for table in self.TABLES:
            self.conn.execute(table)

    def add_exif(self, exif: PhotoExifData) -> None:
        self.conn.execute(
            "insert or ignore into exif (fpath, created_at, f_stop, focal_length, model, exposure_time, iso, width, height) values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                exif["fpath"],
                exif.get("created_at"),
                exif.get("f_stop"),
                exif.get("focal_length"),
                exif.get("model"),
                exif.get("exposure_time"),
                exif.get("iso"),
                exif.get("width"),
                exif.get("height"),
            ),
        )
        self.conn.commit()

    def add_phash(self, phash: PhashData) -> None:
        self.conn.execute(
            "insert or ignore into phashes (fpath, phash) values (?, ?)",
            (phash["fpath"], phash["phash"]),
        )

    def has_exif(self, fpath: str) -> bool:
        return bool(self.conn.execute("select 1 from exif where fpath = ?", (fpath,)).fetchone())

    def has_phash(self, fpath: str) -> bool:
        return bool(self.conn.execute("select 1 from phashes where fpath = ?", (fpath,)).fetchone())

    def add_photo_encoding(self, fpath: str, url: str, role: str, format: str) -> None:
        mimetype = f"image/{format}"

        self.conn.execute(
            "insert or replace into encoded_photos (fpath, mimetype, role, url) values (?, ?, ?, ?)",
            (fpath, mimetype, role, url),
        )
        self.conn.commit()

    def add_video_encoding(self, fpath: str, url: str, role: str, format: str) -> None:
        mimetype = f"video/{format}"

        self.conn.execute(
            "insert or ignore into encoded_videos (fpath, mimetype, role, url) values (?, ?, ?, ?)",
            (fpath, mimetype, role, url),
        )
        self.conn.commit()

    def add_photo(self, fpath: str) -> None:
        dpath = os.path.dirname(fpath)
        self.conn.execute(
            """
            insert or replace into photos (fpath, dpath)
                values (?, ?)
            """,
            (fpath, dpath),
        )
        self.conn.commit()

    def add_video(self, fpath: str) -> None:
        dpath = os.path.dirname(fpath)
        self.conn.execute("insert or replace into videos (fpath, dpath) values (?, ?)", (fpath, dpath))
        self.conn.commit()

    def remove_exif(self, fpath: str) -> None:
        self.conn.execute("delete from exif where fpath = ?", (fpath,))
        self.conn.commit()

    def remove_photo(self, fpath: str) -> None:
        self.conn.execute("delete from photos where fpath = ?", (fpath,))
        self.conn.commit()

    def remove_video(self, fpath: str) -> None:
        self.conn.execute("delete from videos where fpath = ?", (fpath,))
        self.conn.commit()

    def list_photo_data(self) -> Iterator[PhotoModel]:
        for row in self.conn.execute("select * from photo_data"):
            yield PhotoModel.from_row(row)

    def list_video_data(self) -> Iterator[VideoModel]:
        for row in self.conn.execute("select * from video_data"):
            yield VideoModel.from_row(row)

    def list_album_data(self) -> Iterator[AlbumModel]:
        for row in self.conn.execute("select * from album_data"):
            yield AlbumModel.from_row(row)

    def list_photos(self) -> Iterator[str]:
        for row in self.conn.execute("select fpath from photos"):
            yield row[0]

    def list_photo_encodings(self, fpath: str) -> Iterator[EncodedPhotoModel]:
        for row in self.conn.execute(
            "select fpath, mimetype, role, url from encoded_photos where fpath = ?",
            (fpath,),
        ):
            yield EncodedPhotoModel.from_row(row)

    def list_video_encodings(self, fpath: str) -> Iterator[EncodedVideoModel]:
        for row in self.conn.execute(
            "select fpath, mimetype, role, url from encoded_videos where fpath = ?",
            (fpath,),
        ):
            yield EncodedVideoModel.from_row(row)

    def list_videos(self) -> Iterator[str]:
        for row in self.conn.execute("select fpath from videos"):
            yield row[0]

    def list_photo_metadata(self) -> Iterator[PhotoMetadataModel]:
        query = """
        select
            fpath,
            relation,
            target
            from photo_metadata_table
        left join phashes
            on phashes.phash = photo_metadata_table.phash
        where fpath like '%/Published%'
        """

        for row in self.conn.execute(query):
            yield PhotoMetadataModel.from_row(row)

    def remove_deleted_files(self, fpaths: Set[str]) -> None:
        for fpath in self.list_photos():
            if fpath not in fpaths:
                self.remove_photo(fpath)
                self.remove_exif(fpath)

        for fpath in self.list_videos():
            if fpath not in fpaths:
                self.remove_video(fpath)

    def write_media(self, media: Iterator[IMedia]) -> None:
        present_fpaths = set()

        # TODO; find a way to optimise perceptual hashing,
        # to avoid repeat calculation.

        for entry in media:
            if isinstance(entry, Photo):
                self.add_photo(entry.fpath)
                present_fpaths.add(entry.fpath)
            elif isinstance(entry, Video):
                self.add_video(entry.fpath)
                present_fpaths.add(entry.fpath)

        self.remove_deleted_files(present_fpaths)

    def write_exif(self, exifs: Iterator[PhotoExifData]) -> None:
        for exif in exifs:
            self.add_exif(exif)

    def write_phash(self, phashes: Iterator[PhashData]) -> None:
        for phash in phashes:
            self.add_phash(phash)

    def write_album_answers(self, answers: Iterator[AlbumAnswerModel]):
        for answer in answers:
            relation = None
            qid = answer.questionId

            relation = answer.relation()
            if not relation:
                raise Exception(f"Unknown questionId: {qid}")

            self.conn.execute(
                """
            insert or replace into media_metadata_table (src, src_type, relation, target)
                              values (?, ?, ?, ?)
            """,
                (answer.contentId, "album", relation, answer.answer),
            )
        self.conn.commit()

    def write_photo_answers(self, answers: Iterator[AlbumAnswerModel]):
        for answer in answers:
            # bug
            qid = answer.questionId
            if qid in {"question_id", "0", "3"}:
                continue

            relation = None
            qid = answer.questionId

            relation = answer.relation()
            if not relation:
                raise Exception(f"Unknown questionId: {qid}")

            contentId = answer.contentId
            phash = self.conn.execute("select phash from phashes where fpath = ?", (contentId,)).fetchone()

            if not phash:
                continue

            self.conn.execute(
                "insert or replace into photo_metadata_table (phash, src_type, relation, target) values (?, ?, ?, ?)",
                (phash[0], "photo", relation, answer.answer),
            )
        self.conn.commit()
