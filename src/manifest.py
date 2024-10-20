"""
Mirror doesn't really store much locally, but it keeps track of:

- encoded public versions of images and videos, and roles that can be used to reference them
- image and video listings
- album listing
- image and video metadata (this will also largely be echoed onto media via `xattr`)
- arbitrary relations (mostly referring to photos or vidoes) that are imported from external sources. This triple data
  can be treated as an open-schema graph database. It mostly contains Q&A information pulled from Linnaeus
"""

from dataclasses import dataclass
import os

import sqlite3
from typing import Iterator, Optional

from src.album import AlbumMetadata
from src.video import Video
from .photo import Photo
from .tables import (
    ENCODED_IMAGE_TABLE,
    IMAGES_TABLE,
    VIDEOS_ARTIFACT_VIEW,
    IMAGES_ARTIFACT_VIEW,
    VIDEOS_TABLE,
    ALBUM_TABLE,
    PHOTO_RELATIONS_TABLE,
    ENCODED_VIDEO_TABLE,
    ALBUMS_ARTIFACT_VIEW,
)
from .constants import (
    ATTR_DATE_TIME,
    ATTR_FSTOP,
    ATTR_FOCAL_EQUIVALENT,
    ATTR_MODEL,
    ATTR_ISO,
    ATTR_WIDTH,
    ATTR_HEIGHT,
)


@dataclass
class ImageMetadata:
    """Dataclass for image metadata"""

    image_url: str
    thumbnail_url: str
    date_time: str
    album_name: str

    def __init__(
        self, image_url: str, thumbnail_url: str, date_time: str, album_name: str
    ):
        self.image_url = image_url
        self.thumbnail_url = thumbnail_url
        self.date_time = date_time
        self.album_name = album_name


@dataclass
class VideoMetadata:
    """Dataclass for video metadata"""

    pass


class Manifest:
    """The local database containing information about the photo albums"""

    TABLES = {
        IMAGES_TABLE,
        VIDEOS_TABLE,
        ALBUM_TABLE,
        ENCODED_IMAGE_TABLE,
        ENCODED_VIDEO_TABLE,
        PHOTO_RELATIONS_TABLE,
        ALBUMS_ARTIFACT_VIEW,
        VIDEOS_ARTIFACT_VIEW,
        IMAGES_ARTIFACT_VIEW,
    }

    def __init__(self, db_path: str, metadata_path: str):
        fpath = os.path.expanduser(db_path)
        self.conn = sqlite3.connect(fpath)
        self.metadata_path = metadata_path

    def create(self) -> None:
        """Create the local database"""

        cursor = self.conn.cursor()

        for table in Manifest.TABLES:
            cursor.execute(table)

    def list_media_urls(self) -> Iterator[str]:
        """List all published URLs"""

        cursor = self.conn.cursor()
        cursor.execute("select distinct(url) from encoded_images")

        for row in cursor.fetchall():
            yield row[0]

        cursor = self.conn.cursor()
        cursor.execute("select distinct(url) from encoded_videos")

        for row in cursor.fetchall():
            yield row[0]

    def list_publishable_images(self) -> Iterator[Photo]:
        """List all images that are ready to be published"""

        cursor = self.conn.cursor()
        cursor.execute("select fpath from images where published = '1'")

        for row in cursor.fetchall():
            yield Photo(row[0], self.metadata_path)

    def list_publishable_videos(self) -> Iterator[Video]:
        """List all videos that are ready to be published"""

        cursor = self.conn.cursor()
        cursor.execute("select fpath from videos where published = '1'")

        for row in cursor.fetchall():
            yield Video(row[0], self.metadata_path)

    def image_metadata(self, fpath: str) -> Optional[ImageMetadata]:
        """Get metadata for a specific image"""

        cursor = self.conn.cursor()
        cursor.execute(
            """
    select
      full_sized_images.url as image_url_jpeg,
      thumbnail_images.url as thumbnail_url_jpeg,
      images.date_time as date_time,
      albums.album_name as album_name
    from images
    inner join albums on images.album = albums.fpath
    inner join encoded_images as full_sized_images
      on full_sized_images.fpath = images.fpath
    inner join encoded_images as thumbnail_images
      on thumbnail_images.fpath = images.fpath
    where images.published = '1'
      and images.fpath = ?
      and (
        (full_sized_images.mimetype = 'image/webp' and full_sized_images.role = 'full_image_lossless')
        and
        (thumbnail_images.mimetype = 'image/webp' and thumbnail_images.role = 'thumbnail_lossless'))
    """,
            (fpath,),
        )

        row = cursor.fetchone()
        if not row:
            return None

        return ImageMetadata(
            image_url=row[0], thumbnail_url=row[1], date_time=row[2], album_name=row[3]
        )

    def video_metadata(self, fpath: str) -> Optional[VideoMetadata]:
        """Get metadata for a specific video"""

        pass

    def add_album(self, album_md: AlbumMetadata) -> None:
        """Add an album to the local database"""

        cover_path = (
            os.path.join(album_md.fpath, album_md.cover)
            if album_md.cover != "Cover"
            else None
        )

        cursor = self.conn.cursor()
        cursor.execute(
            "insert or replace into albums (fpath, album_name, cover_image, cover_path, description, geolocation, permalink) values (?, ?, ?, ?, ?, ?, ?)",
            (
                album_md.fpath,
                album_md.title,
                album_md.cover,
                cover_path,
                album_md.description,
                album_md.geolocation,
                album_md.permalink,
            ),
        )
        self.conn.commit()

    def add_image(self, image: Photo) -> None:
        """Add an image to the local database"""

        path = image.path
        album = os.path.dirname(path)

        exif_md = image.get_exif_metadata()
        params = {
            "fpath": path,
            "tags": image.get_xattr_tag_string(),
            "published": image.is_published(),
            "album": album,
            "description": image.get_xattr_description(),
            "date_time": exif_md[ATTR_DATE_TIME],
            "f_number": exif_md[ATTR_FSTOP],
            "focal_length": exif_md[ATTR_FOCAL_EQUIVALENT],
            "model": exif_md[ATTR_MODEL],
            "iso": exif_md[ATTR_ISO],
            "blur": image.get_blur(),
            "shutter_speed": image.get_shutter_speed(),
            "width": exif_md[ATTR_WIDTH],
            "height": exif_md[ATTR_HEIGHT],
        }

        cursor = self.conn.cursor()
        cursor.execute(
            """
        insert into images (fpath, tags, published, album, description, date_time, f_number, focal_length, model, iso, blur, shutter_speed, width, height)
        values (:fpath, :tags, :published, :album, :description, :date_time, :f_number, :focal_length, :model, :iso, :blur, :shutter_speed, :width, :height)
        on conflict(fpath)
        do update set
            tags =          :tags,
            published =     :published,
            album =         :album,
            description =   :description,
            date_time =     :date_time,
            f_number =      :f_number,
            focal_length =  :focal_length,
            model =         :model,
            iso =           :iso,
            blur =          :blur,
            shutter_speed = :shutter_speed,
            width =         :width,
            height =        :height
        """,
            params,
        )

        self.conn.commit()

    def add_video(self, video: Video) -> None:
        path = video.path
        album = os.path.dirname(path)

        cursor = self.conn.cursor()
        cursor.execute(
            """
        insert into videos (fpath, tags, published, album, description, share_audio)
        values (:fpath, :tags, :published, :album, :description, :share_audio)
        on conflict(fpath)
        do update set
            tags =        :tags,
            published =   :published,
            album =       :album,
            description = :description,
            share_audio = :share_audio
        """,
            {
                "fpath": path,
                "tags": video.get_xattr_tag_string(),
                "published": video.is_published(),
                "album": album,
                "description": video.get_xattr_description(),
                "share_audio": video.get_xattr_share_audio(),
            },
        )

        self.conn.commit()

    def get_exif_hash(self, fpath: str) -> Optional[str]:
        cursor = self.conn.cursor()
        cursor.execute("select exif_hash from images where fpath = ?", (fpath, ))

        row = cursor.fetchone()
        return row[0] if row else None

    def get_metadata_hash(self, fpath: str) -> Optional[str]:
        cursor = self.conn.cursor()
        cursor.execute("select metadata_hash from images where fpath = ?", (fpath, ))

        row = cursor.fetchone()
        return row[0] if row else None

    def set_exif_hash(self, fpath: str, exif_hash: str) -> None:
        cursor = self.conn.cursor()
        cursor.execute(
            "update images set exif_hash = ? where fpath = ?", (exif_hash, fpath)
        )
        self.conn.commit()

    def set_metadata_hash(self, fpath: str, metadata_hash: str) -> None:
        cursor = self.conn.cursor()
        cursor.execute(
            "update images set metadata_hash = ? where fpath = ?", (metadata_hash, fpath)
        )
        self.conn.commit()

    def add_photo_relation(self, source: str, relation: str, target: str) -> None:
        """Add a relation between an image and a target"""

        cursor = self.conn.cursor()
        cursor.execute(
            """
    insert or replace into photo_relations (source, relation, target)
    values (?, ?, ?)
    """,
            (source, relation, target),
        )
        self.conn.commit()

    def has_encoded_image(self, image: Photo, role: str) -> bool:
        """Check if a thumbnail exists, according to the local database"""

        cursor = self.conn.cursor()
        cursor.execute(
            """
    select fpath from encoded_images
      where fpath = ? and role = ?
    """,
            (image.path, role),
        )

        row = cursor.fetchone()

        return row and bool(row[0])

    def has_video_thumbnail(self, video: Video) -> bool:
        """Check if a video thumbnail exists, according to the local database"""

        cursor = self.conn.cursor()
        cursor.execute(
            """
    select fpath from encoded_videos
      where fpath = ? and role = ?
    """,
            (video.path, "video_thumbnail_webp"),
        )

        row = cursor.fetchone()

        return row and bool(row[0])

    def add_encoded_image_url(
        self, fpath: str, url: str, role: str, format: str = "webp"
    ) -> None:
        """Register a thumbnail URL for an image in the local database"""

        mimetype = f"image/{format}"

        cursor = self.conn.cursor()
        cursor.execute(
            """
    insert or ignore into encoded_images (fpath, mimetype, role, url)
      values (?, ?, ?, ?)
    """,
            (fpath, mimetype, role, url),
        )
        self.conn.commit()

    def add_encoded_video_url(
        self, video: Video, url: str, role: str, format: str = "mp4"
    ) -> None:
        """Register a video URL in the local database"""

        mimetype = f"video/{format}"

        cursor = self.conn.cursor()
        cursor.execute(
            """
    insert or ignore into encoded_videos (fpath, mimetype, role, url)
      values (?, ?, ?, ?)
    """,
            (video.path, mimetype, role, url),
        )
        self.conn.commit()

    def add_album_dates(self, fpath: str, min_date: float, max_date: float) -> None:
        """Set minimum and maximum dates for an album"""

        cursor = self.conn.cursor()
        cursor.execute(
            """
      update albums
        set min_date = ?, max_date = ?
      where fpath = ?
    """,
            (min_date, max_date, fpath),
        )

        self.conn.commit()

    def add_google_photos_metadata(
        self, fpath: str, address: str, lat: str, lon: str
    ) -> None:
        """Insert location data into the images table"""

        cursor = self.conn.cursor()
        cursor.execute(
            """
    update images
      set latitude = ?, longitude = ?, address = ?
      where fpath like '%' || ?;
    """,
            (lat, lon, address, fpath),
        )
        self.conn.commit()

    def clear_photo_relations(self) -> None:
        """Clear all relations between images and targets"""

        cursor = self.conn.cursor()
        cursor.execute("delete from photo_relations")
        self.conn.commit()

    def close(self) -> None:
        """Close the local database connection"""

        self.conn.close()
