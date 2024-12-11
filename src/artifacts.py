"""Mirror produces artifacts - files derived from the database. This file describes the artifacts
that are output, and checks they meet the expected constraints"""

from datetime import datetime
import json
import os
from typing import Any, List, Optional, Protocol

from album import AlbumModel
from config import DATA_URL, PHOTOS_URL
from database import IDatabase
from photo import PhotoModel
from utils import deterministic_hash_str
from video import VideoModel
from flags import Flags

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
            album.description
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

    def validate(self, photo: PhotoModel) -> None:
        pass

    def process(self, photo: PhotoModel) -> List[Any]:
        created_at = datetime.strptime(photo.created_at, "%Y:%m:%d %H:%M:%S")

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
            self.validate(photo)
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

    def validate(self, video: VideoModel) -> None:
        pass

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
            self.validate(video)
            rows.append(self.process(video))

        return json.dumps(rows)


class ArtifactBuilder:
    """Build artifacts from the database, i.e publish
    the database to a directory"""

    def __init__(self, db: IDatabase, output_dir: str):
        self.db = db
        self.output_dir = output_dir

    def remove_artifacts(self, dpath: str) -> None:
        # clear existing albums and images
        removeable = [file for file in os.listdir(dpath) if file.startswith(("albums", "images", "videos"))]

        for file in removeable:
            os.remove(f"{dpath}/{file}")

    def publication_id(self) -> str:
        """Generate a unique publication id"""

        return deterministic_hash_str(str(datetime.now()))

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

        return pid
