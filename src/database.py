"""A SQLite database to store information about albums."""

import os
import sqlite3
from typing import Iterator, Protocol, Set
from src.exif import PhotoExifData
from src.phash import PhashData
from src.media import IMedia
from src.photo import Photo, EncodedPhotoModel, PhotoModel, PhotoMetadataModel, PhotoMetadataSummaryModel
from src.video import EncodedVideoModel, VideoModel
from src.album import AlbumModel, AlbumMetadataModel
from src.tables import (
    ENCODED_PHOTOS_TABLE,
    ENCODED_VIDEO_TABLE,
    PHOTO_METADATA_SUMMARY,
    PHOTO_METADATA_VIEW,
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


class IDatabase(Protocol):
    """To save time, information about albums is stored in a database."""

    def list_album_data(self) -> Iterator[AlbumModel]: ...
    def list_album_metadata(self) -> Iterator[AlbumMetadataModel]: ...
    def list_photo_data(self) -> Iterator[PhotoModel]: ...
    def list_video_data(self) -> Iterator[VideoModel]: ...
    def list_video_encodings(self, fpath: str) -> Iterator[EncodedVideoModel]: ...
    def list_photo_encodings(self, fpath: str) -> Iterator[EncodedPhotoModel]: ...
    def list_photo_metadata(self) -> Iterator[PhotoMetadataModel]: ...
    def has_exif(self, fpath: str) -> bool: ...
    def has_phash(self, fpath: str) -> bool: ...
    def write_media(self, media: Iterator[IMedia]) -> None: ...
    def write_phash(self, phashes: Iterator[PhashData]) -> None: ...
    def write_exif(self, exifs: Iterator[PhotoExifData]) -> None: ...
    def list_exif(self) -> Iterator[PhotoExifData]: ...
    def list_photos(self) -> Iterator[str]: ...
    def list_videos(self) -> Iterator[str]: ...
    def add_photo_encoding(self, fpath: str, url: str, role: str, format: str) -> None: ...
    def add_video_encoding(self, fpath: str, url: str, role: str, format: str) -> None: ...
    def add_exif(self, exif: PhotoExifData) -> None: ...
    def add_phash(self, phash: PhashData) -> None: ...
    def add_photo(self, fpath: str) -> None: ...
    def add_video(self, fpath: str) -> None: ...
    def remove_deleted_files(self, fpaths: Set[str]) -> None: ...
    def remove_exif(self, fpath: str) -> None: ...
    def remove_photo(self, fpath: str) -> None: ...
    def remove_video(self, fpath: str) -> None: ...
    def write_album_metadata(self, metadata: Iterator[AlbumMetadataModel]) -> None: ...
    def list_photo_metadata_summary(self) -> Iterator[PhotoMetadataSummaryModel]: ...


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
        PHOTO_METADATA_VIEW,
        PHOTO_METADATA_SUMMARY
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
                exif.fpath,
                exif.created_at,
                exif.f_stop,
                exif.focal_length,
                exif.model,
                exif.exposure_time,
                exif.iso,
                exif.width,
                exif.height,
            ),
        )
        self.conn.commit()

    def add_phash(self, phash: PhashData) -> None:
        self.conn.execute(
            "insert or ignore into phashes (fpath, phash) values (?, ?)",
            (phash["fpath"], phash.get("phash")),
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

    def list_album_metadata(self) -> Iterator[AlbumMetadataModel]:
        for row in self.conn.execute("select * from media_metadata_table where src_type = 'album'"):
            yield AlbumMetadataModel.from_row(row)

    def list_exif(self) -> Iterator[PhotoExifData]:
        for row in self.conn.execute("select * from exif"):
            yield PhotoExifData.from_row(row)

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

    def write_album_metadata(self, metadata: Iterator[AlbumMetadataModel]):
        # TODO not ideal, move to dedicated function
        self.conn.execute("delete from media_metadata_table where src_type = 'album'")

        for item in metadata:
            self.conn.execute(
                """
            insert or replace into media_metadata_table (src, src_type, relation, target)
                              values (?, ?, ?, ?)
            """,
                (item.src, "album", item.relation, item.target),
            )
        self.conn.commit()

    def list_photo_metadata_summary(self) -> Iterator[PhotoMetadataSummaryModel]:
        for row in self.conn.execute("select * from photo_metadata_summary"):
            yield PhotoMetadataSummaryModel.from_row(row)
