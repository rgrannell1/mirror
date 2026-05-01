from __future__ import annotations

from collections.abc import Generator
from typing import Any

from zahir import JobContext, await_all, concurrency_dependency, resource_dependency, sqlite_dependency

from mirror.commons.config import DATABASE_PATH
from mirror.commons.constants import FULL_SIZED_VIDEO_ROLE, IMAGE_ENCODINGS, MOSAIC_ENCODINGS, VIDEO_ENCODINGS
from mirror.commons.exceptions import InvalidVideoDimensionsError
from mirror.services.cdn import CDN
from mirror.services.database import SqliteDatabase
from mirror.services.encoder import PhotoEncoder
from mirror.workflows.upload.utils import (
    PhotoJobInput,
    UploadOpts,
    list_photos_without_contrasting_grey,
    list_photos_without_mosaic,
    list_photos_without_upload,
    list_videos_without_upload,
    publish_video_encoding,
    publish_video_thumbnail,
)


def compute_contrasting_grey(ctx: JobContext, input: PhotoJobInput) -> Generator[Any, Any, None]:
    fpath = input["fpath"]

    with SqliteDatabase(DATABASE_PATH) as db:
        icons = db.photo_icon_table()
        grey_value = PhotoEncoder.compute_contrasting_grey(fpath)
        icons.add(fpath, grey_value)

    return None
    yield


def compute_image_mosaic(ctx: JobContext, input: PhotoJobInput) -> Generator[Any, Any, None]:
    fpath = input["fpath"]

    with SqliteDatabase(DATABASE_PATH) as db:
        encoded_photos_table = db.encoded_photos_table()
        for role, params in MOSAIC_ENCODINGS.items():
            colours = PhotoEncoder.encode_image_colours(fpath, params["width"], params["height"])
            encoded_photos_table.add(fpath, "".join(colours), role, "custom")

    return None
    yield


_PHOTO_CDN_LIMIT = "global_photo_cdn_limit"
_VIDEO_CDN_LIMIT = "global_video_cdn_limit"


def upload_photo(ctx: JobContext, input: dict) -> Generator[Any, Any, dict]:
    fpath = input["fpath"]
    role = input["role"]
    params = input["params"]
    force = input.get("force", False)

    yield from concurrency_dependency(_PHOTO_CDN_LIMIT, limit=6)

    cdn = CDN()
    with SqliteDatabase(DATABASE_PATH) as db:
        uploaded_url = cdn.upload_photo(
            encoded_data=PhotoEncoder.encode(fpath, role, params),
            role=role,
            format=params["format"],
            force=force,
        )
        db.encoded_photos_table().add(fpath, uploaded_url, role, params["format"])

    yield from sqlite_dependency(
        DATABASE_PATH,
        "select case when exists("
        "select 1 from encoded_photos where fpath = ? and role = ? and url = ?"
        ") then 'satisfied' else 'impossible' end as status",
        (fpath, role, uploaded_url),
    )

    return {"fpath": fpath, "role": role, "url": uploaded_url}


def upload_missing_photos(ctx: JobContext, input: PhotoJobInput) -> Generator[Any, Any, None]:
    fpath = input["fpath"]
    force = input.get("force", False)
    force_roles = set(input.get("force_roles") or [])

    with SqliteDatabase(DATABASE_PATH) as db:
        encodings = list(db.encoded_photos_table().list_for_file(fpath))

    published_roles = {enc.role for enc in encodings if enc.url and enc.url.strip()}

    effects = []
    for role, params in IMAGE_ENCODINGS.items():
        role_forced = force or role in force_roles
        if role in published_roles and not role_forced:
            continue
        if "+cover" not in fpath and role == "social_card":
            continue
        effects.append(ctx.scope.upload_photo({"fpath": fpath, "role": role, "params": params, "force": role_forced}))

    if effects:
        yield await_all(effects)


def upload_video_thumbnail(ctx: JobContext, input: dict) -> Generator[Any, Any, dict]:
    fpath = input["fpath"]
    encoded_path = input["encoded_path"]

    cdn = CDN()
    with SqliteDatabase(DATABASE_PATH) as db:
        publish_video_thumbnail(cdn, db, fpath, encoded_path)

    return {"fpath": fpath}
    yield


def upload_video(ctx: JobContext, input: dict) -> Generator[Any, Any, dict]:
    fpath = input["fpath"]
    role = input["role"]
    params = input["params"]

    yield from concurrency_dependency(_VIDEO_CDN_LIMIT, limit=2)
    yield from resource_dependency("memory", max_percent=65)

    cdn = CDN()
    with SqliteDatabase(DATABASE_PATH) as db:
        try:
            encoded_path = publish_video_encoding(cdn, db, fpath, role, params)
        except InvalidVideoDimensionsError:
            return {"fpath": fpath, "role": role}

    yield from sqlite_dependency(
        DATABASE_PATH,
        "select case when exists("
        "select 1 from encoded_videos where fpath = ? and role = ? and url is not null and url != ''"
        ") then 'satisfied' else 'impossible' end as status",
        (fpath, role),
    )

    if role == FULL_SIZED_VIDEO_ROLE and encoded_path:
        yield ctx.scope.upload_video_thumbnail({"fpath": fpath, "encoded_path": encoded_path})

    return {"fpath": fpath, "role": role}


def upload_missing_videos(ctx: JobContext, input: PhotoJobInput) -> Generator[Any, Any, None]:
    fpath = input["fpath"]

    with SqliteDatabase(DATABASE_PATH) as db:
        encodings = list(db.encoded_videos_table().list_for_file(fpath))

    published_roles = {enc.role for enc in encodings}

    for role, params in VIDEO_ENCODINGS:
        if role in published_roles:
            continue
        yield ctx.scope.upload_video({"fpath": fpath, "role": role, "params": params})

    yield from sqlite_dependency(
        DATABASE_PATH,
        """select case when (
            select count(distinct role) from encoded_videos
            where fpath = ?
            and role in ('video_libx264_unscaled', 'video_libx264_1080p', 'video_libx264_720p', 'video_libx264_480p')
            and url is not null
            and url != ''
        ) = 4 then 'satisfied' else 'impossible' end as status""",
        (fpath,),
    )


def upload_media(ctx: JobContext, input: UploadOpts) -> Generator[Any, Any, None]:
    force_recompute_grey = input.get("force_recompute_grey", False)
    force_recompute_mosaic = input.get("force_recompute_mosaic", False)
    force_upload_images = input.get("force_upload_images", False)
    force_upload_videos = input.get("force_upload_videos", False)
    force_roles = input.get("force_roles") or []
    upload_images = input.get("upload_images")
    upload_videos = input.get("upload_videos")

    with SqliteDatabase(DATABASE_PATH) as db:
        grey_fpaths = list(list_photos_without_contrasting_grey(db, force_recompute_grey))
        mosaic_fpaths = list(list_photos_without_mosaic(db, force_recompute_mosaic))
        photo_fpaths = (
            list(list_photos_without_upload(db, force_upload_images or bool(force_roles))) if upload_images else []
        )
        video_fpaths = list(list_videos_without_upload(db, force_upload_videos)) if upload_videos else []

    grey_effects = [
        ctx.scope.compute_contrasting_grey({"fpath": fpath, "force": force_recompute_grey}) for fpath in grey_fpaths
    ]
    if grey_effects:
        yield await_all(grey_effects)

    mosaic_effects = [
        ctx.scope.compute_image_mosaic({"fpath": fpath, "force": force_recompute_mosaic}) for fpath in mosaic_fpaths
    ]
    if mosaic_effects:
        yield await_all(mosaic_effects)

    if upload_images:
        photo_effects = [
            ctx.scope.upload_missing_photos({"fpath": fpath, "force": force_upload_images, "force_roles": force_roles})
            for fpath in photo_fpaths
        ]
        if photo_effects:
            yield await_all(photo_effects)

    if upload_videos:
        for fpath in video_fpaths:
            yield ctx.scope.upload_missing_videos({"fpath": fpath, "force": force_upload_videos})
