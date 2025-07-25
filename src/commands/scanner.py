"""Scan all media in a vault, and index this information in a database"""

from typing import Iterator, Protocol
from src.config import GEONAMES_USERNAME
from src.constants import KnownRelations
from src.data.types import SemanticTriple
from src.data.wikidata import Wikidata
from src.database import SqliteDatabase
from src.exif import ExifReader, PhotoExifData
from src.phash import PHashReader, PhashData
from src.vault import MediaVault
from src.media import IMedia
from src.photo import Photo
from src.video import Video

from src.data.geoname import Geoname, GeonameMetadataReader
from src.things import Things


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


class GeonamesScanner(IScanner):
    """The API-scanner reads external data sources and updates the database with this information."""

    def __init__(self, db: SqliteDatabase):
        self.db = db

    def scan(self) -> None:
        """Scan the database for geonames and update them"""

        if not GEONAMES_USERNAME:
            raise ValueError("GEONAMES_USERNAME missing")

        geoname_table = self.db.geoname_table()
        photo_metadata_table = self.db.photo_metadata_table()

        geoname_client = Geoname(GEONAMES_USERNAME)
        geonames = set(md.target for md in photo_metadata_table.list_by_target_type("geoname"))

        for geoname in geonames:
            thing = Things.from_urn(geoname)
            id = thing["id"]

            if geoname_table.has(id):
                continue

            res = geoname_client.get_by_id(id)
            if res:
                geoname_table.add(id, res)


class WikidataScanner(IScanner):
    def __init__(self, db: SqliteDatabase):
        self.db = db

    def read_geonames_wikidata_ids(self) -> Iterator[SemanticTriple]:
        for triple in GeonameMetadataReader().read(self.db):
            if triple.relation == KnownRelations.WIKIDATA:
                yield triple

    def read_binomials(self) -> Iterator[str]:
        """Read distinct species binomials from the photo metadata table."""

        photo_metadata_table = self.db.photo_metadata_table()
        binomials = set()

        for photo_md in photo_metadata_table.list():
            target = photo_md.target
            if not Things.is_urn(target):
                continue

            parsed = Things.from_urn(target)
            if parsed["type"] not in {"mammal", "bird", "reptile", "amphibian", "fish"}:
                continue

            id = parsed["id"]
            if not id in binomials:
                yield id.replace('-', ' ').capitalize()
                binomials.add(id)

    def read_stored_binomials(self) -> Iterator[str]:
        """Read distinct species binomials from the wikidata table."""

        wikidata_table = self.db.wikidata_table()
        for datum in wikidata_table.list():
            ...

    def scan(self) -> None:
        """Read or infer wikidata IDs from our database, and collect wikidata properties"""

        wikidata_client = Wikidata()
        wikidata_table = self.db.wikidata_table()

        for triple in self.read_geonames_wikidata_ids():
            qid = triple.target

            if wikidata_table.has(qid):
                continue

            res = wikidata_client.get_by_id(qid)
            if not res:
                continue

            wikidata_table.add(qid, res)

        for binomial in self.read_binomials():
            print(binomial)