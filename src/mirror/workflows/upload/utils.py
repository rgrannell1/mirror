from __future__ import annotations

from typing import Generator, Iterator, TypedDict

from mirror.commons.constants import IMAGE_ENCODINGS, MOSAIC_ENCODINGS, VIDEO_ENCODINGS
from mirror.services.cdn import CDN
from mirror.services.database import SqliteDatabase
from mirror.services.encoder import VideoEncoder


class PhotoJobInput(TypedDict):
    fpath: str


class UploadOpts(TypedDict, total=False):
    force_recompute_grey: bool
    force_recompute_mosaic: bool
    force_upload_images: bool
    force_upload_videos: bool
    force_roles: list[str] | None
    upload_images: bool | None
    upload_videos: bool | None


def list_photos_without_mosaic(db: SqliteDatabase, force_recompute: bool = False) -> Generator[str]:
    photos = db.photos_table()
    encoded_photos_table = db.encoded_photos_table()

    for fpath in photos.list():
        encodings = list(encoded_photos_table.list_for_file(fpath))
        published_roles = {enc.role for enc in encodings}

        if not MOSAIC_ENCODINGS.keys() <= published_roles or force_recompute:
            yield fpath


def list_photos_without_contrasting_grey(db: SqliteDatabase, force_recompute: bool = False) -> Iterator[str]:
    photos = db.photos_table()
    icons = db.photo_icon_table()

    for fpath in photos.list():
        if not icons.get_by_fpath(fpath) or force_recompute:
            yield fpath


def list_photos_without_upload(db: SqliteDatabase, force_upload: bool = False) -> Iterator[str]:
    photos = db.photos_table()

    if force_upload:
        yield from photos.list()
        return

    encoded_photos_table = db.encoded_photos_table()

    for fpath in photos.list():
        encodings = list(encoded_photos_table.list_for_file(fpath))
        published_roles = {enc.role for enc in encodings}

        needs_upload = False
        for role, _params in IMAGE_ENCODINGS.items():
            if role in published_roles:
                continue

            # only generate social-cards for album covers, for the moment
            if "+cover" not in fpath and role == "social_card":
                continue

            needs_upload = True

        if needs_upload:
            yield fpath


def list_videos_without_upload(db: SqliteDatabase, force_upload: bool = False) -> Iterator[str]:
    videos = db.videos_table().list()
    encoded_videos_table = db.encoded_videos_table()

    for fpath in videos:
        encodings = list(encoded_videos_table.list_for_file(fpath))
        published_roles = {enc.role for enc in encodings if enc.url and enc.url.strip()}
        needs_upload = False

        for role, _params in VIDEO_ENCODINGS:
            if role in published_roles:
                continue

            needs_upload = True

        if needs_upload:
            yield fpath


def is_silent(fpath: str) -> bool:
    """is a video silent?"""
    return "+silent" not in fpath


def publish_video_encoding(cdn, db, fpath, role, params):
    width, height, bitrate = params["width"], params["height"], params["bitrate"]
    uploaded_video_name = CDN.video_name(fpath, bitrate, width, height, "webm")

    if cdn.has_object(uploaded_video_name):
        # CDN already has the encoded asset; avoid re-encoding and just update the DB
        uploaded_video_url = cdn.url(uploaded_video_name)
        db.encoded_videos_table().add(fpath, uploaded_video_url, role, "webm")
        return None

    encoded_path = VideoEncoder.encode(
        fpath=fpath,
        upload_file_name=uploaded_video_name,
        video_bitrate=bitrate,
        width=width,
        height=height,
        share_audio=is_silent(fpath),
    )

    if not encoded_path:
        raise Exception("Failed to encode video")

    uploaded_video_url = cdn.upload_file_public(name=uploaded_video_name, encoded_path=encoded_path)

    db.encoded_videos_table().add(fpath, uploaded_video_url, role, "webm")
    db.encoded_videos_table().get_by_fpath_and_role(fpath, role)

    return encoded_path


def publish_video_thumbnail(cdn, db, fpath, encoded_path):
    thumbnail_format = "webp"
    thumbnail_role = "video_thumbnail_webp"
    encoded_thumbnail = VideoEncoder.encode_thumbnail(
        encoded_path, {"format": thumbnail_format, "quality": 85, "method": 6}
    )

    thumbnail_url = cdn.upload_photo(encoded_data=encoded_thumbnail, role=thumbnail_role, format=thumbnail_format)
    db.encoded_photos_table().add(fpath=fpath, url=thumbnail_url, role=thumbnail_role, format=thumbnail_format)
