"""Scan all media in a vault, and index this information in a database"""

from typing import Iterator, Protocol
from src.config import GEONAMES_USERNAME
from src.constants import KnownRelations
from src.data.binomials import list_photo_binomials
from src.data.types import SemanticTriple
from src.data.wikidata import WikidataClient
from src.database import SqliteDatabase
from src.exif import ExifReader, PhotoExifData
from src.phash import PHashReader, PhashData
from src.vault import MediaVault
from src.media import IMedia
from src.photo import Photo
from src.video import Video

from src.data.geoname import GeonameClient, GeonameMetadataReader
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

        geoname_client = GeonameClient(GEONAMES_USERNAME)
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

    def add_geonames_wikidata(self):
        wikidata_client = WikidataClient()
        wikidata_table = self.db.wikidata_table()

        # List wikidata IDs from geonames metadata,
        # and ensure we've got a wikidata entry for each of them
        for triple in self.read_geonames_wikidata_ids():
            qid = triple.target

            if wikidata_table.has(qid):
                continue

            res = wikidata_client.get_by_id(qid)
            if not res:
                wikidata_table.add(qid, None)

            wikidata_table.add(qid, res)

    def add_binomials_wikidata(self):
        """Look up binomials in WikiData."""

        wikidata_client = WikidataClient()
        wikidata_table = self.db.wikidata_table()
        binomials_wikidata_table = self.db.binomials_wikidata_id_table()

        # subtract the set of stored binomials from the ones in our photos
        unsaved_binomials = set(list_photo_binomials(self.db))

        for binomial, qid in binomials_wikidata_table.list():
            if binomial in unsaved_binomials:
                unsaved_binomials.remove(binomial)

        # look each up, and store a binomial -> QID mapping and
        # QID to Wikidata mapping
        for binomial in unsaved_binomials:
            res = wikidata_client.get_by_binomial(binomial)
            if not res:
                binomials_wikidata_table.add(binomial, None)
                continue

            qid = res['id']

            binomials_wikidata_table.add(binomial, qid)
            wikidata_table.add(qid, res)

    def scan(self) -> None:
        """Read or infer wikidata IDs from our database, and collect wikidata properties"""

        self.add_geonames_wikidata()
        self.add_binomials_wikidata()

        print('done')