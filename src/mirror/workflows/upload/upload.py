from __future__ import annotations

from collections.abc import Generator
from typing import Any

from zahir import (
    JobContext,
    await_all,
    concurrency_dependency,
    resource_dependency,
    sqlite_dependency,
)

from mirror.commons.config import DATABASE_PATH
from mirror.commons.constants import (
    FULL_SIZED_VIDEO_ROLE,
    VIDEO_ENCODINGS,
)
from mirror.commons.exceptions import InvalidVideoDimensionsError
from mirror.services.media_publish import (
    PhotoJobInput,
    UploadOpts,
    list_published_photo_roles,
    list_published_video_roles,
    list_upload_work,
    publish_video_encoding,
    publish_video_thumbnail,
    roles_needing_upload,
    store_contrasting_grey,
    store_image_mosaic,
    upload_photo_encoding,
)


def compute_contrasting_grey(ctx: JobContext, input: PhotoJobInput) -> Generator[Any, Any, None]:
    fpath = input["fpath"]

    store_contrasting_grey(fpath)

    return None
    yield


def compute_image_mosaic(ctx: JobContext, input: PhotoJobInput) -> Generator[Any, Any, None]:
    fpath = input["fpath"]

    store_image_mosaic(fpath)

    return None
    yield


_PHOTO_CDN_LIMIT = "global_photo_cdn_limit"
_VIDEO_CDN_LIMIT = "global_video_cdn_limit"


def upload_photo(ctx: JobContext, input: dict) -> Generator[Any, Any, dict]:
    fpath = input["fpath"]
    role = input["role"]
    params = input["params"]

    # Encode before taking a CDN slot, so CPU work does not occupy the upload gate
    yield from concurrency_dependency(_PHOTO_CDN_LIMIT, limit=6)
    uploaded_url = upload_photo_encoding(fpath, role, params)

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

    published_roles = list_published_photo_roles(fpath)

    upload_roles = roles_needing_upload(fpath, published_roles, force, force_roles)

    effects = []
    for role, params in upload_roles:
        job_input = {"fpath": fpath, "role": role, "params": params}
        effects.append(ctx.scope.upload_photo(job_input))

    if effects:
        yield await_all(effects)


def upload_video_thumbnail(ctx: JobContext, input: dict) -> Generator[Any, Any, dict]:
    fpath = input["fpath"]
    encoded_path = input["encoded_path"]

    publish_video_thumbnail(fpath, encoded_path)

    return {"fpath": fpath}
    yield


def upload_video(ctx: JobContext, input: dict) -> Generator[Any, Any, dict]:
    fpath = input["fpath"]
    role = input["role"]
    params = input["params"]

    yield from concurrency_dependency(_VIDEO_CDN_LIMIT, limit=2)
    yield from resource_dependency("memory", max_percent=65)

    try:
        encoded_path = publish_video_encoding(fpath, role, params)
    except InvalidVideoDimensionsError:
        return {"fpath": fpath, "role": role}

    yield from sqlite_dependency(
        DATABASE_PATH,
        "select case when exists("
        "select 1 from encoded_videos where fpath = ? and role = ?"
        " and url is not null and url != ''"
        ") then 'satisfied' else 'impossible' end as status",
        (fpath, role),
    )

    if role == FULL_SIZED_VIDEO_ROLE and encoded_path:
        yield ctx.scope.upload_video_thumbnail({"fpath": fpath, "encoded_path": encoded_path})

    return {"fpath": fpath, "role": role}


def upload_missing_videos(ctx: JobContext, input: PhotoJobInput) -> Generator[Any, Any, None]:
    fpath = input["fpath"]

    published_roles = list_published_video_roles(fpath)

    for role, params in VIDEO_ENCODINGS:
        if role in published_roles:
            continue
        yield ctx.scope.upload_video({"fpath": fpath, "role": role, "params": params})

    yield from sqlite_dependency(
        DATABASE_PATH,
        """select case when (
            select count(distinct role) from encoded_videos
            where fpath = ?
            and role in ('video_libx264_unscaled', 'video_libx264_1080p',
                         'video_libx264_720p', 'video_libx264_480p')
            and url is not null
            and url != ''
        ) = 4 then 'satisfied' else 'impossible' end as status""",
        (fpath,),
    )


def media_upload_effects(ctx: JobContext, input: UploadOpts, work: tuple) -> Generator[list]:
    """Effect batches for the grey, mosaic, and photo-upload work lists."""
    grey_fpaths, mosaic_fpaths, photo_fpaths = work
    force_grey = input.get("force_recompute_grey", False)
    force_mosaic = input.get("force_recompute_mosaic", False)
    force_images = input.get("force_upload_images", False)
    force_roles = input.get("force_roles") or []

    yield [
        ctx.scope.compute_contrasting_grey({"fpath": fpath, "force": force_grey})
        for fpath in grey_fpaths
    ]
    yield [
        ctx.scope.compute_image_mosaic({"fpath": fpath, "force": force_mosaic})
        for fpath in mosaic_fpaths
    ]
    yield [
        ctx.scope.upload_missing_photos({
            "fpath": fpath,
            "force": force_images,
            "force_roles": force_roles,
        })
        for fpath in photo_fpaths
    ]


def upload_media(ctx: JobContext, input: UploadOpts) -> Generator[Any, Any, None]:
    grey_fpaths, mosaic_fpaths, photo_fpaths, video_fpaths = list_upload_work(input)

    batched_work = (grey_fpaths, mosaic_fpaths, photo_fpaths)
    for effects in media_upload_effects(ctx, input, batched_work):
        if effects:
            yield await_all(effects)

    for fpath in video_fpaths:
        yield ctx.scope.upload_missing_videos({
            "fpath": fpath,
            "force": input.get("force_upload_videos", False),
        })
