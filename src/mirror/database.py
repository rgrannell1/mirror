"""A SQLite database to store information about albums."""

import json
import os
import sqlite3
from typing import Iterator, List, Optional, Set
from mirror.data.geoname import GeonameModel
from mirror.data.wikidata import WikidataModel
from mirror.exif import PhotoExifData
from mirror.phash import PhashData
from mirror.photo import EncodedPhotoModel, PhotoModel, PhotoMetadataModel, PhotoMetadataSummaryModel
from mirror.video import EncodedVideoModel, VideoModel
from mirror.album import AlbumDataModel, AlbumMetadataModel

# TODO split into subtables creations
from mirror.tables import (
    ENCODED_PHOTOS_TABLE,
    ENCODED_VIDEO_TABLE,
    GEONAME_TABLE,
    PHOTO_METADATA_SUMMARY,
    PHOTO_METADATA_VIEW,
    PHOTOS_TABLE,
    EXIF_TABLE,
    VIDEO_DATA_VIEW,
    VIDEOS_TABLE,
    ALBUM_DATA_VIEW,
    ALBUM_CONTENTS_TABLE,
    PHOTO_DATA_VIEW,
    PHASHES_TABLE,
    PHOTO_METADATA_TABLE,
    WIKIDATA_TABLE,
    BINOMIALS_WIKIDATA_ID_TABLE,
)
from mirror.video import Video
import string


class PhotosTable:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.conn.execute(PHOTOS_TABLE)

    def add(self, fpath: str) -> None:
        dpath = os.path.dirname(fpath)
        self.conn.execute(
            """
        insert or replace into photos (fpath, dpath)
            values (?, ?)
        """,
            (fpath, dpath),
        )
        self.conn.commit()

    def delete(self, fpath: str) -> None:
        self.conn.execute("delete from photos where fpath = ?", (fpath,))
        self.conn.commit()

    def list(self):
        for row in self.conn.execute("select fpath from photos"):
            yield row[0]


class PhotoDataTable:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.conn.execute(PHOTO_DATA_VIEW)

    def list(self) -> Iterator[PhotoModel]:
        for row in self.conn.execute("select * from photo_data"):
            yield PhotoModel.from_row(row)

    def get_by_fpath(self, fpath: str) -> Optional[PhotoModel]:
        for row in self.conn.execute("select * from photo_data where fpath = ?", (fpath,)):
            return PhotoModel.from_row(row)
        return None


class VideoDataTable:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.conn.execute(VIDEO_DATA_VIEW)

    def list(self) -> Iterator[VideoModel]:
        for row in self.conn.execute("select * from video_data"):
            yield VideoModel.from_row(row)


class PhashesTable:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.conn.execute(PHASHES_TABLE)

    def add(self, phash: PhashData) -> None:
        self.conn.execute(
            "insert or ignore into phashes (fpath, phash) values (?, ?)",
            (phash["fpath"], phash.get("phash")),
        )
        self.conn.commit()

    def phash_from_fpath(self, fpath: str) -> str | None:
        for row in self.conn.execute("select phash from phashes where fpath = ?", (fpath,)):
            return row[0]

        return None

    def fpaths_from_phash(self, phash: str) -> List[str]:
        fpaths = []
        for row in self.conn.execute("select fpath from phashes where phash = ?", (phash,)):
            fpaths.append(row[0])
        return fpaths

    def add_many(self, phashes: Iterator[PhashData]) -> None:
        for phash in phashes:
            self.add(phash)

    def has(self, fpath: str) -> bool:
        return bool(self.conn.execute("select 1 from phashes where fpath = ?", (fpath,)).fetchone())


class VideosTable:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.conn.execute(VIDEOS_TABLE)

    def add(self, fpath: str) -> None:
        dpath = os.path.dirname(fpath)
        self.conn.execute("insert or replace into videos (fpath, dpath) values (?, ?)", (fpath, dpath))
        self.conn.commit()

    def delete(self, fpath: str) -> None:
        self.conn.execute("delete from videos where fpath = ?", (fpath,))
        self.conn.commit()

    def list(self) -> Iterator[str]:
        for row in self.conn.execute("select fpath from videos"):
            yield row[0]


class ExifTable:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.conn.execute(EXIF_TABLE)

    def has(self, fpath: str) -> bool:
        return bool(self.conn.execute("select 1 from exif where fpath = ?", (fpath,)).fetchone())

    def add(self, exif: PhotoExifData) -> None:
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

    def add_many(self, exifs: Iterator[PhotoExifData]) -> None:
        for exif in exifs:
            self.add(exif)

    def list(self):
        for row in self.conn.execute("select * from exif"):
            yield PhotoExifData.from_row(row)

    def delete(self, fpath: str) -> None:
        self.conn.execute("delete from exif where fpath = ?", (fpath,))
        self.conn.commit()


class EncodedPhotosTable:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.conn.execute(ENCODED_PHOTOS_TABLE)

    def add(self, fpath: str, url: str, role: str, format: str) -> None:
        mimetype = f"image/{format}"

        self.conn.execute(
            "insert or replace into encoded_photos (fpath, mimetype, role, url) values (?, ?, ?, ?)",
            (fpath, mimetype, role, url),
        )
        self.conn.commit()

    def fpath_from_url(self, url: str) -> str | None:
        for row in self.conn.execute("select fpath from encoded_photos where url = ?", (url,)):
            return row[0]

        return None

    def list_for_file(self, fpath: str) -> Iterator[EncodedPhotoModel]:
        for row in self.conn.execute(
            "select fpath, mimetype, role, url from encoded_photos where fpath = ?",
            (fpath,),
        ):
            yield EncodedPhotoModel.from_row(row)

    def delete(self, fpath: str) -> None:
        self.conn.execute("delete from encoded_photos where fpath = ?", (fpath,))
        self.conn.commit()


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


class PhotoMetadataTable:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.conn.execute(PHOTO_METADATA_TABLE)

    def list(self) -> Iterator[PhotoMetadataModel]:
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

    def add(self, phash: str, src_type: str, relation: str, target: str) -> None:
        self.conn.execute(
            """
            insert or replace into photo_metadata_table (phash, src_type, relation, target) values (?, ?, ?, ?)""",
            (phash, src_type, relation, target),
        )
        self.conn.commit()

    def add_genre(self, phash: str, genres: List[str]) -> None:
        for genre in set(genres):
            if not genre.strip():
                continue

            self.add(phash, "photo", "style", genre)

    def add_place(self, phash: str, places: List[str]) -> None:
        for place in set(places):
            if not place.strip():
                continue

            self.add(phash, "photo", "location", place)

    def add_subject(self, phash: str, subjects: List[str]) -> None:
        for subject in set(subjects):
            if not subject.strip():
                continue

            self.add(phash, "photo", "subject", subject)

    def add_description(self, phash: str, description: str) -> None:
        if description.strip():
            return self.add(phash, "photo", "summary", description)

    def add_rating(self, phash: str, rating: str) -> None:
        if rating.strip():
            return self.add(phash, "photo", "rating", rating)

    def add_summary(self, phash: str, metadata: PhotoMetadataSummaryModel) -> None:
        self.add_genre(phash, metadata.genre or [])
        self.add_place(phash, metadata.places or [])
        self.add_subject(phash, metadata.subjects or [])
        self.add_description(phash, metadata.description or "")
        self.add_rating(phash, metadata.rating or "")

    def list_by_relation(self, relation: str) -> Iterator[PhotoMetadataModel]:
        query = """
        select
            fpath,
            relation,
            target
            from photo_metadata_table
        left join phashes
            on phashes.phash = photo_metadata_table.phash
        where relation = ?
        """

        for row in self.conn.execute(query, (relation,)):
            yield PhotoMetadataModel.from_row(row)

    def list_by_target_type(self, type: str) -> Iterator[PhotoMetadataModel]:
        # yes, this is SQL injection.

        if not all(c in string.ascii_letters for c in type):
            raise ValueError("type must contain only ASCII letters")

        query = f"""
        select
            fpath,
            relation,
            target
            from photo_metadata_table
        left join phashes
            on phashes.phash = photo_metadata_table.phash
        where target like "urn:ró:{type}:%"
        """

        for row in self.conn.execute(query):
            yield PhotoMetadataModel.from_row(row)


class PhotoMetadataSummaryTable:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.conn.execute(PHOTO_METADATA_SUMMARY)

    def list(self) -> Iterator[PhotoMetadataSummaryModel]:
        for row in self.conn.execute("select * from photo_metadata_summary"):
            yield PhotoMetadataSummaryModel.from_row(row)


class GeonameTable:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.conn.execute(GEONAME_TABLE)

    def add(self, id: str, data: dict) -> None:
        self.conn.execute(
            "insert or replace into geonames (id, data) values (?, ?)",
            (id, json.dumps(data)),
        )
        self.conn.commit()

    def has(self, id: str) -> bool:
        return bool(self.conn.execute("select 1 from geonames where id = ?", (id,)).fetchone())

    def list(self) -> Iterator[GeonameModel]:
        query = "select id, data from geonames"

        for row in self.conn.execute(query):
            yield GeonameModel.from_row(row)


class WikidataTable:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.conn.execute(WIKIDATA_TABLE)

    def add(self, id: str, data: dict | None) -> None:
        self.conn.execute(
            "insert or replace into wikidata (id, data) values (?, ?)",
            (id, json.dumps(data) if data else None),
        )
        self.conn.commit()

    def has(self, id: str) -> bool:
        return bool(self.conn.execute("select 1 from wikidata where id = ?", (id,)).fetchone())

    def get_by_id(self, id: str) -> Optional[WikidataModel]:
        query = "select id, data from wikidata where id = ?"

        for row in self.conn.execute(query, (id,)):
            return WikidataModel.from_row(row)

        return None

    def list(self) -> Iterator[WikidataModel]:
        query = "select id, data from wikidata"

        for row in self.conn.execute(query):
            yield WikidataModel.from_row(row)


class BinomialsWikidataIdTable:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.conn.execute(BINOMIALS_WIKIDATA_ID_TABLE)

    def add(self, binomial: str, qid: Optional[str]) -> None:
        self.conn.execute(
            "insert or replace into binomials_wikidata_id (binomial, qid) values (?, ?)",
            (binomial, qid),
        )
        self.conn.commit()

    def has(self, binomial: str) -> bool:
        return bool(self.conn.execute("select 1 from binomials_wikidata_id where binomial = ?", (binomial,)).fetchone())

    def get_qid(self, binomial: str) -> Optional[str]:
        """Given a binomial, get the WikiData ID"""
        query = "select qid from binomials_wikidata_id where binomial = ?"

        for row in self.conn.execute(query, (binomial,)):
            return row[0]

        return None

    def get_binomial(self, qid: str) -> Optional[str]:
        """Given a WikiData ID, get the binomial"""
        query = "select binomial from binomials_wikidata_id where qid = ?"

        for row in self.conn.execute(query, (qid,)):
            return row[0]

        return None

    def list(self) -> Iterator[tuple[str, str]]:
        query = "select binomial, qid from binomials_wikidata_id"

        for row in self.conn.execute(query):
            yield row


class AlbumDataTable:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.conn.execute(ALBUM_DATA_VIEW)

    def list(self) -> Iterator[AlbumDataModel]:
        query = "select * from album_data"

        for row in self.conn.execute(query):
            yield AlbumDataModel.from_row(row)

    def get_album_data_by_dpath(self, dpath: str) -> Optional[AlbumDataModel]:
        query = "select * from album_data where dpath = ?"

        for row in self.conn.execute(query, (dpath,)):
            return AlbumDataModel.from_row(row)

        return None

    def album_dpath_from_thumbnail_url(self, thumbnail_url: str) -> Optional[str]:
        query = "select dpath from album_data where thumbnail_url = ?"

        for row in self.conn.execute(query, (thumbnail_url,)):
            return row[0]

        return None


class MediaMetadataTable:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        # define the table

    def list_albums(self) -> Iterator[AlbumMetadataModel]:
        for row in self.conn.execute("select * from media_metadata_table where src_type = 'album'"):
            yield AlbumMetadataModel.from_row(row)


class SqliteDatabase:
    """A SQLite database to store information about albums."""

    conn: sqlite3.Connection

    def __init__(self, fpath: str) -> None:
        self.conn = sqlite3.connect(fpath)

    def photos_table(self):
        return PhotosTable(self.conn)

    def photo_data_table(self):
        return PhotoDataTable(self.conn)

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

    def album_data_table(self):
        return AlbumDataTable(self.conn)

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

    def photo_metadata_summary_table(self):
        return PhotoMetadataSummaryTable(self.conn)

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
