"""Scan all media in a vault, and index this information in a database"""

from typing import Iterator, Protocol, Set
from src.database import IDatabase
from src.linnaeus import SqliteLinnaeusDatabase, PhotoAnswerModel
from src.exif import ExifReader, PhotoExifData
from src.phash import PHashReader, PhashData
from src.vault import MediaVault
from src.media import IMedia
from src.photo import Photo


class IScanner(Protocol):
    """Scan information from some source into mirror's database"""

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
        """Return phashes for all photos not already stored in the database"""

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

    def photo_answers(self) -> Iterator[PhotoAnswerModel]:
        """Get all photo answers from Linnaeus"""

        for answer in self.linnaeus.list_photo_answers():
            if answer.contentId == "contentId":  # bug
                continue
            yield answer

    def phashes(self) -> Iterator[PhashData]:
        """Compute phashes for every photo referenced by Linnaeus"""

        distinct_fpaths: Set[str] = set()

        for answer in self.linnaeus.list_photo_answers():
            fpath = answer.contentId

            if fpath in distinct_fpaths or fpath == "fpath":
                continue

            if not self.db.has_phash(fpath):
                yield PHashReader.phash(fpath)

    def scan(self) -> None:
        """Read resouces from Linnaeus and write them to the mirror database"""

        self.db.write_phash(self.phashes())
