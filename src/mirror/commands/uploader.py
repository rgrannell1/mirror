"""Publish media to a CDN"""

import sys
from typing import Any
from mirror.cdn import CDN
from mirror.constants import FULL_SIZED_VIDEO_ROLE, IMAGE_ENCODINGS, VIDEO_ENCODINGS
from mirror.database import SqliteDatabase
from mirror.encoder import PhotoEncoder, VideoEncoder
from mirror.exceptions import InvalidVideoDimensionsException


class MediaUploader:
    """Publish photos and videos to a CDN. This class assumes anything in the database
    is published, but the database can be manually trimmed"""

    db: SqliteDatabase

    MOSAIC_ROLE = "thumbnail_mosaic"
    THUMBNAIL_ROLE = "video_thumbnail_webp"
    THUMBNAIL_FORMAT = "webp"
    FULL_ENCODING_FORMAT = "webp"
    VIDEO_FORMAT = "webm"

    VIDEO_ENCODINGS = VIDEO_ENCODINGS

    def __init__(self, db: SqliteDatabase, cdn: Any):
        self.db = db
        self.cdn = cdn

    def add_image_colours(self, fpath: str) -> None:
        """Add a data-url to the database"""

        encoded_photos_table = self.db.encoded_photos_table()

        encodings = list(encoded_photos_table.list_for_file(fpath))
        published_roles = {enc.role for enc in encodings}

        if self.MOSAIC_ROLE not in published_roles:
            v2 = PhotoEncoder.encode_image_colours(fpath)
            v2_content = f"{''.join(v2)}"

            encoded_photos_table.add(fpath, v2_content, self.MOSAIC_ROLE, "custom")

    def find_contrasting_colour(self, fpath: str) -> None:
        """Compute a nice constrasting grey for the metadata icon. Convert to greyscale, compute luminance
        and choose a grey perceptually a constant distance away."""
        ...

        icons = self.db.photo_icon_table()
        if icons.get_by_fpath(fpath):
            return

        grey_value = PhotoEncoder.compute_contrasting_grey(fpath)
        icons.add(fpath, grey_value)

    def publish_photo_encodings(self, fpath: str) -> None:
        """Publish all encodings for the given photo"""

        encoded_photos_table = self.db.encoded_photos_table()

        encodings = list(encoded_photos_table.list_for_file(fpath))
        published_roles = {enc.role for enc in encodings}

        for role, params in IMAGE_ENCODINGS.items():
            if role in published_roles:
                continue

            uploaded_url = self.cdn.upload_photo(
                encoded_data=PhotoEncoder.encode(fpath, role, params),
                role=role,
                format=params["format"],  # type: ignore
            )
            encoded_photos_table.add(fpath, uploaded_url, role, params["format"])

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

                if role == FULL_SIZED_VIDEO_ROLE:
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

        uploaded_video_url = self.cdn.upload_file_public(name=uploaded_video_name, encoded_path=encoded_path)
        print(f"published {fpath} as {uploaded_video_url}")

        self.db.encoded_videos_table().add(fpath, uploaded_video_url, role, self.VIDEO_FORMAT)

        return encoded_path

    # TODO: merge this
    def publish_thumbnail(self, fpath: str, encoded_path: str):
        """Encode and publish a video thumbnail"""

        encoded_thumbnail = VideoEncoder.encode_thumbnail(
            encoded_path, {"format": self.THUMBNAIL_FORMAT, "quality": 85, "method": 6}
        )

        thumbnail_url = self.cdn.upload_photo(
            encoded_data=encoded_thumbnail, role=self.THUMBNAIL_ROLE, format=self.THUMBNAIL_FORMAT
        )
        self.db.encoded_photos_table().add(
            fpath=fpath, url=thumbnail_url, role=self.THUMBNAIL_ROLE, format=self.THUMBNAIL_FORMAT
        )

    def upload(self) -> None:
        """Publish photos and videos to the CDN, and output artifacts"""

        for fpath in self.db.photos_table().list():
            self.add_image_colours(fpath)
            self.publish_photo_encodings(fpath)
            self.find_contrasting_colour(fpath)

        for fpath in self.db.videos_table().list():
            self.publish_video_encodings(fpath)
