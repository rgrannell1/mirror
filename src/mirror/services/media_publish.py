from __future__ import annotations

from typing import Generator, Iterator, TypedDict

from mirror.commons.config import DATABASE_PATH
from mirror.commons.constants import IMAGE_ENCODINGS, THUMBHASH_ROLES, VIDEO_ENCODINGS
from mirror.services.cdn import CDN
from mirror.services.database import SqliteDatabase
from mirror.services.encoder import PhotoEncoder, VideoEncoder
from mirror.services.selective_upload import is_role_skipped


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


def store_contrasting_grey(fpath: str) -> None:
    """Compute and store one photo's contrasting grey value."""
    with SqliteDatabase(DATABASE_PATH) as db:
        grey_value = PhotoEncoder.compute_contrasting_grey(fpath)
        db.photo_icon_table().add(fpath, grey_value)


def store_image_mosaic(fpath: str) -> None:
    """Compute and store one photo's ThumbHash placeholder."""
    with SqliteDatabase(DATABASE_PATH) as db:
        placeholder = PhotoEncoder.encode_thumbhash(fpath)
        for role in THUMBHASH_ROLES:
            db.encoded_photos_table().add(fpath, placeholder, role, "thumbhash")


def upload_photo_encoding(fpath: str, role: str, params: dict) -> str:
    """Encode, upload, and store one photo rendition."""
    encoded_data = PhotoEncoder.encode(fpath, role, params)
    uploaded_url = CDN().upload_photo(encoded_data, role, params["format"])
    with SqliteDatabase(DATABASE_PATH) as db:
        db.encoded_photos_table().add(fpath, uploaded_url, role, params["format"])
    return uploaded_url


def list_published_photo_roles(fpath: str) -> set[str]:
    """Return photo roles with a stored non-empty URL."""
    with SqliteDatabase(DATABASE_PATH) as db:
        encodings = db.encoded_photos_table().list_for_file(fpath)
        return {encoding.role for encoding in encodings if encoding.url and encoding.url.strip()}


def list_published_video_roles(fpath: str) -> set[str]:
    """Return stored video roles for one file."""
    with SqliteDatabase(DATABASE_PATH) as db:
        return {encoding.role for encoding in db.encoded_videos_table().list_for_file(fpath)}


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


def publish_video_encoding(fpath: str, role: str, params: dict) -> str | None:
    """Encode, upload, and store one video rendition."""
    cdn = CDN()
    uploaded_video_name = CDN.video_name(fpath, params, "mp4")

    if cdn.has_object(uploaded_video_name):
        uploaded_video_url = cdn.url(uploaded_video_name)
        with SqliteDatabase(DATABASE_PATH) as db:
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

    with SqliteDatabase(DATABASE_PATH) as db:
        db.encoded_videos_table().add(fpath, uploaded_video_url, role, "mp4")

    return encoded_path


def publish_video_thumbnail(fpath: str, encoded_path: str) -> None:
    """Encode, upload, and store one video thumbnail."""
    thumbnail_format = "webp"
    thumbnail_role = "video_thumbnail_webp"
    encoded_thumbnail = VideoEncoder.encode_thumbnail(
        encoded_path, {"format": thumbnail_format, "quality": 85, "method": 6}
    )

    thumbnail_url = CDN().upload_photo(
        encoded_data=encoded_thumbnail, role=thumbnail_role, format=thumbnail_format
    )
    with SqliteDatabase(DATABASE_PATH) as db:
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
