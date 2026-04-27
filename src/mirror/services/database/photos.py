"""Photo-related tables and views."""

import os
import sqlite3
import string
from typing import Iterator, List, Optional

from mirror.commons.tables import (
    ENCODED_PHOTOS_TABLE,
    EXIF_TABLE,
    PHASHES_TABLE,
    PHOTO_DATA_VIEW,
    PHOTO_ICON_TABLE,
    PHOTO_METADATA_SUMMARY,
    PHOTO_METADATA_TABLE,
    PHOTO_METADATA_VIEW,
    PHOTOS_TABLE,
)
from mirror.models.exif import PhotoExifData
from mirror.models.phash import PhashData
from mirror.models.photo import (
    EncodedPhotoModel,
    PhotoMetadataModel,
    PhotoMetadataSummaryModel,
    PhotoModel,
)


class PhotoIconTable:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.conn.execute(PHOTO_ICON_TABLE)

    def add(self, fpath: str, grey_value: str) -> None:
        with self.conn as conn:
            conn.execute("begin immediate;")
            conn.execute(
                "insert or replace into photo_icons (fpath, grey_value) values (?, ?)",
                (fpath, grey_value),
            )
            conn.commit()

    def get_by_fpath(self, fpath: str) -> Optional[str]:
        for row in self.conn.execute("select grey_value from photo_icons where fpath = ?", (fpath,)):
            return row[0]
        return None

    def list(self) -> Iterator[tuple[str, str]]:
        for row in self.conn.execute("select fpath, grey_value from photo_icons"):
            yield (row[0], row[1])

    def delete(self, fpath: str) -> None:
        self.conn.execute("delete from photo_icons where fpath = ?", (fpath,))
        self.conn.commit()


class PhotosTable:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.conn.execute(PHOTOS_TABLE)

    def add(self, fpath: str) -> None:
        dpath = os.path.dirname(fpath)

        with self.conn as conn:
            conn.execute("begin immediate;")
            conn.execute(
                """
            insert or replace into photos (fpath, dpath)
                values (?, ?)
            """,
                (fpath, dpath),
            )
            conn.commit()

    def delete(self, fpath: str) -> None:
        self.conn.execute("begin immediate;")
        self.conn.execute("delete from photos where fpath = ?", (fpath,))
        self.conn.commit()

    def list(self):
        for row in self.conn.execute("select fpath from photos"):
            yield row[0]


class PhotoDataView:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.conn.execute(PHOTO_DATA_VIEW)

    def list(self) -> Iterator[PhotoModel]:
        for row in self.conn.execute("select * from view_photo_data"):
            yield PhotoModel.from_row(row)

    def get_by_fpath(self, fpath: str) -> Optional[PhotoModel]:
        for row in self.conn.execute("select * from view_photo_data where fpath = ?", (fpath,)):
            return PhotoModel.from_row(row)
        return None


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

    def add_many(self, phashes: Iterator[PhashData]) -> None:
        rows = [(phash["fpath"], phash.get("phash")) for phash in phashes]
        if not rows:
            return
        self.conn.executemany(
            "insert or ignore into phashes (fpath, phash) values (?, ?)",
            rows,
        )
        self.conn.commit()

    def has(self, fpath: str) -> bool:
        return bool(self.conn.execute("select 1 from phashes where fpath = ?", (fpath,)).fetchone())

    def delete(self, fpath: str) -> None:
        self.conn.execute("delete from phashes where fpath = ?", (fpath,))
        self.conn.commit()


class ExifTable:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.conn.execute(EXIF_TABLE)

    def has(self, fpath: str) -> bool:
        return bool(self.conn.execute("select 1 from exif where fpath = ?", (fpath,)).fetchone())

    def add(self, exif: PhotoExifData) -> None:
        self.conn.execute(
            "insert or ignore into exif"
            " (fpath, created_at, f_stop, focal_length, model, exposure_time, iso, width, height)"
            " values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
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

        with self.conn as conn:
            conn.execute(
                "insert or replace into encoded_photos (fpath, mimetype, role, url) values (?, ?, ?, ?)",
                (fpath, mimetype, role, url),
            )
            conn.commit()

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

    def list_by_role(self, role: str) -> Iterator[EncodedPhotoModel]:
        for row in self.conn.execute(
            "select fpath, mimetype, role, url from encoded_photos where role = ?",
            (role,),
        ):
            yield EncodedPhotoModel.from_row(row)

    def delete(self, fpath: str) -> None:
        self.conn.execute("delete from encoded_photos where fpath = ?", (fpath,))
        self.conn.commit()


class PhotoMetadataView:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.conn.execute(PHOTO_METADATA_VIEW)


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

    def add_covers(self, phash: str, covers: List[str]) -> None:
        for cover in set(covers):
            if not cover.strip():
                continue

            if not cover.startswith("urn:ró:"):
                raise ValueError("cover must start with 'urn:ró:'")

            self.add(phash, "photo", "cover", cover)

    def _clear_relation(self, phash: str, src_type: str, relation: str) -> None:
        self.conn.execute(
            "DELETE FROM photo_metadata_table WHERE phash = ? AND src_type = ? AND relation = ?",
            (phash, src_type, relation),
        )

    def add_summary(self, phash: str, metadata: PhotoMetadataSummaryModel) -> None:
        for relation in ("style", "location", "subject", "summary", "rating"):
            self._clear_relation(phash, "photo", relation)
        self.add_genre(phash, metadata.genre or [])
        self.add_place(phash, metadata.places or [])
        self.add_subject(phash, metadata.subjects or [])
        self.add_description(phash, metadata.description or "")
        self.add_rating(phash, metadata.rating or "")
        self.add_covers(phash, metadata.covers or [])

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


class PhotoMetadataSummaryView:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.conn.execute(PHOTO_METADATA_SUMMARY)

    def list(self) -> Iterator[PhotoMetadataSummaryModel]:
        for row in self.conn.execute("select * from view_photo_metadata_summary"):
            yield PhotoMetadataSummaryModel.from_row(row)
