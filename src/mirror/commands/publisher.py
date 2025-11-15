"""Mirror produces artifacts - files derived from the database. This file describes the artifacts
that are output, and checks they meet the expected constraints"""

from feedgen.feed import FeedGenerator
from datetime import datetime, timezone
import json
import os
from typing import Iterator, List, Optional, Protocol
from dateutil import tz

from mirror.config import PHOTOS_URL
from mirror.data.geoname import GeonameMetadataReader
from mirror.data.mirror import AlbumTriples, ExifReader, PhotoTriples, PhotosCountryReader, VideosReader
from mirror.data.photo_relations import PhotoRelationsReader
from mirror.data.things import ThingsReader
from mirror.data.types import SemanticTriple
from mirror.data.unesco import UnescoReader
from mirror.data.wikidata import WikidataMetadataReader
from mirror.database import SqliteDatabase
from mirror.photo import PhotoMetadataModel, PhotoModel
from mirror.things import Things
from mirror.utils import deterministic_hash_str
from mirror.video import VideoModel


class IArtifact(Protocol):
    """Artifacts expose string content derived from the database"""

    NAME: str
    CLEAN: bool = True

    def content(self, db: SqliteDatabase) -> str:
        """Return the content of the artifact"""
        pass

    @classmethod
    def short_cdn_url(cls, url: Optional[str]) -> str:
        return url.replace(PHOTOS_URL, "") if url else ""

class EnvArtifact(IArtifact):
    """Build artifact describing build information"""

    NAME = "env"

    publication_id: str

    def __init__(self, publication_id: str):
        self.publication_id = publication_id

    def content(self, db: SqliteDatabase) -> str:
        return json.dumps(
            {
                "photos_url": PHOTOS_URL,
                "publication_id": self.publication_id
            }
        )


class AtomArtifact:
    """Build artifact describing Atom feed with pagination"""

    CLEAN = False
    BASE_URL = "https://photos.rgrannell.xyz"

    def image_html(self, photo: PhotoModel) -> str:
        return f'<img src="{photo.mid_image_lossy_url}"/>'

    def video_html(self, video: VideoModel) -> str:
        return f'<video controls><source src="{video.video_url_1080p}" type="video/mp4"></video>'

    def media(self, db: SqliteDatabase) -> List[dict]:
        photos = db.photo_data_table().list()
        videos = db.video_data_table().list()

        media: List[dict] = []

        db.video_data_table()
        db.album_data_view()

        for video in videos:
            media.append(
                {
                    "id": video.poster_url,
                    "created_at": datetime.fromtimestamp(os.path.getmtime(video.fpath), tz=timezone.utc),
                    "url": video.video_url_unscaled,
                    "image": video.poster_url,
                    "content_html": self.video_html(video),
                }
            )

        for photo in photos:
            media.append(
                {
                    "id": photo.thumbnail_url,
                    "created_at": photo.get_ctime(),
                    "url": photo.thumbnail_url,
                    "image": photo.thumbnail_url,
                    "content_html": self.image_html(photo),
                }
            )

        return sorted(media, key=lambda item: item["created_at"])

    def paginate(self, items: List[dict], page_size: int) -> List[List[dict]]:
        """Split items into pages of given size."""

        return [items[idx : idx + page_size] for idx in range(0, len(items), page_size)]

    def subpage_filename(self, items: List[dict]) -> str:
        """Generate a stable filename for a page based on hashed IDs."""

        try:
            ids = ",".join(item["id"] for item in items)
            hash_suffix = deterministic_hash_str(ids)[:8]
            return f"atom-page-{hash_suffix}.xml"
        except Exception as e:
            raise ValueError(f"Error generating filename for items: {items}") from e

    def page_url(self, page) -> str:
        """Get the URL for a particular page"""

        next_file_url = os.path.join("/manifest/atom", self.subpage_filename(page))
        return f"{self.BASE_URL}{next_file_url}"

    def atom_page(self, page, next_page, output_dir):
        fg = FeedGenerator()
        fg.id(f"/{self.subpage_filename(page)}")

        fg.title("Photos.rgrannell.xyz")
        fg.author({"name": "Róisín"})
        fg.link(href=self.page_url(page), rel="self")

        if next_page:
            fg.link(href=self.page_url(next_page), rel="next")

        max_time = None
        for item in page:
            title = "Video" if "<video>" in item["content_html"] else "Photo"

            if not max_time or item["created_at"] > max_time:
                max_time = item["created_at"]

            entry = fg.add_entry()
            entry.id(item["id"])
            entry.title(title)
            entry.link(href=item["url"])
            entry.content(item["content_html"], type="html")

        fg.updated(max_time)

        file_path = os.path.join(output_dir, "atom", self.subpage_filename(page))
        fg.atom_file(file_path)

    def atom_feed(self, media: List[dict], output_dir: str):
        page_size = 20
        pages = self.paginate(media, page_size)

        atom_dir = os.path.join(output_dir, "atom")

        for idx, page in enumerate(pages[1:]):
            next_page = pages[idx + 1] if idx + 1 < len(pages) else None

            self.atom_page(page, next_page, output_dir)

        index_path = os.path.join(atom_dir, "atom-index.xml")
        index = FeedGenerator()

        index.title("Photos.rgrannell.xyz")
        index.id(f"{self.BASE_URL}/atom-index.xml")

        index.subtitle("A feed of my videos and images!")
        index.author({"name": "Róisín"})
        index.link(href=f"{self.BASE_URL}/atom-index.xml", rel="self")
        index.link(href=self.page_url(pages[0]), rel="next")

        max_time = None
        # TODO! A bug!
        for item in page:
            title = "Video" if "<video>" in item["content_html"] else "Photo"

            if not max_time or item["created_at"] > max_time:
                max_time = item["created_at"]

            entry = index.add_entry()
            entry.id(item["id"])
            entry.title(title)
            entry.link(href=item["url"])
            entry.content(item["content_html"], type="html")

        index.updated(max_time)
        index.atom_file(index_path)



class StatsArtifact(IArtifact):
    """Build artifact giving semantic facts for the albums page"""

    NAME = "stats"

    def validate(self, data: dict) -> None:
        countries = data["countries"]
        if countries < 10 or countries > 50:
            raise ValueError("broken countries count")

    def process(self): ...

    def count_type(self, type: str, subjects: List[PhotoMetadataModel]) -> int:
        unique_items = set()
        for subject in subjects:
            value = subject.target

            if not Things.is_urn(value):
                continue

            parsed = Things.from_urn(value)
            if value.startswith(f"urn:ró:{type}:"):
                unique_items.add(parsed["id"])

        return len(unique_items)

    def count_birds(self, subjects: List[PhotoMetadataModel]) -> int:
        return self.count_type("bird", subjects)

    def count_mammals(self, subjects: List[PhotoMetadataModel]) -> int:
        return self.count_type("mammal", subjects)

    def count_unesco_sites(self, places: List[PhotoMetadataModel], db: SqliteDatabase) -> int:
        # TODO this is not accurate.
        # Read through places, then cross-match

        unesco_places = set()

        for thing in ThingsReader().read(db):
            if thing.relation == "feature" and thing.target == "urn:ró:place_feature:unesco":
                unesco_places.add(thing.source)

        photo_places = set()

        for thing in places:
            if thing.target in unesco_places:
                photo_places.add(thing.target)

        return len(photo_places)

    def count_reptiles(self, subjects: List[PhotoMetadataModel]) -> int:
        return self.count_type("reptile", subjects)

    def count_amphibians(self, subjects: List[PhotoMetadataModel]) -> int:
        return self.count_type("amphibian", subjects)

    def count_fish(self, subjects: List[PhotoMetadataModel]) -> int:
        return self.count_type("fish", subjects)

    def count_countries(self, albums) -> int:
        return len({flag for album in albums for flag in album.flags})

    def count_years(self, albums: list) -> int:
        min_date = None
        max_date = None

        # calculate album date-ranges
        TIME_FORMAT = "%Y:%m:%d %H:%M:%S"
        for album in albums:
            if min_date is None or max_date is None:
                min_date = datetime.strptime(album.min_date, TIME_FORMAT)
                max_date = datetime.strptime(album.max_date, TIME_FORMAT)

            min_date = min(min_date, datetime.strptime(album.min_date, TIME_FORMAT))
            max_date = max(max_date, datetime.strptime(album.max_date, TIME_FORMAT))

        if not min_date or not max_date:
            raise ValueError("No albums found or albums have no dates")

        return max_date.year - min_date.year

    def content(self, db: SqliteDatabase) -> str:
        album_table = db.album_data_view()

        albums = list(album_table.list())

        subjects = list(db.photo_metadata_table().list_by_relation("subject"))
        places = list(db.photo_metadata_table().list_by_relation("location"))

        data = {
            "photos": sum(album.photos_count for album in albums),
            "videos": sum(album.videos_count for album in albums),
            "albums": len(albums),
            "years": self.count_years(albums),
            "countries": self.count_countries(albums),
            "bird_species": self.count_birds(subjects),
            "mammal_species": self.count_mammals(subjects),
            "reptile_species": self.count_reptiles(subjects),
            "amphibian_species": self.count_amphibians(subjects),
            "fish_species": self.count_fish(subjects),
            "unesco_sites": self.count_unesco_sites(places, db),
        }

        self.validate(data)
        return json.dumps(data, separators=(",", ":"), ensure_ascii=False)


class TriplesArtifact(IArtifact):
    """Build artifact describing semantic triples in the database"""

    NAME = "triples"

    def __init__(self):
        self.state = {
            # https://en.wikipedia.org/wiki/CURIE, e.g [isbn:0393315703]
            'curie': {
                'urn:ró:': 'i',
                'https://birdwatchireland.ie/birds/': 'birdwatch',
                'https://photos-cdn.rgrannell.xyz/': 'photos',
                'https://en.wikipedia.org/wiki/': 'wiki'
            }
        }

    def simplify(self, value: str) -> str:
        if not isinstance(value, str):
            return value

        for prefix, curie in self.state['curie'].items():
            if value.startswith(prefix):
                mapped =  f"[{value.replace(prefix, curie + ':')}]"

                if '[i::' in mapped:
                    raise ValueError(f"Invalid curie generated {value} -> {mapped}")

                return mapped
        return value

    def process(self, triple: SemanticTriple) -> list:
        return [[
                self.simplify(triple.source),
                triple.relation,
                self.simplify(triple.target)
        ]]

    def read(self, db: SqliteDatabase) -> Iterator[list]:
        readers = [
            AlbumTriples(),
            PhotoTriples(),
            ExifReader(),
            VideosReader(),
            GeonameMetadataReader(),
            ThingsReader(),
            UnescoReader(),
            WikidataMetadataReader(),
            PhotoRelationsReader(),
            PhotosCountryReader()
        ]
        for long, alias in self.state['curie'].items():
            yield [
                long, "curie", alias
            ]

        for reader in readers:
            for triple in reader.read(db):
                yield from self.process(triple)

    def content(self, db: SqliteDatabase) -> str:
        triples = list(self.read(db))
        return json.dumps(triples, separators=(",", ":"), ensure_ascii=False)


class ArtifactBuilder:
    """Build artifacts from the database, i.e publish
    the database to a directory"""

    def __init__(self, db: SqliteDatabase, output_dir: str):
        self.db = db
        self.output_dir = output_dir

    def remove_artifacts(self, dpath: str) -> None:
        # clear existing albums and images

        # TODO factor this out
        mirror_artifacts = [
            StatsArtifact,
            TriplesArtifact,
        ]

        removeable_prefixes = {klass.NAME for klass in mirror_artifacts if klass.CLEAN} | {'tribbles'}
        removeable = [file for file in os.listdir(dpath) if file.startswith(tuple(removeable_prefixes))]

        for file in removeable:
            os.remove(f"{dpath}/{file}")

    def publication_id(self) -> str:
        """Generate a unique publication id"""

        return deterministic_hash_str(str(datetime.now(tz.UTC)))

    def build(self) -> str:
        pid = self.publication_id()
        self.remove_artifacts(self.output_dir)

        print(f"{self.output_dir}/albums.{pid}.json")

        env = EnvArtifact(publication_id=pid)
        with open(f"{self.output_dir}/env.json", "w") as conn:
            conn.write(env.content(self.db))

        # atom feeds
        atom = AtomArtifact()
        atom.atom_feed(atom.media(self.db), self.output_dir)

        mirror_artifacts = [
            StatsArtifact,
            TriplesArtifact,
        ]

        # write each artifact to a `publication-id` output file
        for klass in mirror_artifacts:
            artifact = klass()
            content = artifact.content(self.db)

            with open(f"{self.output_dir}/{artifact.NAME}.{pid}.json", "w") as conn:
                conn.write(content)

        return pid
