"""Publish media to a CDN"""

import base64
import sys
from typing import Any
from src.cdn import CDN
from src.constants import IMAGE_ENCODINGS, VIDEO_ENCODINGS
from src.database import SqliteDatabase
from src.encoder import PhotoEncoder, VideoEncoder
from src.exceptions import InvalidVideoDimensionsException
from src.photo import PhotoContent


class MediaUploader:
    """Publish photos and videos to a CDN. This class assumes anything in the database
    is published, but the database can be manually trimmed"""

    db: SqliteDatabase

    DATA_URL_ROLE = "thumbnail_data_url"
    THUMBNAIL_ROLE = "video_thumbnail_webp"
    THUMBNAIL_FORMAT = "webp"
    FULL_ENCODING_FORMAT = "webp"
    VIDEO_FORMAT = "webm"

    IMAGE_ENCODINGS = IMAGE_ENCODINGS
    VIDEO_ENCODINGS = VIDEO_ENCODINGS

    def __init__(self, db: SqliteDatabase, cdn: Any):
        self.db = db
        self.cdn = cdn

    def encode_image(self, role, fpath, params) -> PhotoContent:
        """Encode thumbnails or other images. Encodes either an image
        or a thumbnail"""

        if role.startswith("thumbnail"):
            return PhotoEncoder.encode_thumbnail(fpath, params)

        return PhotoEncoder.encode(fpath, params)

    def add_data_url(self, fpath: str) -> None:
        """Add a data-url to the database"""

        encoded_photos_table = self.db.encoded_photos_table()

        encodings = list(encoded_photos_table.list_for_file(fpath))
        published_roles = {enc.role for enc in encodings}

        # generate and store a data-url, if required
        if self.DATA_URL_ROLE not in published_roles:
            encoded = PhotoEncoder.encode_image_mosaic(fpath)

            encoded_content = base64.b64encode(encoded.content).decode("ascii")
            data_url = f"data:image/bmp;base64,{encoded_content}"

            self.db.encoded_photos_table().add(fpath, data_url, self.DATA_URL_ROLE, "bmp")

    def publish_photo_encodings(self, fpath: str) -> None:
        """Publish all encodings for the given photo"""

        encoded_photos_table = self.db.encoded_photos_table()

        encodings = list(encoded_photos_table.list_for_file(fpath))
        published_roles = {enc.role for enc in encodings}

        for role, params in self.IMAGE_ENCODINGS:
            if role in published_roles:
                continue

            uploaded_url = self.cdn.upload_photo(
                encoded_data=self.encode_image(role, fpath, params),
                role=role,
                format=params["format"],  # type: ignore
            )
            self.db.encoded_photos_table().add(fpath, uploaded_url, role, params["format"])

    def publish_video_encodings(self, fpath: str) -> None:
        """Publish all encodings for the given video"""

        encoded_videos_table = self.db.encoded_videos_table()

        encodings = list(encoded_videos_table.list_for_file(fpath))
        published_roles = {enc.role for enc in encodings}

        for role, params in self.VIDEO_ENCODINGS:
            if role in published_roles:
                continue

            try:
                encoded_path = self.publish_encoding(fpath, role, params)  # type: ignore

                if role == "video_libx264_unscaled":
                    self.publish_thumbnail(fpath, encoded_path)
            except InvalidVideoDimensionsException as err:
                print(err, file=sys.stderr)
            except Exception as err:
                print(err, file=sys.stderr)

    def is_silent(self, fpath: str) -> bool:
        """is a video silent?"""
        return "+silent" not in fpath

    def publish_encoding(self, fpath: str, role: str, params: dict) -> str:
        """Encode and publish a video encoding"""

        width, height, bitrate = params["width"], params["height"], params["bitrate"]
        uploaded_video_name = CDN.video_name(fpath, bitrate, width, height, self.VIDEO_FORMAT)

        encoded_path = VideoEncoder.encode(
            fpath=fpath,
            upload_file_name=uploaded_video_name,
            video_bitrate=bitrate,
            width=width,
            height=height,
            share_audio=self.is_silent(fpath),
        )

        if not encoded_path:
            raise Exception("Failed to encode video")

        print(fpath)
        uploaded_video_url = self.cdn.upload_file_public(name=uploaded_video_name, encoded_path=encoded_path)

        self.db.add_video_encoding(fpath=fpath, url=uploaded_video_url, role=role, format=self.VIDEO_FORMAT)
        return encoded_path

    def publish_thumbnail(self, fpath: str, encoded_path: str):
        """Encode and publish a video thumbnail"""

        encoded_thumbnail = VideoEncoder.encode_thumbnail(
            encoded_path, {"format": self.THUMBNAIL_FORMAT, "quality": 85, "method": 6}
        )

        thumbnail_url = self.cdn.upload_photo(
            encoded_data=encoded_thumbnail, role=self.THUMBNAIL_ROLE, format=self.THUMBNAIL_FORMAT
        )
        self.db.encoded_photos_table().add(
            fpath=fpath, url=self.THUMBNAIL_ROLE, role=self.THUMBNAIL_ROLE, format=self.THUMBNAIL_FORMAT
        )

    def upload(self) -> None:
        """Publish photos and videos to the CDN, and output artifacts"""

        for fpath in self.db.list_photos():
            self.add_data_url(fpath)
            self.publish_photo_encodings(fpath)

        for fpath in self.db.list_videos():
            self.publish_video_encodings(fpath)
