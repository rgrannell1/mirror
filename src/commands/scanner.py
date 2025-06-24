"""Scan all media in a vault, and index this information in a database"""

from typing import Iterator, Protocol
from src.database import SqliteDatabase
from src.exif import ExifReader, PhotoExifData
from src.phash import PHashReader, PhashData
from src.vault import MediaVault
from src.media import IMedia
from src.photo import Photo
from src.video import Video


class IScanner(Protocol):
    """Scan information from some source into mirror's database"""

    def scan(self) -> None:
        pass


class MediaScanner(IScanner):
    """The media-scanner is a pull-based class responsible for scanning the photo-directories content
    and syncing it into a database.
    """

    def __init__(self, dpath: str, db: SqliteDatabase):
        self.dpath = dpath
        self.db = db

    def _list_current_media(self) -> Iterator[IMedia]:
        """Return all media in the directory"""

        for album in MediaVault(self.dpath).albums():
            for media in album.media():
                yield media

    def _unsaved_exifs(self) -> Iterator[PhotoExifData]:
        """Return exif data for all photos not in the database"""

        exif_table = self.db.exif_table()

        for media in self._list_current_media():
            if not Photo.is_a(media.fpath):
                continue

            if not exif_table.has(media.fpath):
                yield ExifReader.exif(media.fpath)  # type: ignore

    def _unsaved_phashes(self) -> Iterator[PhashData]:
        """Return phashes for all photos not already stored in the database"""

        phash_table = self.db.phashes_table()

        for album in MediaVault(self.dpath).albums():
            for media in album.media():
                if not Photo.is_a(media.fpath):
                    continue

                if not phash_table.has(media.fpath):
                    yield PHashReader.phash(media.fpath)

    def scan(self) -> None:
        """Scanning should collect information on the photo library from various sources. Each writer is
        responsible for minimising state-change (i.e try not to repeat work) and should account for the
        possiblity files are deleted."""

        phash_table = self.db.phashes_table()
        exif_table = self.db.exif_table()
        photos_table = self.db.photos_table()
        videos_table = self.db.videos_table()

        current_fpaths = set()

        for entry in self._list_current_media():
            if isinstance(entry, Photo):
                photos_table.add(entry.fpath)
                current_fpaths.add(entry.fpath)
            elif isinstance(entry, Video):
                videos_table.add(entry.fpath)
                current_fpaths.add(entry.fpath)

        self.db.remove_deleted_files(current_fpaths)

        exif_table.add_many(self._unsaved_exifs())
        phash_table.add_many(self._unsaved_phashes())
