"""Scan all media in a vault, and index this information in a database"""

from typing import Iterator, Protocol
from database import IDatabase
from linnaeus import SqliteLinnaeusDatabase, AlbumAnswerModel
from exif import ExifReader, PhotoExifData
from phash import PHashReader
from vault import MediaVault
from media import IMedia
from photo import Photo


class IScanner(Protocol):
    def scan(self) -> None:
        pass


class MediaScanner(IScanner):
    """The media-scanner is a pull-based class responsible for scanning the photo-directories content
    and syncing it into a database.
    """

    def __init__(self, dpath: str, db: IDatabase):
        self.dpath = dpath
        self.db = db

    def media(self) -> Iterator[IMedia]:
        """Return all media in the directory"""

        for album in MediaVault(self.dpath).albums():
            for media in album.media():
                yield media

    def photo_exif(self, all=False) -> Iterator[PhotoExifData]:
        """Return exif data for all photos not in the database"""

        for media in self.media():
            if not Photo.is_a(media.fpath):
                continue

            if not all and not self.db.has_exif(media.fpath):
                yield ExifReader.exif(media.fpath)  # type: ignore

    def media_phash(self) -> Iterator[str]:
        for album in MediaVault(self.dpath).albums():
            for media in album.media():
                if not Photo.is_a(media.fpath):
                    continue

                if not self.db.has_phash(media.fpath):
                    yield PHashReader.phash(media.fpath)

    def scan(self) -> None:
        """Scanning should collect information on the photo library from various sources. Each writer is
        responsible for minimising state-change (i.e try not to repeat work) and should account for the
        possiblity files are deleted."""

        self.db.write_media(self.media())
        self.db.write_exif(self.photo_exif())
        self.db.write_phash(self.media_phash())


class LinnaeusScanner(IScanner):
    """The linneaeus scanner pulls information from the Linnaeus database and syncs it into the mirror database"""

    def __init__(self, db: IDatabase):
        self.db = db
        self.linnaeus = SqliteLinnaeusDatabase("/home/rg/Code/websites/linneaus.local/.linny.db")

    def album_answers(self) -> Iterator[AlbumAnswerModel]:
        for answer in self.linnaeus.list_album_answers():
            yield answer

    def scan(self) -> None:
        """"""

        self.db.write_album_answers(self.album_answers())
