"""Publish media to a CDN"""

import base64
import sys
from typing import Any, List, Optional, Tuple, cast, TypedDict
from cdn import CDN
from database import IDatabase
from encoder import PhotoEncoder, VideoEncoder
from exceptions import InvalidVideoDimensionsException
from photo import PhotoContent


class VideoEncodingConfig(TypedDict):
    bitrate: str
    width: Optional[int]
    height: Optional[int]


VideoEncoding = Tuple[str, VideoEncodingConfig]


class MediaUploader:
    """Publish photos and videos to a CDN. This class assumes anything in the database
    is published, but the database can be manually trimmed"""

    db: IDatabase

    DATA_URL_ROLE = "thumbnail_data_url"
    THUMBNAIL_ROLE = "video_thumbnail_webp"
    THUMBNAIL_FORMAT = "webp"
    FULL_ENCODING_FORMAT = "webp"
    VIDEO_FORMAT = "webm"

    IMAGE_ENCODINGS = [
        ("thumbnail_lossy", {"format": "webp", "quality": 85, "method": 6}),
        ("full_image_lossless", {"format": "webp", "lossless": True}),
    ]

    VIDEO_ENCODINGS: List[VideoEncoding] = [
        (
            "video_libx264_unscaled",
            cast(
                VideoEncodingConfig,
                {
                    "bitrate": "30M",
                    "width": None,
                    "height": None,
                },
            ),
        ),
        (
            "video_libx264_1080p",
            cast(
                VideoEncodingConfig,
                {
                    "bitrate": "5000k",
                    "width": 1920,
                    "height": 1080,
                },
            ),
        ),
        (
            "video_libx264_720p",
            cast(
                VideoEncodingConfig,
                {
                    "bitrate": "2500k",
                    "width": 1280,
                    "height": 720,
                },
            ),
        ),
        (
            "video_libx264_480p",
            cast(
                VideoEncodingConfig,
                {
                    "bitrate": "1000k",
                    "width": 854,
                    "height": 480,
                },
            ),
        ),
    ]

    def __init__(self, db: IDatabase, cdn: Any):
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

        encodings = list(self.db.list_photo_encodings(fpath))
        published_roles = {enc.role for enc in encodings}

        # generate and store a data-url, if required
        if self.DATA_URL_ROLE not in published_roles:
            encoded = PhotoEncoder.encode_image_mosaic(fpath)

            encoded_content = base64.b64encode(encoded.content).decode("ascii")
            data_url = f"data:image/bmp;base64,{encoded_content}"

            self.db.add_photo_encoding(fpath, data_url, self.DATA_URL_ROLE, "bmp")

    def publish_photo_encodings(self, fpath: str) -> None:
        """Publish all encodings for the given photo"""

        encodings = list(self.db.list_photo_encodings(fpath))
        published_roles = {enc.role for enc in encodings}

        for role, params in self.IMAGE_ENCODINGS:
            if role in published_roles:
                continue

            uploaded_url = self.cdn.upload_photo(
                encoded_data=self.encode_image(role, fpath, params),
                role=role,
                format=params["format"],  # type: ignore
            )
            self.db.add_photo_encoding(fpath=fpath, url=uploaded_url, role=role, format=params["format"])  # type: ignore

    def publish_video_encodings(self, fpath: str) -> None:
        """Publish all encodings for the given video"""

        encodings = list(self.db.list_video_encodings(fpath))
        published_roles = {enc.role for enc in encodings}

        for role, params in self.VIDEO_ENCODINGS:
            if role in published_roles:
                continue

            try:
                encoded_path = self.publish_encoding(fpath, role, params)

                if role == "video_libx264_unscaled":
                    self.publish_thumbnail(fpath, encoded_path)
            except InvalidVideoDimensionsException as err:
                print(err, file=sys.stderr)
            except Exception as err:
                print(err, file=sys.stderr)

    def is_silent(self, fpath: str) -> bool:
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

        uploaded_video_url = self.cdn.upload_file_public(name=uploaded_video_name, encoded_path=encoded_path)

        self.db.add_video_encoding(fpath=fpath, url=uploaded_video_url, role=role, format=self.VIDEO_FORMAT)
        return encoded_path

    def publish_thumbnail(self, fpath: str, encoded_path: str):
        """Encode and publish a video thumbnail"""

        encoded_thumbnail = VideoEncoder.encode_thumbnail(encoded_path, {"format": self.THUMBNAIL_FORMAT, "quality": 85, "method": 6})

        thumbnail_url = self.cdn.upload_photo(
            encoded_data=encoded_thumbnail, role=self.THUMBNAIL_ROLE, format=self.THUMBNAIL_FORMAT
        )
        self.db.add_photo_encoding(fpath=fpath, url=thumbnail_url, role=self.THUMBNAIL_ROLE, format=self.THUMBNAIL_FORMAT)  # type: ignore

    def upload(self) -> None:
        """Publish photos and videos to the CDN, and output artifacts"""

        for fpath in self.db.list_photos():
            self.add_data_url(fpath)
            self.publish_photo_encodings(fpath)

        for fpath in self.db.list_videos():
            self.publish_video_encodings(fpath)
