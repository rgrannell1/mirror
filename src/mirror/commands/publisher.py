"""Mirror produces artifacts - files derived from the database. This file describes the artifacts
that are output, and checks they meet the expected constraints"""

from feedgen.feed import FeedGenerator
from datetime import datetime, timezone
import json
import os
from typing import Any, List, Optional, Protocol
from dateutil import tz
import markdown

from mirror.album import AlbumDataModel
from mirror.config import DATA_URL, PHOTOS_URL
from mirror.data.birdwatch import BirdwatchUrlReader
from mirror.data.geoname import GeonameMetadataReader
from mirror.data.wikidata import WikidataMetadataReader
from mirror.database import SqliteDatabase
from mirror.exif import PhotoExifData
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

    @classmethod
    def short_data_url(cls, url: Optional[str]) -> str:
        return url.replace(DATA_URL, "") if url else ""


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
                "data_url": "data:image/bmp;base64,",
                "publication_id": self.publication_id,
            }
        )


class AlbumsArtifact(IArtifact):
    """Build artifact describing albums in the database"""

    NAME = "albums"

    HEADERS = [
        "id",
        "album_name",
        "dpath",
        "photos_count",
        "videos_count",
        "min_date",
        "max_date",
        "thumbnail_url",
        "mosaic",
        "flags",
        "description",
    ]

    def process(self, album: AlbumDataModel) -> List[Any]:
        min_date = datetime.strptime(album.min_date, "%Y:%m:%d %H:%M:%S")
        max_date = datetime.strptime(album.max_date, "%Y:%m:%d %H:%M:%S")

        description = markdown.markdown(album.description) if album.description else ""

        return [
            album.id,
            album.name,
            album.dpath,
            album.photos_count,
            album.videos_count,
            int(min_date.timestamp() * 1000),
            int(max_date.timestamp() * 1000),
            AlbumsArtifact.short_cdn_url(album.thumbnail_url),
            album.mosaic_colours,
            album.flags,  # TODO MISNAMED
            description,
        ]

    def content(self, db: SqliteDatabase):
        rows: List[List[Any]] = [self.HEADERS]

        for album in db.album_data_table().list():
            processed = self.process(album)

            if len(self.HEADERS) != len(processed):
                raise ValueError(f"Processed album data does not match headers:\n{self.HEADERS}\n{processed}")

            rows.append(self.process(album))

        return json.dumps(rows)


class PhotosArtifact(IArtifact):
    """Build artifact describing images in the database"""

    NAME = "images"

    HEADERS = ["id", "album_id", "thumbnail_url", "mosaic_colours", "full_image", "created_at"]

    def process(self, photo: PhotoModel) -> List[Any]:
        created_at = datetime.strptime(str(photo.created_at), "%Y:%m:%d %H:%M:%S")

        return [
            deterministic_hash_str(photo.fpath),
            photo.album_id,
            PhotosArtifact.short_cdn_url(photo.thumbnail_url),
            photo.mosaic_colours,
            PhotosArtifact.short_cdn_url(photo.full_image),
            int(created_at.timestamp() * 1000),
        ]

    def content(self, db: SqliteDatabase) -> str:
        rows: List[List[Any]] = [self.HEADERS]

        for photo in db.photo_data_table().list():
            rows.append(self.process(photo))

        return json.dumps(rows)


class VideosArtifact(IArtifact):
    """Build artifact describing videos in the database"""

    NAME = "videos"

    HEADERS = [
        "id",
        "album_id",
        "tags",
        "description",
        "video_url_unscaled",
        "video_url_1080p",
        "video_url_720p",
        "video_url_480p",
        "poster_url",
    ]

    def process(self, video: VideoModel) -> List[Any]:
        return [
            deterministic_hash_str(video.fpath),
            video.album_id,
            video.tags,
            video.description,
            VideosArtifact.short_cdn_url(video.video_url_unscaled),
            VideosArtifact.short_cdn_url(video.video_url_1080p),
            VideosArtifact.short_cdn_url(video.video_url_720p),
            VideosArtifact.short_cdn_url(video.video_url_480p),
            VideosArtifact.short_cdn_url(video.poster_url),
        ]

    def content(self, db: SqliteDatabase) -> str:
        rows: List[List[Any]] = [self.HEADERS]

        for video in db.video_data_table().list():
            rows.append(self.process(video))

        return json.dumps(rows)


class AtomArtifact:
    """Build artifact describing Atom feed with pagination"""

    CLEAN = False
    BASE_URL = "https://photos.rgrannell.xyz"

    def image_html(self, photo: PhotoModel) -> str:
        return f'<img src="{photo.full_image}"/>'

    def video_html(self, video: VideoModel) -> str:
        return f'<video controls><source src="{video.video_url_1080p}" type="video/mp4"></video>'

    def media(self, db: SqliteDatabase) -> List[dict]:
        photos = db.photo_data_table().list()
        videos = db.video_data_table().list()

        media: List[dict] = []

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
                    "created_at": datetime.strptime(str(photo.created_at), "%Y:%m:%d %H:%M:%S").replace(
                        tzinfo=timezone.utc
                    ),  # TODO
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
        fg.author({"name": "R* Grannell"})
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
        index.author({"name": "R* Grannell"})
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


class SemanticArtifact(IArtifact):
    """Build artifact describing semantic information in the database"""

    NAME = "semantic"

    def content(self, db: SqliteDatabase) -> str:
        media = []

        # better the other way around
        # TODO remove this
        allowed_relations = {
            "bird_binomial",
            "summary",
            "style",
            "location",
            "mammal_binomial",
            "subject",
            "rating",
            "living_conditions",
            "wildlife",
            "plane_model",
            "vehicle",
        }

        for row in db.photo_metadata_table().list():
            if row.relation not in allowed_relations:
                continue

            target = row.target
            if row.relation == "summary":
                target = markdown.markdown(row.target)

            media.append([deterministic_hash_str(row.fpath), row.relation, target])

        return json.dumps(media)


class ExifArtifact(IArtifact):
    """Build artifact describing exif information in the database"""

    # TODO remap to triple format
    # remap model to a thingx

    NAME = "exif"

    HEADERS = ["id", "created_at", "f_stop", "focal_length", "model", "exposure_time", "iso", "width", "height"]

    def process(self, exif: PhotoExifData) -> List[Any]:
        parts = exif.created_at.split(" ") if exif.created_at else ""
        date = parts[0].replace(":", "/")
        created_at = f"{date} {parts[1]}"

        return [
            deterministic_hash_str(exif.fpath),
            created_at,
            exif.f_stop,
            exif.focal_length,
            exif.model,
            exif.exposure_time,
            exif.iso,
            exif.width,
            exif.height,
        ]

    def content(self, db: SqliteDatabase) -> str:
        rows: List[List[Any]] = [self.HEADERS]

        for exif in db.exif_table().list():
            rows.append(self.process(exif))

        return json.dumps(rows)


class StatsArtifact(IArtifact):
    """Build artifact giving semantic facts for the albums page"""

    NAME = "stats"

    def validate(self, data: dict) -> None:
        countries = data["countries"]
        if countries < 10 or countries > 50:
            raise ValueError("broken countries count")

    def process(self): ...

    def count_birds(self, subjects: List[PhotoMetadataModel]) -> int:
        unique_birds = set()
        for subject in subjects:
            value = subject.target

            if not Things.is_urn(value):
                continue

            parsed = Things.from_urn(value)
            if value.startswith("urn:ró:bird:"):
                unique_birds.add(parsed["id"])

        return len(unique_birds)

    def count_mammals(self, subjects: List[PhotoMetadataModel]) -> int:
        unique_mammals = set()
        for subject in subjects:
            value = subject.target

            if not Things.is_urn(value):
                continue

            parsed = Things.from_urn(value)
            if value.startswith("urn:ró:mammal:"):
                unique_mammals.add(parsed["id"])

        return len(unique_mammals)

    def count_unesco_sites(self, places: List[PhotoMetadataModel]) -> int:
        unique_sites = set()
        for place in places:
            value = place.target

            if not Things.is_urn(value):
                continue

            parsed = Things.from_urn(value)
            if value.startswith("urn:ró:unesco:"):
                unique_sites.add(parsed["id"])

        return len(unique_sites)

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
        album_table = db.album_data_table()

        albums = list(album_table.list())

        subjects = list(db.photo_metadata_table().list_by_relation("subject"))
        places = list(db.photo_metadata_table().list_by_relation("location"))

        data = {
            "photos": sum(album.photos_count for album in albums),
            "albums": len(albums),
            "years": self.count_years(albums),
            "countries": self.count_countries(albums),
            "bird_species": self.count_birds(subjects),
            "mammal_species": self.count_mammals(subjects),
            "unesco_sites": self.count_unesco_sites(places),
        }

        self.validate(data)
        return json.dumps(data)


class TriplesArtifact(IArtifact):
    """Build artifact describing semantic triples in the database"""

    NAME = "triples"

    def content(self, db: SqliteDatabase) -> str:
        triples = []

        geoname_reader = GeonameMetadataReader()
        for triple in geoname_reader.read(db):
            triples.append([triple.source, triple.relation, triple.target])

        wikidata_reader = WikidataMetadataReader()
        for triple in wikidata_reader.read(db):
            triples.append([triple.source, triple.relation, triple.target])

        birdwatch_url_reader = BirdwatchUrlReader()
        for triple in birdwatch_url_reader.read(db):
            triples.append([triple.source, triple.relation, triple.target])

        return json.dumps(triples)


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
            AlbumsArtifact,
            PhotosArtifact,
            VideosArtifact,
            SemanticArtifact,
            ExifArtifact,
            StatsArtifact,
            TriplesArtifact,
        ]

        removeable_prefixes = {
            klass.NAME for klass in mirror_artifacts if klass.CLEAN
        }
        removeable = [
            file
            for file in os.listdir(dpath)
            if file.startswith(tuple(removeable_prefixes))
        ]

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
            AlbumsArtifact,
            PhotosArtifact,
            VideosArtifact,
            SemanticArtifact,
            ExifArtifact,
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
