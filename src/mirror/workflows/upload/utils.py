from __future__ import annotations

from typing import Generator, Iterator, TypedDict

from mirror.commons.config import DATABASE_PATH
from mirror.commons.constants import IMAGE_ENCODINGS, THUMBHASH_ROLES, VIDEO_ENCODINGS
from mirror.services.cdn import CDN
from mirror.services.database import SqliteDatabase
from mirror.services.encoder import VideoEncoder
from mirror.workflows.upload.selective import is_role_skipped


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


def is_legacy_mosaic(value: str) -> bool:
    """True for the old hex-colour mosaic format. ThumbHash base64 never starts with '#'."""
    return value.startswith("#")


def list_photos_without_mosaic(db: SqliteDatabase, force_recompute: bool = False) -> Generator[str]:
    photos = db.photos_table()
    encoded_photos_table = db.encoded_photos_table()

    for fpath in photos.list():
        encodings = list(encoded_photos_table.list_for_file(fpath))
        role_values = {enc.role: enc.url for enc in encodings}

        stale = any(
            role not in role_values or is_legacy_mosaic(role_values[role])
            for role in THUMBHASH_ROLES
        )
        if stale or force_recompute:
            yield fpath


def list_photos_without_contrasting_grey(
    db: SqliteDatabase, force_recompute: bool = False
) -> Iterator[str]:
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

            if is_role_skipped(role, fpath):
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


def publish_video_encoding(cdn, db, fpath, encoding: tuple[str, dict]):
    role, params = encoding
    uploaded_video_name = CDN.video_name(fpath, params, "mp4")

    if cdn.has_object(uploaded_video_name):
        # CDN already has the encoded asset; avoid re-encoding and just update the DB
        uploaded_video_url = cdn.url(uploaded_video_name)
        db.encoded_videos_table().add(fpath, uploaded_video_url, role, "mp4")
        return None

    encoded_path = VideoEncoder.encode(
        fpath=fpath,
        upload_file_name=uploaded_video_name,
        params=params,
        share_audio=is_silent(fpath),
    )

    if not encoded_path:
        raise Exception("Failed to encode video")

    uploaded_video_url = cdn.upload_file_public(name=uploaded_video_name, encoded_path=encoded_path)

    db.encoded_videos_table().add(fpath, uploaded_video_url, role, "mp4")
    db.encoded_videos_table().get_by_fpath_and_role(fpath, role)

    return encoded_path


def publish_video_thumbnail(cdn, db, fpath, encoded_path):
    thumbnail_format = "webp"
    thumbnail_role = "video_thumbnail_webp"
    encoded_thumbnail = VideoEncoder.encode_thumbnail(
        encoded_path, {"format": thumbnail_format, "quality": 85, "method": 6}
    )

    thumbnail_url = cdn.upload_photo(
        encoded_data=encoded_thumbnail, role=thumbnail_role, format=thumbnail_format
    )
    db.encoded_photos_table().add(
        fpath=fpath, url=thumbnail_url, role=thumbnail_role, format=thumbnail_format
    )


def roles_needing_upload(
    fpath: str, published_roles: set[str], force: bool, force_roles: set[str]
) -> Iterator[tuple[str, dict]]:
    """Image roles still to upload for this file."""
    for role, params in IMAGE_ENCODINGS.items():
        role_forced = force or role in force_roles
        if role in published_roles and not role_forced:
            continue

        if is_role_skipped(role, fpath):
            continue

        yield role, params


def list_upload_work(input: UploadOpts) -> tuple[list, list, list, list]:
    """fpaths needing grey, mosaic, photo-upload, and video-upload work."""
    photo_force = input.get("force_upload_images", False) or bool(input.get("force_roles"))

    with SqliteDatabase(DATABASE_PATH) as db:
        grey_fpaths = list(
            list_photos_without_contrasting_grey(db, input.get("force_recompute_grey", False))
        )
        mosaic_fpaths = list(
            list_photos_without_mosaic(db, input.get("force_recompute_mosaic", False))
        )
        photo_fpaths = (
            list(list_photos_without_upload(db, photo_force)) if input.get("upload_images") else []
        )
        video_fpaths = (
            list(list_videos_without_upload(db, input.get("force_upload_videos", False)))
            if input.get("upload_videos")
            else []
        )

    return grey_fpaths, mosaic_fpaths, photo_fpaths, video_fpaths
