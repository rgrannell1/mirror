"""Reconcile the SQLite media index with files present on disk."""

from __future__ import annotations

from typing import Set

from mirror.services.database import SqliteDatabase


class VaultIndexSync:
    """Remove DB rows for media that no longer exists in the vault."""

    def __init__(self, db: SqliteDatabase) -> None:
        self.db = db

    def remove_deleted_photos(self, fpaths: Set[str]) -> None:
        """
        Remove rows for photos not in ``fpaths``.

        Does not touch videos; deletion handling for videos is coupled elsewhere.
        """
        photos_table = self.db.photos_table()
        exif_table = self.db.exif_table()
        phashes_table = self.db.phashes_table()
        icons_table = self.db.photo_icon_table()
        encoded_photos_table = self.db.encoded_photos_table()

        for fpath in photos_table.list():
            if fpath in fpaths:
                continue

            photos_table.delete(fpath)
            exif_table.delete(fpath)
            phashes_table.delete(fpath)
            icons_table.delete(fpath)
            encoded_photos_table.delete(fpath)

    def remove_deleted_files(self, fpaths: Set[str]) -> None:
        """Remove photo and video rows absent from ``fpaths``, plus orphaned thumbnail rows."""
        for fpath in self.db.photos_table().list():
            if fpath not in fpaths:
                self.db.photos_table().delete(fpath)
                self.db.exif_table().delete(fpath)

        for fpath in self.db.videos_table().list():
            if fpath not in fpaths:
                self.db.videos_table().delete(fpath)

        for row in self.db.conn.execute("""
            select *
            from encoded_photos
            left join phashes on encoded_photos.fpath = phashes.fpath
            where encoded_photos.role = 'thumbnail_data_url'
            and phashes.fpath is null;
        """):
            fpath = row[0]
            self.db.encoded_photos_table().delete(fpath)
