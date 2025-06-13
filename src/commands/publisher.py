"""Mirror produces artifacts - files derived from the database. This file describes the artifacts
that are output, and checks they meet the expected constraints"""

from time import ctime
from feedgen.feed import FeedGenerator
from datetime import datetime, timezone
import json
import os
from typing import Any, List, Optional, Protocol
from dateutil import tz

from src.album import AlbumModel
from src.config import DATA_URL, PHOTOS_URL
from src.database import IDatabase
from src.exif import PhotoExifData
from src.photo import PhotoModel
from src.utils import deterministic_hash_str
from src.video import VideoModel
from src.flags import Flags


class IArtifact(Protocol):
    """Artifacts expose string content derived from the database"""

    def content(db: IDatabase, self) -> str:
        """Return the content of the artifact"""
        pass

    @classmethod
    def short_cdn_url(self, url: Optional[str]) -> str:
        return url.replace(PHOTOS_URL, "") if url else ""

    @classmethod
    def short_data_url(self, url: Optional[str]) -> str:
        return url.replace(DATA_URL, "") if url else ""

    @classmethod
    def flags(self, countries: List[str]) -> str:
        return Flags.from_countries(countries)


class MediaArtifact(IArtifact):
    """Build artifact describing secondary information about media in the database"""

    def content(db: IDatabase, self) -> str:
        return "[]"


class EnvArtifact(IArtifact):
    """Build artifact describing build information"""

    publication_id: str

    def __init__(self, publication_id: str):
        self.publication_id = publication_id

    def content(self, _: IDatabase) -> str:
        return json.dumps(
            {
                "photos_url": PHOTOS_URL,
                "data_url": "data:image/bmp;base64,",
                "publication_id": self.publication_id,
            }
        )


class AlbumsArtifact(IArtifact):
    """Build artifact describing albums in the database"""

    HEADERS = [
        "id",
        "album_name",
        "dpath",
        "photos_count",
        "videos_count",
        "min_date",
        "max_date",
        "thumbnail_url",
        "thumbnail_mosaic_url",
        "flags",
        "description",
    ]

    def validate(self, album: AlbumModel) -> None:
        pass

    def process(self, album: AlbumModel) -> List[Any]:
        self.validate(album)

        min_date = datetime.strptime(album.min_date, "%Y:%m:%d %H:%M:%S")
        max_date = datetime.strptime(album.max_date, "%Y:%m:%d %H:%M:%S")

        return [
            album.id,
            album.name,
            album.dpath,
            album.photos_count,
            album.videos_count,
            int(min_date.timestamp() * 1000),
            int(max_date.timestamp() * 1000),
            AlbumsArtifact.short_cdn_url(album.thumbnail_url),
            AlbumsArtifact.short_data_url(album.thumbnail_mosaic_url),
            AlbumsArtifact.flags(album.flags),
            album.description,
        ]

    def content(self, db: IDatabase):
        rows: List[List[Any]] = [self.HEADERS]

        for album in db.list_album_data():
            self.validate(album)
            rows.append(self.process(album))

        return json.dumps(rows)


class PhotosArtifact(IArtifact):
    """Build artifact describing images in the database"""

    HEADERS = ["id", "album_id", "tags", "thumbnail_url", "thumbnail_mosaic_url", "full_image", "created_at"]

    def process(self, photo: PhotoModel) -> List[Any]:
        created_at = datetime.strptime(str(photo.created_at), "%Y:%m:%d %H:%M:%S")

        return [
            deterministic_hash_str(photo.fpath),
            photo.album_id,
            photo.tags,
            PhotosArtifact.short_cdn_url(photo.thumbnail_url),
            PhotosArtifact.short_data_url(photo.thumbnail_mosaic_url),
            PhotosArtifact.short_cdn_url(photo.full_image),
            int(created_at.timestamp() * 1000),
        ]

    def content(self, db: IDatabase) -> str:
        rows: List[List[Any]] = [self.HEADERS]

        for photo in db.list_photo_data():
            rows.append(self.process(photo))

        return json.dumps(rows)


class VideosArtifact(IArtifact):
    """Build artifact describing videos in the database"""

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

    def content(self, db: IDatabase) -> str:
        rows: List[List[Any]] = [self.HEADERS]

        for video in db.list_video_data():
            rows.append(self.process(video))

        return json.dumps(rows)


class AtomArtifact:
    """Build artifact describing Atom feed with pagination"""

    BASE_URL = "https://photos.rgrannell.xyz"

    def image_html(self, photo: PhotoModel) -> str:
        return f'<img src="{photo.full_image}"/>'

    def video_html(self, video: VideoModel) -> str:
        return f'<video controls><source src="{video.video_url_1080p}" type="video/mp4"></video>'

    def media(self, db: IDatabase) -> List[dict]:
        photos = db.list_photo_data()
        videos = db.list_video_data()

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
                    "created_at": datetime.strptime(photo.created_at, "%Y:%m:%d %H:%M:%S").replace(
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

    def content(self, db: IDatabase) -> str:
        media = []

        for row in db.list_photo_metadata():
            media.append([deterministic_hash_str(row.fpath), row.relation, row.target])

        return json.dumps(media)


class ExifArtifact(IArtifact):
    """Build artifact describing exif information in the database"""

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

    def content(self, db: IDatabase) -> str:
        rows: List[List[Any]] = [self.HEADERS]

        for exif in db.list_exif():
            rows.append(self.process(exif))

        return json.dumps(rows)


class ArtifactBuilder:
    """Build artifacts from the database, i.e publish
    the database to a directory"""

    def __init__(self, db: IDatabase, output_dir: str):
        self.db = db
        self.output_dir = output_dir

    def remove_artifacts(self, dpath: str) -> None:
        # clear existing albums and images
        removeable = [
            file for file in os.listdir(dpath) if file.startswith(("albums", "images", "videos", "semantic", "exif"))
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

        albums = AlbumsArtifact()
        with open(f"{self.output_dir}/albums.{pid}.json", "w") as conn:
            conn.write(albums.content(self.db))

        photos = PhotosArtifact()
        with open(f"{self.output_dir}/images.{pid}.json", "w") as conn:
            conn.write(photos.content(self.db))

        env = EnvArtifact(publication_id=pid)
        with open(f"{self.output_dir}/env.json", "w") as conn:
            conn.write(env.content(self.db))

        videos = VideosArtifact()
        with open(f"{self.output_dir}/videos.{pid}.json", "w") as conn:
            conn.write(videos.content(self.db))

        atom = AtomArtifact()
        atom.atom_feed(atom.media(self.db), self.output_dir)

        semantic = SemanticArtifact()
        with open(f"{self.output_dir}/semantic.{pid}.json", "w") as conn:
            conn.write(semantic.content(self.db))

        exif = ExifArtifact()
        with open(f"{self.output_dir}/exif.{pid}.json", "w") as conn:
            conn.write(exif.content(self.db))

        return pid
